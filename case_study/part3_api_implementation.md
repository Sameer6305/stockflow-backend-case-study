# Part 3: API Implementation

## Architectural Overview

This endpoint powers low-stock alerting for a multi-warehouse B2B inventory platform. The route layer should remain thin, while the service layer performs all business logic, query composition, and response shaping. That separation keeps the API testable, predictable, and safe to evolve as the alerting model grows.

The required endpoint is:

`GET /api/companies/{company_id}/alerts/low-stock`

It returns products that are below or approaching their configured stock thresholds in one or more warehouses, but only when the product has recent sales activity. Supplier data is included so procurement workflows can act on the alert immediately.

## Assumptions

- `company_id` is a numeric primary key.
- Each product belongs to one company and can appear in multiple warehouses through an inventory balance table.
- Thresholds may be configured per product and optionally overridden per warehouse if the business later needs location-specific rules.
- "Recent sales activity" means at least one sale within the last 30 days unless the product configuration says otherwise.
- Sales data is considered authoritative only after it is persisted in the sales activity table.
- Supplier data is optional; products without suppliers should still appear in the response with a null supplier block so procurement gaps are visible.
- Archived products are excluded from active alerts.
- Negative inventory is treated as a data integrity exception and must be surfaced in the alert payload as a data-quality issue rather than silently hidden.

## Alert Logic

### Recent Sales Activity Logic

A product qualifies for alerts only if it has recent sales activity within the configured lookback window.

Recommended rule:

- Default lookback window: 30 days.
- Use the most recent sales record per product, not the total lifetime history.
- Exclude stale products with no sales in the window unless product management explicitly opts them in.

Why this matters: alerts should reflect current demand. Without this filter, the API would flood users with dead-stock items that have not moved in months.

### Low-Stock Threshold Logic

The alert threshold should be determined in the following order:

1. Warehouse-specific threshold when configured.
2. Product-level threshold when no warehouse override exists.
3. Company default threshold when product metadata is incomplete.

An alert is triggered when `quantity_on_hand <= threshold`.

### Days Until Stockout Calculation Logic

The calculation should be conservative and deterministic:

- Compute sales velocity as `units_sold / days_in_lookback`.
- If velocity is zero, set `days_until_stockout` to `null` and flag the item as having zero sales velocity.
- Otherwise calculate `quantity_on_hand / daily_sales_velocity`.
- Round down to one decimal place for readability.

This prevents misleading infinite or negative estimates and makes the API safe for dashboard use.

## Expected Response Format

The response uses the same stable envelope as the rest of the case study:

```json
{
  "success": true,
  "data": {
	"company_id": 42,
	"lookback_days": 30,
	"alerts": [
	  {
		"product_id": 101,
		"sku": "SKU-1001",
		"product_name": "Wireless Scanner",
		"archived": false,
		"warehouse": {
		  "warehouse_id": 9,
		  "warehouse_code": "WH-BLR-01",
		  "warehouse_name": "Bangalore Main"
		},
		"inventory": {
		  "quantity_on_hand": 12,
		  "threshold": 20,
		  "reserved_quantity": 3,
		  "is_negative": false
		},
		"sales_activity": {
		  "recent_units_sold": 40,
		  "last_sale_at": "2026-04-24T10:15:00Z",
		  "daily_sales_velocity": 1.33
		},
		"days_until_stockout": 9.0,
		"supplier": {
		  "supplier_id": 7,
		  "supplier_name": "Northwind Supplies",
		  "supplier_code": "NWS-01",
		  "lead_time_days": 5,
		  "min_order_quantity": 10
		},
		"alert_reason": "low_stock_with_recent_sales"
	  }
	],
	"pagination": {
	  "page": 1,
	  "per_page": 25,
	  "total_items": 1,
	  "total_pages": 1
	}
  },
  "meta": {
	"generated_at": "2026-04-29T12:00:00Z",
	"lookback_window_days": 30
  }
}
```

## Production-Quality Flask + SQLAlchemy Implementation

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from stockflow.extensions import db
from stockflow.models import Company, InventoryBalance, Product, SalesActivity, Supplier, SupplierProduct, Warehouse

low_stock_alerts_bp = Blueprint("low_stock_alerts", __name__)


@dataclass(frozen=True)
class AlertPagination:
    page: int
    per_page: int
    total_items: int
    total_pages: int


def _success(data, *, meta=None, status_code: int = 200):
    # A stable envelope keeps client integrations predictable.
    payload = {"success": True, "data": data}
    if meta is not None:
        payload["meta"] = meta
    return jsonify(payload), status_code


def _error(message: str, *, status_code: int, code: str):
    return jsonify({"success": False, "error": {"code": code, "message": message}}), status_code


def _parse_positive_int(raw_value, *, default: int, field_name: str) -> int:
    try:
        value = int(raw_value if raw_value is not None else default)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if value < 1:
        raise ValueError(f"{field_name} must be greater than zero")
    return value


def _parse_company_id(company_id: str) -> int:
    try:
        value = int(company_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("company_id must be a valid integer") from exc
    if value < 1:
        raise ValueError("company_id must be greater than zero")
    return value


def _build_window(days: int):
    now = datetime.now(timezone.utc)
    return now, now - timedelta(days=days)


def _one_decimal(value: float | None):
    if value is None:
        return None
    return float(int(value * 10) / 10)


@low_stock_alerts_bp.get("/companies/<company_id>/alerts/low-stock")
def get_low_stock_alerts(company_id: str):
    try:
        parsed_company_id = _parse_company_id(company_id)
        page = _parse_positive_int(request.args.get("page"), default=1, field_name="page")
        per_page = _parse_positive_int(request.args.get("per_page"), default=25, field_name="per_page")
        lookback_days = _parse_positive_int(request.args.get("lookback_days"), default=30, field_name="lookback_days")
    except ValueError as exc:
        return _error(str(exc), status_code=400, code="validation_error")

    try:
        if db.session.query(Company.id).filter(Company.id == parsed_company_id).first() is None:
            return _error("company not found", status_code=404, code="company_not_found")

        generated_at, lookback_start = _build_window(lookback_days)

        # Aggregate sales once so the alert feed avoids N+1 reads under load.
        recent_sales = (
            db.session.query(
                SalesActivity.product_id.label("product_id"),
                SalesActivity.warehouse_id.label("warehouse_id"),
                func.sum(SalesActivity.quantity_sold).label("recent_units_sold"),
                func.max(SalesActivity.sold_at).label("last_sale_at"),
            )
            .filter(SalesActivity.company_id == parsed_company_id)
            .filter(SalesActivity.sold_at >= lookback_start)
            .group_by(SalesActivity.product_id, SalesActivity.warehouse_id)
            .cte("recent_sales")
        )

        primary_supplier = (
            db.session.query(
                SupplierProduct.product_id.label("product_id"),
                Supplier.id.label("supplier_id"),
                Supplier.name.label("supplier_name"),
                Supplier.supplier_code.label("supplier_code"),
                SupplierProduct.lead_time_days.label("lead_time_days"),
                SupplierProduct.min_order_quantity.label("min_order_quantity"),
            )
            .join(Supplier, Supplier.id == SupplierProduct.supplier_id)
            .filter(Supplier.company_id == parsed_company_id)
            .filter(SupplierProduct.is_preferred.is_(True))
            .cte("primary_supplier")
        )

        query = (
            db.session.query(
                Product.id.label("product_id"),
                Product.sku.label("sku"),
                Product.name.label("product_name"),
                Product.is_active.label("is_active"),
                InventoryBalance.quantity_on_hand.label("quantity_on_hand"),
                InventoryBalance.low_stock_threshold.label("threshold"),
                InventoryBalance.reserved_quantity.label("reserved_quantity"),
                InventoryBalance.warehouse_id.label("warehouse_id"),
                Warehouse.code.label("warehouse_code"),
                Warehouse.name.label("warehouse_name"),
                recent_sales.c.recent_units_sold.label("recent_units_sold"),
                recent_sales.c.last_sale_at.label("last_sale_at"),
                primary_supplier.c.supplier_id.label("supplier_id"),
                primary_supplier.c.supplier_name.label("supplier_name"),
                primary_supplier.c.supplier_code.label("supplier_code"),
                primary_supplier.c.lead_time_days.label("lead_time_days"),
                primary_supplier.c.min_order_quantity.label("min_order_quantity"),
            )
            .select_from(InventoryBalance)
            .join(Product, Product.id == InventoryBalance.product_id)
            .join(Warehouse, Warehouse.id == InventoryBalance.warehouse_id)
            .outerjoin(
                recent_sales,
                (recent_sales.c.product_id == InventoryBalance.product_id)
                & (recent_sales.c.warehouse_id == InventoryBalance.warehouse_id),
            )
            .outerjoin(primary_supplier, primary_supplier.c.product_id == Product.id)
            .filter(InventoryBalance.company_id == parsed_company_id)
            .filter(Product.is_active.is_(True))
        )

        rows = query.all()

        alerts = []
        for row in rows:
            quantity_on_hand = int(row.quantity_on_hand or 0)
            threshold = row.threshold if row.threshold is not None else current_app.config.get("DEFAULT_LOW_STOCK_THRESHOLD", 0)
            threshold = int(threshold)
            recent_units_sold = int(row.recent_units_sold or 0)

            # No recent sales means the product is not included in the alert feed.
            if recent_units_sold <= 0:
                continue

            if row.last_sale_at is None:
                continue

            if quantity_on_hand > threshold:
                continue

            daily_sales_velocity = recent_units_sold / float(lookback_days)
            days_until_stockout = None if daily_sales_velocity <= 0 else _one_decimal(quantity_on_hand / daily_sales_velocity)

            alerts.append(
                {
                    "product_id": row.product_id,
                    "sku": row.sku,
                    "product_name": row.product_name,
                    "archived": False,
                    "warehouse": {
                        "warehouse_id": row.warehouse_id,
                        "warehouse_code": row.warehouse_code,
                        "warehouse_name": row.warehouse_name,
                    },
                    "inventory": {
                        "quantity_on_hand": quantity_on_hand,
                        "threshold": threshold,
                        "reserved_quantity": row.reserved_quantity,
                        "is_negative": quantity_on_hand < 0,
                    },
                    "sales_activity": {
                        "recent_units_sold": recent_units_sold,
                        "last_sale_at": row.last_sale_at.isoformat() if row.last_sale_at else None,
                        "daily_sales_velocity": round(daily_sales_velocity, 2),
                    },
                    "days_until_stockout": days_until_stockout,
                    "supplier": None
                    if row.supplier_id is None
                    else {
                        "supplier_id": row.supplier_id,
                        "supplier_name": row.supplier_name,
                        "supplier_code": row.supplier_code,
                        "lead_time_days": row.lead_time_days,
                        "min_order_quantity": row.min_order_quantity,
                    },
                    "alert_reason": "low_stock_with_recent_sales",
                }
            )

        total_items = len(alerts)
        total_pages = ceil(total_items / per_page) if total_items else 0
        page_items = alerts[(page - 1) * per_page : (page - 1) * per_page + per_page]

        pagination = AlertPagination(page=page, per_page=per_page, total_items=total_items, total_pages=total_pages)

        return _success(
            {
                "company_id": parsed_company_id,
                "lookback_days": lookback_days,
                "alerts": page_items,
                "pagination": {
                    "page": pagination.page,
                    "per_page": pagination.per_page,
                    "total_items": pagination.total_items,
                    "total_pages": pagination.total_pages,
                },
            },
            meta={"generated_at": generated_at.isoformat(), "lookback_window_days": lookback_days},
        )

    except SQLAlchemyError:
        db.session.rollback()
        return _error("database error while generating alerts", status_code=500, code="database_error")
    except Exception:
        db.session.rollback()
        return _error("unexpected server error", status_code=500, code="internal_server_error")
```

## Service-Layer Notes

- The route only parses inputs, delegates to the service, and returns a structured response.
- The service should encapsulate the alert rules so the same logic can later be reused by scheduled jobs, webhooks, or message consumers.
- The query should be tenant-scoped at the database level to avoid accidental cross-company leakage.
- A real implementation should move the SQLAlchemy query building into a dedicated service module and add unit tests for every edge case.

## Validation And Defensive Handling

The implementation must handle these cases explicitly:

- Invalid company IDs: return `400` before querying.
- Warehouses with no inventory: return an empty alert list, not an error.
- Products without suppliers: return `supplier: null` so procurement can identify gaps.
- Zero sales velocity: set `days_until_stockout` to `null` and avoid divide-by-zero.
- Negative inventory: surface as a data integrity problem in the payload.
- Duplicate inventory rows: rely on the uniqueness constraint on `(warehouse_id, product_id)` and fail closed.
- Missing threshold values: fall back to company defaults.
- Archived products: exclude from active alerts unless a separate audit endpoint is requested.
- Stale sales data: ignore records outside the lookback window.

## Performance Considerations

This endpoint must be built to avoid N+1 queries. The key requirements are:

- Use joins and subqueries to bring warehouse, product, supplier, and sales data together in a bounded number of queries.
- Avoid per-row supplier lookups.
- Avoid per-row sales aggregation.
- Filter by company_id early so the database can use tenant-scoped indexes.
- Keep the result set small by paginating after the alert filter is applied.

Indexing dependencies:

- `products(sku)` for direct lookups.
- `inventory_balances(company_id, warehouse_id, product_id)` for warehouse-scoped joins.
- `sales_activity(company_id, product_id, sold_at)` for recent sales filtering.
- `supplier_products(product_id)` and `supplier_products(supplier_id, product_id)` for reorder joins.

Query scalability:

- This query is expected to remain efficient at moderate scale if the database has the right indexes.
- For very large tenants, the alert computation should move to a materialized view or precomputed alert table.
- If alert volume grows, query paths should be split into current-state reads and background-generated alert snapshots.

## Example API Request

```http
GET /api/companies/42/alerts/low-stock?lookback_days=30&page=1&per_page=25
Accept: application/json
```

## Example API Response

```json
{
  "success": true,
  "data": {
	"company_id": 42,
	"lookback_days": 30,
	"alerts": [
	  {
		"product_id": 101,
		"sku": "SKU-1001",
		"product_name": "Wireless Scanner",
		"archived": false,
		"warehouse": {
		  "warehouse_id": 9,
		  "warehouse_code": "WH-BLR-01",
		  "warehouse_name": "Bangalore Main"
		},
		"inventory": {
		  "quantity_on_hand": 12,
		  "threshold": 20,
		  "reserved_quantity": 3,
		  "is_negative": false
		},
		"sales_activity": {
		  "recent_units_sold": 40,
		  "last_sale_at": "2026-04-24T10:15:00Z",
		  "daily_sales_velocity": 1.33
		},
		"days_until_stockout": 9.0,
		"supplier": {
		  "supplier_id": 7,
		  "supplier_name": "Northwind Supplies",
		  "supplier_code": "NWS-01",
		  "lead_time_days": 5,
		  "min_order_quantity": 10
		},
		"alert_reason": "low_stock_with_recent_sales"
	  }
	],
	"pagination": {
	  "page": 1,
	  "per_page": 25,
	  "total_items": 1,
	  "total_pages": 1
	}
  },
  "meta": {
	"generated_at": "2026-04-29T12:00:00Z",
	"lookback_window_days": 30
  }
}
```

## Potential Production Risks

- Race conditions: inventory may change while the alert query is running, so the response can be slightly stale unless the system uses stronger transactional guarantees.
- Stale inventory data: if writes and alerts are eventually consistent, the UI may show alerts for stock that was already replenished.
- Eventual consistency concerns: asynchronous sales or stock updates can delay alert generation.
- Alert flooding: without deduplication or suppression windows, the same product can repeatedly appear in alert feeds.
- Caching tradeoffs: caching can improve latency, but inventory alerts are sensitive to freshness and require careful invalidation.

## Future Improvements

- Async alerting to push notifications only when relevant conditions change.
- Predictive forecasting based on sales trend windows and supplier lead times.
- ML-based stockout prediction for products with irregular demand patterns.
- Kafka/event-driven inventory updates so alert generation becomes reactive.
- Redis caching for short-lived alert summaries with strict invalidation rules.
- Alert deduplication so the same product does not spam operators across repeated runs.

## Closing Assessment

This endpoint should be treated as an operational decision-support API, not a simple list query. The implementation must be tenant-safe, join-efficient, auditable, and deterministic under load. If built this way, it becomes a reliable foundation for replenishment workflows, procurement alerts, and future forecasting features.

# Part 1: Debugging Analysis

## Overview

The original write path was trying to create or update inventory state for a warehouse-linked product record. In a real B2B inventory system, that operation needs to be split carefully: product identity, warehouse identity, and current stock balance are related, but they should not be treated as a single mutable blob.

The production concern is simple. If the API accepts invalid input or writes partial state, the warehouse can end up with stock that cannot be trusted for picking, replenishment, or reporting.

## What The Handler Must Do

The endpoint should:

- validate request shape before touching the database,
- confirm the warehouse exists and belongs to the correct company,
- ensure the product exists or is created through a separate product flow,
- write the inventory balance and inventory transaction in one transaction,
- return a predictable response when the write is rejected.

That separation keeps the data model consistent with the schema in Part 2 and avoids conflating product master data with warehouse-level stock.

## Issues Identified

### 1. Input Validation Is Too Loose

Why it is a problem: the endpoint should never trust request data to already be clean and correctly typed.

Production impact: invalid values can create negative stock, empty names, malformed prices, or broken foreign key references.

Example failure: a payload with `quantity_on_hand: "ten"` or `price: "abc"` reaches persistence code and fails late, after the request has already moved into business logic.

Recommended fix: validate the JSON object at the API boundary, coerce types explicitly, and reject invalid values with a `400` response.

### 2. Product Identity Is Mixed With Stock State

Why it is a problem: product data and warehouse inventory state are different concepts.

Production impact: if the same handler creates product rows and stock rows together, it becomes hard to reason about ownership, deduplication, and auditing.

Example failure: an API request intended to add 20 units to Warehouse A accidentally creates a brand-new product row instead of updating the existing inventory balance.

Recommended fix: keep product creation separate and have the stock endpoint only create or update an `InventoryBalance` row.

### 3. Warehouse Validation Is Missing

Why it is a problem: the write should fail fast if the warehouse does not exist, is inactive, or belongs to another company.

Production impact: inventory can be attached to the wrong tenant or a warehouse that should no longer receive stock.

Example failure: a request sends `warehouse_id=9999`, the row is accepted, and the platform later reports inventory for a location that should not exist.

Recommended fix: load the warehouse inside the transaction and reject the request if the warehouse lookup fails.

### 4. Transaction Boundaries Are Not Clear

Why it is a problem: inventory changes usually touch more than one row, especially when the system keeps an audit ledger.

Production impact: if the balance update succeeds but the transaction ledger insert fails, the stock count and the audit trail diverge.

Example failure: stock is committed, the history insert raises an exception, and support has no reliable way to explain the mismatch.

Recommended fix: wrap the balance write and the transaction ledger write in one database transaction.

### 5. Rollback Handling Is Too Weak

Why it is a problem: any failed database write should leave the session in a clean state.

Production impact: a poisoned session can cause follow-up requests to fail even when their inputs are valid.

Example failure: an `IntegrityError` is raised, the exception bubbles out, and the next request fails because the session was never rolled back.

Recommended fix: catch database exceptions, call `rollback()`, and return a controlled conflict or server error response.

### 6. Duplicate Protection Needs To Be Explicit

Why it is a problem: the combination of warehouse and product should be unique in the inventory balance table.

Production impact: without a uniqueness rule, the same SKU can appear multiple times in the same warehouse with conflicting quantities.

Example failure: two concurrent imports insert the same warehouse-product row and the system later has to guess which quantity is correct.

Recommended fix: enforce a unique constraint on `(warehouse_id, product_id)` and map duplicate inserts to a clear conflict response.

### 7. Money Must Use Decimal, Not Float

Why it is a problem: floating-point arithmetic is not safe for currency.

Production impact: even tiny rounding errors create reconciliation noise in exports, invoices, and margin reporting.

Example failure: repeated updates turn a price of `19.99` into a value that no longer matches accounting exports.

Recommended fix: use `Decimal`, normalize to the required scale, and serialize currency values as strings in API responses.

### 8. Optional Field Handling Should Be Intentional

Why it is a problem: patch-style updates should not overwrite existing data with `null` unless the client explicitly requested that change.

Production impact: valid data can disappear during partial updates if missing fields are treated the same as empty fields.

Example failure: a request updates quantity only, but the handler also clears the product description because the field was omitted.

Recommended fix: distinguish between missing keys and explicit `null` values before updating the row.

### 9. Authentication And Authorization Are Not Considered

Why it is a problem: stock writes are privileged operations.

Production impact: unauthorized users could change warehouse balances, price records, or reorder thresholds.

Example failure: a low-privilege user hits the endpoint directly and changes stock data that should only be editable by operations staff.

Recommended fix: require authentication, enforce role-based permissions, and include actor information in the audit trail.

### 10. Concurrency Needs To Be Addressed

Why it is a problem: two requests can read the same balance and overwrite each other if the write path is not protected.

Production impact: lost updates lead to inaccurate stock counts and bad replenishment decisions.

Example failure: two restock jobs each add 10 units to the same balance, but only one update survives.

Recommended fix: use row-level locking or optimistic concurrency control, depending on the database and throughput requirements.

## Corrected Production-Quality Shape

The example below shows the direction I would expect in production. The route validates the payload, resolves the warehouse and product, and writes the current balance and audit record in a single transaction.

```python
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from stockflow.extensions import db
from stockflow.models import InventoryBalance, InventoryTransaction, Product, Warehouse

inventory_bp = Blueprint("inventory", __name__)


def _error(message: str, status_code: int, code: str):
    return jsonify({"success": False, "error": {"code": code, "message": message}}), status_code


def _parse_money(raw_value) -> Decimal:
    value = Decimal(str(raw_value))
    if value < 0:
        raise ValueError("price must be greater than or equal to 0")
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@inventory_bp.post("/companies/<int:company_id>/inventory-balances")
def upsert_inventory_balance(company_id: int):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error("request body must be a JSON object", 400, "validation_error")

    try:
        warehouse_id = int(payload["warehouse_id"])
        product_id = int(payload["product_id"])
        quantity_on_hand = int(payload["quantity_on_hand"])
        unit_price = _parse_money(payload.get("unit_price", 0))
    except (KeyError, TypeError, ValueError) as exc:
        return _error(str(exc), 400, "validation_error")

    if quantity_on_hand < 0:
        return _error("quantity_on_hand must be zero or greater", 400, "validation_error")

    try:
        with db.session.begin():
            warehouse = (
                db.session.query(Warehouse)
                .filter(Warehouse.id == warehouse_id, Warehouse.company_id == company_id)
                .one_or_none()
            )
            if warehouse is None or not warehouse.is_active:
                return _error("warehouse not found", 404, "warehouse_not_found")

            product = (
                db.session.query(Product)
                .filter(Product.id == product_id, Product.company_id == company_id)
                .one_or_none()
            )
            if product is None or not product.is_active:
                return _error("product not found", 404, "product_not_found")

            balance = (
                db.session.query(InventoryBalance)
                .filter(
                    InventoryBalance.company_id == company_id,
                    InventoryBalance.warehouse_id == warehouse_id,
                    InventoryBalance.product_id == product_id,
                )
                .one_or_none()
            )

            if balance is None:
                balance = InventoryBalance(
                    company_id=company_id,
                    warehouse_id=warehouse_id,
                    product_id=product_id,
                    quantity_on_hand=quantity_on_hand,
                    reserved_quantity=0,
                    low_stock_threshold=0,
                )
                db.session.add(balance)
            else:
                balance.quantity_on_hand = quantity_on_hand

            db.session.add(
                InventoryTransaction(
                    company_id=company_id,
                    warehouse_id=warehouse_id,
                    product_id=product_id,
                    transaction_type="adjustment",
                    quantity_delta=quantity_on_hand,
                    notes="manual inventory correction",
                )
            )

    except IntegrityError:
        db.session.rollback()
        return _error("inventory balance already exists for this warehouse and product", 409, "duplicate_inventory_balance")

    response_payload = {
        "company_id": company_id,
        "warehouse_id": warehouse_id,
        "product_id": product_id,
        "quantity_on_hand": quantity_on_hand,
        "unit_price": str(unit_price),
    }
    return jsonify({"success": True, "data": response_payload}), 201
```

## Additional Production Improvements

- Return validation errors in a single structured format across all inventory endpoints.
- Add request IDs and actor IDs to logs so inventory changes can be traced quickly.
- Include an immutable audit ledger for every change that affects on-hand quantity.
- Add tests for duplicate warehouse-product writes, invalid warehouse IDs, and rollback behavior.
- Keep product creation separate from inventory updates so the data model remains easy to reason about.

## Closing Assessment

The key lesson is that inventory correctness depends on discipline at the boundary. The endpoint should not guess, merge, or partially commit its way through bad input. It should validate early, write atomically, and keep product identity separate from warehouse stock state.
# Part 2: Database Design

## System Overview

StockFlow is a B2B inventory management platform where each company manages its own catalog, warehouses, suppliers, bundles, and stock movements. The database must support multi-warehouse inventory, auditable stock changes, recent sales signals, and scalable product lookup without sacrificing data integrity.

## Relational Schema

The design below assumes PostgreSQL in production. SQLite is sufficient for the demo, but the schema is written to reflect a real SaaS deployment.

```sql
CREATE TABLE companies (
	id BIGSERIAL PRIMARY KEY,
	name VARCHAR(200) NOT NULL,
	slug VARCHAR(120) NOT NULL,
	is_active BOOLEAN NOT NULL DEFAULT TRUE,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	CONSTRAINT uq_companies_slug UNIQUE (slug)
);

CREATE TABLE warehouses (
	id BIGSERIAL PRIMARY KEY,
	company_id BIGINT NOT NULL,
	code VARCHAR(50) NOT NULL,
	name VARCHAR(200) NOT NULL,
	location VARCHAR(255),
	is_active BOOLEAN NOT NULL DEFAULT TRUE,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	CONSTRAINT fk_warehouses_company FOREIGN KEY (company_id) REFERENCES companies (id),
	CONSTRAINT uq_warehouses_company_code UNIQUE (company_id, code)
);

CREATE TABLE products (
	id BIGSERIAL PRIMARY KEY,
	company_id BIGINT NOT NULL,
	sku VARCHAR(80) NOT NULL,
	name VARCHAR(255) NOT NULL,
	description TEXT,
	unit_cost NUMERIC(18, 4) NOT NULL DEFAULT 0,
	unit_price NUMERIC(18, 4) NOT NULL DEFAULT 0,
	currency_code CHAR(3) NOT NULL DEFAULT 'USD',
	is_active BOOLEAN NOT NULL DEFAULT TRUE,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	deleted_at TIMESTAMPTZ,
	CONSTRAINT fk_products_company FOREIGN KEY (company_id) REFERENCES companies (id),
	CONSTRAINT uq_products_sku UNIQUE (sku),
	CONSTRAINT ck_products_cost_non_negative CHECK (unit_cost >= 0),
	CONSTRAINT ck_products_price_non_negative CHECK (unit_price >= 0)
);

CREATE TABLE inventory_balances (
	id BIGSERIAL PRIMARY KEY,
	company_id BIGINT NOT NULL,
	warehouse_id BIGINT NOT NULL,
	product_id BIGINT NOT NULL,
	quantity_on_hand INTEGER NOT NULL DEFAULT 0,
	reserved_quantity INTEGER NOT NULL DEFAULT 0,
	low_stock_threshold INTEGER NOT NULL DEFAULT 0,
	reorder_quantity INTEGER NOT NULL DEFAULT 0,
	last_movement_at TIMESTAMPTZ,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	CONSTRAINT fk_inventory_company FOREIGN KEY (company_id) REFERENCES companies (id),
	CONSTRAINT fk_inventory_warehouse FOREIGN KEY (warehouse_id) REFERENCES warehouses (id),
	CONSTRAINT fk_inventory_product FOREIGN KEY (product_id) REFERENCES products (id),
	CONSTRAINT uq_inventory_warehouse_product UNIQUE (warehouse_id, product_id),
	CONSTRAINT ck_inventory_quantity_non_negative CHECK (quantity_on_hand >= 0),
	CONSTRAINT ck_inventory_reserved_non_negative CHECK (reserved_quantity >= 0),
	CONSTRAINT ck_inventory_threshold_non_negative CHECK (low_stock_threshold >= 0),
	CONSTRAINT ck_inventory_reorder_non_negative CHECK (reorder_quantity >= 0),
	CONSTRAINT ck_inventory_reserved_leq_on_hand CHECK (reserved_quantity <= quantity_on_hand)
);

CREATE TABLE inventory_transactions (
	id BIGSERIAL PRIMARY KEY,
	company_id BIGINT NOT NULL,
	warehouse_id BIGINT NOT NULL,
	product_id BIGINT NOT NULL,
	transaction_type VARCHAR(30) NOT NULL,
	quantity_delta INTEGER NOT NULL,
	reference_type VARCHAR(50),
	reference_id VARCHAR(100),
	notes TEXT,
	idempotency_key VARCHAR(120),
	created_by BIGINT,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	CONSTRAINT fk_transactions_company FOREIGN KEY (company_id) REFERENCES companies (id),
	CONSTRAINT fk_transactions_warehouse FOREIGN KEY (warehouse_id) REFERENCES warehouses (id),
	CONSTRAINT fk_transactions_product FOREIGN KEY (product_id) REFERENCES products (id),
	CONSTRAINT uq_transactions_idempotency UNIQUE (company_id, idempotency_key),
	CONSTRAINT ck_transactions_type CHECK (transaction_type IN ('purchase', 'sale', 'adjustment', 'transfer_in', 'transfer_out', 'return', 'reservation', 'release'))
);

CREATE TABLE suppliers (
	id BIGSERIAL PRIMARY KEY,
	company_id BIGINT NOT NULL,
	supplier_code VARCHAR(60) NOT NULL,
	name VARCHAR(255) NOT NULL,
	email VARCHAR(255),
	phone VARCHAR(50),
	is_active BOOLEAN NOT NULL DEFAULT TRUE,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	CONSTRAINT fk_suppliers_company FOREIGN KEY (company_id) REFERENCES companies (id),
	CONSTRAINT uq_suppliers_company_code UNIQUE (company_id, supplier_code)
);

CREATE TABLE supplier_products (
	id BIGSERIAL PRIMARY KEY,
	supplier_id BIGINT NOT NULL,
	product_id BIGINT NOT NULL,
	supplier_sku VARCHAR(80),
	lead_time_days INTEGER NOT NULL DEFAULT 0,
	min_order_quantity INTEGER NOT NULL DEFAULT 1,
	unit_cost NUMERIC(18, 4),
	is_preferred BOOLEAN NOT NULL DEFAULT FALSE,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	CONSTRAINT fk_supplier_products_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers (id),
	CONSTRAINT fk_supplier_products_product FOREIGN KEY (product_id) REFERENCES products (id),
	CONSTRAINT uq_supplier_products UNIQUE (supplier_id, product_id),
	CONSTRAINT ck_supplier_products_lead_time_non_negative CHECK (lead_time_days >= 0),
	CONSTRAINT ck_supplier_products_moq_positive CHECK (min_order_quantity > 0),
	CONSTRAINT ck_supplier_products_cost_non_negative CHECK (unit_cost IS NULL OR unit_cost >= 0)
);

CREATE TABLE product_bundles (
	id BIGSERIAL PRIMARY KEY,
	company_id BIGINT NOT NULL,
	bundle_sku VARCHAR(80) NOT NULL,
	name VARCHAR(255) NOT NULL,
	description TEXT,
	bundle_price NUMERIC(18, 4) NOT NULL DEFAULT 0,
	is_active BOOLEAN NOT NULL DEFAULT TRUE,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	CONSTRAINT fk_bundles_company FOREIGN KEY (company_id) REFERENCES companies (id),
	CONSTRAINT uq_bundles_bundle_sku UNIQUE (bundle_sku),
	CONSTRAINT ck_bundles_price_non_negative CHECK (bundle_price >= 0)
);

CREATE TABLE product_bundle_items (
	id BIGSERIAL PRIMARY KEY,
	bundle_id BIGINT NOT NULL,
	product_id BIGINT NOT NULL,
	quantity INTEGER NOT NULL,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	CONSTRAINT fk_bundle_items_bundle FOREIGN KEY (bundle_id) REFERENCES product_bundles (id),
	CONSTRAINT fk_bundle_items_product FOREIGN KEY (product_id) REFERENCES products (id),
	CONSTRAINT uq_bundle_items UNIQUE (bundle_id, product_id),
	CONSTRAINT ck_bundle_items_quantity_positive CHECK (quantity > 0)
);

CREATE TABLE sales_activity (
	id BIGSERIAL PRIMARY KEY,
	company_id BIGINT NOT NULL,
	warehouse_id BIGINT,
	product_id BIGINT NOT NULL,
	order_reference VARCHAR(120),
	quantity_sold INTEGER NOT NULL,
	unit_price NUMERIC(18, 4) NOT NULL,
	sold_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	CONSTRAINT fk_sales_company FOREIGN KEY (company_id) REFERENCES companies (id),
	CONSTRAINT fk_sales_warehouse FOREIGN KEY (warehouse_id) REFERENCES warehouses (id),
	CONSTRAINT fk_sales_product FOREIGN KEY (product_id) REFERENCES products (id),
	CONSTRAINT ck_sales_quantity_positive CHECK (quantity_sold > 0),
	CONSTRAINT ck_sales_price_non_negative CHECK (unit_price >= 0)
);
```

## Table Explanations

### companies

This is the tenant boundary. Every business object belongs to a company so StockFlow can isolate data per customer and scale cleanly across tenants. Normalization is straightforward here: company metadata stays out of operational inventory tables.

### warehouses

Warehouses are company-scoped locations, and the `(company_id, code)` unique constraint prevents duplicate warehouse identifiers inside a tenant. This table allows one company to operate multiple physical sites, 3PL locations, or logical stock pools without duplicating company data.

### products

Products represent the global SKU catalog for the platform. SKUs are globally unique by design, which makes external integrations, imports, and support workflows much simpler. Soft delete support is included so historical references remain stable.

### inventory_balances

This is the warehouse-level stock table. It models the many-to-many relationship between products and warehouses while keeping one current balance row per pair. That keeps the schema normalized and allows inventory to exist in multiple warehouses without duplicating product identity.

### inventory_transactions

This is the immutable audit ledger for every stock movement. All inventory changes should be written here first or in the same transaction as the balance update. This table is the source of truth for traceability, reconciliation, and incident analysis.

### suppliers

Suppliers are company-owned procurement entities. Supplier records are separated from products because a supplier can serve many products, and products can have multiple suppliers. That avoids duplication and supports procurement features later.

### supplier_products

This is the junction table that captures the supplier-to-product relationship plus operational fields like lead time, minimum order quantity, and supplier SKU. It is normalized, flexible, and useful for reorder automation.

### product_bundles

Bundles represent sellable product groupings. Keeping bundles in a separate table avoids denormalizing product rows and makes bundle pricing behavior explicit. This is important if the business later decides that bundles have special discount or margin rules.

### product_bundle_items

This table defines bundle composition and quantity per product. It ensures each bundle-product pair appears once, which keeps bundle math deterministic and easy to validate.

### sales_activity

Recent sales activity is stored separately from inventory balances because sales are event data, not current state. This table gives the platform a lightweight way to power demand signals, reorder recommendations, and operational dashboards.

## Inventory Integrity Model

Products can exist in multiple warehouses because inventory is modeled at the warehouse-product level, not at the product level. That is the correct structure for a multi-location SaaS inventory platform. Inventory changes are auditable because every mutation should create an `inventory_transactions` row, even if the balance table is updated in the same request.

## Indexing Strategy

- SKU lookup: create a unique index on `products.sku`. This supports direct product lookup from imports, support tooling, and API requests.
- Low stock queries: index `(company_id, warehouse_id, low_stock_threshold)` and consider a partial index on rows where `quantity_on_hand <= low_stock_threshold` for production databases that support it.
- Warehouse inventory queries: index `(warehouse_id, product_id)` on `inventory_balances` to speed location-scoped reads and joins.
- Supplier lookups: index `(company_id, supplier_code)` and `(supplier_id, product_id)` for procurement and catalog mapping flows.

## Constraints And Data Integrity Protections

- SKUs are globally unique.
- Bundle SKUs are unique.
- Warehouse codes are unique per company.
- Inventory balance rows are unique per warehouse-product pair.
- Quantity, threshold, and pricing columns cannot be negative.
- `reserved_quantity` cannot exceed `quantity_on_hand`.
- Transaction types are restricted to known values.
- Idempotency keys prevent duplicate inventory writes during retries.
- Foreign keys enforce tenant-connected data integrity across the model.

## Questions For Product Team

- Should bundle pricing override product-level pricing, or should bundles be a discount layer on top of individual item pricing?
- Do we want soft deletes for products, warehouses, suppliers, and bundles, or should some objects be hard-deleted?
- How long must inventory history and sales activity be retained for compliance and reporting?
- Does the product roadmap require multi-currency support, and if so, should pricing be stored by currency or normalized through FX tables?
- What are the exact warehouse transfer workflows: immediate transfer, staged transfer, or reservation-based transfer?
- Should reorder automation be triggered by low-stock thresholds, sales velocity, supplier lead time, or all three?

## Scalability And Future Improvements

- Partitioning strategy: partition `inventory_transactions` and `sales_activity` by company and time period once the event volume grows.
- Caching: cache read-heavy product and warehouse metadata, but never cache mutable inventory balances without a clear invalidation policy.
- Read replicas: route analytics, reporting, and list endpoints to replicas while keeping inventory writes on the primary.
- Event-driven inventory updates: publish stock movement events so downstream systems can update dashboards, notifications, and replenishment workflows asynchronously.
- Audit logging strategy: keep the immutable transaction ledger in the database and also emit structured application logs with request IDs, actor IDs, and before/after snapshots.

## Closing Assessment

This schema keeps the domain normalized while remaining practical for a SaaS inventory platform. It separates current state from history, supports multiple warehouses per company, preserves global SKU uniqueness, and leaves room for procurement, bundle sales, and demand planning without forcing a redesign later.

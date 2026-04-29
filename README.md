# StockFlow Backend Case Study

StockFlow is a B2B SaaS inventory management platform designed to help teams track stock levels, warehouse inventory, and replenishment signals with a clean backend architecture. This repository is structured as a production-minded backend case study rather than a tutorial scaffold, with separation between API routes, services, models, database setup, utilities, documentation, tests, and written case-study answers.

## Project Overview

The backend is built with Flask and SQLAlchemy, using SQLite for local demo runs. The architecture follows a service-oriented pattern so that HTTP concerns, business rules, and persistence logic are separated. That makes the code easier to test, extend, and move to a more scalable database later.

## Repository Structure

- `stockflow/` contains the application package.
- `stockflow/routes/` contains Flask blueprints for API routes.
- `stockflow/models/` contains SQLAlchemy models and shared base model behavior.
- `stockflow/services/` contains business logic and data-access orchestration.
- `stockflow/database/` contains database bootstrap helpers.
- `stockflow/utils/` contains reusable helpers such as API response formatting.
- `docs/` contains architecture and implementation notes.
- `tests/` contains the automated test suite.
- `case_study/` contains the three written case-study deliverables.

## Setup Instructions

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Optional environment variables:

- `FLASK_ENV=development` to use the development configuration.
- `DATABASE_URL` to override the default SQLite database path.
- `SECRET_KEY` to set a production-safe secret.

## How to Run

Run the application directly:

```bash
python app.py
```

Or use Flask CLI:

```bash
flask --app app run --debug
```

The API health endpoint is available at `GET /api/health`.

## Explanation of All 3 Parts

### Part 1: Debugging Analysis

This section is reserved for a structured investigation of a production or staging bug. The document should cover the observed symptom, reproduction steps, root cause, fix strategy, and validation notes.

### Part 2: Database Design

This section documents the proposed data model for a B2B inventory system. It should explain the core entities, relationships, constraints, indexes, and scaling assumptions behind the schema.

### Part 3: API Implementation

This section documents the API surface area for the inventory platform. It should describe the main endpoints, request and response structure, validation strategy, and service-layer responsibilities.

## Assumptions

- SQLite is used only for local demo execution and interviewer review.
- The real production deployment would use a managed relational database such as PostgreSQL.
- Authentication, authorization, and audit logging are intentionally out of scope for the starter implementation, but the architecture leaves room for them.
- Inventory items belong to a warehouse by default, but the design can be extended for multi-warehouse transfers and reservation workflows.
- The case study focuses on backend design quality rather than frontend integration.

## Scalability Considerations

- The code uses an application factory and blueprints so the API can grow without becoming a single-file monolith.
- Models are separated from business logic so read/write paths can evolve independently.
- Service functions provide a seam for caching, queue-based workflows, and transactional orchestration.
- The schema is designed to support indexed lookups on SKU, warehouse, and low-stock signals.
- The SQLite backend is intentionally replaceable with PostgreSQL without changing the application surface area.
- The route layer can later be versioned with minimal disruption by mounting additional blueprints.

## API Endpoints Included in the Starter

- `GET /api/health` returns a simple health check payload.
- `GET /api/items` lists inventory items.
- `GET /api/items/<id>` fetches a single inventory item.
- `POST /api/items` creates an inventory item.
- `PATCH /api/items/<id>` updates mutable inventory fields.

## Testing

The test suite is intentionally lightweight but structured to grow with the project. It currently includes a Flask test client foundation and a health-check test. Additional tests should cover service-layer business rules, database constraints, and API edge cases.

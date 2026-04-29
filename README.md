# StockFlow Backend Case Study

StockFlow is a B2B SaaS inventory management platform for companies that operate multiple warehouses, work with multiple suppliers, and need reliable stock visibility across product lines. This repository is written as a hiring submission: focused, modular, and intentionally close to how a real backend codebase is organized.

## Project Overview

The backend uses Flask, SQLAlchemy, and SQLite for local demo execution. The application is structured around an application factory, blueprints, service-layer business logic, and an explicit database session boundary so the code can scale from a case-study demo to a production deployment with PostgreSQL. The runtime app is intentionally compact, while the case-study documents describe the richer warehouse-product model used in the production-oriented design work.

## Architecture Overview

The design keeps the HTTP layer thin and moves business rules into services. That separation reduces coupling, improves testability, and makes it easier to introduce authentication, background workers, caching, and read replicas later.

The main flow is:

1. A Flask blueprint receives a request.
2. Input validation and response formatting stay close to the route.
3. Service code handles business rules and transaction boundaries.
4. SQLAlchemy models represent the domain and persistence layer.

## Repository Structure

- `stockflow/` contains the application package.
- `stockflow/routes/` contains Flask blueprints.
- `stockflow/models/` contains SQLAlchemy models and shared base classes.
- `stockflow/services/` contains business logic and query orchestration.
- `stockflow/database/` contains database bootstrap helpers.
- `stockflow/utils/` contains reusable response and error helpers.
- `docs/` contains architecture notes.
- `tests/` contains the automated test suite.
- `case_study/` contains the three written deliverables for the hiring review.

## Technologies Used

- Python 3.12
- Flask
- Flask-SQLAlchemy
- SQLAlchemy 2.x
- SQLite for local demo review
- pytest for test coverage

## How To Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python app.py
```

Or use Flask CLI:

```bash
flask --app app run --debug
```

The health endpoint is available at `GET /api/health`.

## Engineering Decisions

- Application factory: keeps configuration explicit and test setup predictable.
- Blueprint-based routes: allows the API to grow without turning into a monolith.
- Service layer: keeps inventory rules out of controller code.
- SQLAlchemy models: provide a clean abstraction over relational persistence.
- SQLite for demo mode: keeps setup friction low for reviewers.
- PostgreSQL-ready schema design: leaves room for production scale without redesigning the domain.

## Scalability Considerations

- The package layout supports versioned APIs and additional blueprints.
- Service boundaries make it practical to add async jobs, caching, and idempotent writes.
- The case-study schema is built around tenant-scoped joins and indexed lookups.
- The repository is intentionally lightweight, but the design is compatible with PostgreSQL, read replicas, and event-driven processing.

## Assumptions

- SQLite is used only for local demo execution and reviewer convenience.
- Production would use a managed relational database such as PostgreSQL.
- Authentication, authorization, and audit logging are not fully implemented in the starter code, but the structure leaves room for them.
- Inventory is modeled at the warehouse-product level so the same SKU can exist in multiple warehouses.
- SKUs are globally unique across the platform.
- The submission focuses on backend design quality rather than frontend integration.

## Trade-offs And Assumptions

- The repository keeps the implementation intentionally small so it reads clearly during recruiter review.
- Low-stock alerting is documented with realistic production patterns, but the runtime app remains a compact starter service.
- SQLite is sufficient for the case study, but some integrity and concurrency behaviors are described with PostgreSQL in mind.
- Some production features such as auth, background processing, and audit pipelines are described as future work rather than implemented fully.

## Case Study Deliverables

### Part 1: Debugging Analysis

Structured review of a failed inventory write path, including root cause analysis, production impact, and a corrected implementation.

### Part 2: Database Design

Relational schema design for companies, warehouses, products, inventory balances, suppliers, bundles, transactions, and sales activity.

### Part 3: API Implementation

Production-quality low-stock alert API design with Flask, SQLAlchemy, validation, pagination, and structured JSON responses.

## Testing

The test suite is intentionally lean but representative. It includes a Flask test client foundation and a health-check test. Additional tests should cover service logic, query behavior, and edge cases for inventory and alert generation.

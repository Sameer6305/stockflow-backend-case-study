# StockFlow Architecture Notes

## Design Goals

- Keep the HTTP layer thin.
- Push business rules into a service layer.
- Keep database configuration isolated from route handlers.
- Make the SQLite demo easy to replace with PostgreSQL in production.

## Application Structure

The Flask application is built through an application factory. That makes configuration explicit and allows different environments to reuse the same codebase without branching logic throughout the modules.

## Data Model

The starter code models a simple warehouse-linked inventory item so the application stays small and readable for interview review.

- `Warehouse` stores location-level inventory context.
- `InventoryItem` stores a trackable stock record and a foreign key to the owning warehouse.

The case-study documents expand this into a production-oriented warehouse-product balance model with suppliers, inventory transactions, and sales activity. That keeps the repository believable as a starter service while still showing the direction the design should take in production.

## Service Layer

The service layer owns:

- payload validation
- transaction boundaries
- uniqueness conflict handling
- query composition for list endpoints

This keeps route handlers small and easier to test.

## Error Handling

The codebase uses explicit domain exceptions so the route layer can translate predictable business failures into standard HTTP responses.

## Testing Strategy

The tests use a Flask application fixture with an isolated in-memory SQLite database. That keeps the starter suite fast while preserving a realistic project shape for interview review.

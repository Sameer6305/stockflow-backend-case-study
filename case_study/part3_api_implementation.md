# Part 3: API Implementation

## Objective

Provide a clean REST-style API for inventory operations while keeping the route layer thin and the service layer responsible for business logic.

## API Surface

### Health Check

`GET /api/health`

Purpose:

- confirm service availability
- provide a simple operational probe for deployment checks

### Inventory Collection

`GET /api/items`

Purpose:

- list inventory items
- support pagination at the route layer

`POST /api/items`

Purpose:

- create a new inventory record
- validate identity and stock thresholds before persistence

### Inventory Item

`GET /api/items/<id>`

Purpose:

- fetch one item by numeric identifier

`PATCH /api/items/<id>`

Purpose:

- update mutable inventory fields
- preserve transaction safety and conflict handling

## Request Validation Approach

- Reject non-JSON payloads.
- Validate required fields on create.
- Reject unexpected fields.
- Enforce non-negative quantity and reorder thresholds.
- Return consistent error structures from the route layer.

## Response Shape

Success responses use a stable envelope:

- `success`
- `data`
- optional `meta`

Error responses use:

- `success`
- `error.code`
- `error.message`

## Service-Layer Responsibilities

The service layer owns:

- loading records
- creating and updating rows
- translating database errors into business errors
- keeping commit boundaries explicit

## Why This Structure Works

This design keeps controller code easy to scan, makes unit testing straightforward, and avoids mixing HTTP concerns with persistence logic. It is also easy to extend with authentication, role-based access control, and asynchronous stock movement workflows later.

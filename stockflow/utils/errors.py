"""Domain exceptions used across the application."""

from __future__ import annotations


class StockFlowError(Exception):
    """Base application error."""

    status_code = 400
    error_code = "bad_request"


class ValidationError(StockFlowError):
    status_code = 400
    error_code = "validation_error"


class NotFoundError(StockFlowError):
    status_code = 404
    error_code = "not_found"


class ConflictError(StockFlowError):
    status_code = 409
    error_code = "conflict"

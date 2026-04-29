"""Health-check endpoints."""

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health_check():
    """Return a lightweight service status response."""

    return jsonify(
        {
            "status": "ok",
            "service": "StockFlow API",
            "version": "v1",
        }
    )

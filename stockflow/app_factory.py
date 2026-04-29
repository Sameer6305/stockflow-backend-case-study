"""Flask application factory for StockFlow.

Keeping object construction inside a factory makes the application easier to
configure, test, and extend for multiple environments.
"""

from __future__ import annotations

from flask import Flask, jsonify

from config import get_config

from .extensions import db
from .routes.health import health_bp
from .routes.inventory import inventory_bp


def create_app() -> Flask:
    """Create and configure the Flask application instance."""

    app = Flask(__name__)
    app.config.from_object(get_config())

    db.init_app(app)

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(inventory_bp, url_prefix="/api")

    @app.errorhandler(404)
    def handle_not_found(_: Exception):
        return jsonify({"error": "not_found", "message": "The requested resource was not found."}), 404

    @app.errorhandler(500)
    def handle_internal_error(_: Exception):
        return jsonify({"error": "internal_server_error", "message": "An unexpected error occurred."}), 500

    return app

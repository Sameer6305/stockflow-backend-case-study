"""Database bootstrap helpers used for local development and tests."""

from __future__ import annotations

from flask import Flask

from ..extensions import db


def init_database(app: Flask) -> None:
    """Create tables inside an application context.

    This is intentionally explicit rather than automatic so production boot
    paths stay under operator control.
    """

    with app.app_context():
        from .. import models  # noqa: F401  # Ensures SQLAlchemy sees all tables.

        db.create_all()


def drop_database(app: Flask) -> None:
    """Drop all tables inside an application context."""

    with app.app_context():
        db.drop_all()

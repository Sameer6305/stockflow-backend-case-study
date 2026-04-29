"""Shared SQLAlchemy base model behavior."""

from __future__ import annotations

from datetime import datetime, timezone

from ..extensions import db


class TimestampMixin:
    """Adds standard audit timestamps to persisted records."""

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class BaseModel(db.Model):
    """Base class for all application entities."""

    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)

    def to_dict(self) -> dict:
        raise NotImplementedError("Subclasses must implement to_dict().")

"""Warehouse model used for multi-location inventory."""

from __future__ import annotations

from ..extensions import db
from .base import BaseModel, TimestampMixin


class Warehouse(TimestampMixin, BaseModel):
    __tablename__ = "warehouses"

    code = db.Column(db.String(32), nullable=False, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(255), nullable=True)
    capacity_units = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "location": self.location,
            "capacity_units": self.capacity_units,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

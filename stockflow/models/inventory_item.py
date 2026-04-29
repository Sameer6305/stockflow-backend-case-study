"""Inventory item model for trackable stock units."""

from __future__ import annotations

from sqlalchemy.orm import relationship

from ..extensions import db
from .base import BaseModel, TimestampMixin


class InventoryItem(TimestampMixin, BaseModel):
    __tablename__ = "inventory_items"

    sku = db.Column(db.String(64), nullable=False, unique=True, index=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    quantity_on_hand = db.Column(db.Integer, nullable=False, default=0)
    reorder_point = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=True, index=True)

    warehouse = relationship("Warehouse", backref="inventory_items")

    def stock_status(self) -> str:
        if self.quantity_on_hand <= 0:
            return "out_of_stock"
        if self.quantity_on_hand <= self.reorder_point:
            return "low_stock"
        return "in_stock"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sku": self.sku,
            "name": self.name,
            "description": self.description,
            "quantity_on_hand": self.quantity_on_hand,
            "reorder_point": self.reorder_point,
            "status": self.stock_status(),
            "is_active": self.is_active,
            "warehouse_id": self.warehouse_id,
            "warehouse": self.warehouse.to_dict() if self.warehouse else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

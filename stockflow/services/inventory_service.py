"""Inventory business logic.

The route layer should remain thin. This service layer owns validation,
transactional writes, and query composition so the code stays testable.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import InventoryItem
from ..utils.errors import ConflictError, NotFoundError, ValidationError


@dataclass(frozen=True)
class InventoryPayload:
    """Normalized payload for item creation and updates."""

    sku: str | None = None
    name: str | None = None
    description: str | None = None
    quantity_on_hand: int | None = None
    reorder_point: int | None = None
    warehouse_id: int | None = None
    is_active: bool | None = None


class InventoryService:
    """Encapsulates inventory read and write operations."""

    @staticmethod
    def list_items() -> list[InventoryItem]:
        return InventoryItem.query.order_by(InventoryItem.created_at.desc()).all()

    @staticmethod
    def get_item(item_id: int) -> InventoryItem:
        item = InventoryItem.query.get(item_id)
        if item is None:
            raise NotFoundError(f"Inventory item {item_id} not found.")
        return item

    @staticmethod
    def create_item(payload: dict) -> InventoryItem:
        normalized = InventoryService._normalize_payload(payload, require_identity=True)
        item = InventoryItem(**normalized.__dict__)
        db.session.add(item)

        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            raise ConflictError("An inventory item with that SKU already exists.") from exc

        return item

    @staticmethod
    def update_item(item_id: int, payload: dict) -> InventoryItem:
        item = InventoryService.get_item(item_id)
        normalized = InventoryService._normalize_payload(payload, require_identity=False)

        for field_name, value in normalized.__dict__.items():
            if value is not None:
                setattr(item, field_name, value)

        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            raise ConflictError("The update conflicts with an existing record.") from exc

        return item

    @staticmethod
    def low_stock_items() -> list[InventoryItem]:
        return InventoryItem.query.filter(InventoryItem.quantity_on_hand <= InventoryItem.reorder_point).all()

    @staticmethod
    def _normalize_payload(payload: dict, *, require_identity: bool) -> InventoryPayload:
        if not isinstance(payload, dict):
            raise ValidationError("Request body must be a JSON object.")

        allowed_fields = {"sku", "name", "description", "quantity_on_hand", "reorder_point", "warehouse_id", "is_active"}
        unexpected_fields = sorted(set(payload) - allowed_fields)
        if unexpected_fields:
            raise ValidationError(f"Unexpected fields: {', '.join(unexpected_fields)}.")

        sku = payload.get("sku")
        name = payload.get("name")
        description = payload.get("description")
        quantity_on_hand = payload.get("quantity_on_hand")
        reorder_point = payload.get("reorder_point")
        warehouse_id = payload.get("warehouse_id")
        is_active = payload.get("is_active")

        if require_identity:
            missing_fields = [field for field in ("sku", "name", "quantity_on_hand", "reorder_point") if payload.get(field) is None]
            if missing_fields:
                raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}.")

        try:
            normalized_quantity = int(quantity_on_hand) if quantity_on_hand is not None else None
            normalized_reorder_point = int(reorder_point) if reorder_point is not None else None
            normalized_warehouse_id = int(warehouse_id) if warehouse_id is not None else None
        except (TypeError, ValueError) as exc:
            raise ValidationError("quantity_on_hand, reorder_point, and warehouse_id must be integers.") from exc

        if normalized_quantity is not None and normalized_quantity < 0:
            raise ValidationError("quantity_on_hand must be zero or greater.")

        if normalized_reorder_point is not None and normalized_reorder_point < 0:
            raise ValidationError("reorder_point must be zero or greater.")

        return InventoryPayload(
            sku=sku,
            name=name,
            description=description,
            quantity_on_hand=normalized_quantity,
            reorder_point=normalized_reorder_point,
            warehouse_id=normalized_warehouse_id,
            is_active=bool(is_active) if is_active is not None else None,
        )

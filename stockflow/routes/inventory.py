"""Inventory endpoints for the StockFlow API."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services.inventory_service import InventoryService
from ..utils.errors import ConflictError, NotFoundError, ValidationError
from ..utils.pagination import paginate
from ..utils.responses import error_response, success_response

inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.get("/items")
def list_inventory_items():
    items = [item.to_dict() for item in InventoryService.list_items()]
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=20, type=int)
    page_data = paginate(items, page=page, per_page=per_page)
    return success_response(page_data["items"], meta={k: v for k, v in page_data.items() if k != "items"})


@inventory_bp.get("/items/<int:item_id>")
def get_inventory_item(item_id: int):
    try:
        item = InventoryService.get_item(item_id)
        return success_response(item.to_dict())
    except NotFoundError as exc:
        return error_response(message=str(exc), status_code=exc.status_code, error_code=exc.error_code)


@inventory_bp.post("/items")
def create_inventory_item():
    try:
        item = InventoryService.create_item(request.get_json(silent=True) or {})
        return success_response(item.to_dict(), status_code=201)
    except (ValidationError, ConflictError) as exc:
        return error_response(message=str(exc), status_code=exc.status_code, error_code=exc.error_code)


@inventory_bp.patch("/items/<int:item_id>")
def update_inventory_item(item_id: int):
    try:
        item = InventoryService.update_item(item_id, request.get_json(silent=True) or {})
        return success_response(item.to_dict())
    except (ValidationError, ConflictError, NotFoundError) as exc:
        return error_response(message=str(exc), status_code=exc.status_code, error_code=exc.error_code)

"""Small pagination helper for list endpoints."""

from __future__ import annotations

from math import ceil


def paginate(items: list, *, page: int = 1, per_page: int = 20) -> dict:
    page = max(page, 1)
    per_page = max(per_page, 1)
    total_items = len(items)
    total_pages = ceil(total_items / per_page) if total_items else 0
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "page": page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": total_pages,
    }

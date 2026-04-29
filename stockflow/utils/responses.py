"""API response helpers to keep route code consistent."""

from __future__ import annotations

from flask import jsonify


def success_response(data=None, *, status_code: int = 200, meta: dict | None = None):
    payload = {"success": True, "data": data}
    if meta is not None:
        payload["meta"] = meta
    return jsonify(payload), status_code


def error_response(*, message: str, status_code: int, error_code: str):
    return jsonify({"success": False, "error": {"code": error_code, "message": message}}), status_code

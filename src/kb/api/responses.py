"""Response helpers for the normalized /api/v1 contract."""
from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse


def ok(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Wrap successful response data in the v1 envelope."""
    return {"data": data, "meta": meta or {}, "error": None}


def page(data: Any, *, limit: int, offset: int, total: int) -> dict[str, Any]:
    """Wrap paginated response data in the v1 envelope."""
    return ok(data, {"limit": limit, "offset": offset, "total": total})


def fail(
    *,
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Return a v1 error envelope with an HTTP status code."""
    return JSONResponse(
        status_code=status_code,
        content={
            "data": None,
            "meta": {},
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
        },
    )


def note_not_found() -> JSONResponse:
    return fail(
        code="NOTE_NOT_FOUND",
        message="Note not found",
        status_code=404,
    )


def path_traversal_blocked() -> JSONResponse:
    return fail(
        code="PATH_TRAVERSAL_BLOCKED",
        message="Path traversal blocked",
        status_code=403,
    )


def provider_not_configured(message: str) -> JSONResponse:
    return fail(
        code="PROVIDER_NOT_CONFIGURED",
        message=message,
        status_code=400,
    )


def operation_failed(code: str, message: str) -> JSONResponse:
    return fail(code=code, message=message, status_code=500)

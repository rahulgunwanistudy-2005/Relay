"""Translate typed application errors to HTTP responses. Keeps routers thin and
services free of any web-framework dependency."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from relay.core.application.errors import (
    ApplicationError,
    Conflict,
    InvalidState,
    NotAuthorized,
    NotFound,
)

_STATUS_MAP: list[tuple[type[ApplicationError], int]] = [
    (NotFound, status.HTTP_404_NOT_FOUND),
    (NotAuthorized, status.HTTP_403_FORBIDDEN),
    (Conflict, status.HTTP_409_CONFLICT),
    (InvalidState, status.HTTP_409_CONFLICT),
]


def _status_for(exc: ApplicationError) -> int:
    for exc_type, code in _STATUS_MAP:
        if isinstance(exc, exc_type):
            return code
    return status.HTTP_400_BAD_REQUEST


def install_error_handlers(app: FastAPI) -> None:
    from relay.logging import get_logger

    log = get_logger("relay.api.errors")

    async def handle(_request: Request, exc: ApplicationError) -> JSONResponse:
        return JSONResponse(
            status_code=_status_for(exc),
            content={"error": type(exc).__name__, "detail": str(exc)},
        )

    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Log the full error server-side; never leak a stack trace to the client.
        rid = getattr(request.state, "request_id", None)
        log.exception("api.unhandled_error", path=request.url.path, request_id=rid)
        return JSONResponse(status_code=500, content={"error": "internal_error"})

    app.add_exception_handler(ApplicationError, handle)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, handle_unexpected)

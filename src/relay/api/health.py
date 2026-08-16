"""Liveness and readiness probes.

- ``/health/live``  process is running (no dependencies checked).
- ``/health/ready`` dependencies are reachable; returns 503 when the database
  is not. This is what an orchestrator gates traffic on.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from relay.db.session import engine
from relay.logging import get_logger

log = get_logger("relay.api.health")
router = APIRouter(tags=["health"])


class LiveResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    database: str


@router.get("/health/live", response_model=LiveResponse)
def live() -> LiveResponse:
    return LiveResponse(status="ok")


@router.get("/health/ready", response_model=ReadyResponse)
def ready(response: Response) -> ReadyResponse:
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        log.warning("health.ready.db_unreachable")

    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(status="degraded", database="unreachable")
    return ReadyResponse(status="ok", database="ok")

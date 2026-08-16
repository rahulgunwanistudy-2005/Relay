"""Operational tables owned by the worker.

Phase 0 defines ``WorkerHeartbeat`` so worker liveness/readiness is derived from
persisted state rather than a guess. Phase 7 adds outbox/job leasing tables.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from relay.db.base import Base


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeat"

    worker_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    last_beat_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    beats: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

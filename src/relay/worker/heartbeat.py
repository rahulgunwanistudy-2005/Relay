"""Heartbeat persistence — worker readiness is derived from this table."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from relay.worker.models import WorkerHeartbeat

# A worker is considered live if it beat within this multiple of its interval.
STALE_MULTIPLIER = 3


def record_heartbeat(session: Session, worker_id: str, now: dt.datetime) -> None:
    stmt = insert(WorkerHeartbeat).values(
        worker_id=worker_id, last_beat_at=now, started_at=now, beats=1
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[WorkerHeartbeat.worker_id],
        set_={
            "last_beat_at": now,
            "beats": WorkerHeartbeat.beats + 1,
        },
    )
    session.execute(stmt)


def latest_heartbeat(engine: Engine) -> WorkerHeartbeat | None:
    with Session(engine) as session:
        return session.execute(
            select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_beat_at.desc()).limit(1)
        ).scalar_one_or_none()


def any_worker_live(engine: Engine, now: dt.datetime, interval_seconds: int) -> bool:
    hb = latest_heartbeat(engine)
    if hb is None:
        return False
    age = (now - hb.last_beat_at).total_seconds()
    return age <= interval_seconds * STALE_MULTIPLIER

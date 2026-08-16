"""Outbox: retry with backoff, dead-letter after max attempts, lease recovery."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from relay.core.enums import OutboxStatus
from relay.core.models.outbox import OutboxEvent
from relay.worker.claiming import claim_outbox
from relay.worker.processing import process_outbox

pytestmark = [pytest.mark.integration, pytest.mark.worker]

T0 = dt.datetime(2026, 6, 1, 0, 0, tzinfo=dt.UTC)


def _add_event(engine: Engine, event_type: str = "test.event") -> None:
    import uuid

    with Session(engine) as s:
        s.add(
            OutboxEvent(
                event_type=event_type,
                aggregate_id=uuid.uuid4(),
                payload={},
                available_at=T0,
            )
        )
        s.commit()


def test_successful_handler_marks_processed(engine: Engine) -> None:
    _add_event(engine)
    seen = []
    with Session(engine) as s:
        n = process_outbox(
            s,
            now=T0,
            worker_id="w1",
            lease_seconds=60,
            max_attempts=5,
            backoff_s=30,
            limit=10,
            handlers={"test.event": lambda _s, row: seen.append(row.id)},
        )
        s.commit()
    assert n == 1 and len(seen) == 1
    with Session(engine) as s:
        row = s.execute(select(OutboxEvent)).scalar_one()
        assert row.status is OutboxStatus.processed
        assert row.processed_at is not None
        assert row.lease_owner is None


def test_failing_handler_retries_with_backoff_then_dead_letters(engine: Engine) -> None:
    _add_event(engine)

    def boom(_s, _row):
        raise RuntimeError("handler failed")

    handlers = {"test.event": boom}
    now = T0
    for attempt in range(1, 4):  # max_attempts=3
        with Session(engine) as s:
            process_outbox(
                s,
                now=now,
                worker_id="w1",
                lease_seconds=60,
                max_attempts=3,
                backoff_s=30,
                limit=10,
                handlers=handlers,
            )
            s.commit()
        with Session(engine) as s:
            row = s.execute(select(OutboxEvent)).scalar_one()
            assert row.attempt_count == attempt
            if attempt < 3:
                assert row.status is OutboxStatus.pending
                # Backoff pushes availability into the future.
                assert row.available_at > now
                now = row.available_at  # advance to when it's claimable again
            else:
                assert row.status is OutboxStatus.dead
                assert "handler failed" in row.last_error


def test_expired_lease_is_reclaimed(engine: Engine) -> None:
    _add_event(engine)
    # Worker A claims but "crashes" before processing.
    with Session(engine) as s:
        claimed = claim_outbox(s, now=T0, worker_id="crashed", lease_seconds=60, limit=10)
        assert len(claimed) == 1
        s.commit()

    # Before lease expiry, the row is not claimable by anyone else.
    with Session(engine) as s:
        assert (
            claim_outbox(
                s, now=T0 + dt.timedelta(seconds=30), worker_id="w2", lease_seconds=60, limit=10
            )
            == []
        )
        s.commit()

    # After lease expiry, a fresh worker reclaims it.
    with Session(engine) as s:
        reclaimed = claim_outbox(
            s, now=T0 + dt.timedelta(seconds=120), worker_id="w2", lease_seconds=60, limit=10
        )
        assert len(reclaimed) == 1
        assert reclaimed[0].lease_owner == "w2"
        s.commit()

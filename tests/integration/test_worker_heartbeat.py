from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import Engine

from relay.core.clock import FrozenClock
from relay.worker.heartbeat import any_worker_live, latest_heartbeat
from relay.worker.runner import Worker

pytestmark = pytest.mark.integration


def test_tick_records_and_increments_heartbeat(engine: Engine) -> None:
    clock = FrozenClock(dt.datetime(2026, 1, 1, tzinfo=dt.UTC))
    worker = Worker(engine, "w-test", clock=clock, poll_interval_s=0.0)

    worker.tick()
    hb = latest_heartbeat(engine)
    assert hb is not None
    assert hb.worker_id == "w-test"
    assert hb.beats == 1

    clock.advance(5)
    worker.tick()
    hb = latest_heartbeat(engine)
    assert hb.beats == 2
    assert hb.last_beat_at == clock.now()


def test_any_worker_live_respects_staleness(engine: Engine) -> None:
    start = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    clock = FrozenClock(start)
    Worker(engine, "w-live", clock=clock, poll_interval_s=0.0).tick()

    # Just beat -> live.
    assert any_worker_live(engine, clock.now(), interval_seconds=5) is True

    # Far in the future past the stale window -> not live.
    future = start + dt.timedelta(seconds=1000)
    assert any_worker_live(engine, future, interval_seconds=5) is False


def test_any_worker_live_false_when_no_heartbeat(engine: Engine) -> None:
    now = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    assert any_worker_live(engine, now, interval_seconds=5) is False

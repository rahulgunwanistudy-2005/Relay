from __future__ import annotations

import datetime as dt

import pytest

from relay.core.clock import FrozenClock, SystemClock


def test_system_clock_is_utc_aware() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == dt.timedelta(0)


def test_frozen_clock_requires_tz_aware() -> None:
    with pytest.raises(ValueError):
        FrozenClock(dt.datetime(2026, 1, 1, 0, 0, 0))


def test_frozen_clock_advance() -> None:
    start = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    clock = FrozenClock(start)
    assert clock.now() == start
    clock.advance(90)
    assert clock.now() == start + dt.timedelta(seconds=90)

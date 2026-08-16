"""Recurrence math: timezone/DST correctness, month boundaries, leap years."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from relay.core.recurrence import next_occurrence

NY = "America/New_York"


def test_daily_keeps_wall_clock_across_dst_spring_forward() -> None:
    # US DST begins 2026-03-08. "Every day at 09:00 local" must stay 09:00 local.
    anchor = dt.datetime(2026, 3, 7, 9, 0, tzinfo=ZoneInfo(NY))
    after = anchor
    nxt = next_occurrence(
        "FREQ=DAILY;BYHOUR=9;BYMINUTE=0;BYSECOND=0", anchor=anchor, after=after, timezone=NY
    )
    assert nxt is not None
    local = nxt.astimezone(ZoneInfo(NY))
    assert (local.year, local.month, local.day) == (2026, 3, 8)
    assert local.hour == 9  # wall clock preserved despite the -1h DST shift
    # And it is stored/returned as UTC (EDT = UTC-4 on that date).
    assert nxt.utcoffset() == dt.timedelta(0)
    assert nxt.hour == 13


def test_monthly_by_month_day_31_skips_short_months() -> None:
    anchor = dt.datetime(2026, 1, 31, 9, 0, tzinfo=ZoneInfo("UTC"))
    nxt = next_occurrence("FREQ=MONTHLY;BYMONTHDAY=31", anchor=anchor, after=anchor, timezone="UTC")
    assert nxt is not None
    local = nxt.astimezone(ZoneInfo("UTC"))
    # February has no 31st, so the next is March 31.
    assert (local.month, local.day) == (3, 31)


def test_leap_day_yearly_lands_on_next_leap_year() -> None:
    anchor = dt.datetime(2024, 2, 29, 12, 0, tzinfo=ZoneInfo("UTC"))
    nxt = next_occurrence(
        "FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=29", anchor=anchor, after=anchor, timezone="UTC"
    )
    assert nxt is not None
    assert (nxt.year, nxt.month, nxt.day) == (2028, 2, 29)


def test_exhausted_rule_returns_none() -> None:
    anchor = dt.datetime(2026, 1, 1, 9, 0, tzinfo=ZoneInfo("UTC"))
    nxt = next_occurrence("FREQ=DAILY;COUNT=1", anchor=anchor, after=anchor, timezone="UTC")
    assert nxt is None

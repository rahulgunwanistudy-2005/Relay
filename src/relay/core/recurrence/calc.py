"""Next-occurrence computation from an iCalendar RRULE.

Work in the household's local timezone so that "every day at 09:00" stays at
09:00 across DST transitions, then return a timezone-aware UTC datetime. This is
why every stored timestamp is timestamptz.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from dateutil import rrule


def next_occurrence(
    rrule_str: str,
    *,
    anchor: dt.datetime,
    after: dt.datetime,
    timezone: str,
) -> dt.datetime | None:
    """First occurrence strictly after ``after``.

    ``anchor`` is the series start (DTSTART). ``after`` is usually "now" or the
    just-completed occurrence. Returns UTC-aware datetime, or None if the rule
    is exhausted.
    """
    tz = ZoneInfo(timezone)
    local_anchor = anchor.astimezone(tz).replace(tzinfo=None)
    local_after = after.astimezone(tz).replace(tzinfo=None)

    rule = rrule.rrulestr(rrule_str, dtstart=local_anchor)
    nxt = rule.after(local_after, inc=False)
    if nxt is None:
        return None
    # Attach the local tz (handles DST offset for that wall-clock date) → UTC.
    return nxt.replace(tzinfo=tz).astimezone(dt.UTC)

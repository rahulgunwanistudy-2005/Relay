"""Injectable clock.

Domain scheduling and the worker receive a ``Clock``. Production uses
``SystemClock``; tests use ``FrozenClock``. The clock changes only the time
source — never business logic.
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol


class Clock(Protocol):
    def now(self) -> dt.datetime:
        """Return the current time as a timezone-aware UTC datetime."""
        ...


class SystemClock:
    def now(self) -> dt.datetime:
        return dt.datetime.now(dt.UTC)


class FrozenClock:
    """Test clock. Never use in production."""

    def __init__(self, at: dt.datetime) -> None:
        if at.tzinfo is None:
            raise ValueError("FrozenClock requires a timezone-aware datetime")
        self._now = at.astimezone(dt.UTC)

    def now(self) -> dt.datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now = self._now + dt.timedelta(seconds=seconds)

    def set(self, at: dt.datetime) -> None:
        self._now = at.astimezone(dt.UTC)

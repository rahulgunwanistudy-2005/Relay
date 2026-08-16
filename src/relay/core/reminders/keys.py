"""Deterministic reminder identity.

A reminder's dedupe key is a pure function of its logical identity, so
materialization is idempotent and a transfer produces a fresh, distinct key for
the new ownership version.
"""

from __future__ import annotations

import datetime as dt
import uuid

from relay.core.enums import ReminderType


def make_dedupe_key(
    *,
    responsibility_id: uuid.UUID,
    cycle_id: uuid.UUID,
    lifecycle_step_id: uuid.UUID | None,
    ownership_version: int,
    reminder_type: ReminderType,
    scheduled_for: dt.datetime,
) -> str:
    step = str(lifecycle_step_id) if lifecycle_step_id else "-"
    # Minute-resolution window keeps re-materialization within the same minute
    # idempotent without collapsing genuinely distinct schedules.
    window = scheduled_for.astimezone(dt.UTC).strftime("%Y%m%dT%H%M")
    return (
        f"{responsibility_id}:{cycle_id}:{step}:{ownership_version}:{reminder_type.value}:{window}"
    )

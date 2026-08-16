"""Crash/restart safety: a worker that dies mid-tick loses no obligation and
creates no duplicate delivery on restart (at-least-once + idempotent effects)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from relay.core.clock import FrozenClock
from relay.core.enums import ReminderState, ReminderType, ResponsibilityStatus
from relay.core.models import Reminder, ResponsibilityCycle
from relay.notifications.channels import InAppChannel
from relay.notifications.models import NotificationDelivery
from relay.worker.claiming import claim_due_reminders
from relay.worker.runner import Worker
from tests.factories import make_household, make_membership, make_responsibility, make_user

pytestmark = [pytest.mark.integration, pytest.mark.worker]

DUE = dt.datetime(2026, 6, 1, 9, 0, tzinfo=dt.UTC)


@pytest.fixture
def due_reminders(engine: Engine):
    with Session(engine) as s:
        hh = make_household(s)
        owner = make_membership(s, make_user(s), hh)
        resp = make_responsibility(s, hh, owner, owner=owner, status=ResponsibilityStatus.active)
        cycle = ResponsibilityCycle(responsibility_id=resp.id, sequence=1)
        s.add(cycle)
        s.flush()
        for i in range(3):
            s.add(
                Reminder(
                    responsibility_id=resp.id,
                    cycle_id=cycle.id,
                    recipient_membership_id=owner.id,
                    ownership_version=1,
                    reminder_type=ReminderType.cycle_due,
                    scheduled_for=DUE,
                    state=ReminderState.scheduled,
                    dedupe_key=f"due-{i}",
                )
            )
        s.commit()
        return {"resp": resp.id}


def _count(engine, model) -> int:
    with Session(engine) as s:
        return s.execute(select(func.count()).select_from(model)).scalar_one()


def test_crash_before_commit_loses_nothing_and_restart_fires_once(engine, due_reminders) -> None:
    now = DUE + dt.timedelta(minutes=1)

    # Simulate a worker that claims work then crashes before committing.
    crash_session = Session(engine)
    claimed = claim_due_reminders(crash_session, now=now, limit=100)
    assert len(claimed) == 3
    crash_session.rollback()  # crash: transaction dies, locks released
    crash_session.close()

    # Nothing was lost or half-processed.
    assert _count(engine, NotificationDelivery) == 0
    with Session(engine) as s:
        still_scheduled = s.execute(
            select(func.count())
            .select_from(Reminder)
            .where(Reminder.state == ReminderState.scheduled)
        ).scalar_one()
        assert still_scheduled == 3

    # Restart: a fresh worker fires every obligation exactly once.
    worker = Worker(engine, "restarted", clock=FrozenClock(now), channels=[InAppChannel()])
    worker.tick()
    assert _count(engine, NotificationDelivery) == 3

    # A further tick does not duplicate.
    worker.tick()
    assert _count(engine, NotificationDelivery) == 3
    with Session(engine) as s:
        fired = s.execute(
            select(func.count()).select_from(Reminder).where(Reminder.state == ReminderState.fired)
        ).scalar_one()
        assert fired == 3

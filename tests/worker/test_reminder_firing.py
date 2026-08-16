"""Worker fires due reminders exactly once and records delivery evidence."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from relay.core.clock import FrozenClock
from relay.core.enums import DeliveryStatus, ReminderState, ReminderType, ResponsibilityStatus
from relay.core.models import Reminder, ResponsibilityCycle
from relay.notifications.channels import InAppChannel
from relay.notifications.models import InAppNotification, NotificationDelivery
from relay.worker.runner import Worker
from tests.factories import make_household, make_membership, make_responsibility, make_user

pytestmark = [pytest.mark.integration, pytest.mark.worker]

DUE = dt.datetime(2026, 6, 1, 9, 0, tzinfo=dt.UTC)


@pytest.fixture
def due_reminder(engine: Engine):
    with Session(engine) as s:
        hh = make_household(s)
        owner = make_membership(s, make_user(s), hh)
        resp = make_responsibility(s, hh, owner, owner=owner, status=ResponsibilityStatus.active)
        cycle = ResponsibilityCycle(responsibility_id=resp.id, sequence=1)
        s.add(cycle)
        s.flush()
        s.add(
            Reminder(
                responsibility_id=resp.id,
                cycle_id=cycle.id,
                recipient_membership_id=owner.id,
                ownership_version=1,
                reminder_type=ReminderType.cycle_due,
                scheduled_for=DUE,
                state=ReminderState.scheduled,
                dedupe_key="due-1",
            )
        )
        s.commit()
        return {"owner": owner.id, "resp": resp.id}


def _worker(engine, clock) -> Worker:
    return Worker(engine, "w1", clock=clock, channels=[InAppChannel()])


def test_worker_fires_due_reminder_and_records_delivery(engine: Engine, due_reminder) -> None:
    clock = FrozenClock(DUE + dt.timedelta(minutes=1))
    processed = _worker(engine, clock).tick()
    assert processed >= 1

    with Session(engine) as s:
        r = s.execute(select(Reminder).where(Reminder.dedupe_key == "due-1")).scalar_one()
        assert r.state is ReminderState.fired
        assert r.fired_at is not None

        delivery = s.execute(select(NotificationDelivery)).scalar_one()
        assert delivery.status is DeliveryStatus.delivered
        assert delivery.recipient_membership_id == due_reminder["owner"]

        note = s.execute(select(InAppNotification)).scalar_one()
        assert note.recipient_membership_id == due_reminder["owner"]


def test_reminder_not_fired_before_due(engine: Engine, due_reminder) -> None:
    clock = FrozenClock(DUE - dt.timedelta(hours=1))
    _worker(engine, clock).tick()
    with Session(engine) as s:
        r = s.execute(select(Reminder).where(Reminder.dedupe_key == "due-1")).scalar_one()
        assert r.state is ReminderState.scheduled
        assert s.execute(select(func.count()).select_from(NotificationDelivery)).scalar_one() == 0


def test_firing_is_idempotent_across_ticks(engine: Engine, due_reminder) -> None:
    clock = FrozenClock(DUE + dt.timedelta(minutes=1))
    w = _worker(engine, clock)
    w.tick()
    w.tick()  # second tick must not re-fire
    with Session(engine) as s:
        deliveries = s.execute(select(func.count()).select_from(NotificationDelivery)).scalar_one()
        assert deliveries == 1

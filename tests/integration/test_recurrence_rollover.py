"""Recurrence roll-over: complete a cycle → next cycle, cloned steps, owner
carried, obligations materialized. Historical cycles are never overwritten."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from relay.core.application import handoff
from relay.core.application.scheduling import complete_cycle_and_advance
from relay.core.clock import FrozenClock
from relay.core.enums import CycleStatus, LifecycleKind, ReminderState, ResponsibilityStatus
from relay.core.models import (
    LifecycleStep,
    RecurrenceRule,
    Reminder,
    ResponsibilityCycle,
)
from tests.factories import make_household, make_membership, make_responsibility, make_user

pytestmark = [pytest.mark.integration, pytest.mark.worker]

ANCHOR = dt.datetime(2026, 6, 1, 9, 0, tzinfo=dt.UTC)


@pytest.fixture
def recurring(engine: Engine):
    with Session(engine) as s:
        hh = make_household(s, tz="UTC")
        a = make_membership(s, make_user(s, name="A"), hh)
        b = make_membership(s, make_user(s, name="B"), hh)
        resp = make_responsibility(s, hh, a, owner=a, status=ResponsibilityStatus.active)
        cycle = ResponsibilityCycle(
            responsibility_id=resp.id, sequence=1, status=CycleStatus.active, target_at=ANCHOR
        )
        s.add(cycle)
        s.flush()
        s.add(
            LifecycleStep(
                cycle_id=cycle.id,
                step_key="execute",
                kind=LifecycleKind.execute,
                description="do it",
                ordering=1,
                due_at=ANCHOR,
            )
        )
        s.add(
            RecurrenceRule(
                responsibility_id=resp.id,
                rrule="FREQ=DAILY;BYHOUR=9;BYMINUTE=0;BYSECOND=0",
                timezone="UTC",
                anchor_at=ANCHOR,
                enabled=True,
            )
        )
        s.commit()
        return {"a": a.id, "b": b.id, "resp": resp.id, "cycle1": cycle.id}


def test_advance_creates_next_cycle_with_cloned_steps_and_reminders(engine, recurring) -> None:
    clock = FrozenClock(ANCHOR + dt.timedelta(hours=1))
    with Session(engine) as s:
        new_cycle = complete_cycle_and_advance(s, responsibility_id=recurring["resp"], clock=clock)
        s.commit()
        assert new_cycle is not None
        assert new_cycle.sequence == 2

    with Session(engine) as s:
        cycles = (
            s.execute(
                select(ResponsibilityCycle)
                .where(ResponsibilityCycle.responsibility_id == recurring["resp"])
                .order_by(ResponsibilityCycle.sequence)
            )
            .scalars()
            .all()
        )
        assert len(cycles) == 2
        assert cycles[0].status is CycleStatus.completed  # history preserved
        assert cycles[0].completed_at is not None
        assert cycles[1].status is CycleStatus.pending
        # Next occurrence is the following day at 09:00.
        assert cycles[1].target_at == ANCHOR + dt.timedelta(days=1)

        # Steps cloned into the new cycle.
        steps = (
            s.execute(select(LifecycleStep).where(LifecycleStep.cycle_id == cycles[1].id))
            .scalars()
            .all()
        )
        assert [st.step_key for st in steps] == ["execute"]

        # Reminders materialized for the new cycle, owned by A.
        reminders = (
            s.execute(
                select(Reminder).where(
                    Reminder.cycle_id == cycles[1].id, Reminder.state == ReminderState.scheduled
                )
            )
            .scalars()
            .all()
        )
        assert reminders
        assert all(r.recipient_membership_id == recurring["a"] for r in reminders)


def test_disabled_recurrence_completes_without_next(engine, recurring) -> None:
    with Session(engine) as s:
        s.execute(
            select(RecurrenceRule).where(RecurrenceRule.responsibility_id == recurring["resp"])
        ).scalar_one().enabled = False
        s.commit()
    clock = FrozenClock(ANCHOR + dt.timedelta(hours=1))
    with Session(engine) as s:
        result = complete_cycle_and_advance(s, responsibility_id=recurring["resp"], clock=clock)
        s.commit()
        assert result is None
    with Session(engine) as s:
        cycles = (
            s.execute(
                select(ResponsibilityCycle).where(
                    ResponsibilityCycle.responsibility_id == recurring["resp"]
                )
            )
            .scalars()
            .all()
        )
        assert len(cycles) == 1
        assert cycles[0].status is CycleStatus.completed


def test_transfer_then_advance_routes_new_cycle_to_new_owner(engine, recurring) -> None:
    # Transfer A -> B, then roll the recurrence forward.
    with Session(engine) as s:
        cid = handoff.propose_handoff(
            s,
            actor_membership_id=recurring["a"],
            responsibility_id=recurring["resp"],
            target_membership_id=recurring["b"],
        ).id
        s.commit()
    with Session(engine) as s:
        handoff.accept_handoff(
            s, actor_membership_id=recurring["b"], contract_id=cid, idempotency_key="rec-x"
        )
        s.commit()

    clock = FrozenClock(ANCHOR + dt.timedelta(hours=1))
    with Session(engine) as s:
        new_cycle = complete_cycle_and_advance(s, responsibility_id=recurring["resp"], clock=clock)
        s.commit()
        cid2 = new_cycle.id

    with Session(engine) as s:
        reminders = (
            s.execute(
                select(Reminder).where(
                    Reminder.cycle_id == cid2, Reminder.state == ReminderState.scheduled
                )
            )
            .scalars()
            .all()
        )
        assert reminders
        # No Boomerang across cycles: new obligations belong to B.
        assert all(r.recipient_membership_id == recurring["b"] for r in reminders)

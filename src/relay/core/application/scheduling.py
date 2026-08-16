"""Reminder materialization and recurrence roll-over.

Materialization is idempotent (dedupe-key upsert). Recurrence preserves the
completed cycle, creates the next one in the household timezone, clones the
lifecycle, carries the current owner, and materializes the next obligations.
"""

from __future__ import annotations

import uuid
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from relay.core.application.errors import NotFound
from relay.core.clock import Clock, SystemClock
from relay.core.enums import CycleStatus, OwnershipEventType, ReminderState, ReminderType
from relay.core.models import (
    LifecycleStep,
    OwnershipEvent,
    RecurrenceRule,
    Reminder,
    Responsibility,
    ResponsibilityCycle,
)
from relay.core.recurrence import next_occurrence
from relay.core.reminders import make_dedupe_key


def _upsert_reminder(
    session: Session,
    *,
    responsibility: Responsibility,
    cycle: ResponsibilityCycle,
    step: LifecycleStep | None,
    reminder_type: ReminderType,
    scheduled_for,
) -> bool:
    owner = responsibility.current_owner_membership_id
    if owner is None:
        return False
    key = make_dedupe_key(
        responsibility_id=responsibility.id,
        cycle_id=cycle.id,
        lifecycle_step_id=step.id if step else None,
        ownership_version=responsibility.ownership_version,
        reminder_type=reminder_type,
        scheduled_for=scheduled_for,
    )
    stmt = (
        insert(Reminder)
        .values(
            responsibility_id=responsibility.id,
            cycle_id=cycle.id,
            lifecycle_step_id=step.id if step else None,
            recipient_membership_id=owner,
            ownership_version=responsibility.ownership_version,
            reminder_type=reminder_type,
            scheduled_for=scheduled_for,
            state=ReminderState.scheduled,
            dedupe_key=key,
        )
        .on_conflict_do_nothing(index_elements=[Reminder.dedupe_key])
    )
    result = cast("CursorResult", session.execute(stmt))
    return bool(result.rowcount)


def materialize_cycle_reminders(
    session: Session, *, responsibility: Responsibility, cycle: ResponsibilityCycle
) -> int:
    count = 0
    if cycle.target_at is not None:
        count += int(
            _upsert_reminder(
                session,
                responsibility=responsibility,
                cycle=cycle,
                step=None,
                reminder_type=ReminderType.cycle_due,
                scheduled_for=cycle.target_at,
            )
        )
    for step in cycle.steps:
        if step.due_at is not None:
            count += int(
                _upsert_reminder(
                    session,
                    responsibility=responsibility,
                    cycle=cycle,
                    step=step,
                    reminder_type=ReminderType.step_due,
                    scheduled_for=step.due_at,
                )
            )
    return count


def complete_cycle_and_advance(
    session: Session, *, responsibility_id: uuid.UUID, clock: Clock = SystemClock()
) -> ResponsibilityCycle | None:
    """Complete the latest open cycle. If recurrence is enabled and not
    exhausted, create the next cycle (clone steps, carry owner) and materialize
    its reminders. Returns the new cycle, or None when there is no next."""
    now = clock.now()
    responsibility = session.execute(
        select(Responsibility).where(Responsibility.id == responsibility_id).with_for_update()
    ).scalar_one_or_none()
    if responsibility is None:
        raise NotFound("responsibility not found")

    current = session.execute(
        select(ResponsibilityCycle)
        .where(
            ResponsibilityCycle.responsibility_id == responsibility_id,
            ResponsibilityCycle.status != CycleStatus.completed,
        )
        .order_by(ResponsibilityCycle.sequence.desc())
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    if current is None:
        raise NotFound("no open cycle to complete")

    current.status = CycleStatus.completed
    current.completed_at = now

    rule = session.execute(
        select(RecurrenceRule).where(
            RecurrenceRule.responsibility_id == responsibility_id,
            RecurrenceRule.enabled.is_(True),
        )
    ).scalar_one_or_none()
    if rule is None:
        return None

    after = current.target_at or now
    nxt = next_occurrence(rule.rrule, anchor=rule.anchor_at, after=after, timezone=rule.timezone)
    if nxt is None:
        return None

    new_cycle = ResponsibilityCycle(
        responsibility_id=responsibility_id,
        sequence=current.sequence + 1,
        status=CycleStatus.pending,
        starts_at=now,
        target_at=nxt,
    )
    session.add(new_cycle)
    session.flush()

    # Clone the lifecycle (structure carries; execution state resets).
    old_steps = (
        session.execute(select(LifecycleStep).where(LifecycleStep.cycle_id == current.id))
        .scalars()
        .all()
    )
    for step in old_steps:
        session.add(
            LifecycleStep(
                cycle_id=new_cycle.id,
                step_key=step.step_key,
                kind=step.kind,
                description=step.description,
                ordering=step.ordering,
                provenance=step.provenance,
                confidence=step.confidence,
                is_assumption=step.is_assumption,
            )
        )
    session.flush()

    rule.next_materialization_at = nxt

    session.add(
        OwnershipEvent(
            responsibility_id=responsibility_id,
            event_type=OwnershipEventType.created,
            actor_membership_id=None,
            previous_owner_membership_id=responsibility.current_owner_membership_id,
            new_owner_membership_id=responsibility.current_owner_membership_id,
            ownership_version=responsibility.ownership_version,
            reason_metadata={"recurrence_cycle": new_cycle.sequence},
        )
    )

    # Owner carries across cycles (No Boomerang). Materialize next obligations.
    session.refresh(new_cycle)
    materialize_cycle_reminders(session, responsibility=responsibility, cycle=new_cycle)
    return new_cycle

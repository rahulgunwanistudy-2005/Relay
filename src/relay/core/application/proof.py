"""Proof of Relief — operational facts computed from persisted state only.

No wellness scores, no invented percentages. Everything here is reconstructable
from OwnershipEvent, reminders, lifecycle steps, and recurrence.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from relay.core.application.errors import NotFound
from relay.core.enums import (
    LifecycleKind,
    OwnershipEventType,
    StepStatus,
)
from relay.core.models import (
    LifecycleStep,
    OwnershipEvent,
    RecurrenceRule,
    Reminder,
    Responsibility,
    ResponsibilityCycle,
)


@dataclasses.dataclass(frozen=True)
class ProofOfRelief:
    responsibility_id: uuid.UUID
    transferred: bool
    ownership_version_before: int | None
    ownership_version_after: int | None
    new_owner_membership_id: uuid.UUID | None
    at: dt.datetime | None
    reminders_rerouted: int
    lifecycle_obligations_transferred: int
    decision_points_transferred: int
    recurrence_obligations_transferred: int


_DECISION_KINDS = {LifecycleKind.decide, LifecycleKind.options}


def proof_of_relief(
    session: Session, *, responsibility_id: uuid.UUID, household_id: uuid.UUID
) -> ProofOfRelief:
    resp = session.execute(
        select(Responsibility).where(
            Responsibility.id == responsibility_id,
            Responsibility.household_id == household_id,
        )
    ).scalar_one_or_none()
    if resp is None:
        raise NotFound("responsibility not found")

    last_transfer = session.execute(
        select(OwnershipEvent)
        .where(
            OwnershipEvent.responsibility_id == responsibility_id,
            OwnershipEvent.event_type == OwnershipEventType.transferred,
        )
        .order_by(OwnershipEvent.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if last_transfer is None:
        return ProofOfRelief(
            responsibility_id=responsibility_id,
            transferred=False,
            ownership_version_before=None,
            ownership_version_after=None,
            new_owner_membership_id=None,
            at=None,
            reminders_rerouted=0,
            lifecycle_obligations_transferred=0,
            decision_points_transferred=0,
            recurrence_obligations_transferred=0,
        )

    new_version = last_transfer.ownership_version
    # Reminders now scheduled for the new owner at the new ownership version.
    reminders_rerouted = session.execute(
        select(func.count())
        .select_from(Reminder)
        .where(
            Reminder.responsibility_id == responsibility_id,
            Reminder.ownership_version == new_version,
            Reminder.recipient_membership_id == last_transfer.new_owner_membership_id,
        )
    ).scalar_one()

    current_cycle = session.execute(
        select(ResponsibilityCycle)
        .where(ResponsibilityCycle.responsibility_id == responsibility_id)
        .order_by(ResponsibilityCycle.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()

    lifecycle_obligations = decision_points = 0
    if current_cycle is not None:
        open_steps = (
            session.execute(
                select(LifecycleStep).where(
                    LifecycleStep.cycle_id == current_cycle.id,
                    LifecycleStep.status != StepStatus.done,
                )
            )
            .scalars()
            .all()
        )
        lifecycle_obligations = len(open_steps)
        decision_points = sum(1 for s in open_steps if s.kind in _DECISION_KINDS)

    recurrence_obligations = session.execute(
        select(func.count())
        .select_from(RecurrenceRule)
        .where(
            RecurrenceRule.responsibility_id == responsibility_id,
            RecurrenceRule.enabled.is_(True),
        )
    ).scalar_one()

    return ProofOfRelief(
        responsibility_id=responsibility_id,
        transferred=True,
        ownership_version_before=new_version - 1,
        ownership_version_after=new_version,
        new_owner_membership_id=last_transfer.new_owner_membership_id,
        at=last_transfer.created_at,
        reminders_rerouted=int(reminders_rerouted),
        lifecycle_obligations_transferred=lifecycle_obligations,
        decision_points_transferred=decision_points,
        recurrence_obligations_transferred=int(recurrence_obligations),
    )


def ownership_history(
    session: Session, *, responsibility_id: uuid.UUID, household_id: uuid.UUID
) -> list[OwnershipEvent]:
    resp = session.execute(
        select(Responsibility).where(
            Responsibility.id == responsibility_id,
            Responsibility.household_id == household_id,
        )
    ).scalar_one_or_none()
    if resp is None:
        raise NotFound("responsibility not found")
    return list(
        session.execute(
            select(OwnershipEvent)
            .where(OwnershipEvent.responsibility_id == responsibility_id)
            .order_by(OwnershipEvent.created_at.asc())
        ).scalars()
    )

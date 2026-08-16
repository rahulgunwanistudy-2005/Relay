"""Responsibility lifecycle services: create from a confirmed draft, X-Ray read,
scope edits (version bump), step completion/reopen, and completion."""

from __future__ import annotations

import dataclasses
import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from relay.core.application.errors import InvalidState, NotFound
from relay.core.application.scheduling import (
    complete_cycle_and_advance,
    materialize_cycle_reminders,
)
from relay.core.clock import Clock, SystemClock
from relay.core.enums import (
    CycleStatus,
    LifecycleKind,
    OwnershipEventType,
    Provenance,
    ResponsibilityStatus,
    StepStatus,
)
from relay.core.models import (
    AuditEvent,
    Household,
    LifecycleStep,
    Membership,
    OwnershipEvent,
    RecurrenceRule,
    Responsibility,
    ResponsibilityCycle,
    StepDependency,
)
from relay.core.ownership import state_machine as sm


@dataclasses.dataclass(frozen=True)
class StepInput:
    step_key: str
    kind: LifecycleKind
    description: str
    ordering: int = 0
    due_at: dt.datetime | None = None
    provenance: Provenance = Provenance.user_explicit
    is_assumption: bool = False


def create_responsibility(
    session: Session,
    *,
    actor: Membership,
    title: str,
    steps: list[StepInput],
    domain: str = "general",
    completion_standard: str | None = None,
    target_at: dt.datetime | None = None,
    recurrence_rrule: str | None = None,
    clock: Clock = SystemClock(),
) -> Responsibility:
    """Create a canonical, active responsibility owned by the creator, with its
    first cycle, lifecycle steps, optional recurrence, and materialized reminders."""
    if not steps:
        raise InvalidState("a responsibility needs at least one lifecycle step")

    responsibility = Responsibility(
        household_id=actor.household_id,
        title=title.strip(),
        domain=domain,
        completion_standard=completion_standard,
        status=ResponsibilityStatus.active,
        current_owner_membership_id=actor.id,
        created_by_membership_id=actor.id,
    )
    session.add(responsibility)
    session.flush()

    cycle = ResponsibilityCycle(
        responsibility_id=responsibility.id,
        sequence=1,
        status=CycleStatus.active,
        starts_at=clock.now(),
        target_at=target_at,
    )
    session.add(cycle)
    session.flush()

    for s in steps:
        session.add(
            LifecycleStep(
                cycle_id=cycle.id,
                step_key=s.step_key,
                kind=s.kind,
                description=s.description,
                ordering=s.ordering,
                due_at=s.due_at,
                provenance=s.provenance,
                is_assumption=s.is_assumption,
            )
        )
    session.flush()

    if recurrence_rrule:
        household = session.get(Household, actor.household_id)
        session.add(
            RecurrenceRule(
                responsibility_id=responsibility.id,
                rrule=recurrence_rrule,
                timezone=household.timezone if household else "UTC",
                anchor_at=target_at or clock.now(),
                enabled=True,
            )
        )

    session.add(
        OwnershipEvent(
            responsibility_id=responsibility.id,
            event_type=OwnershipEventType.created,
            actor_membership_id=actor.id,
            previous_owner_membership_id=None,
            new_owner_membership_id=actor.id,
            ownership_version=responsibility.ownership_version,
        )
    )
    session.add(
        AuditEvent(
            household_id=actor.household_id,
            actor_membership_id=actor.id,
            event_type="responsibility.created",
            resource_type="responsibility",
            resource_id=responsibility.id,
        )
    )

    session.refresh(cycle)
    materialize_cycle_reminders(session, responsibility=responsibility, cycle=cycle)
    return responsibility


def get_responsibility_scoped(
    session: Session, *, responsibility_id: uuid.UUID, household_id: uuid.UUID
) -> Responsibility:
    """Fetch a responsibility scoped to the caller's household. Never by id alone."""
    resp = session.execute(
        select(Responsibility).where(
            Responsibility.id == responsibility_id,
            Responsibility.household_id == household_id,
        )
    ).scalar_one_or_none()
    if resp is None:
        raise NotFound("responsibility not found")
    return resp


def latest_cycle(session: Session, responsibility_id: uuid.UUID) -> ResponsibilityCycle | None:
    return session.execute(
        select(ResponsibilityCycle)
        .where(ResponsibilityCycle.responsibility_id == responsibility_id)
        .order_by(ResponsibilityCycle.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()


def list_responsibilities(session: Session, *, household_id: uuid.UUID) -> list[Responsibility]:
    return list(
        session.execute(
            select(Responsibility)
            .where(Responsibility.household_id == household_id)
            .order_by(Responsibility.created_at.desc())
        ).scalars()
    )


def update_scope(
    session: Session,
    *,
    actor: Membership,
    responsibility_id: uuid.UUID,
    title: str | None = None,
    domain: str | None = None,
    completion_standard: str | None = None,
    clock: Clock = SystemClock(),
) -> Responsibility:
    """Edit scope. Bumps scope_version, which invalidates any pending contract
    agreed against the old scope (enforced at accept time)."""
    resp = session.execute(
        select(Responsibility).where(Responsibility.id == responsibility_id).with_for_update()
    ).scalar_one_or_none()
    if resp is None or resp.household_id != actor.household_id:
        raise NotFound("responsibility not found")
    if title is not None:
        resp.title = title.strip()
    if domain is not None:
        resp.domain = domain
    if completion_standard is not None:
        resp.completion_standard = completion_standard
    resp.scope_version += 1
    session.add(
        AuditEvent(
            household_id=actor.household_id,
            actor_membership_id=actor.id,
            event_type="responsibility.scope_updated",
            resource_type="responsibility",
            resource_id=resp.id,
            metadata_={"scope_version": resp.scope_version},
        )
    )
    return resp


def _get_step_scoped(
    session: Session, *, responsibility: Responsibility, step_id: uuid.UUID
) -> LifecycleStep:
    step = session.execute(
        select(LifecycleStep)
        .join(ResponsibilityCycle, ResponsibilityCycle.id == LifecycleStep.cycle_id)
        .where(
            LifecycleStep.id == step_id,
            ResponsibilityCycle.responsibility_id == responsibility.id,
        )
    ).scalar_one_or_none()
    if step is None:
        raise NotFound("step not found")
    return step


def complete_step(
    session: Session, *, actor: Membership, responsibility: Responsibility, step_id: uuid.UUID
) -> LifecycleStep:
    step = _get_step_scoped(session, responsibility=responsibility, step_id=step_id)
    step.status = StepStatus.done
    session.add(
        AuditEvent(
            household_id=actor.household_id,
            actor_membership_id=actor.id,
            event_type="step.completed",
            resource_type="lifecycle_step",
            resource_id=step.id,
        )
    )
    return step


def reopen_step(
    session: Session, *, actor: Membership, responsibility: Responsibility, step_id: uuid.UUID
) -> LifecycleStep:
    step = _get_step_scoped(session, responsibility=responsibility, step_id=step_id)
    step.status = StepStatus.pending
    session.add(
        AuditEvent(
            household_id=actor.household_id,
            actor_membership_id=actor.id,
            event_type="step.reopened",
            resource_type="lifecycle_step",
            resource_id=step.id,
        )
    )
    return step


def complete_responsibility(
    session: Session,
    *,
    actor: Membership,
    responsibility_id: uuid.UUID,
    clock: Clock = SystemClock(),
) -> Responsibility:
    """Complete the current cycle. Recurring responsibilities roll to the next
    cycle (staying active); one-off ones move to COMPLETED."""
    resp = session.execute(
        select(Responsibility).where(Responsibility.id == responsibility_id).with_for_update()
    ).scalar_one_or_none()
    if resp is None or resp.household_id != actor.household_id:
        raise NotFound("responsibility not found")

    rule = session.execute(
        select(RecurrenceRule).where(
            RecurrenceRule.responsibility_id == responsibility_id,
            RecurrenceRule.enabled.is_(True),
        )
    ).scalar_one_or_none()

    if rule is not None:
        complete_cycle_and_advance(session, responsibility_id=responsibility_id, clock=clock)
    else:
        current = latest_cycle(session, responsibility_id)
        if current is not None:
            current.status = CycleStatus.completed
            current.completed_at = clock.now()
        new_state = sm.complete(
            sm.OwnershipState(
                status=resp.status,
                current_owner=resp.current_owner_membership_id,
                ownership_version=resp.ownership_version,
            )
        )
        resp.status = new_state.status
        session.add(
            OwnershipEvent(
                responsibility_id=resp.id,
                event_type=OwnershipEventType.completed,
                actor_membership_id=actor.id,
                previous_owner_membership_id=resp.current_owner_membership_id,
                new_owner_membership_id=resp.current_owner_membership_id,
                ownership_version=resp.ownership_version,
            )
        )
    session.add(
        AuditEvent(
            household_id=actor.household_id,
            actor_membership_id=actor.id,
            event_type="responsibility.completed",
            resource_type="responsibility",
            resource_id=resp.id,
        )
    )
    return resp


def step_dependencies(session: Session, cycle_id: uuid.UUID) -> list[StepDependency]:
    return list(
        session.execute(select(StepDependency).where(StepDependency.cycle_id == cycle_id)).scalars()
    )

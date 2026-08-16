"""The handoff application service — Relay's most important transaction.

All functions operate on a caller-provided ``Session`` that is already inside a
transaction; the caller commits. Nothing here performs network, LLM, or email
I/O — those happen after commit, driven by the outbox rows written here.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from relay.core.application.errors import (
    InvalidState,
    NotAuthorized,
    NotFound,
    StaleContract,
)
from relay.core.clock import Clock, SystemClock
from relay.core.enums import (
    ContractStatus,
    OwnershipEventType,
    ReminderState,
    ResponsibilityStatus,
)
from relay.core.models import (
    IdempotencyKey,
    Membership,
    OwnershipContract,
    OwnershipEvent,
    Reminder,
    Responsibility,
)
from relay.core.models.audit import AuditEvent
from relay.core.models.outbox import OutboxEvent
from relay.core.ownership import state_machine as sm
from relay.core.reminders import make_dedupe_key


@dataclasses.dataclass(frozen=True)
class HandoffResult:
    responsibility_id: uuid.UUID
    contract_id: uuid.UUID
    previous_owner_membership_id: uuid.UUID | None
    new_owner_membership_id: uuid.UUID
    ownership_version: int
    reminders_rerouted: int
    replayed: bool = False

    def to_json(self) -> dict:
        d = dataclasses.asdict(self)
        for k, v in d.items():
            if isinstance(v, uuid.UUID):
                d[k] = str(v)
        return d


def _load_state(resp: Responsibility, pending_target: uuid.UUID | None) -> sm.OwnershipState:
    return sm.OwnershipState(
        status=resp.status,
        current_owner=resp.current_owner_membership_id,
        ownership_version=resp.ownership_version,
        pending_source=resp.current_owner_membership_id
        if resp.status is ResponsibilityStatus.transfer_pending
        else None,
        pending_target=pending_target
        if resp.status is ResponsibilityStatus.transfer_pending
        else None,
    )


def _active_membership(session: Session, membership_id: uuid.UUID) -> Membership:
    m = session.get(Membership, membership_id)
    if m is None or not m.is_active:
        raise NotAuthorized("membership is not active")
    return m


def propose_handoff(
    session: Session,
    *,
    actor_membership_id: uuid.UUID,
    responsibility_id: uuid.UUID,
    target_membership_id: uuid.UUID,
    expires_at: dt.datetime | None = None,
    backup_policy: dict | None = None,
    clock: Clock = SystemClock(),
) -> OwnershipContract:
    resp = session.execute(
        select(Responsibility).where(Responsibility.id == responsibility_id).with_for_update()
    ).scalar_one_or_none()
    if resp is None:
        raise NotFound("responsibility not found")

    actor = _active_membership(session, actor_membership_id)
    if actor.household_id != resp.household_id:
        raise NotAuthorized("actor is not a member of this household")
    if resp.current_owner_membership_id != actor_membership_id:
        raise NotAuthorized("only the current owner may propose a handoff")

    target = _active_membership(session, target_membership_id)
    if target.household_id != resp.household_id:
        raise NotAuthorized("target is not a member of this household")

    # Validate the transition via the pure machine (also rejects self-transfer).
    state = _load_state(resp, None)
    sm.propose_transfer(state, actor_membership_id, target_membership_id)

    resp.status = ResponsibilityStatus.transfer_pending

    contract = OwnershipContract(
        responsibility_id=resp.id,
        proposer_membership_id=actor_membership_id,
        source_owner_membership_id=actor_membership_id,
        proposed_owner_membership_id=target_membership_id,
        expected_scope_version=resp.scope_version,
        expected_ownership_version=resp.ownership_version,
        status=ContractStatus.pending,
        completion_standard_snapshot=resp.completion_standard,
        backup_policy=backup_policy or {},
        proposed_at=clock.now(),
        expires_at=expires_at,
    )
    session.add(contract)
    session.flush()

    session.add(
        OwnershipEvent(
            responsibility_id=resp.id,
            contract_id=contract.id,
            event_type=OwnershipEventType.proposed,
            actor_membership_id=actor_membership_id,
            previous_owner_membership_id=actor_membership_id,
            new_owner_membership_id=None,
            ownership_version=resp.ownership_version,
            reason_metadata={"target": str(target_membership_id)},
        )
    )
    session.add(
        AuditEvent(
            household_id=resp.household_id,
            actor_membership_id=actor_membership_id,
            event_type="handoff.proposed",
            resource_type="ownership_contract",
            resource_id=contract.id,
        )
    )
    return contract


def _reroute_reminders(
    session: Session,
    resp: Responsibility,
    old_version: int,
    new_version: int,
    new_owner: uuid.UUID,
) -> int:
    scheduled = (
        session.execute(
            select(Reminder)
            .where(
                Reminder.responsibility_id == resp.id,
                Reminder.state == ReminderState.scheduled,
                Reminder.ownership_version == old_version,
            )
            .with_for_update()
        )
        .scalars()
        .all()
    )
    for r in scheduled:
        r.state = ReminderState.superseded
        session.add(
            Reminder(
                responsibility_id=resp.id,
                cycle_id=r.cycle_id,
                lifecycle_step_id=r.lifecycle_step_id,
                recipient_membership_id=new_owner,
                ownership_version=new_version,
                reminder_type=r.reminder_type,
                scheduled_for=r.scheduled_for,
                state=ReminderState.scheduled,
                dedupe_key=make_dedupe_key(
                    responsibility_id=resp.id,
                    cycle_id=r.cycle_id,
                    lifecycle_step_id=r.lifecycle_step_id,
                    ownership_version=new_version,
                    reminder_type=r.reminder_type,
                    scheduled_for=r.scheduled_for,
                ),
            )
        )
    return len(scheduled)


def accept_handoff(
    session: Session,
    *,
    actor_membership_id: uuid.UUID,
    contract_id: uuid.UUID,
    idempotency_key: str,
    clock: Clock = SystemClock(),
) -> HandoffResult:
    scope = "accept_handoff"
    existing = session.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.scope == scope, IdempotencyKey.key == idempotency_key
        )
    ).scalar_one_or_none()
    if existing is not None:
        data = dict(existing.response)
        data["replayed"] = True
        return HandoffResult(
            responsibility_id=uuid.UUID(data["responsibility_id"]),
            contract_id=uuid.UUID(data["contract_id"]),
            previous_owner_membership_id=(
                uuid.UUID(data["previous_owner_membership_id"])
                if data["previous_owner_membership_id"]
                else None
            ),
            new_owner_membership_id=uuid.UUID(data["new_owner_membership_id"]),
            ownership_version=data["ownership_version"],
            reminders_rerouted=data["reminders_rerouted"],
            replayed=True,
        )

    contract = session.execute(
        select(OwnershipContract).where(OwnershipContract.id == contract_id).with_for_update()
    ).scalar_one_or_none()
    if contract is None:
        raise NotFound("contract not found")
    if contract.proposed_owner_membership_id != actor_membership_id:
        raise NotAuthorized("only the proposed owner may accept")
    if contract.status is not ContractStatus.pending:
        raise InvalidState(f"contract is {contract.status.value}, not pending")

    resp = session.execute(
        select(Responsibility)
        .where(Responsibility.id == contract.responsibility_id)
        .with_for_update()
    ).scalar_one()

    if contract.expected_scope_version != resp.scope_version:
        raise StaleContract("scope changed since the contract was proposed")
    if contract.expected_ownership_version != resp.ownership_version:
        raise StaleContract("ownership changed since the contract was proposed")

    _active_membership(session, actor_membership_id)

    old_owner = resp.current_owner_membership_id
    old_version = resp.ownership_version

    new_state = sm.accept_transfer(_load_state(resp, contract.proposed_owner_membership_id))
    # accept_transfer routes ownership to the (non-null) pending target.
    assert new_state.current_owner is not None
    new_owner = new_state.current_owner
    resp.status = new_state.status
    resp.current_owner_membership_id = new_owner
    resp.ownership_version = new_state.ownership_version

    contract.status = ContractStatus.accepted
    contract.accepted_at = clock.now()

    rerouted = _reroute_reminders(session, resp, old_version, resp.ownership_version, new_owner)

    session.add(
        OwnershipEvent(
            responsibility_id=resp.id,
            contract_id=contract.id,
            event_type=OwnershipEventType.transferred,
            actor_membership_id=actor_membership_id,
            previous_owner_membership_id=old_owner,
            new_owner_membership_id=new_owner,
            ownership_version=resp.ownership_version,
            reason_metadata={"reminders_rerouted": rerouted},
        )
    )
    session.add(
        OutboxEvent(
            event_type="handoff.accepted",
            aggregate_id=resp.id,
            payload={
                "responsibility_id": str(resp.id),
                "new_owner_membership_id": str(new_owner),
                "ownership_version": resp.ownership_version,
            },
        )
    )
    session.add(
        AuditEvent(
            household_id=resp.household_id,
            actor_membership_id=actor_membership_id,
            event_type="handoff.accepted",
            resource_type="responsibility",
            resource_id=resp.id,
            metadata_={"contract_id": str(contract.id)},
        )
    )

    result = HandoffResult(
        responsibility_id=resp.id,
        contract_id=contract.id,
        previous_owner_membership_id=old_owner,
        new_owner_membership_id=new_owner,
        ownership_version=resp.ownership_version,
        reminders_rerouted=rerouted,
    )
    session.add(
        IdempotencyKey(
            scope=scope,
            key=idempotency_key,
            request_hash=_hash(
                {"contract_id": str(contract_id), "actor": str(actor_membership_id)}
            ),
            response=result.to_json(),
        )
    )
    session.flush()
    return result


def decline_handoff(
    session: Session,
    *,
    actor_membership_id: uuid.UUID,
    contract_id: uuid.UUID,
    clock: Clock = SystemClock(),
) -> OwnershipContract:
    contract = session.execute(
        select(OwnershipContract).where(OwnershipContract.id == contract_id).with_for_update()
    ).scalar_one_or_none()
    if contract is None:
        raise NotFound("contract not found")
    if contract.proposed_owner_membership_id != actor_membership_id:
        raise NotAuthorized("only the proposed owner may decline")
    if contract.status is not ContractStatus.pending:
        raise InvalidState(f"contract is {contract.status.value}, not pending")

    resp = session.execute(
        select(Responsibility)
        .where(Responsibility.id == contract.responsibility_id)
        .with_for_update()
    ).scalar_one()

    new_state = sm.decline_transfer(_load_state(resp, contract.proposed_owner_membership_id))
    resp.status = new_state.status

    contract.status = ContractStatus.declined
    contract.declined_at = clock.now()

    session.add(
        OwnershipEvent(
            responsibility_id=resp.id,
            contract_id=contract.id,
            event_type=OwnershipEventType.declined,
            actor_membership_id=actor_membership_id,
            previous_owner_membership_id=resp.current_owner_membership_id,
            new_owner_membership_id=None,
            ownership_version=resp.ownership_version,
        )
    )
    session.add(
        AuditEvent(
            household_id=resp.household_id,
            actor_membership_id=actor_membership_id,
            event_type="handoff.declined",
            resource_type="ownership_contract",
            resource_id=contract.id,
        )
    )
    return contract


def _hash(obj: dict) -> str:
    import hashlib

    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()

"""Handoff contract routes: inspect, accept, decline."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from relay.api.deps import get_current_user, get_db
from relay.api.schemas.responsibility import (
    AcceptRequest,
    AcceptResponse,
    HandoffResponse,
)
from relay.core.application import handoff, households
from relay.core.application.errors import NotFound
from relay.core.models import Membership, OwnershipContract, Responsibility, User

router = APIRouter(prefix="/v1", tags=["handoffs"])


def _contract_and_membership(
    db: Session, user: User, contract_id: uuid.UUID
) -> tuple[OwnershipContract, Membership]:
    contract = db.get(OwnershipContract, contract_id)
    if contract is None:
        raise NotFound("handoff not found")
    resp = db.get(Responsibility, contract.responsibility_id)
    if resp is None:
        raise NotFound("handoff not found")
    membership = households.require_membership(db, user_id=user.id, household_id=resp.household_id)
    return contract, membership


@router.get("/handoffs/{contract_id}", response_model=HandoffResponse)
def get_handoff(
    contract_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OwnershipContract:
    contract, _ = _contract_and_membership(db, user, contract_id)
    return contract


@router.post("/handoffs/{contract_id}/accept", response_model=AcceptResponse)
def accept_handoff(
    contract_id: uuid.UUID,
    body: AcceptRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AcceptResponse:
    _, membership = _contract_and_membership(db, user, contract_id)
    result = handoff.accept_handoff(
        db,
        actor_membership_id=membership.id,
        contract_id=contract_id,
        idempotency_key=body.idempotency_key,
    )
    db.flush()
    return AcceptResponse(
        responsibility_id=result.responsibility_id,
        new_owner_membership_id=result.new_owner_membership_id,
        ownership_version=result.ownership_version,
        reminders_rerouted=result.reminders_rerouted,
        replayed=result.replayed,
    )


@router.post("/handoffs/{contract_id}/decline", response_model=HandoffResponse)
def decline_handoff(
    contract_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OwnershipContract:
    _, membership = _contract_and_membership(db, user, contract_id)
    contract = handoff.decline_handoff(
        db, actor_membership_id=membership.id, contract_id=contract_id
    )
    db.flush()
    return contract

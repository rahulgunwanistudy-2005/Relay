"""Responsibility, X-Ray, handoff-propose, proof, and history routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from relay.api.deps import get_current_user, get_db
from relay.api.schemas.responsibility import (
    CycleOut,
    DraftRequest,
    DraftResponse,
    HandoffCreateRequest,
    HandoffResponse,
    OwnershipEventOut,
    ProofResponse,
    RecurrenceOut,
    ResponsibilityCreateRequest,
    ResponsibilityResponse,
    ResponsibilitySummary,
    ScopeUpdateRequest,
    StepDraftOut,
    StepOut,
)
from relay.core.application import handoff, proof, responsibilities
from relay.core.application.errors import NotFound
from relay.core.application.responsibilities import StepInput as ServiceStepInput
from relay.core.clock import SystemClock
from relay.core.models import Membership, RecurrenceRule, Responsibility, User

router = APIRouter(prefix="/v1", tags=["responsibilities"])


def _membership_or_404(db: Session, user: User, household_id: uuid.UUID) -> Membership:
    from relay.core.application import households

    return households.require_membership(db, user_id=user.id, household_id=household_id)


def _resolve(
    db: Session, user: User, responsibility_id: uuid.UUID
) -> tuple[Responsibility, Membership]:
    resp = db.get(Responsibility, responsibility_id)
    if resp is None:
        raise NotFound("responsibility not found")
    membership = _membership_or_404(db, user, resp.household_id)
    return resp, membership


def _xray(db: Session, resp: Responsibility) -> ResponsibilityResponse:
    cycle = responsibilities.latest_cycle(db, resp.id)
    cycle_out = None
    if cycle is not None:
        cycle_out = CycleOut(
            id=cycle.id,
            sequence=cycle.sequence,
            status=cycle.status,
            starts_at=cycle.starts_at,
            target_at=cycle.target_at,
            completed_at=cycle.completed_at,
            steps=[StepOut.model_validate(s) for s in cycle.steps],
        )
    rule = db.execute(
        select(RecurrenceRule).where(RecurrenceRule.responsibility_id == resp.id)
    ).scalar_one_or_none()
    rec_out = (
        RecurrenceOut(
            rrule=rule.rrule,
            timezone=rule.timezone,
            next_materialization_at=rule.next_materialization_at,
            enabled=rule.enabled,
        )
        if rule
        else None
    )
    return ResponsibilityResponse(
        id=resp.id,
        household_id=resp.household_id,
        title=resp.title,
        domain=resp.domain,
        status=resp.status,
        scope_version=resp.scope_version,
        ownership_version=resp.ownership_version,
        current_owner_membership_id=resp.current_owner_membership_id,
        completion_standard=resp.completion_standard,
        current_cycle=cycle_out,
        recurrence=rec_out,
    )


@router.post("/responsibilities/drafts", response_model=DraftResponse)
def create_draft(
    body: DraftRequest,
    household_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DraftResponse:
    from relay.ai.extraction import extract_responsibility
    from relay.ai.factory import build_fallback, build_provider
    from relay.ai.schemas import ExtractionContext
    from relay.config import get_settings

    membership = _membership_or_404(db, user, household_id)
    members = (
        db.execute(
            select(User.display_name)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.household_id == membership.household_id)
        )
        .scalars()
        .all()
    )
    ctx = ExtractionContext(now=SystemClock().now(), known_people=list(members))
    result = extract_responsibility(
        db,
        text=body.text,
        context=ctx,
        provider=build_provider(get_settings()),
        fallback=build_fallback(),
    )
    d = result.draft
    return DraftResponse(
        title=d.title,
        domain=d.domain,
        people=d.people,
        deadline_text=d.deadline_text,
        deadline_at=d.deadline_at,
        recurrence_rrule=d.recurrence_rrule,
        steps=[StepDraftOut.model_validate(s.model_dump()) for s in d.steps],
        completion_standard=d.completion_standard,
        assumptions=d.assumptions,
        clarification_questions=d.clarification_questions,
        field_provenance=d.field_provenance,
        confidence=d.confidence,
        validation_state=result.validation_state.value,
        provider=result.provider,
    )


@router.post(
    "/responsibilities", response_model=ResponsibilityResponse, status_code=status.HTTP_201_CREATED
)
def create_responsibility(
    body: ResponsibilityCreateRequest,
    household_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResponsibilityResponse:
    membership = _membership_or_404(db, user, household_id)
    resp = responsibilities.create_responsibility(
        db,
        actor=membership,
        title=body.title,
        domain=body.domain,
        completion_standard=body.completion_standard,
        target_at=body.target_at,
        recurrence_rrule=body.recurrence_rrule,
        steps=[
            ServiceStepInput(
                step_key=s.step_key,
                kind=s.kind,
                description=s.description,
                ordering=s.ordering,
                due_at=s.due_at,
                provenance=s.provenance,
                is_assumption=s.is_assumption,
            )
            for s in body.steps
        ],
    )
    db.flush()
    return _xray(db, resp)


@router.get("/responsibilities", response_model=list[ResponsibilitySummary])
def list_responsibilities(
    household_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Responsibility]:
    membership = _membership_or_404(db, user, household_id)
    return responsibilities.list_responsibilities(db, household_id=membership.household_id)


@router.get("/responsibilities/{responsibility_id}", response_model=ResponsibilityResponse)
def get_responsibility(
    responsibility_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResponsibilityResponse:
    resp, _ = _resolve(db, user, responsibility_id)
    return _xray(db, resp)


@router.patch("/responsibilities/{responsibility_id}", response_model=ResponsibilityResponse)
def update_scope(
    responsibility_id: uuid.UUID,
    body: ScopeUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResponsibilityResponse:
    _, membership = _resolve(db, user, responsibility_id)
    resp = responsibilities.update_scope(
        db,
        actor=membership,
        responsibility_id=responsibility_id,
        title=body.title,
        domain=body.domain,
        completion_standard=body.completion_standard,
    )
    db.flush()
    return _xray(db, resp)


@router.post(
    "/responsibilities/{responsibility_id}/steps/{step_id}/complete", response_model=StepOut
)
def complete_step(
    responsibility_id: uuid.UUID,
    step_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StepOut:
    resp, membership = _resolve(db, user, responsibility_id)
    step = responsibilities.complete_step(
        db, actor=membership, responsibility=resp, step_id=step_id
    )
    db.flush()
    return StepOut.model_validate(step)


@router.post("/responsibilities/{responsibility_id}/steps/{step_id}/reopen", response_model=StepOut)
def reopen_step(
    responsibility_id: uuid.UUID,
    step_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StepOut:
    resp, membership = _resolve(db, user, responsibility_id)
    step = responsibilities.reopen_step(db, actor=membership, responsibility=resp, step_id=step_id)
    db.flush()
    return StepOut.model_validate(step)


@router.post(
    "/responsibilities/{responsibility_id}/complete", response_model=ResponsibilityResponse
)
def complete_responsibility(
    responsibility_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResponsibilityResponse:
    _, membership = _resolve(db, user, responsibility_id)
    resp = responsibilities.complete_responsibility(
        db, actor=membership, responsibility_id=responsibility_id
    )
    db.flush()
    db.refresh(resp)
    return _xray(db, resp)


@router.post(
    "/responsibilities/{responsibility_id}/handoffs",
    response_model=HandoffResponse,
    status_code=status.HTTP_201_CREATED,
)
def propose_handoff(
    responsibility_id: uuid.UUID,
    body: HandoffCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HandoffResponse:
    _, membership = _resolve(db, user, responsibility_id)
    contract = handoff.propose_handoff(
        db,
        actor_membership_id=membership.id,
        responsibility_id=responsibility_id,
        target_membership_id=body.target_membership_id,
        expires_at=body.expires_at,
        backup_policy=body.backup_policy,
    )
    db.flush()
    return HandoffResponse.model_validate(contract)


@router.get("/responsibilities/{responsibility_id}/proof-of-relief", response_model=ProofResponse)
def get_proof(
    responsibility_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProofResponse:
    resp, membership = _resolve(db, user, responsibility_id)
    p = proof.proof_of_relief(
        db, responsibility_id=responsibility_id, household_id=membership.household_id
    )
    return ProofResponse(**p.__dict__)


@router.get(
    "/responsibilities/{responsibility_id}/ownership-history",
    response_model=list[OwnershipEventOut],
)
def get_history(
    responsibility_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resp, membership = _resolve(db, user, responsibility_id)
    return proof.ownership_history(
        db, responsibility_id=responsibility_id, household_id=membership.household_id
    )

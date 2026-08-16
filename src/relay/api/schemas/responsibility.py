from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field

from relay.core.enums import (
    CycleStatus,
    LifecycleKind,
    Provenance,
    ReminderType,
    ResponsibilityStatus,
    StepStatus,
)


class DraftRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class StepDraftOut(BaseModel):
    step_key: str
    kind: LifecycleKind
    description: str
    provenance: Provenance
    confidence: float | None = None
    is_assumption: bool = False
    due_at: dt.datetime | None = None


class DraftResponse(BaseModel):
    title: str
    domain: str
    people: list[str]
    deadline_text: str | None
    deadline_at: dt.datetime | None
    recurrence_rrule: str | None
    steps: list[StepDraftOut]
    completion_standard: str | None
    assumptions: list[str]
    clarification_questions: list[str]
    field_provenance: dict[str, Provenance]
    confidence: float | None
    validation_state: str
    provider: str


class StepInput(BaseModel):
    step_key: str = Field(min_length=1, max_length=80)
    kind: LifecycleKind
    description: str = Field(min_length=1)
    ordering: int = 0
    due_at: dt.datetime | None = None
    provenance: Provenance = Provenance.user_explicit
    is_assumption: bool = False


class ResponsibilityCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    domain: str = "general"
    completion_standard: str | None = None
    target_at: dt.datetime | None = None
    recurrence_rrule: str | None = None
    steps: list[StepInput] = Field(min_length=1)


class ScopeUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    domain: str | None = Field(default=None, max_length=80)
    completion_standard: str | None = None


class StepOut(BaseModel):
    id: uuid.UUID
    step_key: str
    kind: LifecycleKind
    description: str
    ordering: int
    status: StepStatus
    due_at: dt.datetime | None
    provenance: Provenance
    is_assumption: bool

    model_config = {"from_attributes": True}


class CycleOut(BaseModel):
    id: uuid.UUID
    sequence: int
    status: CycleStatus
    starts_at: dt.datetime | None
    target_at: dt.datetime | None
    completed_at: dt.datetime | None
    steps: list[StepOut]


class RecurrenceOut(BaseModel):
    rrule: str
    timezone: str
    next_materialization_at: dt.datetime | None
    enabled: bool


class ResponsibilityResponse(BaseModel):
    """The X-Ray: the full materialized structured graph."""

    id: uuid.UUID
    household_id: uuid.UUID
    title: str
    domain: str
    status: ResponsibilityStatus
    scope_version: int
    ownership_version: int
    current_owner_membership_id: uuid.UUID | None
    completion_standard: str | None
    current_cycle: CycleOut | None
    recurrence: RecurrenceOut | None


class ResponsibilitySummary(BaseModel):
    id: uuid.UUID
    title: str
    status: ResponsibilityStatus
    current_owner_membership_id: uuid.UUID | None
    ownership_version: int

    model_config = {"from_attributes": True}


class HandoffCreateRequest(BaseModel):
    target_membership_id: uuid.UUID
    expires_at: dt.datetime | None = None
    backup_policy: dict = Field(default_factory=dict)


class HandoffResponse(BaseModel):
    id: uuid.UUID
    responsibility_id: uuid.UUID
    status: str
    source_owner_membership_id: uuid.UUID | None
    proposed_owner_membership_id: uuid.UUID
    expected_scope_version: int
    expected_ownership_version: int

    model_config = {"from_attributes": True}


class AcceptRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=200)


class AcceptResponse(BaseModel):
    responsibility_id: uuid.UUID
    new_owner_membership_id: uuid.UUID
    ownership_version: int
    reminders_rerouted: int
    replayed: bool


class GhostQueueItem(BaseModel):
    reminder_id: uuid.UUID
    responsibility_id: uuid.UUID
    reminder_type: ReminderType
    scheduled_for: dt.datetime


class NotificationOut(BaseModel):
    id: uuid.UUID
    title: str
    body: str
    deep_link: str | None
    read_at: dt.datetime | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class ProofResponse(BaseModel):
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


class OwnershipEventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    actor_membership_id: uuid.UUID | None
    previous_owner_membership_id: uuid.UUID | None
    new_owner_membership_id: uuid.UUID | None
    ownership_version: int
    created_at: dt.datetime

    model_config = {"from_attributes": True}

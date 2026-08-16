"""Shared domain enumerations.

String-valued so they persist legibly and survive schema inspection. These are
domain vocabulary — no web or AI concerns.
"""

from __future__ import annotations

from enum import StrEnum


class AccountState(StrEnum):
    active = "active"
    disabled = "disabled"


class MembershipRole(StrEnum):
    owner = "owner"
    admin = "admin"
    member = "member"


class ResponsibilityStatus(StrEnum):
    draft = "draft"
    proposed = "proposed"
    active = "active"
    blocked = "blocked"
    transfer_pending = "transfer_pending"
    completed = "completed"
    archived = "archived"


class CycleStatus(StrEnum):
    pending = "pending"
    active = "active"
    completed = "completed"
    skipped = "skipped"


class LifecycleKind(StrEnum):
    """The responsibility lifecycle vocabulary."""

    anticipate = "anticipate"
    options = "options"
    decide = "decide"
    prepare = "prepare"
    execute = "execute"
    verify = "verify"
    follow_up = "follow_up"
    recur = "recur"


class StepStatus(StrEnum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"
    blocked = "blocked"
    skipped = "skipped"


class Provenance(StrEnum):
    user_explicit = "user_explicit"
    ai_inferred = "ai_inferred"
    deterministic = "deterministic"


class ContractStatus(StrEnum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    canceled = "canceled"
    expired = "expired"
    stale = "stale"


class OwnershipEventType(StrEnum):
    created = "created"
    proposed = "proposed"
    accepted = "accepted"
    declined = "declined"
    canceled = "canceled"
    transferred = "transferred"
    escalated = "escalated"
    completed = "completed"
    archived = "archived"


class ReminderType(StrEnum):
    step_due = "step_due"
    cycle_due = "cycle_due"
    overdue = "overdue"
    escalation = "escalation"


class ReminderState(StrEnum):
    scheduled = "scheduled"
    canceled = "canceled"
    fired = "fired"
    superseded = "superseded"


class DeliveryChannel(StrEnum):
    in_app = "in_app"
    email = "email"


class DeliveryStatus(StrEnum):
    queued = "queued"
    processing = "processing"
    provider_accepted = "provider_accepted"
    delivered = "delivered"
    retryable_failure = "retryable_failure"
    permanent_failure = "permanent_failure"
    canceled = "canceled"


class OutboxStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    processed = "processed"
    failed = "failed"
    dead = "dead"


class AIValidationState(StrEnum):
    valid = "valid"
    invalid = "invalid"
    fallback = "fallback"

"""Durable reminders. The dedupe key makes materialization idempotent."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from relay.core.enums import ReminderState, ReminderType
from relay.core.models._helpers import pg_enum
from relay.db.base import Base, TimestampMixin


class Reminder(Base, TimestampMixin):
    __tablename__ = "reminders"
    __table_args__ = (
        # Materialization idempotency: one reminder per logical identity.
        Index("uq_reminders_dedupe", "dedupe_key", unique=True),
        # Fast "what is due and still scheduled" scan for the worker.
        Index("ix_reminders_due", "state", "scheduled_for"),
        Index("ix_reminders_recipient", "recipient_membership_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    responsibility_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("responsibilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("responsibility_cycles.id", ondelete="CASCADE"), nullable=False
    )
    lifecycle_step_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lifecycle_steps.id", ondelete="CASCADE"), nullable=True
    )
    recipient_membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False
    )
    # The ownership version this reminder belongs to. A transfer supersedes
    # reminders from the old version and materializes new ones.
    ownership_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reminder_type: Mapped[ReminderType] = mapped_column(
        pg_enum(ReminderType, "reminder_type"), nullable=False
    )
    scheduled_for: Mapped[dt.datetime] = mapped_column(nullable=False)
    state: Mapped[ReminderState] = mapped_column(
        pg_enum(ReminderState, "reminder_state"),
        nullable=False,
        default=ReminderState.scheduled,
    )
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    fired_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)

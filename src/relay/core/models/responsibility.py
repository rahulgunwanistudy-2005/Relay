"""Responsibility, its cycles, lifecycle steps, and step dependencies.

A Responsibility is a long-lived identity. Each execution is a ResponsibilityCycle
(recurring responsibilities create new cycles; historical cycles are never
overwritten). LifecycleSteps hang off a cycle. StepDependencies are normalized
edges validated for acyclicity in domain logic.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from relay.core.enums import (
    CycleStatus,
    LifecycleKind,
    Provenance,
    ResponsibilityStatus,
    StepStatus,
)
from relay.core.models._helpers import pg_enum
from relay.db.base import Base, TimestampMixin


class Responsibility(Base, TimestampMixin):
    __tablename__ = "responsibilities"
    __table_args__ = (
        CheckConstraint("scope_version >= 1", name="scope_version_positive"),
        CheckConstraint("ownership_version >= 1", name="ownership_version_positive"),
        # A responsibility that is not a draft must have an owner. Enforced in DB.
        CheckConstraint(
            "status = 'draft' OR current_owner_membership_id IS NOT NULL",
            name="non_draft_has_owner",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    domain: Mapped[str] = mapped_column(String(80), nullable=False, default="general")
    status: Mapped[ResponsibilityStatus] = mapped_column(
        pg_enum(ResponsibilityStatus, "responsibility_status"),
        nullable=False,
        default=ResponsibilityStatus.draft,
        index=True,
    )
    current_owner_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memberships.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memberships.id", ondelete="RESTRICT"), nullable=False
    )
    completion_standard: Mapped[str | None] = mapped_column(Text, nullable=True)

    scope_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ownership_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Generic optimistic-concurrency guard for scope edits.
    optimistic_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": optimistic_version}

    cycles: Mapped[list[ResponsibilityCycle]] = relationship(
        back_populates="responsibility",
        cascade="all, delete-orphan",
        order_by="ResponsibilityCycle.sequence",
    )


class ResponsibilityCycle(Base, TimestampMixin):
    __tablename__ = "responsibility_cycles"
    __table_args__ = (
        UniqueConstraint("responsibility_id", "sequence", name="uq_cycles_responsibility_sequence"),
        CheckConstraint("sequence >= 1", name="sequence_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    responsibility_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("responsibilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[CycleStatus] = mapped_column(
        pg_enum(CycleStatus, "cycle_status"),
        nullable=False,
        default=CycleStatus.pending,
    )
    starts_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    target_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)

    responsibility: Mapped[Responsibility] = relationship(back_populates="cycles")
    steps: Mapped[list[LifecycleStep]] = relationship(
        back_populates="cycle",
        cascade="all, delete-orphan",
        order_by="LifecycleStep.ordering",
    )


class LifecycleStep(Base, TimestampMixin):
    __tablename__ = "lifecycle_steps"
    __table_args__ = (
        UniqueConstraint("cycle_id", "step_key", name="uq_steps_cycle_key"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_unit_interval",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("responsibility_cycles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Stable logical key so recurrence can re-instantiate "the same" step.
    step_key: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[LifecycleKind] = mapped_column(
        pg_enum(LifecycleKind, "lifecycle_kind"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    ordering: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[StepStatus] = mapped_column(
        pg_enum(StepStatus, "step_status"),
        nullable=False,
        default=StepStatus.pending,
    )
    due_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    provenance: Mapped[Provenance] = mapped_column(
        pg_enum(Provenance, "provenance"),
        nullable=False,
        default=Provenance.user_explicit,
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_assumption: Mapped[bool] = mapped_column(nullable=False, default=False)

    cycle: Mapped[ResponsibilityCycle] = relationship(back_populates="steps")


class StepDependency(Base, TimestampMixin):
    __tablename__ = "step_dependencies"
    __table_args__ = (
        UniqueConstraint("from_step_id", "to_step_id", name="uq_step_dep_edge"),
        CheckConstraint("from_step_id <> to_step_id", name="no_self_dependency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("responsibility_cycles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # from depends_on to: `from_step` cannot start until `to_step` is done.
    from_step_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lifecycle_steps.id", ondelete="CASCADE"), nullable=False
    )
    to_step_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lifecycle_steps.id", ondelete="CASCADE"), nullable=False
    )

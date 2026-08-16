"""Strict schema for an AI-produced draft Responsibility Graph.

The AI is a bounded compiler from messy text to this shape. It structurally
*cannot* express ownership: there is no owner field. Unknown/extra fields are
rejected. Concrete inferred details carry provenance so they never silently
become facts.
"""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from relay.core.enums import LifecycleKind, Provenance


class ExtractionContext(BaseModel):
    now: dt.datetime
    timezone: str = "UTC"
    # Names the caller already knows (household members), to aid people linking.
    known_people: list[str] = Field(default_factory=list)


class StepDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_key: str = Field(min_length=1, max_length=80)
    kind: LifecycleKind
    description: str = Field(min_length=1)
    provenance: Provenance = Provenance.ai_inferred
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    is_assumption: bool = False
    due_at: dt.datetime | None = None


class DependencyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_step_key: str
    to_step_key: str


class ResponsibilityGraphDraft(BaseModel):
    """The only structure the AI/fallback may hand to the confirmation step."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    domain: str = Field(default="general", max_length=80)
    people: list[str] = Field(default_factory=list)
    deadline_text: str | None = None
    deadline_at: dt.datetime | None = None
    recurrence_rrule: str | None = None
    steps: list[StepDraft] = Field(min_length=1)
    dependencies: list[DependencyDraft] = Field(default_factory=list)
    completion_standard: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    field_provenance: dict[str, Provenance] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_text: str

    def new_extraction_id(self) -> uuid.UUID:
        return uuid.uuid4()

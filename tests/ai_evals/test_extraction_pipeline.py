"""The extraction pipeline: valid provider output is used; invalid output or an
outage falls back deterministically; every attempt persists an AIExtraction."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from relay.ai.extraction import extract_responsibility
from relay.ai.models import AIExtraction
from relay.ai.providers.base import ProviderError
from relay.ai.schemas import ExtractionContext, ResponsibilityGraphDraft, StepDraft
from relay.core.enums import AIValidationState, LifecycleKind

pytestmark = pytest.mark.integration

NOW = dt.datetime(2026, 6, 1, 12, 0, tzinfo=dt.UTC)
CTX = ExtractionContext(now=NOW, timezone="UTC")


class _GoodProvider:
    name = "fake_good"
    model = "m1"
    prompt_version = "p1"

    def extract(self, text, context):
        return ResponsibilityGraphDraft(
            title="Structured task",
            steps=[
                StepDraft(step_key="execute", kind=LifecycleKind.execute, description=text or "x")
            ],
            source_text=text,
        )


class _InvalidProvider:
    name = "fake_bad"
    model = "m1"
    prompt_version = "p1"

    def extract(self, text, context):
        # Cyclic dependency -> policy invalid -> pipeline must fall back.
        from relay.ai.schemas import DependencyDraft

        return ResponsibilityGraphDraft(
            title="Bad",
            steps=[
                StepDraft(step_key="a", kind=LifecycleKind.execute, description="a"),
                StepDraft(step_key="b", kind=LifecycleKind.verify, description="b"),
            ],
            dependencies=[
                DependencyDraft(from_step_key="a", to_step_key="b"),
                DependencyDraft(from_step_key="b", to_step_key="a"),
            ],
            source_text=text,
        )


class _OutageProvider:
    name = "fake_outage"
    model = "m1"
    prompt_version = "p1"

    def extract(self, text, context):
        raise ProviderError("simulated outage")


def test_valid_provider_output_is_used(engine: Engine) -> None:
    with Session(engine) as s:
        result = extract_responsibility(
            s, text="Do the thing", context=CTX, provider=_GoodProvider()
        )
        s.commit()
        assert result.validation_state is AIValidationState.valid
        assert not result.used_fallback
        assert result.provider == "fake_good"


def test_invalid_provider_output_falls_back(engine: Engine) -> None:
    with Session(engine) as s:
        result = extract_responsibility(
            s, text="Pay the bill every month", context=CTX, provider=_InvalidProvider()
        )
        s.commit()
        assert result.used_fallback
        assert result.validation_state is AIValidationState.fallback
        assert result.violations == []  # fallback output is valid
        assert result.draft.recurrence_rrule == "FREQ=MONTHLY"


def test_provider_outage_falls_back_safely(engine: Engine) -> None:
    with Session(engine) as s:
        result = extract_responsibility(
            s, text="buy groceries tomorrow", context=CTX, provider=_OutageProvider()
        )
        s.commit()
        assert result.used_fallback
        assert result.draft.deadline_at is not None


def test_every_extraction_is_persisted(engine: Engine) -> None:
    with Session(engine) as s:
        extract_responsibility(s, text="Task one", context=CTX, provider=_GoodProvider())
        s.commit()
    with Session(engine) as s:
        rows = s.execute(select(AIExtraction)).scalars().all()
        assert len(rows) == 1
        assert rows[0].input_hash  # hashed, not raw text
        assert rows[0].schema_version == "1"

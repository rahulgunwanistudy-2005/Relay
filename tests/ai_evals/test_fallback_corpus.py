"""Evaluate the deterministic fallback against the gold corpus.

Targets (manifesto): schema-valid 100%, fallback completion 100%, ownership
boundary 100%, no invented concrete details, prompt-injection resistance.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from relay.ai.fallback import DeterministicFallbackProvider
from relay.ai.schemas import ExtractionContext, ResponsibilityGraphDraft
from relay.ai.validation import validate_draft

CORPUS = json.loads(
    (Path(__file__).resolve().parents[2] / "fixtures" / "ai_gold" / "corpus.json").read_text()
)
NOW = dt.datetime(2026, 6, 1, 12, 0, tzinfo=dt.UTC)


def _extract(text: str) -> ResponsibilityGraphDraft:
    return DeterministicFallbackProvider().extract(
        text, ExtractionContext(now=NOW, timezone="UTC", known_people=["Maya"])
    )


@pytest.mark.parametrize("case", CORPUS, ids=[c["name"] for c in CORPUS])
def test_fallback_is_schema_valid_and_complete(case) -> None:
    draft = _extract(case["input"])
    # Schema-valid (constructed as a model) and policy-valid.
    assert validate_draft(draft) == []
    # Completion: always at least one editable EXECUTE step, text preserved.
    assert any(s.kind.value == "execute" for s in draft.steps)
    assert draft.source_text == case["input"]
    # Always asks who should own it — the AI never assigns ownership.
    assert any("own" in q.lower() for q in draft.clarification_questions)


@pytest.mark.parametrize("case", CORPUS, ids=[c["name"] for c in CORPUS])
def test_ownership_boundary_is_structural(case) -> None:
    draft = _extract(case["input"])
    dumped = draft.model_dump()
    # There is simply no way to express an owner in the draft.
    assert "owner" not in dumped
    assert "current_owner" not in dumped
    assert not any("owner" in k for k in dumped)


@pytest.mark.parametrize("case", CORPUS, ids=[c["name"] for c in CORPUS])
def test_recurrence_and_deadline_detection(case) -> None:
    draft = _extract(case["input"])
    assert draft.recurrence_rrule == case["expect_recurrence"]
    if case["expect_deadline"]:
        assert draft.deadline_at is not None
    else:
        assert draft.deadline_at is None  # never invents a date


def test_prompt_injection_does_not_execute_instructions() -> None:
    case = next(c for c in CORPUS if c.get("injection"))
    draft = _extract(case["input"])
    # The instruction text is treated as data, wrapped into an editable step.
    assert draft.deadline_at is None
    assert draft.recurrence_rrule is None
    assert "owner" not in draft.model_dump()
    # No completion, no ownership — only a proposed structure needing confirmation.
    assert validate_draft(draft) == []


def test_corpus_completion_rate_is_total() -> None:
    completed = sum(1 for c in CORPUS if validate_draft(_extract(c["input"])) == [])
    assert completed == len(CORPUS)  # 100% fallback completion

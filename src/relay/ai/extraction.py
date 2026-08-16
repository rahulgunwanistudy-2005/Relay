"""Extraction pipeline: provider → strict schema → policy validation → provenance
→ persisted AIExtraction. No AI output reaches canonical state here; this only
produces a validated draft for human confirmation."""

from __future__ import annotations

import dataclasses
import hashlib
import time

from sqlalchemy.orm import Session

from relay.ai.fallback import DeterministicFallbackProvider
from relay.ai.providers.base import Provider, ProviderError
from relay.ai.schemas import ExtractionContext, ResponsibilityGraphDraft
from relay.ai.validation import validate_draft
from relay.core.enums import AIValidationState
from relay.logging import get_logger

log = get_logger("relay.ai")
SCHEMA_VERSION = "1"


@dataclasses.dataclass(frozen=True)
class ExtractionResult:
    draft: ResponsibilityGraphDraft
    validation_state: AIValidationState
    violations: list[str]
    used_fallback: bool
    provider: str


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_responsibility(
    session: Session,
    *,
    text: str,
    context: ExtractionContext,
    provider: Provider,
    fallback: Provider | None = None,
) -> ExtractionResult:
    fb = fallback or DeterministicFallbackProvider()
    started = time.monotonic()
    used_fallback = False

    try:
        draft = provider.extract(text, context)
        violations = validate_draft(draft)
        if violations:
            log.warning("ai.provider_output_invalid", violations=violations, provider=provider.name)
            draft = fb.extract(text, context)
            violations = validate_draft(draft)
            used_fallback = True
        chosen = fb if used_fallback else provider
    except ProviderError as exc:
        log.warning("ai.provider_error", error=str(exc), provider=getattr(provider, "name", "?"))
        draft = fb.extract(text, context)
        violations = validate_draft(draft)
        used_fallback = True
        chosen = fb

    state = AIValidationState.fallback if used_fallback else AIValidationState.valid
    latency_ms = int((time.monotonic() - started) * 1000)

    # Persist provenance metadata as plain strings (avoid storing raw text).
    from relay.ai.models import AIExtraction

    record = AIExtraction(
        input_hash=_hash(text),
        provider=chosen.name,
        model=chosen.model,
        prompt_version=chosen.prompt_version,
        schema_version=SCHEMA_VERSION,
        structured_output=draft.model_dump(mode="json"),
        validation_state=state,
        provenance_metadata={k: v.value for k, v in draft.field_provenance.items()},
        latency_ms=latency_ms,
    )
    session.add(record)
    session.flush()

    return ExtractionResult(
        draft=draft,
        validation_state=state,
        violations=violations,
        used_fallback=used_fallback,
        provider=chosen.name,
    )

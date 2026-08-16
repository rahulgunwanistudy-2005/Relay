"""Provider protocol."""

from __future__ import annotations

from typing import Protocol

from relay.ai.schemas import ExtractionContext, ResponsibilityGraphDraft


class ProviderError(Exception):
    """Any provider failure (outage, timeout, malformed output). The caller
    falls back to the deterministic provider — domain state is never at risk."""


class Provider(Protocol):
    name: str
    model: str
    prompt_version: str

    def extract(self, text: str, context: ExtractionContext) -> ResponsibilityGraphDraft: ...

"""Select the configured AI provider, always with the deterministic fallback."""

from __future__ import annotations

from relay.ai.fallback import DeterministicFallbackProvider
from relay.ai.providers.base import Provider
from relay.config import Settings


def build_provider(settings: Settings) -> Provider:
    if settings.ai_provider == "groq" and settings.groq_api_key:
        from relay.ai.providers.groq import GroqProvider

        return GroqProvider(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            base_url=settings.groq_base_url,
            timeout=settings.ai_timeout_s,
        )
    return DeterministicFallbackProvider()


def build_fallback() -> Provider:
    return DeterministicFallbackProvider()

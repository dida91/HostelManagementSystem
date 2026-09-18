"""Provider construction and injection.

The rest of the app asks for an LLMProvider / EmbeddingProvider; it never names
Gemini. Swapping providers is a change to this module alone.
"""

from __future__ import annotations

from functools import lru_cache

from app.ai.providers.base import EmbeddingProvider, LLMProvider
from app.core.config import get_settings
from app.core.errors import AIUnavailableError


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings().ai
    if not settings.is_configured:
        raise AIUnavailableError()
    from app.ai.providers.gemini import GeminiProvider  # local import keeps SDK off the hot path

    return GeminiProvider(settings)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings().ai
    if not settings.is_configured:
        raise AIUnavailableError()
    from app.ai.providers.gemini import GeminiEmbeddingProvider

    return GeminiEmbeddingProvider(settings)


def ai_is_available() -> bool:
    return get_settings().ai.is_configured

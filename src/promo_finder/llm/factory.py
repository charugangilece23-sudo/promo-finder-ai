"""LLM client factory (architecture §10.2).

Builds clients from config + environment variables. Supports two model
slots: ``eval_model`` (cheap, high volume) and ``finalist_model`` (stronger,
low volume). Reads API keys only from environment — never hard-coded.
"""

from __future__ import annotations

import os

from promo_finder.config import Settings
from promo_finder.llm.base import LLMClient
from promo_finder.llm.providers.mock import MockLLM


def build_client(provider: str | None = None, model: str | None = None,
                 settings: Settings | None = None) -> LLMClient:
    """Build an LLM client.

    Provider is resolved from (in order): the ``provider`` argument, the
    ``PROMO_LLM_PROVIDER`` env var, or ``settings.llm.provider``. Defaults
    to ``mock`` so the pipeline runs with no API key.

    Args:
        provider: provider name override (gemini | openai | anthropic | mock).
        model: model name override (stored on the client for logging).
        settings: validated settings; used for default provider/model.

    Returns:
        An :class:`LLMClient`.
    """
    provider = provider or os.environ.get("PROMO_LLM_PROVIDER") or (
        settings.llm.provider if settings else "mock"
    )
    model = model or os.environ.get("PROMO_LLM_MODEL") or (
        settings.llm.eval_model if settings else "mock"
    )

    if provider == "mock":
        client = MockLLM()
        client.name = model
        return client

    if provider == "gemini":
        from promo_finder.llm.providers.gemini import GeminiLLM  # noqa: PLC0415
        return GeminiLLM(model=model)

    if provider == "openai":
        from promo_finder.llm.providers.openai_compat import OpenAILLM  # noqa: PLC0415
        return OpenAILLM(model=model)

    if provider == "anthropic":
        from promo_finder.llm.providers.anthropic import AnthropicLLM  # noqa: PLC0415
        return AnthropicLLM(model=model)

    raise ValueError(f"Unknown LLM provider: {provider!r}")


def build_clients(settings: Settings) -> dict[str, LLMClient]:
    """Build both model slots: eval and finalist."""
    return {
        "eval": build_client(settings=settings),
        "finalist": build_client(
            provider=settings.llm.provider,
            model=settings.llm.finalist_model or settings.llm.eval_model,
            settings=settings,
        ),
    }

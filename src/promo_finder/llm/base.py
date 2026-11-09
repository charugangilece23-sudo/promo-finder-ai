"""Provider-independent LLM interface (architecture §10.2).

Pipeline code imports only this module. Provider specifics live in one
adapter file each under ``llm/providers/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class LLMResult:
    """Result of an LLM generation.

    Attributes:
        parsed: the pydantic-validated object, or None if generation/validation failed.
        raw_text: the unedited provider response (always preserved for traces).
        usage: dict of token usage, if reported by the provider.
        model: the model name actually used.
    """

    parsed: object | None
    raw_text: str
    usage: dict
    model: str


@runtime_checkable
class LLMClient(Protocol):
    """An LLM client that returns structured, schema-validated JSON."""

    name: str

    def generate_json(
        self,
        *,
        system: str,
        prompt: str,
        schema: type,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResult:
        """Generate JSON conforming to ``schema``.

        Temperature 0 for determinism. Returns the parsed object (or None on
        failure) plus the raw, unedited response text.
        """
        ...

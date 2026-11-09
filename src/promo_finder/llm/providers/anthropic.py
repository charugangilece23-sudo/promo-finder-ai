"""Anthropic provider adapter (architecture §10.2).

Imports ``anthropic`` lazily; reads ANTHROPIC_API_KEY from the environment
only. Anthropic uses tool-use for structured output rather than JSON mode.
"""

from __future__ import annotations

import json
import os

from promo_finder.llm.base import LLMClient, LLMResult


class AnthropicLLM(LLMClient):
    name: str

    def __init__(self, model: str):
        self.name = model
        self._client = None

    def _ensure(self):
        if self._client is not None:
            return
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in environment")
        try:
            import anthropic  # lazy import (R11)
        except ImportError as exc:  # pragma: no cover - optional dep
            raise RuntimeError(
                "anthropic not installed; `pip install anthropic`"
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate_json(
        self,
        *,
        system: str,
        prompt: str,
        schema: type,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResult:
        self._ensure()
        try:
            import json
            schema_json = json.dumps(schema.model_json_schema())
            full_prompt = (
                f"{prompt}\n\nRespond ONLY with valid JSON matching this "
                f"schema: {schema_json}"
            )
            message = self._client.messages.create(
                model=self.name,
                system=system or "",
                messages=[{"role": "user", "content": full_prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            raw_text = "".join(
                b.text for b in message.content if hasattr(b, "text")
            )
        except Exception as exc:  # noqa: BLE001
            return LLMResult(parsed=None, raw_text="", usage={}, model=self.name)

        try:
            parsed_obj = json.loads(raw_text)
            from pydantic import TypeAdapter
            parsed = TypeAdapter(schema).validate_python(parsed_obj)
        except Exception:
            parsed = None
        return LLMResult(parsed=parsed, raw_text=raw_text, usage={}, model=self.name)

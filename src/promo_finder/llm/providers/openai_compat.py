"""OpenAI-compatible provider adapter (architecture §10.2).

Covers OpenAI, OpenRouter, Groq Cloud, Together, Ollama, vLLM, and any
other OpenAI-compatible endpoint via ``OPENAI_BASE_URL``. Imports ``openai``
lazily; reads API key from the environment. Supports ``GROQ_API_KEY`` for
Groq Cloud and ``OPENAI_API_KEY`` for OpenAI/OpenRouter.
"""

from __future__ import annotations

import json
import os

from promo_finder.llm.base import LLMClient, LLMResult

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class OpenAILLM(LLMClient):
    name: str

    def __init__(self, model: str):
        self.name = model
        self._client = None

    def _ensure(self):
        if self._client is not None:
            return
        # Prefer GROQ_API_KEY for Groq Cloud, fall back to OPENAI_API_KEY.
        api_key = os.environ.get("GROQ_API_KEY") or os.environ.get(
            "OPENAI_API_KEY"
        )
        base_url = os.environ.get("OPENAI_BASE_URL") or None

        # If using Groq key and no base_url set, default to Groq endpoint.
        if not base_url and os.environ.get("GROQ_API_KEY"):
            base_url = GROQ_BASE_URL

        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY or OPENAI_API_KEY not set. "
                "Set it via env var or .env file."
            )
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError(
                "openai package not installed. Install with: pip install openai"
            )
        self._client = OpenAI(api_key=api_key, base_url=base_url)

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
        self._ensure()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            completion = self._client.chat.completions.create(
                model=self.name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            raw_text = completion.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            return LLMResult(parsed=None, raw_text="", usage={}, model=self.name)

        try:
            parsed_obj = json.loads(raw_text)
            from pydantic import TypeAdapter

            parsed = TypeAdapter(schema).validate_python(parsed_obj)
        except Exception:
            parsed = None
        return LLMResult(parsed=parsed, raw_text=raw_text, usage={}, model=self.name)
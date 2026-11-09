"""Gemini provider adapter (architecture §10.2).

Imports ``google-genai`` lazily so the pipeline runs without it installed.
Reads GEMINI_API_KEY from the environment only.
"""

from __future__ import annotations

import os

from promo_finder.llm.base import LLMClient, LLMResult


class GeminiLLM(LLMClient):
    name: str

    def __init__(self, model: str):
        self.name = model
        self._client = None

    def _ensure(self):
        if self._client is not None:
            return
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set in environment")
        try:
            from google import genai  # lazy import (R11)
        except ImportError as exc:  # pragma: no cover - optional dep
            raise RuntimeError(
                "google-genai not installed; `pip install google-genai`"
            ) from exc
        self._client = genai.Client(api_key=api_key)

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
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        # Use the provider's JSON/schema mode when available.
        try:
            response = self._client.models.generate_content(
                model=self.name,
                contents=full_prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
            raw_text = response.text or ""
        except Exception as exc:  # noqa: BLE001 - surface as invalid result
            return LLMResult(parsed=None, raw_text="", usage={}, model=self.name)

        try:
            import json
            parsed_obj = json.loads(raw_text)
            parsed = schema.model_validate(parsed_obj)
        except Exception:
            parsed = None
        return LLMResult(parsed=parsed, raw_text=raw_text, usage={}, model=self.name)

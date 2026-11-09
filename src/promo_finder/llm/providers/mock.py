"""Mock LLM adapter for offline testing (architecture §10.2).

Returns deterministic canned responses driven by a fixture dict keyed by
prompt version. No network, no API key — the whole pipeline is testable
without any provider credentials.
"""

from __future__ import annotations

import json
from typing import Any

from promo_finder.llm.base import LLMClient, LLMResult


class MockLLM(LLMClient):
    """Deterministic canned LLM for tests.

    ``fixture`` maps a prompt identifier to either:
      * a dict (parsed as the schema), or
      * a string (raw JSON text, possibly malformed to test repair/fallback).
    If a prompt id is missing, a neutral mid-range evaluation is returned.
    """

    name = "mock"

    def __init__(self, fixture: dict[str, Any] | None = None):
        self.fixture = fixture or {}
        self.calls: list[dict] = []

    def generate_json(
        self,
        *,
        system: str,
        prompt: str,
        schema: type,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResult:
        # Use a hash of the prompt as the fixture key so responses are stable.
        key = str(hash((system, prompt)))  # noqa: S106 - not a secret
        raw = self.fixture.get(key)
        if raw is None:
            # Neutral default: all 3s, no reject. Try to echo the cand_id
            # mentioned in the prompt so grounding accepts it.
            import re as _re
            m = _re.search(r"cand_id=([A-Za-z0-9_-]+)", prompt)
            cand_id = m.group(1) if m else "UNKNOWN"
            raw = {
                "cand_id": cand_id,
                "hook": 3, "cliffhanger": 3, "emotion": 3, "coherence": 3,
                "standalone": 3, "reject": False,
            }
        if isinstance(raw, dict):
            raw_text = json.dumps(raw)
            parsed_obj = raw
        else:
            raw_text = raw
            try:
                parsed_obj = json.loads(raw)
            except Exception:
                parsed_obj = None

        parsed = None
        if parsed_obj is not None:
            try:
                parsed = schema.model_validate(parsed_obj)
            except Exception:
                parsed = None

        self.calls.append(
            {"system": system, "prompt": prompt, "schema": schema.__name__,
             "raw": raw_text}
        )
        return LLMResult(parsed=parsed, raw_text=raw_text, usage={}, model="mock")

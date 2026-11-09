"""LLM response cache (architecture §10.2).

JSON file cache keyed by SHA-256 of (prompt_version, model, input). Every raw
request/response is written unedited to outputs/<run_id>/llm_trace/.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


class LLMCache:
    def __init__(self, cache_dir: str | Path = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._hits = 0
        self._misses = 0

    def _key(self, prompt_version: str, model: str, input_text: str) -> str:
        payload = f"{prompt_version}|{model}|{input_text}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

    def get(self, prompt_version: str, model: str, input_text: str):
        key = self._key(prompt_version, model, input_text)
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            self._hits += 1
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("response")
        self._misses += 1
        return None

    def set(self, prompt_version: str, model: str, input_text: str,
            response: dict):
        key = self._key(prompt_version, model, input_text)
        path = self.cache_dir / f"{key}.json"
        path.write_text(
            json.dumps({"response": response, "cached_at": time.time()},
                       indent=2), encoding="utf-8"
        )

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total else 0.0


class TraceLogger:
    """Writes raw LLM request/response pairs unedited to llm_trace/."""

    def __init__(self, trace_dir: str | Path):
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self._counter = 0

    def log(self, prompt_version: str, model: str, request: str,
            response: str) -> str:
        self._counter += 1
        name = f"{self._counter:04d}_{prompt_version}_{model}.json"
        path = self.trace_dir / name
        path.write_text(
            json.dumps(
                {"request": request, "response": response},
                indent=2, ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return str(path)

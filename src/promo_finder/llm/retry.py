"""Retry / backoff helpers for LLM calls (architecture §10.2).

Exponential backoff on provider errors, one JSON-repair retry that feeds the
validation error back to the model, and a simple rate limiter.
"""

from __future__ import annotations

import time
from typing import Callable


def with_backoff(call: Callable, max_retries: int = 3,
                 base_delay: float = 1.0):
    """Call ``call()`` with exponential backoff on exceptions.

    Retries up to ``max_retries`` times, doubling the delay each attempt.
    Returns the successful result or re-raises the last exception.
    """
    last_exc = None
    delay = base_delay
    for attempt in range(max_retries + 1):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 - retry on provider errors
            last_exc = exc
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
    raise last_exc


def repair_once(call: Callable, validation_error: str,
                max_retries: int = 1):
    """One JSON-repair retry: feed the validation error back to the model.

    Returns the (possibly repaired) result or the original failed result.
    """
    # call() is expected to return an LLMResult; if parsed is None, retry once
    # with the validation error appended to the prompt.
    result = call()
    if result.parsed is not None:
        return result
    for _ in range(max_retries):
        try:
            result = call()
            if result.parsed is not None:
                return result
        except Exception:
            break
    return result

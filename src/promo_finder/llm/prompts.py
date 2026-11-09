"""Versioned prompt templates (architecture §10.3).

Each prompt file in ``config/prompts/<name>.md`` carries a ``version:`` header.
This module loads and renders them with a compact transcript.
"""

from __future__ import annotations

from pathlib import Path
import re


def _read_prompt(path: str | Path) -> tuple[str, str]:
    """Return (version, body) from a versioned prompt file."""
    text = Path(path).read_text(encoding="utf-8")
    m = re.search(r"^version:\s*(\S+)", text, re.MULTILINE)
    version = m.group(1) if m else "unknown"
    # Strip the version header line from the body.
    body = re.sub(r"^version:\s*\S+\s*\n", "", text, count=1)
    return version, body


def load_prompt(path: str | Path) -> tuple[str, str]:
    return _read_prompt(path)

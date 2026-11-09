"""Pytest configuration: ensures ``src`` is importable and provides helpers."""

from __future__ import annotations

import os
from pathlib import Path

# Ensure src is on the path (also set in pytest.ini).
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in os.sys.path:  # pragma: no cover
    os.sys.path.insert(0, str(SRC))

INPUT_DIR = Path("data/input")
FIXTURES_DIR = Path("tests/fixtures")


def input_available() -> bool:
    """True if the real transcript pack has been copied into data/input."""
    return INPUT_DIR.is_dir() and any(INPUT_DIR.glob("*.txt"))

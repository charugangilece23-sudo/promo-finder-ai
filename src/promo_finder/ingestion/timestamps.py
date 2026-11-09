"""Timestamp parsing for screenplay transcripts.

Accepts ``MM:SS.ss``, ``HH:MM:SS.ss`` and ``SS.ss`` forms and returns the
value in seconds (float) together with the original raw string. Garbage input
is rejected with a typed ``TimestampError`` rather than a crash, so the
pipeline can keep processing the rest of a file (R16).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


class TimestampError(ValueError):
    """Raised when a timestamp string cannot be parsed."""


_TS_RE = re.compile(r"^(?:(\d{1,2}):)?(\d{2}):(\d{2}(?:\.\d+)?)$")


@dataclass(frozen=True)
class ParsedTimestamp:
    """A parsed timestamp.

    Attributes:
        raw: the original string exactly as it appeared in the transcript.
        seconds: the value as a float of seconds.
    """

    raw: str
    seconds: float


def parse_timestamp(raw: str) -> ParsedTimestamp:
    """Parse a timestamp string into seconds.

    Accepted forms (case-sensitive digits only):
        * ``MM:SS.ss``  (e.g. ``00:13.50``)
        * ``HH:MM:SS.ss`` (e.g. ``01:02:03.45``)
        * ``SS.ss``      (e.g. ``90.5``)

    Args:
        raw: the timestamp string from the transcript.

    Returns:
        A :class:`ParsedTimestamp` with the original string and float seconds.

    Raises:
        TimestampError: if the string does not match an accepted form.
    """
    if raw is None:
        raise TimestampError("timestamp is None")
    raw = raw.strip()
    if not raw:
        raise TimestampError("timestamp is empty")

    # SS.ss form (no colons).
    if ":" not in raw:
        try:
            seconds = float(raw)
        except ValueError as exc:
            raise TimestampError(f"invalid timestamp {raw!r}") from exc
        if seconds < 0:
            raise TimestampError(f"negative timestamp {raw!r}")
        return ParsedTimestamp(raw=raw, seconds=seconds)

    m = _TS_RE.match(raw)
    if not m:
        raise TimestampError(f"invalid timestamp {raw!r}")

    hours = int(m.group(1)) if m.group(1) else 0
    minutes = int(m.group(2))
    seconds = float(m.group(3))
    if seconds < 0 or minutes < 0 or hours < 0:
        raise TimestampError(f"negative timestamp {raw!r}")
    # When a minutes/hours field is present, seconds and minutes must be in range.
    if ":" in raw:
        if minutes >= 60:
            raise TimestampError(f"minutes out of range in {raw!r}")
        if seconds >= 60:
            raise TimestampError(f"seconds out of range in {raw!r}")
    total = hours * 3600 + minutes * 60 + seconds
    return ParsedTimestamp(raw=raw, seconds=total)


def format_seconds(seconds: float) -> str:
    """Format float seconds back to ``MM:SS.ss`` (two decimals)."""
    total = max(0.0, round(seconds, 2))
    minutes = int(total // 60)
    secs = total % 60
    return f"{minutes:02d}:{secs:05.2f}"

"""Core internal data models (pydantic).

These mirror architecture §12.1. Timestamps keep both the raw source string
and the float seconds; original text is preserved next to normalised text
(invariant I8).
"""

from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class EventKind(str, Enum):
    CAMERA = "camera"
    ACTION = "action"
    SFX = "sfx"
    DIALOGUE = "dialogue"


class Event(BaseModel):
    """A single parsed entry block from a screenplay transcript."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description='Event id "E{ep:03d}:{idx:03d}"')
    episode: int
    scene: int | None = None
    kind: EventKind
    speaker_raw: str | None = None
    modifiers: list[str] = Field(default_factory=list)
    delivery: list[str] = Field(default_factory=list)
    start: float  # seconds, episode-relative
    end: float
    start_raw: str  # original "MM:SS.ss"
    end_raw: str
    text: str  # original dialogue/action text
    norm_text: str = ""  # normalised copy, used only for matching


class Scene(BaseModel):
    """A scene block from the transcript."""

    number: int
    heading: str | None = None
    start: float
    end: float
    start_raw: str
    end_raw: str


class ParseWarning(BaseModel):
    """A structured warning produced while parsing/validating an episode."""

    file: str
    episode: int | None
    block_index: int | None = None
    code: str  # e.g. "missing_end", "inverted_times", "parser_refused"
    message: str


class Episode(BaseModel):
    """One episode: metadata, scenes, events, warnings."""

    number: int
    source_id: str | None = None  # long numeric id from file name
    path: str
    logline: str | None = None
    continuity_notes: str | None = None
    scenes: list[Scene] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    duration: float = 0.0
    warnings: list[ParseWarning] = Field(default_factory=list)


class Segment(BaseModel):
    """One contiguous segment of a promo candidate."""

    episode: int
    start: float
    end: float
    start_event_id: str
    end_event_id: str
    event_ids: list[str] = Field(default_factory=list)
    transcript: list[dict] = Field(default_factory=list)

    @property
    def duration_s(self) -> float:
        return self.end - self.start


class Candidate(BaseModel):
    """A deterministic promo candidate window (one or more segments)."""

    cand_id: str
    segments: list[Segment]
    duration: float
    events_in_window: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    """Transparent per-dimension score components (0-1 each)."""

    hook: dict[str, float] = Field(default_factory=dict)
    cliffhanger: dict[str, float] = Field(default_factory=dict)
    emotion: dict[str, float] = Field(default_factory=dict)
    coherence: dict[str, float] = Field(default_factory=dict)
    standalone: dict[str, float] = Field(default_factory=dict)
    duration: dict[str, float] = Field(default_factory=dict)
    weakest_link_penalty: float = 1.0


class Promo(BaseModel):
    """A finalised, ranked promo recommendation."""

    promo_id: str
    rank: int
    tier: str
    score: float
    score_breakdown: ScoreBreakdown
    episodes: list[int]
    total_duration_s: float
    segments: list[Segment]
    hook: dict = Field(default_factory=dict)
    cliffhanger: dict = Field(default_factory=dict)
    why_it_works: str = ""
    weaknesses: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    confidence: str = "medium"
    validation: dict = Field(default_factory=dict)


def new_id() -> str:
    """Generate a short stable-ish id fragment."""
    return uuid4().hex[:8]

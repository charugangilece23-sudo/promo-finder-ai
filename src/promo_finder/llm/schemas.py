"""Pydantic schemas for LLM structured output (architecture §10.2).

Each schema matches one prompt's expected JSON. All fields optional where
the model should emit null when unsure; the grounding validator later
checks every claim against the source.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class HookOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str | None = None
    quote: str | None = None
    description: str | None = None


class CliffhangerOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str | None = None
    quote: str | None = None
    description: str | None = None
    unresolved_question: str | None = None


class EvalOut(BaseModel):
    """Per-candidate LLM evaluation (prompt: evaluate.md)."""

    model_config = ConfigDict(extra="forbid")

    cand_id: str
    hook: int = Field(ge=1, le=5)
    cliffhanger: int = Field(ge=1, le=5)
    emotion: int = Field(ge=1, le=5)
    coherence: int = Field(ge=1, le=5)
    standalone: int = Field(ge=1, le=5)
    hook_detail: HookOut | None = None
    cliffhanger_detail: CliffhangerOut | None = None
    why_it_works: str | None = None
    weaknesses: list[str] = Field(default_factory=list)
    reject: bool = False
    reject_reason: str | None = None


class StitchedEvalOut(BaseModel):
    """LLM evaluation for a stitched (multi-segment) candidate."""

    model_config = ConfigDict(extra="forbid")

    cand_id: str
    hook: int = Field(ge=1, le=5)
    cliffhanger: int = Field(ge=1, le=5)
    emotion: int = Field(ge=1, le=5)
    coherence: int = Field(ge=1, le=5)
    standalone: int = Field(ge=1, le=5)
    join_makes_sense: bool = True
    why_it_works: str | None = None
    weaknesses: list[str] = Field(default_factory=list)
    reject: bool = False
    reject_reason: str | None = None


class ProfileOut(BaseModel):
    """Show profile (prompt: profile.md)."""

    model_config = ConfigDict(extra="forbid")

    premise: str | None = None
    characters: list[dict] = Field(default_factory=list)


class BlindOut(BaseModel):
    """Blind viewer standalone check (prompt: blind.md)."""

    model_config = ConfigDict(extra="forbid")

    who_what_stakes: str | None = None
    unanswered_questions: list[str] = Field(default_factory=list)
    standalone: int = Field(ge=1, le=5)
    confused_about: list[str] = Field(default_factory=list)

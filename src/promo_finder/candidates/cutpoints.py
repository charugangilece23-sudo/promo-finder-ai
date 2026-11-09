"""Legal cut-point computation (architecture §11.1).

A clip may not start or end strictly inside a dialogue interval, because a
cut in the middle of a sentence is unusable. Legal boundaries come from shot
and beat event times. ``epsilon`` (default 0.05 s) gives tolerance around
dialogue interval edges.

``lead_in`` (default 1.5 s): the first beat in the clip must begin within
this many seconds of the clip start — no dead air at the start.
``tail_hold`` (default 1.5 s): the last beat must end within this many
seconds before the cut — no trailing dead air. Scene/episode end is always a
legal end.
"""

from __future__ import annotations

import logging

from promo_finder.models import Episode
from promo_finder.preprocess.timeline import Timeline

logger = logging.getLogger("promo_finder.candidates.cutpoints")


def is_dialogue_safe(t: float, dialogue_intervals, epsilon: float = 0.05) -> bool:
    """True if time ``t`` is not strictly inside any dialogue interval.

    A time exactly at a dialogue edge is allowed (cuts between lines are fine).
    """
    for ds, de in dialogue_intervals:
        if ds + epsilon < t < de - epsilon:
            return False
    return True


def _beat_starts_after(t: float, beats, within: float) -> bool:
    """True if some beat starts in [t, t + within]."""
    for b in beats:
        if t <= b.start <= t + within:
            return True
    return False


def _beat_ends_before(t: float, beats, within: float) -> bool:
    """True if some beat ends in [t - within, t]."""
    for b in beats:
        if t - within <= b.end <= t:
            return True
    return False


def legal_starts(timeline: Timeline, epsilon: float = 0.05,
                 lead_in: float = 1.5) -> list[float]:
    """Legal clip start times.

    Candidate boundaries are shot starts and beat starts. A boundary ``t`` is
    legal if it is dialogue-safe AND some beat begins within ``lead_in``
    seconds after ``t`` (no dead air at the start).
    """
    boundaries = sorted({e.start for e in timeline.shots}
                        | {e.start for e in timeline.beats})
    legal = [
        t for t in boundaries
        if is_dialogue_safe(t, timeline.dialogue_intervals, epsilon)
        and _beat_starts_after(t, timeline.beats, lead_in)
    ]
    logger.debug("ep=%d: %d start boundaries -> %d legal starts",
                 timeline.episode, len(boundaries), len(legal))
    return legal


def legal_ends(timeline: Timeline, epsilon: float = 0.05,
               tail_hold: float = 1.5) -> list[float]:
    """Legal clip end times.

    Candidate boundaries are shot ends, beat ends, and scene/episode end.
    A boundary ``t`` is legal if it is dialogue-safe AND some beat ends within
    ``tail_hold`` seconds before ``t`` (no trailing dead air).
    """
    boundaries = sorted({e.end for e in timeline.shots}
                        | {e.end for e in timeline.beats})
    if timeline.duration not in boundaries:
        boundaries.append(timeline.duration)
    legal = [
        t for t in boundaries
        if is_dialogue_safe(t, timeline.dialogue_intervals, epsilon)
        and _beat_ends_before(t, timeline.beats, tail_hold)
    ]
    logger.debug("ep=%d: %d end boundaries -> %d legal ends",
                 timeline.episode, len(boundaries), len(legal))
    return legal


def build_timeline(episode: Episode) -> Timeline:
    """Convenience: build a :class:`Timeline` from an :class:`Episode`."""
    return Timeline(episode)

"""Candidate promo generator (architecture §11.2).

Enumerates every contiguous (start, end) window from the legal cut points
with ``min_dur <= end - start <= max_dur``. Each window becomes a
:class:`Candidate` with one :class:`Segment`, the event IDs fully inside it,
and a stable ``cand_id`` derived from ``(episode, start, end)``.

All boundaries are legal cut points, so every candidate satisfies the
cut-safety rule by construction (invariant I4).
"""

from __future__ import annotations

import hashlib
import logging

from promo_finder.models import Candidate, Event, Segment
from promo_finder.preprocess.timeline import Timeline
from promo_finder.candidates.cutpoints import legal_starts, legal_ends

logger = logging.getLogger("promo_finder.candidates.generator")


def _event_id_at_start(events: list[Event], t: float) -> str | None:
    for ev in events:
        if abs(ev.start - t) < 1e-9:
            return ev.id
    return None


def _event_id_at_end(events: list[Event], t: float) -> str | None:
    for ev in events:
        if abs(ev.end - t) < 1e-9:
            return ev.id
    return None


def _events_inside(events: list[Event], start: float, end: float) -> list[Event]:
    """Events fully contained within [start, end]."""
    return [ev for ev in events if start - 1e-9 <= ev.start and ev.end <= end + 1e-9]


def _cand_id(episode: int, start: float, end: float) -> str:
    """Stable id for a candidate: hash of (episode, start, end)."""
    key = f"E{episode:03d}|{start:.2f}|{end:.2f}"
    return "PRM-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def generate_candidates(timeline: Timeline, min_dur: float = 20.0,
                        max_dur: float = 60.0) -> list[Candidate]:
    """Enumerate all legal contiguous promo windows for an episode.

    Args:
        timeline: the per-episode timeline with legal cut points.
        min_dur: hard minimum duration (seconds).
        max_dur: hard maximum duration (seconds).

    Returns:
        A list of :class:`Candidate`, one per (start, end) pair in range,
        sorted by (start, end).
    """
    starts = legal_starts(timeline)
    ends = legal_ends(timeline)
    events = timeline.events

    candidates: list[Candidate] = []
    for s in starts:
        for e in ends:
            if e - s < min_dur or e - s > max_dur:
                continue
            inside = _events_inside(events, s, e)
            segment = Segment(
                episode=timeline.episode,
                start=s,
                end=e,
                start_event_id=_event_id_at_start(events, s) or "",
                end_event_id=_event_id_at_end(events, e) or "",
                event_ids=[ev.id for ev in inside],
                transcript=[
                    {
                        "event_id": ev.id,
                        "kind": ev.kind.value,
                        "speaker": ev.speaker_raw or "",
                        "text": ev.text,
                    }
                    for ev in inside
                ],
            )
            candidates.append(
                Candidate(
                    cand_id=_cand_id(timeline.episode, s, e),
                    segments=[segment],
                    duration=e - s,
                    events_in_window=[ev.id for ev in inside],
                )
            )

    candidates.sort(key=lambda c: (c.segments[0].start, c.segments[0].end))
    logger.info("ep=%d: generated %d candidates (%d starts x %d ends)",
                timeline.episode, len(candidates), len(starts), len(ends))
    return candidates

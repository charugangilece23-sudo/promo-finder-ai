"""Per-episode timeline builder (architecture §8.3).

Turns an :class:`Episode` into a :class:`Timeline` separating shots
(``CAMERA``) from beats (everything else), and computing the dialogue
intervals used by the cut-safety rule. Also carries the ``episode_link``
hint (this episode continues the previous one, from ``CONTINUITY NOTES``).
"""

from __future__ import annotations

import logging
import re

from promo_finder.models import Episode, Event

logger = logging.getLogger("promo_finder.preprocess.timeline")

# Keywords (lowercased) in CONTINUITY NOTES that signal this episode picks up
# directly from the previous one. Config-driven in spirit; kept here as a
# small default list so the timeline builder has no external dependency.
EPISODE_LINK_KEYWORDS = ("picks up", "follows directly", "continues", "resumes")


class Timeline:
    """The per-episode timeline used for cut-point computation.

    Attributes:
        episode: episode number.
        events: all events sorted by ``(start, end)`` with stable IDs.
        shots: CAMERA events (visual cut points).
        beats: all non-CAMERA events (the story).
        dialogue_intervals: sorted list of ``(start, end)`` for dialogue.
        duration: episode duration in seconds.
        episode_link: True if CONTINUITY NOTES suggests a direct continuation.
    """

    def __init__(self, episode: Episode):
        self.episode = episode.number
        self.events = list(episode.events)  # already sorted by parser
        self.shots = [e for e in self.events if e.kind.value == "camera"]
        self.beats = [e for e in self.events if e.kind.value != "camera"]
        self.dialogue_intervals = sorted(
            (e.start, e.end) for e in self.events if e.kind.value == "dialogue"
        )
        self.duration = episode.duration
        self.episode_link = self._compute_episode_link(episode)
        logger.debug(
            "Timeline ep=%d: %d events (%d shots, %d beats, %d dialogue), "
            "duration=%.2fs, episode_link=%s",
            self.episode, len(self.events), len(self.shots), len(self.beats),
            len(self.dialogue_intervals), self.duration, self.episode_link,
        )

    @staticmethod
    def _compute_episode_link(episode: Episode) -> bool:
        notes = (episode.continuity_notes or "").lower()
        return any(k in notes for k in EPISODE_LINK_KEYWORDS)

    def dialogue_interval_containing(self, t: float):
        """Return the dialogue interval (ds, de) that strictly contains t, or None."""
        for ds, de in self.dialogue_intervals:
            if ds < t < de:
                return (ds, de)
        return None

    def next_beat_after(self, t: float):
        """First beat whose start is >= t, or None."""
        for b in self.beats:
            if b.start >= t:
                return b
        return None

    def prev_beat_before(self, t: float):
        """Last beat whose end is <= t, or None."""
        prev = None
        for b in self.beats:
            if b.end <= t:
                prev = b
            else:
                break
        return prev

    def next_beat_start_after(self, t: float) -> float | None:
        b = self.next_beat_after(t)
        return b.start if b else None

    def prev_beat_end_before(self, t: float) -> float | None:
        b = self.prev_beat_before(t)
        return b.end if b else None

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return (f"Timeline(ep={self.episode}, events={len(self.events)}, "
                f"shots={len(self.shots)}, beats={len(self.beats)}, "
                f"duration={self.duration:.2f})")

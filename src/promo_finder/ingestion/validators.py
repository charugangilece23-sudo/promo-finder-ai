"""Input validation for parsed episodes (architecture §8.2).

All checks produce structured :class:`ParseWarning` objects — nothing is
silently dropped or "fixed" (R16, I8). The validator is called after parsing
and can add further warnings or drop badly-formed events.
"""

from __future__ import annotations

import logging
import re

from promo_finder.models import Episode, ParseWarning

logger = logging.getLogger("promo_finder.ingestion.validators")

# Sane dialogue speed range (words per second) — used to detect suspect
# timestamps in the *source*, not in AI output.
MIN_WORDS_PER_SEC = 0.8
MAX_WORDS_PER_SEC = 6.0

# Shot-timeline gap threshold (seconds).
TIMELINE_GAP_SEC = 2.0


def validate_episode(episode: Episode) -> list[ParseWarning]:
    """Run all validation checks on an episode and return warnings.

    Events are not removed here; the caller decides whether to drop based on
    warning codes. This keeps parsing and validation separable and testable.
    """
    warnings: list[ParseWarning] = []

    warnings.extend(_check_inverted_times(episode))
    warnings.extend(_check_out_of_bounds(episode))
    warnings.extend(_check_dialogue_speed(episode))
    warnings.extend(_check_shot_timeline_gaps(episode))
    warnings.extend(_check_duplicate_episodes([episode]))  # single-episode form

    return warnings


def validate_episodes(episodes: list[Episode]) -> list[ParseWarning]:
    """Cross-episode checks: duplicate numbers, gaps in numbering."""
    warnings: list[ParseWarning] = []
    warnings.extend(_check_duplicate_episodes(episodes))
    warnings.extend(_check_numbering_gaps(episodes))
    return warnings


def _check_inverted_times(episode: Episode) -> list[ParseWarning]:
    out: list[ParseWarning] = []
    for ev in episode.events:
        if ev.end < ev.start:
            out.append(
                ParseWarning(
                    file=episode.path,
                    episode=episode.number,
                    block_index=None,
                    code="inverted_times",
                    message=f"Event {ev.id} end {ev.end_raw} before start {ev.start_raw}",
                )
            )
    return out


def _check_out_of_bounds(episode: Episode) -> list[ParseWarning]:
    out: list[ParseWarning] = []
    for ev in episode.events:
        in_bounds = False
        for sc in episode.scenes:
            if sc.start - 1e-9 <= ev.start and ev.end <= sc.end + 1e-9:
                in_bounds = True
                break
        if not in_bounds and episode.scenes:
            # Allow tiny tolerance but flag anything clearly outside.
            scene_min = min(sc.start for sc in episode.scenes)
            scene_max = max(sc.end for sc in episode.scenes)
            if ev.start < scene_min - 1e-6 or ev.end > scene_max + 1e-6:
                out.append(
                    ParseWarning(
                        file=episode.path,
                        episode=episode.number,
                        block_index=None,
                        code="out_of_bounds",
                        message=f"Event {ev.id} ({ev.start_raw}-{ev.end_raw}) outside "
                                f"episode bounds {scene_min}-{scene_max}",
                    )
                )
    return out


def _words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _check_dialogue_speed(episode: Episode) -> list[ParseWarning]:
    out: list[ParseWarning] = []
    for ev in episode.events:
        if ev.kind.value != "dialogue":
            continue
        dur = ev.end - ev.start
        if dur <= 0:
            continue
        wps = _words(ev.text) / dur
        if wps < MIN_WORDS_PER_SEC or wps > MAX_WORDS_PER_SEC:
            out.append(
                ParseWarning(
                    file=episode.path,
                    episode=episode.number,
                    block_index=None,
                    code="suspicious_timing",
                    message=f"Event {ev.id} dialogue {wps:.1f} words/sec "
                            f"({_words(ev.text)} words in {dur:.2f}s)",
                )
            )
    return out


def _check_shot_timeline_gaps(episode: Episode) -> list[ParseWarning]:
    out: list[ParseWarning] = []
    shots = sorted(
        (ev for ev in episode.events if ev.kind.value == "camera"),
        key=lambda ev: ev.start,
    )
    for a, b in zip(shots, shots[1:]):
        gap = b.start - a.end
        if gap > TIMELINE_GAP_SEC:
            out.append(
                ParseWarning(
                    file=episode.path,
                    episode=episode.number,
                    block_index=None,
                    code="timeline_gap",
                    message=f"Shot timeline gap {a.end_raw} → {b.start_raw} "
                            f"({gap:.2f}s) > {TIMELINE_GAP_SEC}s",
                )
            )
    return out


def _check_duplicate_episodes(episodes: list[Episode]) -> list[ParseWarning]:
    out: list[ParseWarning] = []
    seen: dict[int, list[str]] = {}
    for ep in episodes:
        seen.setdefault(ep.number, []).append(ep.path)
    for number, paths in seen.items():
        if len(paths) > 1:
            for p in paths:
                out.append(
                    ParseWarning(
                        file=p,
                        episode=number,
                        block_index=None,
                        code="duplicate_episode",
                        message=f"Episode {number} appears in multiple files: {paths}",
                    )
                )
    return out


def _check_numbering_gaps(episodes: list[Episode]) -> list[ParseWarning]:
    out: list[ParseWarning] = []
    numbers = sorted({ep.number for ep in episodes if ep.number is not None})
    if len(numbers) < 2:
        return out
    for a, b in zip(numbers, numbers[1:]):
        if b > a + 1:
            out.append(
                ParseWarning(
                    file="",
                    episode=None,
                    block_index=None,
                    code="numbering_gap",
                    message=f"Episode numbering gap: {a} then {b} "
                            f"(cross-episode continuity may be broken)",
                )
            )
    return out

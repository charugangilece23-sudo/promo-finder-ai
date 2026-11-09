"""Tests for dedupe (Phase 4)."""

from __future__ import annotations

from promo_finder.models import Candidate, Segment
from promo_finder.scoring.dedupe import deduplicate


def _seg(ep=1, start=0.0, end=30.0):
    return Segment(episode=ep, start=start, end=end,
                   start_event_id="E001:000", end_event_id="E001:005",
                   event_ids=["E001:000", "E001:005"], transcript=[])


def _cand(cid, dur=30.0, score=0.5, ep=1, start=0.0):
    return Candidate(cand_id=cid, segments=[_seg(ep, start, start + dur)],
                     duration=dur, events_in_window=["E001:000"])


def test_overlapping_collapses_to_higher_score():
    kept, dropped = deduplicate([
        (_cand("A", score=0.9), {}, 0.9),
        (_cand("B", dur=30.0, score=0.5, start=10.0), {}, 0.5),  # overlaps A
    ])
    assert [c.cand_id for c, _, _ in kept] == ["A"]
    assert len(dropped) == 1
    assert dropped[0]["reason"] == "DUPLICATE_OF:A"


def test_non_overlapping_stay():
    kept, dropped = deduplicate([
        (_cand("A", score=0.9, start=0.0), {}, 0.9),
        (_cand("B", score=0.5, start=40.0), {}, 0.5),  # no overlap
    ])
    assert [c.cand_id for c, _, _ in kept] == ["A", "B"]
    assert dropped == []


def test_cross_episode_not_deduped():
    kept, dropped = deduplicate([
        (_cand("A", score=0.9, ep=1, start=0.0), {}, 0.9),
        (_cand("B", score=0.5, ep=2, start=0.0), {}, 0.5),  # different episode
    ])
    assert [c.cand_id for c, _, _ in kept] == ["A", "B"]
    assert dropped == []

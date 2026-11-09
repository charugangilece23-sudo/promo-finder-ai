"""Tests for ranker (Phase 4)."""

from __future__ import annotations

from promo_finder.models import Candidate, Segment
from promo_finder.scoring.ranker import rank


def _seg(ep=1, start=0.0, end=30.0):
    return Segment(episode=ep, start=start, end=end,
                   start_event_id="E001:000", end_event_id="E001:005",
                   event_ids=["E001:000", "E001:005"], transcript=[])


def _cand(cid, score, ep=1, start=0.0, hook=0.0, cliff=0.0):
    return Candidate(cand_id=cid, segments=[_seg(ep, start, start + 30.0)],
                     duration=30.0, events_in_window=["E001:000"])


def test_rank_by_score_desc():
    feats = lambda h, c: {"hook": {"score": h}, "cliffhanger": {"score": c}}
    out = rank([
        (_cand("A", 0.5, hook=0.2, cliff=0.2), feats(0.2, 0.2), 0.5),
        (_cand("B", 0.8, hook=0.2, cliff=0.2), feats(0.2, 0.2), 0.8),
        (_cand("C", 0.6, hook=0.2, cliff=0.2), feats(0.2, 0.2), 0.6),
    ])
    assert [c.cand_id for c, _, _ in out] == ["B", "C", "A"]


def test_tie_broken_by_hook_then_cliff():
    feats = lambda h, c: {"hook": {"score": h}, "cliffhanger": {"score": c}}
    out = rank([
        (_cand("A", 0.5, ep=1, start=10.0), feats(0.4, 0.9), 0.5),
        (_cand("B", 0.5, ep=1, start=5.0), feats(0.8, 0.1), 0.5),
        (_cand("C", 0.5, ep=1, start=5.0), feats(0.8, 0.5), 0.5),
    ])
    # C and B tie on score+hook; C has higher cliff -> first
    assert [c.cand_id for c, _, _ in out] == ["C", "B", "A"]

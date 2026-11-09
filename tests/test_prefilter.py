"""Tests for the prefilter/clustering (Phase 4, architecture §11.5)."""

from __future__ import annotations

from promo_finder.config import Settings
from promo_finder.models import Candidate, Episode, Segment
from promo_finder.preprocess.timeline import Timeline
from promo_finder.candidates.prefilter import prefilter_candidates


def _seg(start=0.0, end=30.0):
    return Segment(episode=1, start=start, end=end,
                   start_event_id="E001:000", end_event_id="E001:005",
                   event_ids=["E001:000", "E001:005"], transcript=[])


def _cand(cid, dur=30.0, start=0.0):
    return Candidate(cand_id=cid, segments=[_seg(start, start + dur)],
                     duration=dur, events_in_window=["E001:000"])


def test_prefilter_caps_to_clusters():
    settings = Settings(prefilter={"variants_per_cluster": 2,
                                   "clusters_per_episode": 2,
                                   "iou_threshold": 0.5})
    tl = Timeline(Episode(
        number=1, path="x", events=[], scenes=[], duration=100.0))
    # Several overlapping candidates (same cluster) + one far apart.
    cands = [
        (_cand("A", start=0.0), {}, 0.9),
        (_cand("B", start=5.0), {}, 0.8),   # overlaps A (IoU high)
        (_cand("C", start=10.0), {}, 0.7),  # overlaps A
        (_cand("D", start=60.0), {}, 0.6),  # separate cluster
    ]
    kept = prefilter_candidates([c for c, _, _ in cands], tl, settings)
    # At most clusters_per_episode * variants_per_cluster = 4 kept.
    assert len(kept) <= 4


def test_prefilter_returns_scored_tuples():
    settings = Settings()
    tl = Timeline(Episode(
        number=1, path="x", events=[], scenes=[], duration=100.0))
    cands = [(_cand("A", start=0.0), {}, 0.0)]
    out = prefilter_candidates([c for c, _, _ in cands], tl, settings)
    assert len(out) == 1
    cand, feats, score = out[0]
    assert cand.cand_id == "A"
    assert "hook" in feats
    assert isinstance(score, float)

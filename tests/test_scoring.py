"""Tests for scoring/fusion (Phase 4/6, architecture §11.7)."""

from __future__ import annotations

from promo_finder.config import Settings
from promo_finder.models import Candidate, Event, EventKind, Segment
from promo_finder.scoring.scorer import (
    combine_dimension, weakest_link_penalty, score_candidate, hard_gates_ok,
)


def _seg(ep=1, start=0.0, end=30.0):
    return Segment(
        episode=ep, start=start, end=end,
        start_event_id="E001:000", end_event_id="E001:005",
        event_ids=["E001:000", "E001:005"],
        transcript=[],
    )


def _cand(dur=30.0, ep=1, start=0.0):
    return Candidate(
        cand_id="c", segments=[_seg(ep, start, start + dur)],
        duration=dur, events_in_window=["E001:000"],
    )


def test_combine_dimension_llm_none_uses_det():
    assert combine_dimension(0.7, None, 0.5) == 0.7


def test_combine_dimension_fusion():
    # alpha=0.5, det=0.8, llm=(5-1)/4=1.0 -> 0.5*1.0 + 0.5*0.8 = 0.9
    assert abs(combine_dimension(0.8, 1.0, 0.5) - 0.9) < 1e-9


def test_weakest_link_penalty():
    # min must-have >= knee -> penalty 1
    combined = {"hook": 0.85, "cliffhanger": 0.7, "standalone": 0.65}
    settings = Settings()
    assert weakest_link_penalty(combined, settings) == 1.0
    # hook=0.20, knee=0.5 -> penalty = 0.6 + 0.4*(0.20/0.5) = 0.6+0.16=0.76
    combined2 = {"hook": 0.20, "cliffhanger": 0.7, "standalone": 0.65}
    assert abs(weakest_link_penalty(combined2, settings) - 0.76) < 1e-9


def test_score_candidate_illustrative_example():
    """AGENTS §11.7: s={hook .85, cliff .70, standalone .65, emotion .80,
    coherence .75, duration 1.0} -> base .7625 -> SCORE ~76 (tier A)."""
    settings = Settings()
    cand = _cand(dur=30.0)
    features = {
        "hook": {"score": 0.85},
        "cliffhanger": {"score": 0.70},
        "standalone": {"score": 0.65},
        "emotion": {"score": 0.80},
        "coherence": {"score": 0.75},
        "duration": {"score": 1.0},
    }
    score, sb = score_candidate(cand, features, settings)
    expected_base = 0.25 * 0.85 + 0.25 * 0.70 + 0.20 * 0.65 + 0.15 * 0.80 + 0.10 * 0.75 + 0.05 * 1.0
    assert abs(score - 100 * expected_base) < 1e-6  # penalty=1
    assert sb.weakest_link_penalty == 1.0


def test_weakest_link_penalty_drops_score():
    """hook=0.20 -> penalty 0.76 -> score ~52 (tier C)."""
    settings = Settings()
    cand = _cand(dur=30.0)
    features = {
        "hook": {"score": 0.20},
        "cliffhanger": {"score": 0.70},
        "standalone": {"score": 0.65},
        "emotion": {"score": 0.80},
        "coherence": {"score": 0.75},
        "duration": {"score": 1.0},
    }
    score, sb = score_candidate(cand, features, settings)
    assert abs(sb.weakest_link_penalty - 0.76) < 1e-9
    assert 44 < score < 47  # ~45.6 -> tier C (< 60)


def test_hard_gates_reject_out_of_range():
    assert hard_gates_ok(_cand(dur=19.9)) is False
    assert hard_gates_ok(_cand(dur=60.1)) is False
    assert hard_gates_ok(_cand(dur=30.0)) is True


def test_llm_unavailable_alpha_zero():
    settings = Settings(llm_share={"hook": 0.0, "cliffhanger": 0.0,
                                   "standalone": 0.0, "emotion": 0.0,
                                   "coherence": 0.0})
    cand = _cand(dur=30.0)
    features = {d: {"score": 0.5} for d in ["hook", "cliffhanger", "standalone",
                                            "emotion", "coherence", "duration"]}
    score, sb = score_candidate(cand, features, settings, llm_eval=None)
    # alpha=0 => combined == det == 0.5 for all => base=0.5 => score=50
    assert abs(score - 50.0) < 1e-6

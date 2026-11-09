"""Tests for risk flags (Phase 6, architecture §11.8)."""

from __future__ import annotations

from promo_finder.scoring.flags import (
    compute_flags, calibration_drift,
    LOW_HOOK, WEAK_CLIFFHANGER, LLM_DET_DISAGREE, NEEDS_CONTEXT, NO_LLM,
)


def _feats(hook=0.8, cliff=0.8, standalone=0.8):
    return {
        "hook": {"score": hook, "features": {"speech_within_1s": 1.0, "shock_hits": 0.5}},
        "cliffhanger": {"score": cliff, "features": {}},
        "standalone": {"score": standalone, "features": {}},
    }


def test_no_llm_flag():
    flags = compute_flags(_feats(), None, {}, None, None, None, no_llm=True)
    assert NO_LLM in flags


def test_low_hook_flag():
    flags = compute_flags(_feats(hook=0.2), None, {}, None, None, None)
    assert LOW_HOOK in flags


def test_weak_cliffhanger_flag():
    flags = compute_flags(_feats(cliff=0.2), None, {}, None, None, None)
    assert WEAK_CLIFFHANGER in flags


def test_llm_det_disagree():
    flags = compute_flags(_feats(hook=0.8), {"scores": {"hook": 0.1}}, {}, None,
                          None, None)
    assert LLM_DET_DISAGREE in flags


def test_needs_context():
    flags = compute_flags(_feats(standalone=0.2), None, {}, None, None, None)
    assert NEEDS_CONTEXT in flags


def test_no_flags_for_strong_clean():
    flags = compute_flags(_feats(), None, {}, None, None, None)
    assert flags == []


def test_calibration_drift():
    # |4-3| = 1 is not > 1.0, so no drift.
    drifting = calibration_drift({1: 3.0, 2: 4.0}, global_mean=3.0, threshold=1.0)
    assert drifting == []
    # |5-3| = 2 > 1.0, so drift.
    drifting = calibration_drift({1: 3.0, 2: 5.0}, global_mean=3.0, threshold=1.0)
    assert drifting == [2]

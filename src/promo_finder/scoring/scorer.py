"""Score fusion (architecture §11.7).

Combines deterministic and LLM components into one transparent score:

    s_i = α_i · llm_i + (1 − α_i) · det_i          # both in [0,1]

base = Σ w_i · s_i
penalty = min(1, floor + (1−floor)·min(s_hook, s_cliff, s_standalone) / knee)
SCORE = 100 · base · penalty

Hard gates (reject, not penalise): duration outside 20–60 s, cut inside
dialogue, out-of-bounds segments. With no LLM, α_i = 0 and tier is capped at B.
"""

from __future__ import annotations

from promo_finder.config import Settings
from promo_finder.models import Candidate, ScoreBreakdown

DIMENSIONS = ["hook", "cliffhanger", "standalone", "emotion", "coherence", "duration"]
MUST_HAVE = ["hook", "cliffhanger", "standalone"]


def _llm_value(llm_eval: dict | None, dim: str) -> float | None:
    """Extract a 0-1 LLM value for a dimension, or None if unavailable."""
    if not llm_eval:
        return None
    # LLM returns 1-5 anchors -> (x-1)/4.
    raw = llm_eval.get(dim)
    if raw is None:
        return None
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return None
    if not (1.0 <= x <= 5.0):
        return None
    return (x - 1.0) / 4.0


def combine_dimension(det: float, llm: float | None, alpha: float) -> float:
    """s_i = α·llm + (1−α)·det. If llm is None, use det (α effectively 0)."""
    if llm is None:
        return det
    return alpha * llm + (1.0 - alpha) * det


def weakest_link_penalty(combined: dict[str, float], settings: Settings) -> float:
    """Penalty applied when a must-have dimension is low.

    penalty = min(1, floor + (1−floor)·min(s_hook, s_cliff, s_standalone) / knee)
    """
    wl = settings.weakest_link
    floor = wl.floor_penalty
    knee = wl.knee
    dims = [d for d in MUST_HAVE if d in combined]
    if not dims:
        return 1.0
    m = min(combined[d] for d in dims)
    if knee <= 0:
        return floor
    penalty = floor + (1.0 - floor) * min(m / knee, 1.0)
    return min(1.0, max(0.0, penalty))


def score_candidate(
    candidate: Candidate,
    features: dict,
    settings: Settings,
    llm_eval: dict | None = None,
) -> tuple[float, ScoreBreakdown]:
    """Compute the fused score and full breakdown for one candidate.

    Returns (score_out_of_100, breakdown).
    """
    w = settings.weights
    alpha = settings.llm_share

    det_scores = {
        d: features[d]["score"] for d in DIMENSIONS if d in features
    }

    combined: dict[str, float] = {}
    breakdown: dict[str, dict] = {}
    for d in DIMENSIONS:
        det = det_scores.get(d, 0.0)
        llm = _llm_value(llm_eval, d)
        a = alpha.get(d, 0.0)
        c = combine_dimension(det, llm, a)
        combined[d] = c
        breakdown[d] = {
            "det": round(det, 4),
            "llm": round(llm, 4) if llm is not None else 0.0,
            "combined": round(c, 4),
        }

    # Duration combined (seconds + plateau).
    dur = features.get("duration", {})
    breakdown["duration"] = {
        "det": round(det_scores.get("duration", 0.0), 4),
        "seconds": round(candidate.duration, 4),
        "combined": round(combined.get("duration", 0.0), 4),
    }

    base = sum(w.get(d, 0.0) * combined[d] for d in DIMENSIONS)
    penalty = weakest_link_penalty(combined, settings)
    score = 100.0 * base * penalty

    sb = ScoreBreakdown(
        hook=breakdown.get("hook", {}),
        cliffhanger=breakdown.get("cliffhanger", {}),
        emotion=breakdown.get("emotion", {}),
        coherence=breakdown.get("coherence", {}),
        standalone=breakdown.get("standalone", {}),
        duration=breakdown.get("duration", {}),
        weakest_link_penalty=round(penalty, 4),
    )
    return round(score, 2), sb


def hard_gates_ok(candidate: Candidate) -> bool:
    """Reject candidates that fail hard gates (duration, bounds)."""
    seg = candidate.segments[0]
    if not (20.0 <= candidate.duration <= 60.0):
        return False
    if seg.end <= seg.start:
        return False
    return True

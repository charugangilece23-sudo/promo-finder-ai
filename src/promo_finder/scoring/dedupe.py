"""Overlap deduplication (architecture §11.9).

Two promos conflict if, in the same episode, their overlap >= 50% of the
shorter segment. Keep the higher score; record the dropped one with reason
DUPLICATE_OF:<id> in the debug dump.
"""

from __future__ import annotations

from promo_finder.models import Candidate


def _overlap(a_start, a_end, b_start, b_end) -> float:
    lo = max(a_start, b_start)
    hi = min(a_end, b_end)
    return max(0.0, hi - lo)


def deduplicate(
    candidates: list[tuple[Candidate, dict, float]],
) -> tuple[list[tuple[Candidate, dict, float]], list[dict]]:
    """Remove overlapping candidates, keeping the higher score.

    Args:
        candidates: list of ``(candidate, features, score)`` sorted by score desc.

    Returns:
        ``(kept, dropped)`` where ``dropped`` entries have a ``reason`` key.
    """
    kept: list[tuple[Candidate, dict, float]] = []
    dropped: list[dict] = []

    for cand, feats, score in candidates:
        conflict = False
        for kept_cand, _, _ in kept:
            a = cand.segments[0]
            b = kept_cand.segments[0]
            if a.episode != b.episode:
                continue
            overlap = _overlap(a.start, a.end, b.start, b.end)
            shorter = min(a.end - a.start, b.end - b.start)
            if shorter <= 0:
                continue
            if overlap / shorter >= 0.5:
                conflict = True
                dropped.append({
                    "cand_id": cand.cand_id,
                    "reason": f"DUPLICATE_OF:{kept_cand.cand_id}",
                    "score": score,
                    "kept_score": score,  # placeholder; kept is higher
                })
                break
        if not conflict:
            kept.append((cand, feats, score))

    return kept, dropped

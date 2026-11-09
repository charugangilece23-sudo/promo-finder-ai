"""Ranking (architecture §11.9).

Sort by score; ties broken by higher hook, then higher cliffhanger, then
earlier episode. Deterministic and reproducible.
"""

from __future__ import annotations

from promo_finder.models import Candidate


def rank(
    kept: list[tuple[Candidate, dict, float]],
) -> list[tuple[Candidate, dict, float]]:
    """Sort candidates by score with deterministic tie-breaks."""
    return sorted(
        kept,
        key=lambda item: (
            -item[2],  # score desc
            -item[1].get("hook", {}).get("score", 0.0),  # hook desc
            -item[1].get("cliffhanger", {}).get("score", 0.0),  # cliff desc
            item[0].segments[0].episode,  # earlier episode
            item[0].segments[0].start,  # earlier start
        ),
    )

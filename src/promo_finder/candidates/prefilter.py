"""Candidate prefilter and clustering (architecture §11.5).

Scores each candidate with the deterministic weights, clusters overlapping
windows (temporal IoU > threshold), keeps up to ``variants_per_cluster``
distinct cut points per cluster, and keeps the top ``clusters_per_episode``
clusters. This caps LLM load while preserving boundary alternatives.
"""

from __future__ import annotations

import logging

from promo_finder.config import Settings
from promo_finder.candidates.features import extract_all_features
from promo_finder.candidates.generator import Candidate
from promo_finder.preprocess.timeline import Timeline

logger = logging.getLogger("promo_finder.candidates.prefilter")


def _iou(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    lo = max(a_start, b_start)
    hi = min(a_end, b_end)
    inter = max(0.0, hi - lo)
    union = max(a_end, b_end) - min(a_start, b_start)
    if union <= 0:
        return 0.0
    return inter / union


def _det_score(features: dict, settings: Settings) -> float:
    """Prefilter score from deterministic features with config weights."""
    w = settings.weights
    return (
        w.get("hook", 0.25) * features["hook"]["score"]
        + w.get("cliffhanger", 0.25) * features["cliffhanger"]["score"]
        + w.get("standalone", 0.20) * features["standalone"]["score"]
        + w.get("emotion", 0.15) * features["emotion"]["score"]
        + w.get("coherence", 0.10) * features["coherence"]["score"]
        + w.get("duration", 0.05) * features["duration"]["score"]
    )


def prefilter_candidates(
    candidates: list[Candidate],
    timeline: Timeline,
    settings: Settings,
) -> list[tuple[Candidate, dict, float]]:
    """Score, cluster, and prune candidates.

    Returns a list of ``(candidate, features, prefilter_score)`` tuples,
    sorted by score descending, capped to ``clusters_per_episode`` clusters
    with ``variants_per_cluster`` variants each.
    """
    if not candidates:
        return []

    # Score every candidate.
    scored: list[tuple[Candidate, dict, float]] = []
    for c in candidates:
        feats = extract_all_features(c, timeline)
        score = _det_score(feats, settings)
        scored.append((c, feats, score))

    scored.sort(key=lambda item: item[2], reverse=True)

    # Cluster by temporal IoU > threshold (first segment only, contiguous case).
    thr = settings.prefilter.iou_threshold
    clusters: list[list[tuple[Candidate, dict, float]]] = []
    for item in scored:
        c, _, _ = item
        seg = c.segments[0]
        placed = False
        for cluster in clusters:
            rep_seg = cluster[0][0].segments[0]
            if _iou(seg.start, seg.end, rep_seg.start, rep_seg.end) > thr:
                cluster.append(item)
                placed = True
                break
        if not placed:
            clusters.append([item])

    # Sort clusters by their best score.
    clusters.sort(key=lambda cl: max(it[2] for it in cl), reverse=True)

    # Keep top clusters, each with up to variants_per_cluster variants
    # (with distinct cut points).
    kept: list[tuple[Candidate, dict, float]] = []
    max_clusters = settings.prefilter.clusters_per_episode
    max_variants = settings.prefilter.variants_per_cluster
    for cluster in clusters[:max_clusters]:
        seen_cuts: set[tuple[float, float]] = set()
        variants = 0
        for item in cluster:
            seg = item[0].segments[0]
            cut = (seg.start, seg.end)
            if cut in seen_cuts:
                continue
            seen_cuts.add(cut)
            kept.append(item)
            variants += 1
            if variants >= max_variants:
                break

    kept.sort(key=lambda item: item[2], reverse=True)
    logger.info(
        "ep=%d: %d candidates -> %d clusters -> %d kept",
        timeline.episode, len(candidates), len(clusters), len(kept),
    )
    return kept

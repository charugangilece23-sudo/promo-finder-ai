"""LLM candidate evaluator (architecture §10.2, §10.5).

Batches candidates per episode (≤ 20 per call), calls the LLM, validates
via grounding, retries on failure, and only accepts grounded LLM output.
Heuristic fallback is used ONLY when no LLM client is configured (I6).
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

from promo_finder.config import Settings
from promo_finder.candidates.features import extract_all_features
from promo_finder.candidates.generator import Candidate
from promo_finder.llm.base import LLMClient
from promo_finder.llm.prompts import load_prompt
from promo_finder.llm.schemas import EvalOut
from promo_finder.preprocess.timeline import Timeline
from promo_finder.scoring.scorer import score_candidate
from promo_finder.validation.grounding import validate_eval

logger = logging.getLogger("promo_finder.scoring.evaluator")

MAX_CANDIDATES_PER_CALL = 20
MAX_LLM_RETRIES = 50  # keep retrying until LLM succeeds
RETRY_DELAY_BASE = 5.0  # seconds, doubles each retry
RETRY_DELAY_MAX = 120.0  # cap delay at 2 minutes


def _compact_transcript(timeline: Timeline,
                        candidate: Candidate) -> str:
    """Build the compact transcript text for the candidate's events."""
    seg = candidate.segments[0]
    inside = [e for e in timeline.events
              if seg.start - 1e-9 <= e.start and e.end <= seg.end + 1e-9]
    lines = []
    for ev in inside:
        tag = ev.speaker_raw or ev.kind.value.upper()
        ann = ""
        if ev.modifiers:
            ann += " (" + ", ".join(ev.modifiers) + ")"
        if ev.delivery:
            ann += " (" + ", ".join(ev.delivery) + ")"
        lines.append(
            f"{ev.id} [{_ts(ev.start)}-{_ts(ev.end)}] {tag}{ann}: \"{ev.text}\""
        )
    return "\n".join(lines)


def _ts(seconds: float) -> str:
    total = max(0.0, round(seconds, 2))
    m = int(total // 60)
    s = total % 60
    return f"{m:02d}:{s:05.2f}"


def evaluate_candidates(
    prefiltered: list[tuple[Candidate, dict, float]],
    timeline: Timeline,
    client: LLMClient | None,
    settings: Settings,
    prompt_version: str = "v1",
) -> list[tuple[Candidate, dict, float, dict | None]]:
    """Evaluate prefiltered candidates with the LLM (or heuristic fallback).

    Args:
        prefiltered: list of (candidate, features, prefilter_score).
        timeline: the episode timeline.
        client: LLM client; None means heuristic-only (I6).
        settings: validated settings.
        prompt_version: version of the evaluate prompt (for cache key).

    Returns:
        List of (candidate, features, fused_score, llm_eval_or_none).
        llm_eval is None when heuristic-only.
    """
    if not prefiltered:
        return []

    results: list[tuple[Candidate, dict, float, dict | None]] = []

    # Process in batches to cap LLM input size.
    for i in range(0, len(prefiltered), MAX_CANDIDATES_PER_CALL):
        batch = prefiltered[i:i + MAX_CANDIDATES_PER_CALL]
        batch_results = _evaluate_batch(batch, timeline, client, settings,
                                        prompt_version)
        results.extend(batch_results)

    return results


def _evaluate_batch(batch, timeline, client, settings, prompt_version):
    results = []
    for cand, feats, pre_score in batch:
        if client is None:
            # Heuristic-only (I6): no LLM client configured.
            score, _ = score_candidate(cand, feats, settings, llm_eval=None)
            results.append((cand, feats, score, None))
            continue

        # Build the prompt: compact transcript once + this candidate.
        transcript = _compact_transcript(timeline, cand)
        seg = cand.segments[0]
        prompt = (
            f"COMPACT TRANSCRIPT (episode {timeline.episode}):\n{transcript}\n\n"
            f"CANDIDATE: cand_id={cand.cand_id}, "
            f"start_event_id={seg.start_event_id}, "
            f"end_event_id={seg.end_event_id}, duration={cand.duration:.2f}s\n"
            f"Evaluate this candidate."
        )
        version, body = load_prompt("config/prompts/evaluate.md")
        full_prompt = body + "\n\n" + prompt

        def _call():
            return client.generate_json(
                system="You evaluate promo candidates for a TV microdrama. "
                       "Return structured JSON only.",
                prompt=full_prompt,
                schema=EvalOut,
                temperature=0.0,
                max_tokens=4096,
            )

        # Keep retrying until LLM succeeds or max retries exceeded.
        # No heuristic fallback on LLM failure.
        eval_out = None
        grounded = None
        delay = RETRY_DELAY_BASE
        for attempt in range(MAX_LLM_RETRIES):
            try:
                result = _call()
            except Exception as exc:  # noqa: BLE001 - retry on provider errors
                logger.warning(
                    "LLM call failed for %s (attempt %d/%d): %s",
                    cand.cand_id, attempt + 1, MAX_LLM_RETRIES, exc,
                )
                if attempt < MAX_LLM_RETRIES - 1:
                    sleep_for = min(delay + random.uniform(0, 2), RETRY_DELAY_MAX)
                    logger.info("Sleeping %.1fs before retry...", sleep_for)
                    time.sleep(sleep_for)
                    delay = min(delay * 2, RETRY_DELAY_MAX)
                continue

            eval_out = result.parsed
            if eval_out is None:
                logger.warning(
                    "LLM invalid JSON/schema for %s (attempt %d/%d); retrying",
                    cand.cand_id, attempt + 1, MAX_LLM_RETRIES,
                )
                if attempt < MAX_LLM_RETRIES - 1:
                    sleep_for = min(delay + random.uniform(0, 2), RETRY_DELAY_MAX)
                    logger.info("Sleeping %.1fs before retry...", sleep_for)
                    time.sleep(sleep_for)
                    delay = min(delay * 2, RETRY_DELAY_MAX)
                continue

            # Build events_by_id for grounding.
            events_by_id = {e.id: e for e in timeline.events}
            grounded = validate_eval(eval_out, cand, events_by_id,
                                     hook_window=3.0, tail_window=5.0)

            if not grounded["valid"]:
                logger.warning(
                    "LLM ungrounded for %s (attempt %d/%d); retrying",
                    cand.cand_id, attempt + 1, MAX_LLM_RETRIES,
                )
                if attempt < MAX_LLM_RETRIES - 1:
                    sleep_for = min(delay + random.uniform(0, 2), RETRY_DELAY_MAX)
                    logger.info("Sleeping %.1fs before retry...", sleep_for)
                    time.sleep(sleep_for)
                    delay = min(delay * 2, RETRY_DELAY_MAX)
                continue

            # Success — valid LLM output with grounding.
            logger.info(
                "LLM eval OK for %s (attempt %d/%d): hook=%s cliff=%s emotion=%s "
                "coherence=%s standalone=%s",
                cand.cand_id, attempt + 1, MAX_LLM_RETRIES,
                eval_out.hook, eval_out.cliffhanger, eval_out.emotion,
                eval_out.coherence, eval_out.standalone,
            )
            break

        if eval_out is None or grounded is None or not grounded["valid"]:
            raise RuntimeError(
                f"LLM evaluation failed for {cand.cand_id} after "
                f"{MAX_LLM_RETRIES} retries. No heuristic fallback."
            )

        # Build llm_eval dict for the scorer (1-5 anchors).
        llm_eval = {
            "hook": float(eval_out.hook),
            "cliffhanger": float(eval_out.cliffhanger),
            "standalone": float(eval_out.standalone),
            "emotion": float(eval_out.emotion),
            "coherence": float(eval_out.coherence),
        }
        score, _ = score_candidate(cand, feats, settings, llm_eval=llm_eval)

        # Attach grounded hook/cliffhanger text for output.
        llm_eval["_hook_block"] = grounded["hook"]
        llm_eval["_cliff_block"] = grounded["cliffhanger"]
        llm_eval["_flags"] = grounded["flags"]

        results.append((cand, feats, score, llm_eval))

    return results
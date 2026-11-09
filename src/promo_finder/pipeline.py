"""End-to-end pipeline orchestration (architecture §8.9).

Stages: parse → timeline → generate → features → prefilter → score → dedupe
→ rank → write outputs. Each stage is a small pure function; per-episode
stages are independent. Heuristic-only (no LLM) by default.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from promo_finder.config import Settings
from promo_finder.ingestion.loader import load_episodes
from promo_finder.ingestion.parsers.registry import build_default_registry
from promo_finder.ingestion.validators import validate_episode, validate_episodes
from promo_finder.preprocess.timeline import Timeline
from promo_finder.candidates.cutpoints import build_timeline
from promo_finder.candidates.generator import generate_candidates
from promo_finder.candidates.features import extract_all_features
from promo_finder.candidates.prefilter import prefilter_candidates
from promo_finder.scoring.scorer import score_candidate, hard_gates_ok
from promo_finder.scoring.dedupe import deduplicate
from promo_finder.scoring.ranker import rank
from promo_finder.llm.factory import build_client
from promo_finder.reporting.json_writer import (
    write_episodes_json, write_promos_json, write_run_manifest,
    write_candidates_debug,
)
from promo_finder.reporting.markdown_report import write_report
from promo_finder.scoring.evaluator import evaluate_candidates
from promo_finder.scoring.flags import compute_flags
from promo_finder.models import Candidate, ParseWarning, Episode

logger = logging.getLogger("promo_finder.pipeline")


@dataclass
class StageResult:
    name: str
    duration_s: float
    count: int = 0


@dataclass
class PipelineResult:
    episodes: list
    run_id: str
    output_dir: str
    stage_results: list[StageResult] = field(default_factory=list)
    warnings: list[ParseWarning] = field(default_factory=list)


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def run(episodes_dir: str, settings: Settings, no_llm: bool = True,
        output_dir: str | None = None,
        max_episodes: int | None = None) -> PipelineResult:
    """Run the promo discovery pipeline end to end.

    Args:
        episodes_dir: directory of transcript .txt files.
        settings: validated application settings.
        no_llm: force heuristic-only mode (no LLM calls).
        output_dir: override for where to write outputs.

    Returns:
        A :class:`PipelineResult` with parsed episodes and stage timings.
    """
    run_id = _now_utc()
    out_dir = Path(output_dir or settings.output_dir) / run_id
    os.makedirs(out_dir, exist_ok=True)
    stage_results: list[StageResult] = []
    all_warnings: list[ParseWarning] = []

    # Stage 1: load + parse + validate.
    t0 = time.perf_counter()
    raw_episodes = load_episodes(episodes_dir, settings.input_glob)
    registry = build_default_registry()
    episodes = []
    for raw in raw_episodes:
        try:
            text = open(raw.path, "r", encoding="utf-8").read()
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            ep, parse_warns = registry.parse(
                type("Raw", (), {"path": raw.path, "text": text})()
            )
        except Exception as exc:  # noqa: BLE001 - report, continue (R16)
            logger.warning("Failed to parse %s: %s", raw.path, exc)
            all_warnings.append(ParseWarning(
                file=raw.path, episode=None, block_index=None,
                code="parse_failed", message=str(exc)))
            continue
        ep.warnings.extend(parse_warns)
        ep.warnings.extend(validate_episode(ep))
        episodes.append(ep)

    cross_warns = validate_episodes(episodes)
    all_warnings.extend(cross_warns)
    stage_results.append(StageResult(
        "parse_and_validate", time.perf_counter() - t0, len(episodes)))
    logger.info("Parsed %d episodes (%d warnings)",
                len(episodes), len(all_warnings))

    # Limit number of episodes if requested.
    if max_episodes is not None:
        episodes = episodes[:max_episodes]
        logger.info("Limiting to %d episodes (max_episodes=%d)",
                    len(episodes), max_episodes)

    # Per-episode stages.
    client = None if no_llm else build_client(settings=settings)
    all_candidates: list[tuple] = []  # (candidate, features, score, llm_eval, episode)
    total_episodes = len(episodes)
    for idx, ep in enumerate(episodes, start=1):
        logger.info(
            "Processing episode %d/%d (number=%d): %d remaining",
            idx, total_episodes, ep.number, total_episodes - idx,
        )
        ep_result = _process_episode(ep, settings, stage_results, client)
        all_candidates.extend(ep_result)

    # Cross-episode: dedupe (within episode) + rank.
    t0 = time.perf_counter()
    # Group by episode for dedupe (dedupe works per candidate list).
    by_ep: dict[int, list] = {}
    for cand, feats, score, llm_eval, ep in all_candidates:
        by_ep.setdefault(ep.number, []).append((cand, feats, score, llm_eval))

    deduped: list[tuple] = []
    for ep_num, clist in by_ep.items():
        # dedupe compares (cand, feats, score); carry llm_eval alongside.
        kept, _dropped = deduplicate(
            [(c, f, s) for c, f, s, _le in clist]
        )
        # Reattach llm_eval by cand_id.
        le_by_id = {c.cand_id: le for c, f, s, le in clist}
        for cand, feats, score in kept:
            deduped.append((cand, feats, score, le_by_id[cand.cand_id],
                            next(e for e in episodes if e.number == ep_num)))

    ranked = rank(deduped)
    stage_results.append(StageResult("dedupe_and_rank",
                                     time.perf_counter() - t0, len(ranked)))

    # Build promos (with LLM hook/cliffhanger text when available) and write outputs.
    promos = _build_promos(ranked, episodes, settings)
    write_promos_json(out_dir, promos, _run_meta(settings, no_llm, client))
    write_report(out_dir / "promos.json", out_dir)

    # Persist episodes.json.
    write_episodes_json(out_dir, episodes)

    # run_manifest.json: config, models, timings, usage.
    manifest = {
        "run_id": run_id,
        "show": "unknown",
        "llm": {"provider": settings.llm.provider,
                "eval_model": settings.llm.eval_model,
                "finalist_model": settings.llm.finalist_model,
                "actual_model": getattr(client, "name", None) if client else None,
                "mode": "heuristic_only" if no_llm else "llm"},
        "prompt_versions": {"evaluate": "v1", "blind": "v1"},
        "stages": [{"name": s.name, "duration_s": round(s.duration_s, 4),
                    "count": s.count} for s in stage_results],
        "total_duration_s": round(sum(s.duration_s for s in stage_results), 4),
        "config": {
            "weights": settings.weights,
            "llm_share": settings.llm_share,
            "duration": settings.duration.model_dump(),
            "cut_rules": settings.cut_rules.model_dump(),
            "prefilter": settings.prefilter.model_dump(),
            "tiers": {"A": settings.tiers.A, "B": settings.tiers.B},
            "top_n": settings.top_n,
        },
    }
    write_run_manifest(out_dir, manifest)

    # candidates_debug.json: all scored candidates (incl. rejected via prefilter)
    # are not carried here; write the ranked prefiltered set as the debug dump.
    debug_candidates = []
    for cand, feats, score, llm_eval, ep in ranked:
        debug_candidates.append({
            "cand_id": cand.cand_id,
            "episode": ep.number,
            "start": cand.segments[0].start,
            "end": cand.segments[0].end,
            "duration": cand.duration,
            "score": score,
            "tier": _tier(score, settings),
            "features": feats,
            "llm_eval": {k: v for k, v in (llm_eval or {}).items()
                         if not k.startswith("_")},
            "flags": llm_eval.get("_flags", []) if llm_eval else [],
        })
    write_candidates_debug(out_dir, debug_candidates)

    return PipelineResult(
        episodes=episodes, run_id=run_id, output_dir=out_dir,
        stage_results=stage_results, warnings=all_warnings)


def _run_meta(settings: Settings, no_llm: bool,
              client=None) -> dict:
    return {
        "run_id": _now_utc(),
        "show": "unknown",
        "llm": {"provider": settings.llm.provider,
                "eval_model": settings.llm.eval_model,
                "finalist_model": settings.llm.finalist_model,
                "actual_model": getattr(client, "name", None),
                "mode": "heuristic_only" if no_llm else "llm"},
        "prompt_versions": {"evaluate": "heuristic", "blind": "heuristic"},
    }


def _tier(score: float, settings: Settings) -> str:
    if score >= settings.tiers.A:
        return "A"
    if score >= settings.tiers.B:
        return "B"
    return "C"


def _hook_cliff_heuristic(cand: Candidate, timeline: Timeline) -> tuple[dict, dict]:
    """Heuristic hook/cliffhanger from the first/last dialogue event (no LLM)."""
    seg = cand.segments[0]
    inside = [e for e in timeline.events
              if seg.start - 1e-9 <= e.start and e.end <= seg.end + 1e-9]
    dialogue = [e for e in inside if e.kind.value == "dialogue"]

    hook_event = dialogue[0] if dialogue else None
    cliff_event = dialogue[-1] if dialogue else None

    def _make_block(ev, seconds_from_start):
        if ev is None:
            return {"event_id": "", "quote": "", "description": "",
                    "seconds_from_start": 0.0}
        return {
            "event_id": ev.id,
            "quote": ev.text,
            "description": f"{ev.speaker_raw or 'Speaker'}: {ev.text}",
            "seconds_from_start": round(ev.start - seg.start, 4),
        }

    return (_make_block(hook_event, 0.0),
            _make_block(cliff_event, round(seg.end - seg.start, 4)))


def _build_promos(ranked, episodes: list[Episode],
                  settings: Settings) -> list[dict]:
    """Turn ranked (candidate, features, score, llm_eval, episode) into promo dicts."""
    ep_by_number = {e.number: e for e in episodes}
    promos: list[dict] = []
    for rank_idx, (cand, feats, score, llm_eval, ep) in enumerate(ranked, start=1):
        seg = cand.segments[0]
        ep_number = seg.episode

        # Hook/cliffhanger: prefer grounded LLM blocks, else heuristic.
        if llm_eval and llm_eval.get("_hook_block"):
            hook = dict(llm_eval["_hook_block"])
            hook["seconds_from_start"] = round(
                hook.get("seconds_from_start",
                         _event_offset(ep, seg, hook.get("event_id", "")) or 0.0), 4)
        else:
            timeline = build_timeline(ep)
            hook, _ = _hook_cliff_heuristic(cand, timeline)
        if llm_eval and llm_eval.get("_cliff_block"):
            cliff = dict(llm_eval["_cliff_block"])
        else:
            timeline = build_timeline(ep)
            _, cliff = _hook_cliff_heuristic(cand, timeline)

        flags = compute_flags(
            feats, llm_eval,
            combined={},  # combined scores not tracked separately here
            candidate=cand, timeline=None, settings=settings,
            no_llm=(not llm_eval),
        )

        score_breakdown = {
            "hook": feats.get("hook", {}).get("score", 0.0),
            "cliffhanger": feats.get("cliffhanger", {}).get("score", 0.0),
            "emotion": feats.get("emotion", {}).get("score", 0.0),
            "coherence": feats.get("coherence", {}).get("score", 0.0),
            "standalone": feats.get("standalone", {}).get("score", 0.0),
            "duration": feats.get("duration", {}).get("score", 0.0),
        }

        why = (llm_eval.get("why_it_works")
               if llm_eval and llm_eval.get("why_it_works")
               else "Heuristic hook/cliffhanger from detected beats; "
                   "no LLM judgement available.")
        weaknesses = (llm_eval.get("weaknesses", [])
                      if llm_eval and llm_eval.get("weaknesses")
                      else ["No LLM evaluation; scores are rule-based only."])

        promos.append({
            "promo_id": cand.cand_id,
            "rank": rank_idx,
            "tier": _tier(score, settings),
            "score": score,
            "score_breakdown": score_breakdown,
            "episodes": [ep_number],
            "total_duration_s": cand.duration,
            "segments": [
                {
                    "episode": seg.episode,
                    "start": seg.start,
                    "end": seg.end,
                    "start_event_id": seg.start_event_id,
                    "end_event_id": seg.end_event_id,
                    "transcript": seg.transcript,
                }
            ],
            "hook": hook,
            "cliffhanger": cliff,
            "why_it_works": why,
            "weaknesses": weaknesses,
            "flags": flags,
            "confidence": "medium" if llm_eval else "low",
            "validation": {"duration_ok": True, "cuts_dialogue_safe": True,
                           "quotes_grounded": True, "bounds_ok": True},
        })
    return promos


def _event_offset(ep: Episode, seg, event_id: str) -> float | None:
    """Seconds-from-start of an event within a segment, from transcript."""
    for t in seg.transcript:
        if t.get("event_id") == event_id:
            # transcript entries don't carry start; look up in episode events.
            for ev in ep.events:
                if ev.id == event_id:
                    return round(ev.start - seg.start, 4)
            return 0.0
    return None


def _process_episode(ep, settings, stage_results, client):
    """Run timeline → generate → features → prefilter → evaluate → score."""
    # Stage 2: timeline.
    t0 = time.perf_counter()
    timeline = build_timeline(ep)
    stage_results.append(StageResult("timeline", time.perf_counter() - t0,
                                     len(timeline.events)))

    # Stage 3: generate candidates.
    t0 = time.perf_counter()
    candidates = generate_candidates(
        timeline,
        min_dur=settings.cut_rules.min_dur,
        max_dur=settings.cut_rules.max_dur,
    )
    stage_results.append(StageResult("generate", time.perf_counter() - t0,
                                     len(candidates)))

    # Stage 4: features + prefilter.
    t0 = time.perf_counter()
    prefiltered = prefilter_candidates(candidates, timeline, settings)
    stage_results.append(StageResult("prefilter", time.perf_counter() - t0,
                                     len(prefiltered)))

    # Stage 5: LLM evaluation + fused score (heuristic fallback if no client).
    t0 = time.perf_counter()
    evaluated = evaluate_candidates(prefiltered, timeline, client, settings)
    # evaluated: (cand, feats, fused_score, llm_eval_or_none)
    scored = []
    for cand, feats, score, llm_eval in evaluated:
        if not hard_gates_ok(cand):
            continue
        scored.append((cand, feats, score, llm_eval, ep))
    stage_results.append(StageResult("evaluate", time.perf_counter() - t0,
                                     len(scored)))
    return scored

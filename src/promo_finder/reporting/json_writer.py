"""JSON output writers (architecture §12.3).

Writes ``episodes.json`` (the per-episode parse report) and other debug
artifacts. All output is deterministic and serialisable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from promo_finder.models import Episode


def episode_to_dict(episode: Episode) -> dict[str, Any]:
    """Serialise an episode (and its events/scenes/warnings) to a dict."""
    return {
        "number": episode.number,
        "source_id": episode.source_id,
        "path": episode.path,
        "logline": episode.logline,
        "continuity_notes": episode.continuity_notes,
        "duration": episode.duration,
        "scenes": [
            {
                "number": sc.number,
                "heading": sc.heading,
                "start": sc.start,
                "end": sc.end,
                "start_raw": sc.start_raw,
                "end_raw": sc.end_raw,
            }
            for sc in episode.scenes
        ],
        "events": [
            {
                "id": ev.id,
                "kind": ev.kind.value,
                "speaker_raw": ev.speaker_raw,
                "modifiers": ev.modifiers,
                "delivery": ev.delivery,
                "start": ev.start,
                "end": ev.end,
                "start_raw": ev.start_raw,
                "end_raw": ev.end_raw,
                "text": ev.text,
                "norm_text": ev.norm_text,
            }
            for ev in episode.events
        ],
        "warnings": [
            {
                "code": w.code,
                "message": w.message,
                "episode": w.episode,
                "block_index": w.block_index,
            }
            for w in episode.warnings
        ],
    }


def write_episodes_json(output_dir: str | Path, episodes: list[Episode]) -> Path:
    """Write ``episodes.json`` into ``output_dir`` and return its path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "episodes.json"
    payload = {
        "schema_version": "1.0",
        "episodes": [episode_to_dict(ep) for ep in episodes],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _format_ts(seconds: float) -> str:
    total = max(0.0, round(seconds, 2))
    minutes = int(total // 60)
    secs = total % 60
    return f"{minutes:02d}:{secs:05.2f}"


def promo_to_dict(promo: dict) -> dict:
    """Serialise a promo dict (built by the pipeline) for promos.json."""
    return {
        "promo_id": promo["promo_id"],
        "rank": promo["rank"],
        "tier": promo["tier"],
        "score": promo["score"],
        "score_breakdown": promo["score_breakdown"],
        "episodes": promo["episodes"],
        "total_duration_s": round(promo["total_duration_s"], 4),
        "segments": [
            {
                "episode": seg["episode"],
                "start": _format_ts(seg["start"]),
                "end": _format_ts(seg["end"]),
                "start_s": round(seg["start"], 4),
                "end_s": round(seg["end"], 4),
                "duration_s": round(seg["end"] - seg["start"], 4),
                "start_event_id": seg["start_event_id"],
                "end_event_id": seg["end_event_id"],
                "transcript": seg["transcript"],
            }
            for seg in promo["segments"]
        ],
        "hook": promo.get("hook", {}),
        "cliffhanger": promo.get("cliffhanger", {}),
        "why_it_works": promo.get("why_it_works", ""),
        "weaknesses": promo.get("weaknesses", []),
        "flags": promo.get("flags", []),
        "confidence": promo.get("confidence", "medium"),
        "validation": promo.get("validation", {}),
    }


def write_promos_json(output_dir: str | Path, promos: list[dict],
                      run_meta: dict) -> Path:
    """Write ``promos.json`` into ``output_dir`` and return its path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "promos.json"
    payload = {
        "schema_version": "1.0",
        "run": run_meta,
        "promos": [promo_to_dict(p) for p in promos],
        "rejected_summary": {"duplicates": 0, "gate_failures": 0,
                             "llm_invalid": 0},
        "warnings": [],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    return path


def write_run_manifest(output_dir: str | Path,
                       manifest: dict) -> Path:
    """Write ``run_manifest.json`` recording config, models, timings, usage."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "run_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    return path


def write_candidates_debug(output_dir: str | Path,
                           candidates: list[dict]) -> Path:
    """Write ``candidates_debug.json`` with all scored candidates incl. rejected."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "candidates_debug.json"
    path.write_text(json.dumps({"candidates": candidates},
                               indent=2, ensure_ascii=False), encoding="utf-8")
    return path


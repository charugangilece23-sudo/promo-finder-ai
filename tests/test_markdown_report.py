"""Tests for the markdown report writer (Phase 4)."""

from __future__ import annotations

import json

from promo_finder.reporting.markdown_report import write_report


def test_report_contains_required_fields(tmp_path):
    promos = {
        "schema_version": "1.0",
        "run": {
            "run_id": "2026-11-08T01-00-00Z",
            "show": "test",
            "llm": {"provider": "mock", "eval_model": "mock",
                    "finalist_model": None, "mode": "heuristic_only"},
            "prompt_versions": {"evaluate": "heuristic", "blind": "heuristic"},
        },
        "promos": [
            {
                "promo_id": "PRM-abc123",
                "rank": 1,
                "tier": "A",
                "score": 87.6,
                "score_breakdown": {"hook": 0.85, "cliffhanger": 0.70},
                "episodes": [2],
                "total_duration_s": 30.0,
                "segments": [
                    {"episode": 2, "start_s": 10.0, "end_s": 40.0,
                     "start": "00:10.00", "end": "00:40.00",
                     "start_event_id": "E002:005", "end_event_id": "E002:020",
                     "transcript": []}
                ],
                "hook": {"event_id": "E002:005", "quote": "You knew!",
                         "description": "ALICE: You knew!", "seconds_from_start": 0.0},
                "cliffhanger": {"event_id": "E002:020", "quote": "Why?",
                                "description": "BOB: Why?", "seconds_from_start": 25.0},
                "why_it_works": "Strong reveal hook and unresolved question.",
                "weaknesses": ["No LLM."],
                "flags": ["NO_LLM"],
                "confidence": "low",
                "validation": {"duration_ok": True, "cuts_dialogue_safe": True,
                               "quotes_grounded": True, "bounds_ok": True},
            }
        ],
    }
    pfile = tmp_path / "promos.json"
    pfile.write_text(json.dumps(promos), encoding="utf-8")
    out = write_report(pfile, tmp_path)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "PRM-abc123" in text
    assert "You knew!" in text
    assert "Why?" in text
    assert "Ranked table" in text
    assert "Known limitations" in text
    assert "00:10.00" in text and "00:40.00" in text

"""Tests for the grounding validator (Phase 5, architecture §13.2).

Hallucination tests: an LLM response citing a non-existent event_id, a quote
not in the source, or unknown cand_id must be rejected/neutralised and never
reach the output.
"""

from __future__ import annotations

from promo_finder.models import Candidate, Event, EventKind, Segment
from promo_finder.preprocess.timeline import Timeline
from promo_finder.validation.grounding import validate_eval
from promo_finder.llm.schemas import EvalOut


def _cand_and_events():
    events = [
        Event(id="E001:000", episode=1, scene=1, kind=EventKind.DIALOGUE,
              speaker_raw="ALICE", modifiers=[], delivery=["Angry"],
              start=0.0, end=3.0, start_raw="00:00.00", end_raw="00:03.00",
              text="You knew this before I walked in!", norm_text=""),
        Event(id="E001:001", episode=1, scene=1, kind=EventKind.DIALOGUE,
              speaker_raw="BOB", modifiers=[], delivery=["Cold"],
              start=27.0, end=30.0, start_raw="00:27.00", end_raw="00:30.00",
              text="Why did you do it?", norm_text=""),
    ]
    seg = Segment(episode=1, start=0.0, end=30.0,
                  start_event_id="E001:000", end_event_id="E001:001",
                  event_ids=["E001:000", "E001:001"],
                  transcript=[
                      {"event_id": "E001:000", "kind": "dialogue",
                       "speaker": "ALICE", "text": "You knew this before I walked in!"},
                      {"event_id": "E001:001", "kind": "dialogue",
                       "speaker": "BOB", "text": "Why did you do it?"},
                  ])
    cand = Candidate(cand_id="C1", segments=[seg], duration=30.0,
                     events_in_window=["E001:000", "E001:001"])
    events_by_id = {e.id: e for e in events}
    return cand, events_by_id


def test_grounding_valid_passes():
    cand, events_by_id = _cand_and_events()
    eval_out = EvalOut(
        cand_id="C1", hook=5, cliffhanger=5, emotion=4, coherence=4, standalone=4,
        hook_detail={"event_id": "E001:000", "quote": "You knew this before I walked in!",
                     "description": "ALICE accuses"},
        cliffhanger_detail={"event_id": "E001:001", "quote": "Why did you do it?",
                            "description": "Bob asks", "unresolved_question": "why"},
        why_it_works="Great", weaknesses=[], reject=False,
    )
    result = validate_eval(eval_out, cand, events_by_id)
    assert result["valid"] is True
    assert result["hook"]["quote"] == "You knew this before I walked in!"
    assert result["cliffhanger"]["quote"] == "Why did you do it?"
    assert result["flags"] == []


def test_grounding_rejects_unknown_cand_id():
    cand, events_by_id = _cand_and_events()
    eval_out = EvalOut(cand_id="NONEXISTENT", hook=5, cliffhanger=5, emotion=4,
                       coherence=4, standalone=4)
    result = validate_eval(eval_out, cand, events_by_id)
    assert result["valid"] is False
    assert "UNKNOWN_CAND_ID" in result["flags"]


def test_grounding_rejects_event_not_in_candidate():
    cand, events_by_id = _cand_and_events()
    eval_out = EvalOut(
        cand_id="C1", hook=5, cliffhanger=5, emotion=4, coherence=4, standalone=4,
        hook_detail={"event_id": "E999:999", "quote": "some other line",
                     "description": "x"},
        cliffhanger_detail={"event_id": "E001:001", "quote": "Why did you do it?",
                            "description": "x", "unresolved_question": "q"},
    )
    result = validate_eval(eval_out, cand, events_by_id)
    assert result["valid"] is True
    # The offending hook is neutralised with a code-chosen verbatim quote
    # (the first dialogue in the clip), not left empty.
    assert result["hook"]["event_id"] == "E001:000"
    assert result["hook"]["quote"] == "You knew this before I walked in!"
    assert "UNGROUNDED_LLM_TEXT" in result["flags"]


def test_grounding_rejects_quote_not_in_source():
    cand, events_by_id = _cand_and_events()
    eval_out = EvalOut(
        cand_id="C1", hook=5, cliffhanger=5, emotion=4, coherence=4, standalone=4,
        hook_detail={"event_id": "E001:000", "quote": "I am the walrus",
                     "description": "x"},
        cliffhanger_detail={"event_id": "E001:001", "quote": "Why did you do it?",
                            "description": "x", "unresolved_question": "q"},
    )
    result = validate_eval(eval_out, cand, events_by_id)
    assert result["valid"] is True
    assert result["hook"]["quote"] == "You knew this before I walked in!"  # replaced by code
    assert "UNGROUNDED_LLM_TEXT" in result["flags"]


def test_grounding_hook_outside_window_neutralised():
    """Hook event must be within first hook_window seconds."""
    cand, events_by_id = _cand_and_events()
    # E001:001 starts at 27s, outside the 3s hook window for a clip starting at 0.
    eval_out = EvalOut(
        cand_id="C1", hook=5, cliffhanger=5, emotion=4, coherence=4, standalone=4,
        hook_detail={"event_id": "E001:001", "quote": "Why did you do it?",
                     "description": "x"},
        cliffhanger_detail={"event_id": "E001:001", "quote": "Why did you do it?",
                            "description": "x", "unresolved_question": "q"},
    )
    result = validate_eval(eval_out, cand, events_by_id, hook_window=3.0,
                           tail_window=5.0)
    assert "UNGROUNDED_LLM_TEXT" in result["flags"]

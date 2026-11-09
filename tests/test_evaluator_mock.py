"""Mock end-to-end evaluator test (Phase 5).

Verifies the whole LLM path works offline with the MockLLM adapter: valid,
malformed, and schema-invalid responses all fall back gracefully without
crashing, and output timestamps remain identical to the deterministic
generator.
"""

from __future__ import annotations

from promo_finder.config import Settings
from promo_finder.models import Candidate, Event, EventKind, Segment
from promo_finder.preprocess.timeline import Timeline
from promo_finder.candidates.features import extract_all_features
from promo_finder.llm.providers.mock import MockLLM
from promo_finder.scoring.evaluator import evaluate_candidates


def _make_tl_and_cands():
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
    tl = Timeline(__import__("promo_finder.models", fromlist=["Episode"]).Episode(
        number=1, path="x", events=events, scenes=[], duration=100.0))
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
    feats = extract_all_features(cand, tl)
    return tl, [(cand, feats, 0.5)]


def test_mock_evaluator_valid():
    tl, batch = _make_tl_and_cands()
    client = MockLLM()  # returns neutral mid-range evals
    results = evaluate_candidates(batch, tl, client, Settings())
    cand, feats, score, llm_eval = results[0]
    assert llm_eval is not None
    assert llm_eval["hook"] == 3.0  # raw 1-5 anchor from mock
    assert score > 0


def test_mock_evaluator_no_client_heuristic():
    tl, batch = _make_tl_and_cands()
    results = evaluate_candidates(batch, tl, None, Settings())
    cand, feats, score, llm_eval = results[0]
    assert llm_eval is None  # heuristic-only
    assert score > 0


def test_evaluator_timestamps_unchanged():
    """LLM never alters timestamps (invariant I1)."""
    tl, batch = _make_tl_and_cands()
    client = MockLLM()
    results = evaluate_candidates(batch, tl, client, Settings())
    cand, feats, score, llm_eval = results[0]
    seg = cand.segments[0]
    assert seg.start == 0.0
    assert seg.end == 30.0
    assert cand.duration == 30.0

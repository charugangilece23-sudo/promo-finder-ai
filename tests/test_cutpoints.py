"""Tests for legal cut points (Phase 3, architecture §11.1)."""

from __future__ import annotations

import os

from promo_finder.models import Episode, Event, EventKind, Scene
from promo_finder.preprocess.timeline import Timeline
from promo_finder.candidates.cutpoints import (
    is_dialogue_safe, legal_starts, legal_ends,
)


def _ep_with_dialogue(dialogue_intervals, path="ep1.txt", duration=100.0):
    events = []
    for i, (ds, de) in enumerate(dialogue_intervals):
        events.append(Event(
            id=f"E001:{i:03d}", episode=1, scene=1,
            kind=EventKind.DIALOGUE, speaker_raw="ALICE", modifiers=[], delivery=[],
            start=ds, end=de, start_raw=f"{ds:.2f}", end_raw=f"{de:.2f}",
            text=f"line {i}",
        ))
    # Add shots/beats at the dialogue edges so cuts are legal there.
    edges = sorted({ds for ds, _ in dialogue_intervals} | {de for _, de in dialogue_intervals})
    for i, e in enumerate(edges):
        events.append(Event(
            id=f"E001:{len(dialogue_intervals)+i:03d}", episode=1, scene=1,
            kind=EventKind.CAMERA, speaker_raw=None, modifiers=[], delivery=[],
            start=e, end=e + 0.5, start_raw=f"{e:.2f}", end_raw=f"{e+0.5:.2f}",
            text=f"shot at {e}",
        ))
    return Episode(
        number=1, path=path,
        scenes=[Scene(number=1, heading=None, start=0.0, end=duration,
                      start_raw="00:00.00", end_raw=f"{duration:.2f}")],
        events=events, duration=duration,
    )


def test_is_dialogue_safe_rejects_inside_dialogue():
    tl = Timeline(_ep_with_dialogue([(10.0, 20.0)]))
    assert is_dialogue_safe(5.0, tl.dialogue_intervals) is True
    assert is_dialogue_safe(10.0, tl.dialogue_intervals) is True  # edge allowed
    assert is_dialogue_safe(15.0, tl.dialogue_intervals) is False  # strictly inside
    assert is_dialogue_safe(20.0, tl.dialogue_intervals) is True  # edge allowed


def test_epsilon_tolerance():
    tl = Timeline(_ep_with_dialogue([(10.0, 20.0)]))
    # epsilon = 0.05: inside zone is (ds+eps, de-eps) = (10.05, 19.95).
    assert is_dialogue_safe(10.04, tl.dialogue_intervals, epsilon=0.05) is True   # just outside zone
    assert is_dialogue_safe(10.06, tl.dialogue_intervals, epsilon=0.05) is False   # inside zone
    assert is_dialogue_safe(19.94, tl.dialogue_intervals, epsilon=0.05) is False   # inside zone
    assert is_dialogue_safe(19.96, tl.dialogue_intervals, epsilon=0.05) is True   # just outside zone


def test_no_legal_cut_inside_dialogue_interval_real_data():
    """AGENTS §1.3 pitfall: Ep 2 dialogue 01:26.80-01:33.00 and
    01:19.20-01:22.50 span shot boundaries; no legal start/end strictly inside."""
    path = os.path.join(os.path.dirname(__file__), os.pardir, "data", "input",
                        "episode-002-Episode 1671704.txt")
    if not os.path.exists(path):
        return
    from promo_finder.ingestion.loader import load_episodes
    from promo_finder.ingestion.parsers.registry import build_default_registry
    reg = build_default_registry()
    ep_raw = load_episodes(os.path.dirname(path))[1]
    text = open(ep_raw.path, encoding="utf-8").read().replace("\r\n", "\n").replace("\r", "\n")
    ep, _ = reg.parse(type("Raw", (), {"path": ep_raw.path, "text": text})())
    tl = Timeline(ep)

    # AGENTS §1.3 pitfall: no legal start/end lies strictly inside any
    # dialogue interval (e.g. the long dialogue spans in Ep 2).
    starts = legal_starts(tl)
    ends = legal_ends(tl)
    for ds, de in tl.dialogue_intervals:
        for s in starts:
            assert not (ds < s < de), f"legal start {s} inside dialogue {ds}-{de}"
        for e in ends:
            assert not (ds < e < de), f"legal end {e} inside dialogue {ds}-{de}"


def test_lead_in_rejects_dead_air_start():
    # A start with no beat beginning within lead_in (1.5s) is not legal.
    ep = Episode(
        number=1, path="ep1.txt",
        scenes=[Scene(number=1, heading=None, start=0.0, end=100.0,
                      start_raw="00:00.00", end_raw="01:40.00")],
        events=[
            Event(id="E001:000", episode=1, scene=1, kind=EventKind.CAMERA,
                  speaker_raw=None, modifiers=[], delivery=[], start=0.0, end=4.0,
                  start_raw="00:00.00", end_raw="00:04.00", text="shot"),
            # next beat starts at 10s (> lead_in 1.5s from t=0)
            Event(id="E001:001", episode=1, scene=1, kind=EventKind.DIALOGUE,
                  speaker_raw="ALICE", modifiers=[], delivery=[], start=10.0, end=12.0,
                  start_raw="00:10.00", end_raw="00:12.00", text="hello"),
        ],
        duration=100.0,
    )
    tl = Timeline(ep)
    # t=0 has a beat at 10s which is NOT within 1.5s -> not a legal start
    assert 0.0 not in legal_starts(tl, lead_in=1.5)

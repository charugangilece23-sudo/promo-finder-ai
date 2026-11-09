"""Tests for the timeline builder (Phase 3)."""

from __future__ import annotations

import os

from promo_finder.models import Episode, Event, EventKind, Scene
from promo_finder.preprocess.timeline import Timeline


def _ep(path="ep1.txt", number=1, continuity="None."):
    return Episode(
        number=number,
        path=path,
        scenes=[Scene(number=1, heading=None, start=0.0, end=100.0,
                      start_raw="00:00.00", end_raw="01:40.00")],
        events=[
            Event(id="E001:000", episode=1, scene=1, kind=EventKind.CAMERA,
                  speaker_raw=None, modifiers=[], delivery=[], start=0.0, end=4.0,
                  start_raw="00:00.00", end_raw="00:04.00", text="shot 1"),
            Event(id="E001:001", episode=1, scene=1, kind=EventKind.DIALOGUE,
                  speaker_raw="ALICE", modifiers=[], delivery=["Angry"],
                  start=2.5, end=4.0, start_raw="00:02.50", end_raw="00:04.00",
                  text="hello"),
            Event(id="E001:002", episode=1, scene=1, kind=EventKind.ACTION,
                  speaker_raw=None, modifiers=[], delivery=[], start=4.0, end=6.0,
                  start_raw="00:04.00", end_raw="00:06.00", text="she leaves"),
        ],
        duration=100.0,
        continuity_notes=continuity,
    )


def test_timeline_splits_shots_and_beats():
    ep = _ep()
    tl = Timeline(ep)
    assert len(tl.events) == 3
    assert len(tl.shots) == 1
    assert len(tl.beats) == 2
    assert tl.duration == 100.0


def test_dialogue_intervals():
    ep = _ep()
    tl = Timeline(ep)
    assert tl.dialogue_intervals == [(2.5, 4.0)]


def test_episode_link_from_continuity_notes():
    ep = _ep(continuity="Picks up directly from Episode 1's cliffhanger.")
    assert Timeline(ep).episode_link is True
    ep2 = _ep(continuity="A brand new story begins.")
    assert Timeline(ep2).episode_link is False


def test_next_prev_beat_links():
    ep = _ep()
    tl = Timeline(ep)
    assert tl.next_beat_start_after(0.0) == 2.5
    assert tl.next_beat_start_after(5.0) is None
    assert tl.prev_beat_end_before(10.0) == 6.0
    assert tl.prev_beat_end_before(1.0) is None


def test_ids_stable_and_sorted():
    path = os.path.join(os.path.dirname(__file__), os.pardir, "data", "input",
                        "episode-001-Episode 1671703.txt")
    if not os.path.exists(path):
        return
    from promo_finder.ingestion.loader import load_episodes
    from promo_finder.ingestion.parsers.registry import build_default_registry
    reg = build_default_registry()
    ep_raw = load_episodes(os.path.dirname(path))[0]
    text = open(ep_raw.path, encoding="utf-8").read().replace("\r\n", "\n").replace("\r", "\n")
    ep, _ = reg.parse(type("Raw", (), {"path": ep_raw.path, "text": text})())
    tl = Timeline(ep)
    ids = [e.id for e in tl.events]
    assert ids == sorted(ids)

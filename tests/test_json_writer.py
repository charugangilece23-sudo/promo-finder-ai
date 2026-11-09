"""Tests for the JSON writer (Phase 3)."""

from __future__ import annotations

import json

from promo_finder.models import Episode, Event, EventKind, Scene, ParseWarning
from promo_finder.reporting.json_writer import episode_to_dict, write_episodes_json


def _episode():
    return Episode(
        number=1,
        path="ep1.txt",
        source_id="1671703",
        logline="A logline.",
        continuity_notes="Picks up from Ep 1.",
        scenes=[
            Scene(number=1, heading="INT. ROOM – DAY", start=0.0, end=10.0,
                  start_raw="00:00.00", end_raw="00:10.00")
        ],
        events=[
            Event(id="E001:000", episode=1, scene=1, kind=EventKind.CAMERA,
                  speaker_raw=None, modifiers=[], delivery=[], start=0.0, end=4.0,
                  start_raw="00:00.00", end_raw="00:04.00", text="a shot"),
            Event(id="E001:001", episode=1, scene=1, kind=EventKind.DIALOGUE,
                  speaker_raw="ALICE", modifiers=[], delivery=["Angry"],
                  start=2.5, end=4.0, start_raw="00:02.50", end_raw="00:04.00",
                  text="hello"),
        ],
        duration=10.0,
        warnings=[ParseWarning(file="ep1.txt", episode=1, block_index=None,
                               code="test_warn", message="a test warning")],
    )


def test_episode_to_dict_round_trip():
    ep = _episode()
    d = episode_to_dict(ep)
    assert d["number"] == 1
    assert d["source_id"] == "1671703"
    assert d["duration"] == 10.0
    assert len(d["events"]) == 2
    assert d["events"][0]["kind"] == "camera"
    assert d["events"][1]["speaker_raw"] == "ALICE"
    assert d["events"][1]["delivery"] == ["Angry"]
    assert len(d["warnings"]) == 1
    assert d["warnings"][0]["code"] == "test_warn"


def test_write_episodes_json(tmp_path):
    ep = _episode()
    path = write_episodes_json(tmp_path, [ep])
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert len(data["episodes"]) == 1
    assert data["episodes"][0]["number"] == 1

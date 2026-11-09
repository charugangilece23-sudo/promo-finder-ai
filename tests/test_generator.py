"""Tests for the candidate generator (Phase 4)."""

from __future__ import annotations

import os

from promo_finder.models import Episode, Event, EventKind
from promo_finder.preprocess.timeline import Timeline
from promo_finder.candidates.generator import generate_candidates


def _beats_and_total(num_beats=6, beat_dur=5.0, gap=1.0):
    """Build dialogue beats separated by gaps, returning (events, total)."""
    events = []
    t = 0.0
    for i in range(num_beats):
        events.append(Event(
            id=f"E001:{i:03d}", episode=1, scene=1,
            kind=EventKind.DIALOGUE, speaker_raw="ALICE", modifiers=[], delivery=[],
            start=t, end=t + beat_dur, start_raw=f"{t:.2f}",
            end_raw=f"{t + beat_dur:.2f}", text=f"line {i}",
        ))
        t += beat_dur + gap
    return events, t


def _make_tl(events, total):
    return Timeline(Episode(
        number=1, path="ep1.txt",
        events=events,
        scenes=[],
        duration=total,
    ))


def test_all_candidates_satisfy_duration():
    events, total = _beats_and_total(num_beats=6, beat_dur=5.0, gap=1.0)
    tl = _make_tl(events, total)
    cands = generate_candidates(tl, min_dur=20.0, max_dur=60.0)
    for c in cands:
        seg = c.segments[0]
        assert 20.0 <= c.duration <= 60.0
        assert seg.end > seg.start
        assert c.duration == seg.end - seg.start


def test_cuts_not_inside_dialogue():
    events, total = _beats_and_total(num_beats=4, beat_dur=5.0, gap=1.0)
    tl = _make_tl(events, total)
    cands = generate_candidates(tl, min_dur=20.0, max_dur=60.0)
    dialogue = [(e.start, e.end) for e in events if e.kind.value == "dialogue"]
    for c in cands:
        s = c.segments[0].start
        e = c.segments[0].end
        for ds, de in dialogue:
            assert not (ds < s < de), f"start {s} inside dialogue {ds}-{de}"
            assert not (ds < e < de), f"end {e} inside dialogue {ds}-{de}"


def test_cand_id_stable_and_unique():
    events, total = _beats_and_total(num_beats=4, beat_dur=10.0, gap=1.0)
    tl = _make_tl(events, total)
    cands = generate_candidates(tl, min_dur=20.0, max_dur=60.0)
    ids = [c.cand_id for c in cands]
    assert len(ids) == len(set(ids))  # unique
    cands2 = generate_candidates(tl, min_dur=20.0, max_dur=60.0)
    assert [c.cand_id for c in cands2] == ids  # deterministic


def test_real_episode_all_candidates_valid():
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
    cands = generate_candidates(tl, min_dur=20.0, max_dur=60.0)
    assert len(cands) > 0
    for c in cands:
        seg = c.segments[0]
        assert 20.0 <= c.duration <= 60.0
        assert seg.start >= 0
        assert seg.end <= ep.duration + 1e-9

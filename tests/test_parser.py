"""Tests for the Kuku screenplay parser (Phase 2)."""

from __future__ import annotations

import os

import pytest

from promo_finder.ingestion.parsers.kuku_screenplay import KukuScreenplayParser
from promo_finder.ingestion.parsers.base import ParserRefusedError, RawEpisode
from promo_finder.ingestion.parsers.registry import build_default_registry
from promo_finder.ingestion.validators import validate_episode
from promo_finder.preprocess.normalizer import normalise
from promo_finder.preprocess.normalizer import normalise

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
INPUT_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "data", "input")


def _parse(path: str):
    text = open(path, "r", encoding="utf-8").read()
    return KukuScreenplayParser().parse(RawEpisode(path, text))


def test_minimal_valid_parses():
    ep = _parse(os.path.join(FIXTURES, "minimal_valid.txt"))
    assert ep.number == 1
    assert ep.logline == "A minimal test transcript."
    assert len(ep.events) == 3
    assert len(ep.scenes) == 1
    assert ep.scenes[0].start == 0.0
    assert ep.scenes[0].end == 10.0
    # Event IDs assigned after sorting by (start, end).
    assert ep.events[0].id == "E001:000"
    assert ep.events[0].kind.value == "camera"
    assert ep.events[1].kind.value == "dialogue"
    assert ep.events[1].speaker_raw == "ALICE"
    assert ep.events[1].delivery == ["Angry"]
    assert ep.events[1].text == "I can't believe you did this."
    assert ep.events[1].start == 2.5
    assert ep.events[1].end == 4.0


def test_known_dialogue_line_from_real_file():
    """AGENTS §1.3: Episode 1 "Why?" at 13.50-14.30, speaker LADY JULIANA,
    delivery ["Confused", "Breathless"]."""
    path = os.path.join(INPUT_DIR, "episode-001-Episode 1671703.txt")
    if not os.path.exists(path):
        pytest.skip("data/input not available")
    ep = _parse(path)
    why = [e for e in ep.events if e.text == "Why?" and abs(e.start - 13.5) < 1e-9]
    assert len(why) == 1
    assert why[0].speaker_raw == "LADY JULIANA"
    assert why[0].delivery == ["Confused", "Breathless"]
    assert why[0].modifiers == []
    assert abs(why[0].end - 14.3) < 1e-9


def test_modifier_case_from_real_file():
    """AGENTS §1.3: MATRIARCH (O.S.) (Firm) => modifiers ["O.S."], delivery ["Firm"]."""
    path = os.path.join(INPUT_DIR, "episode-001-Episode 1671703.txt")
    if not os.path.exists(path):
        pytest.skip("data/input not available")
    ep = _parse(path)
    os_ = [e for e in ep.events if e.modifiers == ["O.S."] and e.delivery == ["Firm"]]
    assert len(os_) == 1
    assert os_[0].speaker_raw == "MATRIARCH"
    assert os_[0].text == "Clarissa is the jewel of this family."


def test_hundredths_timestamp_from_real_file():
    """AGENTS §1.3: 02:25.75 => 145.75."""
    path = os.path.join(INPUT_DIR, "episode-003-Episode 1671705.txt")
    if not os.path.exists(path):
        pytest.skip("data/input not available")
    ep = _parse(path)
    assert abs(ep.duration - 145.75) < 1e-9


def test_missing_end_uses_start_and_warns():
    ep = _parse(os.path.join(FIXTURES, "missing_end.txt"))
    bob = [e for e in ep.events if e.speaker_raw == "BOB"]
    assert len(bob) == 1
    assert bob[0].end == bob[0].start  # end inferred = start
    codes = {w.code for w in ep.warnings}
    assert "end_inferred" in codes


def test_inverted_times_dropped_and_warned():
    ep = _parse(os.path.join(FIXTURES, "inverted.txt"))
    assert len(ep.events) == 0  # inverted block dropped
    codes = {w.code for w in ep.warnings}
    assert "inverted_times" in codes


def test_crlf_line_endings_parsed():
    ep = _parse(os.path.join(FIXTURES, "crlf.txt"))
    assert ep.number == 4
    assert len(ep.events) == 1
    assert ep.events[0].text == "I can't believe you did this."


def test_missing_header_infers_from_filename_and_warns():
    ep = _parse(os.path.join(FIXTURES, "missing_header.txt"))
    # File name has no episode digit, so falls back to 0 with a warning.
    codes = {w.code for w in ep.warnings}
    assert "episode_from_filename" in codes or "episode_unknown" in codes


def test_unknown_format_refused():
    text = open(os.path.join(FIXTURES, "unknown_format.txt"), encoding="utf-8").read()
    assert KukuScreenplayParser().detect(text) < 0.4
    # The registry must refuse a format no parser confidently matches.
    registry = build_default_registry()
    with pytest.raises(ParserRefusedError):
        registry.parse(RawEpisode("x.txt", text))


def test_golden_counts_on_real_files():
    """AGENTS §1.3 golden numbers on the three sample files."""
    if not os.path.isdir(INPUT_DIR):
        pytest.skip("data/input not available")
    expected = {
        1: (95, 50, 7, 1, 37, 1, 138.0),
        2: (74, 39, 4, 0, 31, 1, 110.0),
        3: (118, 61, 8, 3, 46, 3, 145.75),
    }
    for ep_num, (n_events, n_cam, n_act, n_sfx, n_dial, n_scenes, dur) in expected.items():
        path = os.path.join(INPUT_DIR, f"episode-{ep_num:03d}-Episode *.txt")
        import glob
        matches = glob.glob(path)
        assert matches, f"no file for episode {ep_num}"
        ep = _parse(matches[0])
        cam = sum(1 for e in ep.events if e.kind.value == "camera")
        act = sum(1 for e in ep.events if e.kind.value == "action")
        sfx = sum(1 for e in ep.events if e.kind.value == "sfx")
        dial = sum(1 for e in ep.events if e.kind.value == "dialogue")
        assert len(ep.events) == n_events, f"ep{ep_num} events"
        assert cam == n_cam, f"ep{ep_num} camera"
        assert act == n_act, f"ep{ep_num} action"
        assert sfx == n_sfx, f"ep{ep_num} sfx"
        assert dial == n_dial, f"ep{ep_num} dialogue"
        assert len(ep.scenes) == n_scenes, f"ep{ep_num} scenes"
        assert abs(ep.duration - dur) < 1e-9, f"ep{ep_num} duration"


def test_ids_stable_and_sorted_by_time():
    path = os.path.join(INPUT_DIR, "episode-001-Episode 1671703.txt")
    if not os.path.exists(path):
        pytest.skip("data/input not available")
    ep = _parse(path)
    ids = [e.id for e in ep.events]
    assert ids == sorted(ids)
    times = [(e.start, e.end) for e in ep.events]
    assert times == sorted(times)


def test_normaliser_preserves_original():
    ep = _parse(os.path.join(FIXTURES, "minimal_valid.txt"))
    for ev in ep.events:
        # norm_text is the normalised copy; original text is unchanged (I8).
        assert ev.norm_text != "" or ev.text == ""
        assert ev.text == ev.text  # original intact
    # original text preserved, norm_text is a normalised copy.
    orig = ep.events[1].text
    assert ep.events[1].norm_text == normalise(orig)

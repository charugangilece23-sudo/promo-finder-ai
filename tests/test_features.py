"""Tests for deterministic features (Phase 4, architecture §11.4)."""

from __future__ import annotations

from promo_finder.models import Candidate, Episode, Event, EventKind, Segment
from promo_finder.preprocess.timeline import Timeline
from promo_finder.candidates.features import (
    hook_features, hook_score,
    cliffhanger_features, cliffhanger_score,
    emotion_features, emotion_score,
    standalone_features, standalone_det_score,
    duration_features, duration_combined,
    extract_all_features,
)


def _seg(ep=1, start=0.0, end=30.0):
    return Segment(
        episode=ep, start=start, end=end,
        start_event_id="E001:000", end_event_id="E001:005",
        event_ids=["E001:000", "E001:001", "E001:005"],
        transcript=[],
    )


def _cand(seg):
    return Candidate(cand_id="x", segments=[seg], duration=seg.end - seg.start,
                     events_in_window=list(seg.event_ids))


def _tl(events):
    return Timeline(Episode(
        number=1, path="x", events=events, scenes=[], duration=100.0))


def _ev(eid, start, end, kind, speaker=None, delivery=None, text=""):
    return Event(
        id=eid, episode=1, scene=1, kind=kind,
        speaker_raw=speaker, modifiers=[],
        delivery=delivery or [], start=start, end=end,
        start_raw=f"{start:.2f}", end_raw=f"{end:.2f}", text=text,
    )


def test_hook_high_when_speech_within_1s_and_shock():
    events = [
        _ev("E001:000", 0.0, 1.0, EventKind.CAMERA, text="shot"),
        _ev("E001:001", 0.5, 2.0, EventKind.DIALOGUE, speaker="ALICE",
            delivery=["Outraged"], text="You knew this before I walked in!"),
    ]
    tl = _tl(events)
    seg = _seg(start=0.0, end=30.0)
    c = _cand(seg)
    hf = hook_features(c, tl, {"delivery_intensities": {"Outraged": 0.95},
                               "shock_terms": ["knew"],
                               "second_person_terms": ["you"]})
    assert hf.speech_within_1s == 1.0
    assert hf.delivery_intensity == 0.95
    assert hf.shock_hits > 0
    assert hf.second_person > 0
    assert hook_score(hf) > 0.7


def test_hook_low_for_quiet_opening():
    events = [
        _ev("E001:000", 0.0, 12.0, EventKind.CAMERA, text="a long establishing shot"),
    ]
    tl = _tl(events)
    seg = _seg(start=0.0, end=30.0)
    c = _cand(seg)
    hf = hook_features(c, tl, {"delivery_intensities": {},
                               "shock_terms": [], "second_person_terms": []})
    assert hf.speech_within_1s == 0.0
    assert hf.quiet_opening_penalty == 1.0
    assert hook_score(hf) < 0.4


def test_cliffhanger_high_on_question_with_next_beat():
    events = [
        _ev("E001:000", 25.0, 29.0, EventKind.DIALOGUE, speaker="ALICE",
            delivery=["Gasping"], text="Why?"),
        _ev("E001:001", 30.0, 32.0, EventKind.DIALOGUE, speaker="BOB",
            delivery=["Cold"], text="Because."),
    ]
    tl = _tl(events)
    seg = _seg(start=10.0, end=29.0)
    c = _cand(seg)
    cf = cliffhanger_features(c, tl, {"cliffhanger_terms": ["?"],
                                      "resolution_terms": []})
    assert cf.final_is_question_or_ellipsis == 1.0
    assert cf.next_beat_cut_off == 1.0
    assert cliffhanger_score(cf) > 0.6


def test_cliffhanger_low_on_calm_resolution():
    events = [
        _ev("E001:000", 25.0, 29.0, EventKind.DIALOGUE, speaker="ALICE",
            delivery=["Calm"], text="It is settled. Peace at last."),
    ]
    tl = _tl(events)
    seg = _seg(start=10.0, end=29.0)
    c = _cand(seg)
    cf = cliffhanger_features(c, tl, {"cliffhanger_terms": [],
                                      "resolution_terms": ["peace", "settled"]})
    assert cf.calm_resolution_penalty == 1.0
    assert cliffhanger_score(cf) < 0.5


def test_emotion_high_with_alternating_speakers():
    events = [
        _ev("E001:000", 0.0, 5.0, EventKind.DIALOGUE, speaker="ALICE",
            delivery=["Outraged"], text="You betrayed me!"),
        _ev("E001:001", 5.0, 10.0, EventKind.DIALOGUE, speaker="BOB",
            delivery=["Cold"], text="I had to."),
        _ev("E001:002", 10.0, 15.0, EventKind.DIALOGUE, speaker="ALICE",
            delivery=["Horrified"], text="How could you?"),
    ]
    tl = _tl(events)
    seg = _seg(start=0.0, end=30.0)
    c = _cand(seg)
    ef = emotion_features(c, tl, {"delivery_intensities": {
        "Outraged": 0.95, "Cold": 0.4, "Horrified": 0.9}})
    assert ef.speaker_alternations >= 0.5
    assert ef.peak_delivery_intensity == 0.95
    assert emotion_score(ef) > 0.6


def test_standalone_proxy_two_speakers():
    events = [
        _ev("E001:000", 0.0, 5.0, EventKind.DIALOGUE, speaker="ALICE", text="Hello"),
        _ev("E001:001", 5.0, 10.0, EventKind.DIALOGUE, speaker="BOB", text="Hi"),
    ]
    tl = _tl(events)
    seg = _seg(start=0.0, end=30.0)
    c = _cand(seg)
    sf = standalone_features(c, tl)
    assert sf.distinct_speakers == 1.0  # 2 speakers / 2
    assert standalone_det_score(sf) > 0.7


def test_standalone_pronoun_only_opener_penalised():
    events = [
        _ev("E001:000", 0.0, 5.0, EventKind.DIALOGUE, speaker="ALICE", text="Why?"),
        _ev("E001:001", 5.0, 10.0, EventKind.DIALOGUE, speaker="BOB", text="Yes."),
    ]
    tl = _tl(events)
    seg = _seg(start=0.0, end=30.0)
    c = _cand(seg)
    sf = standalone_features(c, tl)
    assert sf.opening_not_pronoun_only == 0.0


def test_duration_soft_plateau():
    for dur, expected_full in [(25.0, True), (30.0, True), (45.0, True),
                               (20.0, False), (60.0, False)]:
        seg = _seg(start=0.0, end=dur)
        c = _cand(seg)
        df = duration_features(c)
        assert df.in_hard_range is True
        score = duration_combined(df)
        if expected_full:
            assert score == 1.0, f"dur {dur} should be full"
        else:
            assert score < 1.0


def test_extract_all_returns_all_dimensions():
    events = [
        _ev("E001:000", 0.0, 5.0, EventKind.DIALOGUE, speaker="ALICE",
            delivery=["Outraged"], text="You knew!"),
        _ev("E001:001", 6.0, 11.0, EventKind.DIALOGUE, speaker="BOB",
            delivery=["Cold"], text="Why?"),
    ]
    tl = _tl(events)
    seg = _seg(start=0.0, end=30.0)
    c = _cand(seg)
    out = extract_all_features(c, tl,
                               {"delivery_intensities": {"Outraged": 0.95, "Cold": 0.4},
                                "shock_terms": ["knew"],
                                "second_person_terms": ["you"],
                                "cliffhanger_terms": ["?"],
                                "resolution_terms": []})
    assert set(out.keys()) == {"hook", "cliffhanger", "emotion", "coherence",
                               "standalone", "duration"}
    assert 0.0 <= out["hook"]["score"] <= 1.0
    assert 0.0 <= out["cliffhanger"]["score"] <= 1.0

"""Tests for input validators (Phase 2)."""

from __future__ import annotations

from promo_finder.models import Episode, Event, EventKind, Scene
from promo_finder.ingestion.validators import validate_episode, validate_episodes


def _event(eid, start, end, kind="dialogue", text="hello world"):
    return Event(
        id=eid,
        episode=1,
        scene=1,
        kind=EventKind(kind),
        speaker_raw=None,
        modifiers=[],
        delivery=[],
        start=start,
        end=end,
        start_raw=f"{start:.2f}",
        end_raw=f"{end:.2f}",
        text=text,
    )


def _episode(events, scenes=None, number=1, path="ep1.txt"):
    return Episode(
        number=number,
        path=path,
        scenes=scenes or [Scene(number=1, heading=None, start=0.0, end=100.0,
                               start_raw="00:00.00", end_raw="01:40.00")],
        events=events,
        duration=100.0,
    )


def test_inverted_times_warned_not_dropped():
    ep = _episode([_event("E001:000", 5.0, 2.0)])
    warns = validate_episode(ep)
    codes = {w.code for w in warns}
    assert "inverted_times" in codes
    # Event is not dropped by the validator.
    assert len(ep.events) == 1


def test_out_of_bounds_warned():
    ep = _episode([_event("E001:000", 150.0, 160.0)])
    warns = validate_episode(ep)
    assert any(w.code == "out_of_bounds" for w in warns)


def test_in_bounds_no_warning():
    ep = _episode([_event("E001:000", 10.0, 20.0)])
    warns = validate_episode(ep)
    assert not any(w.code in ("out_of_bounds", "inverted_times") for w in warns)


def test_suspicious_dialogue_speed():
    ep = _episode([_event("E001:000", 0.0, 1.0, text="a " * 100)])  # 100 words/sec
    warns = validate_episode(ep)
    assert any(w.code == "suspicious_timing" for w in warns)


def test_duplicate_episode_numbers():
    ep1 = _episode([], number=1, path="a.txt")
    ep2 = _episode([], number=1, path="b.txt")
    warns = validate_episodes([ep1, ep2])
    assert any(w.code == "duplicate_episode" for w in warns)


def test_numbering_gap():
    ep1 = _episode([], number=1, path="a.txt")
    ep3 = _episode([], number=3, path="c.txt")
    warns = validate_episodes([ep1, ep3])
    assert any(w.code == "numbering_gap" for w in warns)


def test_no_warnings_for_clean_episode():
    ep = _episode([_event("E001:000", 10.0, 12.0, text="hello world")])
    warns = validate_episode(ep)
    assert warns == []

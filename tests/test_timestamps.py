"""Tests for the timestamp parser (Phase 2)."""

from __future__ import annotations

import pytest

from promo_finder.ingestion.timestamps import (
    ParsedTimestamp,
    TimestampError,
    format_seconds,
    parse_timestamp,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("00:13.50", ParsedTimestamp(raw="00:13.50", seconds=13.5)),
        ("02:25.75", ParsedTimestamp(raw="02:25.75", seconds=145.75)),
        ("00:00.00", ParsedTimestamp(raw="00:00.00", seconds=0.0)),
        ("01:00:00.00", ParsedTimestamp(raw="01:00:00.00", seconds=3600.0)),
        ("01:02:03.45", ParsedTimestamp(raw="01:02:03.45", seconds=3723.45)),
        ("90.5", ParsedTimestamp(raw="90.5", seconds=90.5)),
        ("5", ParsedTimestamp(raw="5", seconds=5.0)),
    ],
)
def test_parse_timestamp_accepted_forms(raw, expected):
    assert parse_timestamp(raw) == expected


def test_parse_timestamp_keeps_raw_string():
    ts = parse_timestamp("02:25.75")
    assert ts.raw == "02:25.75"
    assert ts.seconds == 145.75


@pytest.mark.parametrize("bad", ["", "   ", "ab:cd.ef", "12:70.00", None])
def test_parse_timestamp_rejects_garbage(bad):
    with pytest.raises(TimestampError):
        parse_timestamp(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("raw,expected", [("00:13", 13.0), ("00:59", 59.0)])
def test_parse_timestamp_minutes_seconds(raw, expected):
    assert parse_timestamp(raw).seconds == expected


def test_format_seconds():
    assert format_seconds(13.5) == "00:13.50"
    assert format_seconds(145.75) == "02:25.75"
    assert format_seconds(0) == "00:00.00"
    assert format_seconds(3661.5) == "61:01.50"

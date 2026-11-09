"""Tests for the text normaliser (Phase 2)."""

from __future__ import annotations

from promo_finder.preprocess.normalizer import normalise


def test_nfkc_and_dash_unification():
    assert normalise("Int. Cathedral – Day") == "Int. Cathedral - Day"
    assert normalise("Int. Cathedral — Day") == "Int. Cathedral - Day"


def test_quote_and_ellipsis_unification():
    assert normalise('He said "hello"') == 'He said "hello"'
    assert normalise("Wait…") == "Wait..."
    assert normalise("Wait… ") == "Wait..."


def test_whitespace_collapse():
    assert normalise("a   b\tc\nd") == "a b c d"


def test_original_never_mutated():
    original = 'He said "wait…"'
    normalise(original)
    # normalise returns a new string; no in-place mutation is possible in Python
    # for str, but the function must not alter the caller's reference.
    assert original == 'He said "wait…"'


def test_empty_string():
    assert normalise("") == ""
    assert normalise("   ") == ""

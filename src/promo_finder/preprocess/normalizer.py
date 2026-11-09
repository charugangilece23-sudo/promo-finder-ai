"""Text normalisation (architecture §8.2).

Produces a ``norm_text`` copy used only for matching. The original ``text``
is never altered (invariant I8).
"""

from __future__ import annotations

import unicodedata


def normalise(text: str) -> str:
    """Return a normalised copy of ``text`` for matching only.

    Steps: NFKC, unify dashes/quotes/ellipsis, collapse whitespace. The
    original string is preserved by the caller.
    """
    if not text:
        return ""
    # NFKC compatibility decomposition + composition.
    s = unicodedata.normalize("NFKC", text)
    # Unify dashes to hyphen.
    s = s.replace("\u2012", "-").replace("\u2013", "-").replace("\u2014", "-")
    s = s.replace("\u2212", "-")
    # Unify ellipsis.
    s = s.replace("\u2026", "...")
    # Unify quotes to straight.
    s = s.replace("\u2018", "'").replace("\u2019", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    # Collapse whitespace.
    s = " ".join(s.split())
    return s

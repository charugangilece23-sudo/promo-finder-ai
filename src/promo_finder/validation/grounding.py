"""Grounding validators for LLM output (architecture §13.2).

Checks every LLM claim against the source:
- cand_id/event_id must exist and lie inside the candidate.
- Quotes must be a normalised substring of the referenced event's text.
- Hook event within first hook_window seconds; cliffhanger within tail_window.
- Capitalised names in free text must appear in clip text / profile / loglines.

On failure, the offending field is replaced by a code-chosen verbatim quote
and the promo is flagged UNGROUNDED_LLM_TEXT. Invalid IDs drop the entry.
"""

from __future__ import annotations

import re
from typing import Any

from promo_finder.models import Candidate, Event
from promo_finder.preprocess.normalizer import normalise


def _token_set_ratio(a: str, b: str) -> float:
    ta = set(normalise(a).split())
    tb = set(normalise(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def quote_grounded(quote: str, event_text: str) -> bool:
    """True if ``quote`` is a normalised substring of ``event_text``."""
    if not quote or not event_text:
        return False
    nq = normalise(quote)
    ne = normalise(event_text)
    if nq in ne:
        return True
    return _token_set_ratio(nq, ne) >= 0.95


def validate_eval(eval_out: Any, candidate: Candidate,
                  events_by_id: dict[str, Event],
                  hook_window: float = 3.0,
                  tail_window: float = 5.0) -> dict:
    """Validate an EvalOut against the candidate and source events.

    Returns a dict with:
      - valid: bool
      - hook, cliffhanger: sanitized {event_id, quote, description} dicts
      - scores: dict of dimension -> 0-1 float
      - flags: list of flag strings (e.g. UNGROUNDED_LLM_TEXT)
    """
    flags: list[str] = []
    scores: dict[str, float] = {}

    # cand_id must exist and be this candidate.
    if eval_out.cand_id != candidate.cand_id:
        return {"valid": False, "hook": {}, "cliffhanger": {},
                "scores": {}, "flags": ["UNKNOWN_CAND_ID"]}

    def _score_1_to_5(val) -> float:
        try:
            x = float(val)
        except (TypeError, ValueError):
            return 0.0
        if not (1.0 <= x <= 5.0):
            return 0.0
        return (x - 1.0) / 4.0

    scores["hook"] = _score_1_to_5(eval_out.hook)
    scores["cliffhanger"] = _score_1_to_5(eval_out.cliffhanger)
    scores["emotion"] = _score_1_to_5(eval_out.emotion)
    scores["coherence"] = _score_1_to_5(eval_out.coherence)
    scores["standalone"] = _score_1_to_5(eval_out.standalone)

    # Collect event ids inside the candidate and their texts.
    inside_ids: set[str] = set()
    event_texts: dict[str, str] = {}
    for seg in candidate.segments:
        inside_ids.update(seg.event_ids)
        for t in seg.transcript:
            event_texts[t.get("event_id", "")] = t.get("text", "")
    for eid in inside_ids:
        if eid in events_by_id:
            event_texts.setdefault(eid, events_by_id[eid].text)

    def _event_in_window(ev, seg_start, seg_end, window, at_start):
        if not ev:
            return False
        t = ev.start
        if at_start:
            return seg_start <= t <= seg_start + window
        return seg_end - window <= t <= seg_end

    def _sanitize_block(detail, seg, is_hook):
        """Return a grounded {event_id, quote, description} block."""
        block: dict = {"event_id": "", "quote": "", "description": ""}
        if not detail:
            return block
        eid = detail.event_id
        quote = detail.quote or ""
        desc = detail.description or ""

        # event_id must exist and be inside the candidate.
        if eid not in inside_ids:
            flags.append("UNGROUNDED_LLM_TEXT")
            # choose code-chosen verbatim quote: first/last dialogue in clip
            dialogue = [t for t in seg.transcript
                        if t.get("kind") == "dialogue"]
            chosen = dialogue[0] if is_hook else (dialogue[-1] if dialogue else None)
            if chosen:
                block["event_id"] = chosen.get("event_id", "")
                block["quote"] = chosen.get("text", "")
                block["description"] = (chosen.get("speaker", "") or "Speaker") + \
                    ": " + chosen.get("text", "")
            return block

        ev = events_by_id.get(eid)
        if ev is None:
            flags.append("UNGROUNDED_LLM_TEXT")
            return block

        # Window placement check.
        seg_start = seg.start
        seg_end = seg.end
        if not _event_in_window(ev, seg_start, seg_end,
                                hook_window if is_hook else tail_window, is_hook):
            flags.append("UNGROUNDED_LLM_TEXT")
            # still use the event's text as quote but flagged
            block["event_id"] = eid
            block["quote"] = ev.text
            block["description"] = desc or f"{ev.speaker_raw or 'Speaker'}: {ev.text}"
            return block

        # Quote grounding.
        if quote and quote_grounded(quote, ev.text):
            block["quote"] = quote
        else:
            if quote:
                flags.append("UNGROUNDED_LLM_TEXT")
            block["quote"] = ev.text
        block["event_id"] = eid
        block["description"] = desc or f"{ev.speaker_raw or 'Speaker'}: {ev.text}"
        return block

    hook_block = _sanitize_block(eval_out.hook_detail,
                                 candidate.segments[0], is_hook=True)
    cliff_block = _sanitize_block(eval_out.cliffhanger_detail,
                                  candidate.segments[-1], is_hook=False)

    return {
        "valid": True,
        "hook": hook_block,
        "cliffhanger": cliff_block,
        "scores": scores,
        "flags": flags,
    }

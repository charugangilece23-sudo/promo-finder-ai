"""Parser for the observed Kuku screenplay format (architecture §8.1).

Format (verified against the real transcripts):

    EPISODE NUMBER: Episode 1
    EPISODE LOGLINE: <free text>
    CONTINUITY NOTES: <free text>

    --- SCRIPT START ---

    SCENE 01
    Scene heading: INT. CATHEDRAL – DAY
    Scene start: 00:00.00
    Scene end: 02:18.00

    Actions and dialogue:

    **CAMERA:**
    Start: (00:00.00) | End: (00:04.80)
    <shot description>

    **LADY JULIANA (Confused, Breathless):**
    Start: (00:13.50) | End: (00:14.30)
    "Why?"

    --- SCRIPT END ---

Entry blocks overlap in time; CAMERA blocks are shots, everything else is a
beat. Speaker names are inconsistent and are never used as keys.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from promo_finder.models import (
    Event,
    EventKind,
    Episode,
    ParseWarning,
    Scene,
)
from promo_finder.ingestion.timestamps import ParsedTimestamp, parse_timestamp
from promo_finder.ingestion.parsers.base import BaseParser, RawEpisode
from promo_finder.preprocess.normalizer import normalise

logger = logging.getLogger("promo_finder.ingestion.parsers.kuku_screenplay")

# Configurable modifier parentheticals (arch §8.1 / AGENTS §1.3).
MODIFIERS = {"O.S.", "V.O.", "Off-screen", "Off screen", "CONT'D"}

_LABEL_TO_KIND = {
    "CAMERA": EventKind.CAMERA,
    "ACTION": EventKind.ACTION,
    "SOUND FX": EventKind.SFX,
}

_HEADER_RE = re.compile(
    r"^(EPISODE NUMBER|EPISODE LOGLINE|CONTINUITY NOTES)\s*:\s*(.*)$",
    re.IGNORECASE,
)
_SCRIPT_START_RE = re.compile(r"^--- SCRIPT START ---\s*$", re.IGNORECASE)
_SCRIPT_END_RE = re.compile(r"^--- SCRIPT END ---\s*$", re.IGNORECASE)
_SCENE_RE = re.compile(r"^SCENE\s+(\d+)\s*$", re.IGNORECASE)
_SCENE_HEADING_RE = re.compile(r"^Scene heading:\s*(.*)$", re.IGNORECASE)
_SCENE_START_RE = re.compile(r"^Scene start:\s*(.*)$", re.IGNORECASE)
_SCENE_END_RE = re.compile(r"^Scene end:\s*(.*)$", re.IGNORECASE)
_LABEL_RE = re.compile(r"^\*\*(.+?)\*\*:?\s*$")
_TIMESTAMP_LINE_RE = re.compile(
    r"^Start:\s*\((.+?)\s*\)\s*\|\s*End:\s*\((.+?)\s*\)\s*$",
    re.IGNORECASE,
)
_START_ONLY_RE = re.compile(
    r"^Start:\s*\((.+?)\s*\)\s*$",
    re.IGNORECASE,
)

DETECT_THRESHOLD = 0.4


def _strip_quotes(text: str) -> str:
    """Strip surrounding straight/curly quotes from dialogue text."""
    text = text.strip()
    if len(text) >= 2 and text[0] in "\"'" and text[-1] in "\"'":
        return text[1:-1].strip()
    return text


def _split_annotations(label: str) -> tuple[str, list[str], list[str]]:
    """Split a speaker label into the base name, modifiers, and delivery tags.

    Parenthetical groups after the name are divided into ``modifiers``
    (``O.S.``, ``V.O.``, ``Off-screen``, …) and ``delivery`` tags (everything
    else). Speaker strings are never used as keys downstream.
    """
    name = label
    modifiers: list[str] = []
    delivery: list[str] = []

    parens = re.findall(r"\(([^)]*)\)", label)
    if parens:
        # Remove all parenthetical groups from the name.
        name = re.sub(r"\s*\([^)]*\)", "", label).strip()
        for group in parens:
            parts = [p.strip() for p in group.split(",") if p.strip()]
            for part in parts:
                if part in MODIFIERS:
                    modifiers.append(part)
                else:
                    delivery.append(part)

    return name, modifiers, delivery


_LABEL_TO_KIND = {
    "CAMERA": EventKind.CAMERA,
    "ACTION": EventKind.ACTION,
    "SOUND FX": EventKind.SFX,
}


def _kind_for_label(label: str) -> EventKind:
    base = label.split("(")[0].strip().upper()
    return _LABEL_TO_KIND.get(base, EventKind.DIALOGUE)


def _build_warning(
    file: str,
    episode: int | None,
    code: str,
    message: str,
    block_index: int | None = None,
) -> ParseWarning:
    return ParseWarning(
        file=file,
        episode=episode,
        block_index=block_index,
        code=code,
        message=message,
    )


class KukuScreenplayParser(BaseParser):
    name = "kuku_screenplay"

    def detect(self, text: str) -> float:
        """Confidence that this text is a Kuku screenplay transcript."""
        score = 0.0
        if "--- SCRIPT START ---" in text:
            score += 0.4
        if re.search(r"EPISODE NUMBER\s*:", text, re.IGNORECASE):
            score += 0.3
        if re.search(r"^\*\*.+\*\*:", text, re.MULTILINE):
            score += 0.2
        if re.search(r"Start:\s*\(.*?\)\s*\|\s*End:\s*\(.*?\)", text):
            score += 0.3
        return min(score, 1.0)

    def parse(self, raw: RawEpisode) -> Episode:
        file = raw.path
        text = raw.text
        # Normalise line endings so CRLF files parse identically to LF files.
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        warnings: list[ParseWarning] = []

        episode_number: int | None = None
        logline: str | None = None
        continuity_notes: str | None = None

        # --- Header ---
        for line in text.splitlines():
            m = _HEADER_RE.match(line)
            if not m:
                continue
            key = m.group(1).upper()
            value = m.group(2).strip()
            if key == "EPISODE NUMBER":
                m2 = re.search(r"(\d+)", value)
                episode_number = int(m2.group(1)) if m2 else None
                if episode_number is None:
                    warnings.append(
                        _build_warning(file, None, "missing_episode_number",
                                       "EPISODE NUMBER header has no digit")
                    )
            elif key == "EPISODE LOGLINE":
                logline = value
            elif key == "CONTINUITY NOTES":
                continuity_notes = value

        # Fall back to filename if header missing.
        if episode_number is None:
            m = re.search(r"episode[-_]?(\d+)", raw.path, re.IGNORECASE)
            if m:
                episode_number = int(m.group(1))
                warnings.append(
                    _build_warning(file, episode_number, "episode_from_filename",
                                   "No EPISODE NUMBER header; inferred from file name")
                )
            else:
                warnings.append(
                    _build_warning(file, None, "episode_unknown",
                                   "Could not determine episode number")
                )
                episode_number = 0

        # --- Body ---
        lines = text.splitlines()
        scenes: list[Scene] = []
        raw_events: list[dict] = []

        in_script = False
        current_scene: Optional[Scene] = None
        scene_number = 0

        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]

            if _SCRIPT_START_RE.match(line):
                in_script = True
                i += 1
                continue
            if _SCRIPT_END_RE.match(line):
                in_script = False
                i += 1
                continue
            if not in_script:
                i += 1
                continue

            # Scene header.
            m = _SCENE_RE.match(line)
            if m:
                scene_number = int(m.group(1))
                # Read the following Scene heading/start/end lines.
                j = i + 1
                heading = None
                start_raw = ""
                end_raw = ""
                while j < n and not _SCENE_RE.match(lines[j]) and lines[j].strip() != "":
                    hm = _SCENE_HEADING_RE.match(lines[j])
                    if hm:
                        heading = hm.group(1).strip()
                    sm = _SCENE_START_RE.match(lines[j])
                    if sm:
                        start_raw = sm.group(1).strip()
                    em = _SCENE_END_RE.match(lines[j])
                    if em:
                        end_raw = em.group(1).strip()
                    j += 1
                start_s = _parse_or_warn(start_raw, file, episode_number, warnings, "scene_start")
                end_s = _parse_or_warn(end_raw, file, episode_number, warnings, "scene_end")
                current_scene = Scene(
                    number=scene_number,
                    heading=heading,
                    start=start_s.seconds if start_s else 0.0,
                    end=end_s.seconds if end_s else 0.0,
                    start_raw=start_raw,
                    end_raw=end_raw,
                )
                scenes.append(current_scene)
                i = j
                continue

            # Entry block label.
            m = _LABEL_RE.match(line)
            if m:
                # The source writes **LABEL:** with the colon inside the
                # closing asterisks, so strip a trailing colon.
                label = m.group(1).strip().removesuffix(":")
                block_index = len(raw_events)
                # Next line should be the Start:/End: timestamp line.
                if i + 1 >= n:
                    warnings.append(
                        _build_warning(file, episode_number, "missing_timestamp_line",
                                       f"Block '{label}' has no Start/End line",
                                       block_index=block_index)
                    )
                    i += 1
                    continue
                ts_line = lines[i + 1]
                tm = _TIMESTAMP_LINE_RE.match(ts_line)
                end_inferred = False
                if not tm:
                    sm = _START_ONLY_RE.match(ts_line)
                    if not sm:
                        warnings.append(
                            _build_warning(file, episode_number, "invalid_timestamp_line",
                                           f"Block '{label}' has unparseable Start/End line",
                                           block_index=block_index)
                        )
                        i += 2
                        continue
                    start_raw = sm.group(1).strip()
                    end_raw = start_raw
                    end_inferred = True
                else:
                    start_raw = tm.group(1).strip()
                    end_raw = tm.group(2).strip()
                start_p = _parse_or_warn(start_raw, file, episode_number, warnings,
                                         "block_start", block_index)
                end_p = _parse_or_warn(end_raw, file, episode_number, warnings,
                                       "block_end", block_index)

                # Collect text lines until blank / next ** / next SCENE.
                j = i + 2
                text_lines: list[str] = []
                while j < n:
                    nl = lines[j]
                    if nl.strip() == "":
                        break
                    if _LABEL_RE.match(nl) or _SCENE_RE.match(nl):
                        break
                    text_lines.append(nl)
                    j += 1
                body = "\n".join(text_lines).strip()
                dialogue_text = _strip_quotes(body)

                kind = _kind_for_label(label)
                speaker_raw = None
                modifiers: list[str] = []
                delivery: list[str] = []
                if kind == EventKind.DIALOGUE:
                    speaker_raw, modifiers, delivery = _split_annotations(label)
                elif label.upper() == "SOUND FX":
                    speaker_raw = None

                # Validate times.
                if start_p is None or end_p is None:
                    warnings.append(
                        _build_warning(file, episode_number, "missing_times",
                                       f"Block '{label}' dropped: missing Start/End",
                                       block_index=block_index)
                    )
                    i = j
                    continue
                if end_p.seconds < start_p.seconds:
                    warnings.append(
                        _build_warning(file, episode_number, "inverted_times",
                                       f"Block '{label}' end {end_p.raw} before start {start_p.raw}",
                                       block_index=block_index)
                    )
                    i = j
                    continue
                if end_p.seconds == start_p.seconds:
                    warnings.append(
                        _build_warning(file, episode_number, "end_inferred",
                                       f"Block '{label}' has zero duration; end=start",
                                       block_index=block_index)
                    )

                raw_events.append(
                    {
                        "order": len(raw_events),
                        "episode": episode_number,
                        "scene": current_scene.number if current_scene else None,
                        "kind": kind,
                        "speaker_raw": speaker_raw,
                        "modifiers": modifiers,
                        "delivery": delivery,
                        "start": start_p.seconds,
                        "end": end_p.seconds,
                        "start_raw": start_p.raw,
                        "end_raw": end_p.raw,
                        "text": dialogue_text,
                    }
                )
                i = j
                continue

            i += 1

        # --- Sort events and assign stable IDs ---
        # Sort by (start, end, original order). IDs reflect timeline order.
        raw_events.sort(key=lambda ev: (ev["start"], ev["end"], ev["order"]))

        events: list[Event] = []
        for idx, ev in enumerate(raw_events):
            events.append(
                Event(
                    id=f"E{ev['episode']:03d}:{idx:03d}",
                    episode=ev["episode"],
                    scene=ev["scene"],
                    kind=ev["kind"],
                    speaker_raw=ev["speaker_raw"],
                    modifiers=ev["modifiers"],
                    delivery=ev["delivery"],
                    start=ev["start"],
                    end=ev["end"],
                    start_raw=ev["start_raw"],
                    end_raw=ev["end_raw"],
                    text=ev["text"],
                    norm_text=normalise(ev["text"]),
                )
            )

        # Duration from last event end, else scene end, else 0.
        duration = 0.0
        if events:
            duration = max(ev.end for ev in events)
        elif scenes:
            duration = max(sc.end for sc in scenes)

        # Missing scene block ⇒ one synthetic scene.
        if not scenes and events:
            warnings.append(
                _build_warning(file, episode_number, "synthetic_scene",
                               "No SCENE block found; created one synthetic scene")
            )
            scenes.append(Scene(
                number=1,
                heading=None,
                start=0.0,
                end=duration,
                start_raw="",
                end_raw="",
            ))

        # Episode bounds: warn if an event is not contained in ANY scene.
        for ev in events:
            in_any_scene = False
            for sc in scenes:
                if sc.start - 1e-9 <= ev.start and ev.end <= sc.end + 1e-9:
                    in_any_scene = True
                    break
            if not in_any_scene and scenes:
                scene_min = min(sc.start for sc in scenes)
                scene_max = max(sc.end for sc in scenes)
                if ev.start < scene_min - 1e-6 or ev.end > scene_max + 1e-6:
                    warnings.append(
                        _build_warning(file, episode_number, "event_out_of_scene",
                                       f"Event {ev.id} ({ev.start_raw}-{ev.end_raw}) "
                                       f"outside episode bounds {scene_min}-{scene_max}",
                                       block_index=None)
                    )

        return Episode(
            number=episode_number,
            source_id=_source_id_from_path(raw.path),
            path=raw.path,
            logline=logline,
            continuity_notes=continuity_notes,
            scenes=scenes,
            events=events,
            duration=duration,
            warnings=warnings,
        )


def _parse_or_warn(
    raw: str,
    file: str,
    episode: int | None,
    warnings: list[ParseWarning],
    code: str,
    block_index: int | None = None,
) -> Optional[ParsedTimestamp]:
    try:
        return parse_timestamp(raw)
    except Exception as exc:  # noqa: BLE001 - turn into warning
        warnings.append(
            _build_warning(file, episode, code,
                           f"Invalid timestamp {raw!r}: {exc}",
                           block_index=block_index)
        )
        return None


def _source_id_from_path(path: str) -> str | None:
    """Extract the long numeric id from a file name like episode-001-Episode 1671703.txt."""
    m = re.search(r"Episode\s+(\d+)", path)
    return m.group(1) if m else None

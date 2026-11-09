"""File loader for transcript packs.

Globs ``*.txt`` (pattern from config), reads each file as UTF-8 (with a
``utf-8-sig`` then ``latin-1`` fallback that emits a warning), and returns
:class:`RawEpisode` objects sorted by parsed episode number — never by file
name (FR-01).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("promo_finder.ingestion.loader")

_EPISODE_RE = re.compile(r"EPISODE NUMBER:\s*Episode\s*(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class RawEpisode:
    """A raw transcript file before parsing."""

    path: str
    text: str


def _read_text(path: Path) -> tuple[str, list[str]]:
    """Read a file, trying utf-8-sig then latin-1 with warnings.

    Returns the text and a list of warning messages.
    """
    warnings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        warnings.append(f"{path.name}: not valid UTF-8; fell back to latin-1")
        text = path.read_text(encoding="latin-1")
    return text, warnings


def _episode_number_from_header(text: str) -> int | None:
    m = _EPISODE_RE.search(text)
    return int(m.group(1)) if m else None


def _episode_number_from_filename(path: Path) -> int | None:
    m = re.search(r"episode[-_]?(\d+)", path.stem, re.IGNORECASE)
    return int(m.group(1)) if m else None


def load_episodes(input_dir: str | Path, glob_pattern: str = "*.txt") -> list[RawEpisode]:
    """Load all transcript files from a directory, sorted by episode number.

    Args:
        input_dir: directory containing ``*.txt`` transcripts.
        glob_pattern: glob pattern to match transcript files.

    Returns:
        A list of :class:`RawEpisode` sorted by parsed episode number. Files
        whose episode number cannot be determined are placed last, sorted by
        file name.
    """
    input_dir = Path(input_dir)
    paths = sorted(input_dir.glob(glob_pattern))

    episodes: list[RawEpisode] = []
    parsed: list[tuple[int, str, RawEpisode]] = []
    unparsed: list[tuple[str, RawEpisode]] = []

    for path in paths:
        if not path.is_file():
            continue
        text, warnings = _read_text(path)
        ep = _episode_number_from_header(text)
        if ep is None:
            ep = _episode_number_from_filename(path)
            if ep is None:
                logger.warning(
                    "Could not determine episode number for %s; sorting by name",
                    path.name,
                )
                unparsed.append((path.name, RawEpisode(str(path), text)))
                continue
            logger.warning(
                "%s: no EPISODE NUMBER header; inferred %d from file name",
                path.name,
                ep,
            )
        parsed.append((ep, path.name, RawEpisode(str(path), text)))

    parsed.sort(key=lambda item: (item[0], item[1]))
    unparsed.sort(key=lambda item: item[0])

    for ep, _name, ep_obj in parsed:
        episodes.append(ep_obj)
    for _name, ep_obj in unparsed:
        episodes.append(ep_obj)

    return episodes

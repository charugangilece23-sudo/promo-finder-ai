"""Parser protocol and registry (architecture §8.1).

New transcript formats are supported by adding a new :class:`FormatParser`
implementation and registering it — no rewrite of existing parsers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from promo_finder.models import Episode, ParseWarning


class RawEpisode:
    """Minimal raw-episode view carried into a parser."""

    def __init__(self, path: str, text: str):
        self.path = path
        self.text = text


@runtime_checkable
class FormatParser(Protocol):
    """A transcript format parser.

    ``detect`` returns a confidence score in [0, 1] for how well this parser
    matches the given text. ``parse`` turns a :class:`RawEpisode` into an
    :class:`Episode`, collecting structured warnings for anything it can't
    handle gracefully.
    """

    name: str

    def detect(self, text: str) -> float:  # noqa: D401 - protocol
        ...

    def parse(self, raw: RawEpisode) -> Episode:  # noqa: D401 - protocol
        ...


class BaseParser(ABC):
    """Base class implementing the FormatParser protocol."""

    name = "base"

    @abstractmethod
    def detect(self, text: str) -> float:
        ...

    @abstractmethod
    def parse(self, raw: RawEpisode) -> Episode:
        ...


class ParserRefusedError(Exception):
    """Raised when a parser explicitly refuses to handle a format."""


class ParseError(Exception):
    """Raised when parsing fails fatally for an episode."""


class ParserRegistry:
    """Holds registered parsers and picks the highest-confidence match."""

    def __init__(self) -> None:
        self._parsers: list[FormatParser] = []

    def register(self, parser: FormatParser) -> None:
        self._parsers.append(parser)

    def best(self, text: str) -> FormatParser | None:
        """Return the parser with the highest detect confidence, or None."""
        best: FormatParser | None = None
        best_score = 0.0
        for parser in self._parsers:
            score = parser.detect(text)
            if score > best_score:
                best_score = score
                best = parser
        return best

    def parse(self, raw: RawEpisode) -> tuple[Episode, list[ParseWarning]]:
        """Parse using the best parser; raise if none is confident enough."""
        parser = self.best(raw.text)
        if parser is None:
            raise ParserRefusedError(
                f"No parser confidently matched {raw.path}"
            )
        episode = parser.parse(raw)
        # The parser itself populates episode.warnings.
        return episode, episode.warnings

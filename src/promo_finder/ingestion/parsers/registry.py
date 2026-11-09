"""Parser registry with the Kuku screenplay parser registered by default."""

from __future__ import annotations

from promo_finder.ingestion.parsers.base import (
    FormatParser,
    ParserRegistry,
    ParserRefusedError,
)
from promo_finder.ingestion.parsers.kuku_screenplay import KukuScreenplayParser


def build_default_registry() -> ParserRegistry:
    """Build a registry with all known parsers registered."""
    registry = ParserRegistry()
    registry.register(KukuScreenplayParser())
    return registry

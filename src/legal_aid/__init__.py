"""Offline legal-aid directory models and verified snapshot processing."""

from .directory import (
    LegalAidContact,
    LegalAidFallback,
    build_delhi_contacts,
    build_nalsa_fallback,
    build_tele_law_fallback,
)
from .finder import (
    LegalAidFinder,
    LegalAidFinderError,
    LegalAidSearchResult,
    MatchStatus,
)

__all__ = [
    "LegalAidContact",
    "LegalAidFallback",
    "build_delhi_contacts",
    "build_nalsa_fallback",
    "build_tele_law_fallback",
    "LegalAidFinder",
    "LegalAidFinderError",
    "LegalAidSearchResult",
    "MatchStatus",
]

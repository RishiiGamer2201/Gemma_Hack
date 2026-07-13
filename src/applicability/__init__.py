"""Deterministic statutory applicability gates used before legal retrieval."""

from .delhi_rent import (
    DRC_PROFILE_ID,
    DRC_SOURCE_ID,
    ApplicabilityDecision,
    DelhiRentApplicabilityFacts,
    DelhiRentApplicabilityResult,
    evaluate_delhi_rent_applicability,
)

__all__ = [
    "DRC_PROFILE_ID",
    "DRC_SOURCE_ID",
    "ApplicabilityDecision",
    "DelhiRentApplicabilityFacts",
    "DelhiRentApplicabilityResult",
    "evaluate_delhi_rent_applicability",
]

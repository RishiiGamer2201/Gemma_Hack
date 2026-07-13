"""Reviewed domain-to-collection routing for the official corpus.

Searching every act at once is not merely slow, it is unsafe: an unscoped lexical
query about unpaid wages ranks criminal-code sections above the Code on Wages.
This module records which reviewed sources a domain may retrieve from. It is a
retrieval-scoping decision, not a legal conclusion about which law governs a case;
applicability gates and human review still decide that.
"""

from __future__ import annotations

from collections.abc import Sequence

from src.models.schemas import LegalDomain

from .types import RetrievalDocument

# Sources that may be consulted for any domain. The Constitution is the supreme
# law and legal-aid statutes describe entitlement to help rather than the merits
# of a dispute, so both remain in scope everywhere.
UNIVERSAL_SOURCE_IDS: tuple[str, ...] = (
    "constitution_2026_en",
    "constitution_2026_hi_en",
    "legal_services_authorities_act_en",
    "nalsa_free_legal_services_regulations_2010_en",
    "nalsa_lok_adalat_regulations_2009_en",
)

_DOMAIN_SOURCE_PREFIXES: dict[LegalDomain, tuple[str, ...]] = {
    LegalDomain.CRIMINAL: ("bns_2023", "bnss_2023", "bsa_2023"),
    LegalDomain.LABOUR: ("code_on_wages", "labour_codes"),
    LegalDomain.CONSUMER: ("consumer_",),
    # A deposit or tenancy dispute may be governed by rent law, or by contract and
    # consumer-service law when rent control does not apply. The Delhi Rent Control
    # Act additionally carries an applicability profile and stays excluded until the
    # premises facts approve it, so listing it here cannot force it into an answer.
    LegalDomain.TENANCY_PROPERTY: ("delhi_rent_control", "consumer_protection_act"),
    LegalDomain.CONSTITUTIONAL: ("constitution_",),
}


class CollectionError(RuntimeError):
    """Raised when a domain cannot be routed to any reviewed source."""


def collection_for_domain(
    documents: Sequence[RetrievalDocument],
    domain: LegalDomain,
) -> tuple[RetrievalDocument, ...]:
    """Return only the chunks a domain is permitted to retrieve from.

    ``LegalDomain.OTHER`` deliberately returns the full corpus: the safety router
    already refuses to proceed on an unclassified dispute, so an unscoped search
    here can only be reached by a caller that bypassed that gate, and returning
    everything is more honest than silently guessing a domain.
    """

    if domain is LegalDomain.OTHER:
        return tuple(documents)

    prefixes = _DOMAIN_SOURCE_PREFIXES[domain]
    selected = tuple(
        document
        for document in documents
        if _corpus_source(document).startswith(prefixes)
        or _corpus_source(document) in UNIVERSAL_SOURCE_IDS
    )
    if not selected:
        raise CollectionError(f"no reviewed source is routed for domain '{domain.value}'")
    return selected


def _corpus_source(document: RetrievalDocument) -> str:
    value = document.metadata.get("corpus_source_id")
    return str(value) if value else ""

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

# No source is in scope for every domain.
#
# The Constitution is excluded despite being the supreme law: measured on a
# labelled query set, adding its ~4,900 chunks (English plus the Hindi-English
# diglot) to every collection swamped the governing statute and halved Recall@5.
# It remains priority 1 and is retrieved for constitutional questions.
#
# The legal-aid statutes are excluded too. They describe entitlement to free legal
# help, not the merits of a dispute, and observed on a real deposit query they
# ranked Legal Services Authorities Act sections above the governing law. Legal aid
# is served by the dedicated finder, which reads a verified contact directory; it
# is not a retrieval concern.
#
# A fundamental-rights or legal-aid question arising inside another domain is a
# human-review matter. It is not worth degrading every merits search to cover it.
UNIVERSAL_SOURCE_IDS: tuple[str, ...] = ()

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

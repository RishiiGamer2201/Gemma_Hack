"""Deterministic evidence retrieval from confirmed facts.

The researcher performs no generation. It converts confirmed facts into a scoped,
date-filtered query over reviewed official chunks and returns typed evidence with
complete provenance. Anything it cannot cite, it does not return.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.models.schemas import ConfirmedFacts, SourceEvidence
from src.retrieval import (
    HybridRetriever,
    QueryExpander,
    RetrievalDebugTrace,
    SearchFilters,
    to_source_evidence,
)
from src.retrieval.collections import CollectionError, collection_for_domain
from src.retrieval.hybrid import EmbeddingCallback
from src.retrieval.types import RetrievalDocument

MAX_EVIDENCE = 8


class ResearchError(RuntimeError):
    """A bounded failure while assembling an official evidence bundle."""


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Retrieved evidence plus the trace that explains how it was selected."""

    evidence: tuple[SourceEvidence, ...]
    trace: RetrievalDebugTrace
    query: str
    warnings: tuple[str, ...] = ()

    @property
    def undated_evidence(self) -> tuple[SourceEvidence, ...]:
        """Evidence whose commencement date is not proven by the reviewed source."""

        return tuple(item for item in self.evidence if item.effective_from is None)


def build_query(facts: ConfirmedFacts) -> str:
    """Build a retrieval query from confirmed fields only."""

    parts = [facts.incident_summary, *facts.material_facts]
    query = " ".join(part.strip() for part in parts if part.strip())
    if not query:
        raise ResearchError("confirmed facts contain no searchable text")
    return query


def retrieve_evidence(
    facts: ConfirmedFacts,
    documents: Sequence[RetrievalDocument],
    *,
    approved_profiles: frozenset[str] = frozenset(),
    limit: int = 6,
    query_expander: QueryExpander | None = None,
    include_undated_sources: bool = True,
    embedding_callback: EmbeddingCallback | None = None,
) -> EvidenceBundle:
    """Retrieve official evidence for explicitly confirmed facts.

    Retrieval is refused before confirmation. The incident date, when known,
    selects only material in force on that date.

    Several central acts in the reviewed corpus commence by Government
    notification rather than on a date stated in their own text, so no effective
    date can be proven from the source. ``include_undated_sources`` admits those
    sources and returns a warning naming each one; callers must display it. Set it
    to ``False`` for a strict, provable-date-only bundle.
    """

    if not facts.confirmed or facts.confirmed_at is None:
        raise ResearchError("retrieval requires explicitly confirmed facts")
    if not 1 <= limit <= MAX_EVIDENCE:
        raise ResearchError(f"limit must be between 1 and {MAX_EVIDENCE}")

    try:
        scoped = collection_for_domain(documents, facts.domain)
    except CollectionError as exc:
        # No reviewed source is routed for this domain. The caller must abstain
        # rather than fall back to an unscoped search over unrelated law.
        raise ResearchError(str(exc)) from exc
    retriever = HybridRetriever(
        scoped,
        query_expander=query_expander,
        embedding_callback=embedding_callback,
        embedding_version_key=(
            "embeddinggemma" if embedding_callback is not None else "bm25-only"
        ),
    )

    # Jurisdiction is deliberately not used as a hard filter: central acts are
    # recorded with jurisdiction "India" while a user states a state or city, so
    # filtering on it would discard the very law that governs them.
    filters = SearchFilters(
        effective_on=facts.incident_date,
        applicability_profiles=approved_profiles,
        include_undated_sources=include_undated_sources,
    )

    query = build_query(facts)
    debug = retriever.search_with_debug(query, limit=limit, filters=filters)
    evidence = tuple(to_source_evidence(result) for result in debug.results)

    warnings: list[str] = []
    undated = tuple(item for item in evidence if item.effective_from is None)
    if undated:
        acts = sorted({item.act for item in undated})
        warnings.append(
            "The commencement date of the following source(s) is not proven by the "
            "reviewed text, which leaves commencement to a Government notification. "
            "They are shown as possibly relevant, not as confirmed to be in force on "
            "the incident date: " + "; ".join(acts) + "."
        )
    if any(item.excerpt_truncated for item in evidence):
        warnings.append(
            "One or more excerpts were shortened to fit the display limit and are not "
            "the complete provision; open the official source before relying on them."
        )
    return EvidenceBundle(
        evidence=evidence,
        trace=debug.trace,
        query=query,
        warnings=tuple(warnings),
    )

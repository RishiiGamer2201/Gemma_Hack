"""Offline hybrid retrieval using BM25 and optional local embeddings."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import fields
import hashlib
import json
import math

from .bm25 import BM25Index
from .debug import (
    ChannelCandidate,
    DebugSearchResult,
    RetrievalDebugTrace,
    corpus_sha256,
)
from .query import QueryExpander
from .tokenize import tokenize
from .types import RetrievalDocument, RetrievalResult, SearchFilters


EmbeddingCallback = Callable[[Sequence[str]], Sequence[Sequence[float]]]


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions do not match")
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class HybridRetriever:
    """Combine lexical and semantic ranks through reciprocal-rank fusion.

    The embedding callback is optional and is expected to run locally. It accepts
    a batch of strings and returns one numeric vector per string. No network or
    model dependency is introduced by this class.
    """

    def __init__(
        self,
        documents: Sequence[RetrievalDocument] | Iterable[RetrievalDocument],
        *,
        embedding_callback: EmbeddingCallback | None = None,
        rrf_k: int = 60,
        bm25_weight: float = 1.0,
        embedding_weight: float = 1.0,
        query_expander: QueryExpander | None = None,
        embedding_version_key: str = "unspecified-local-embedding",
    ) -> None:
        if rrf_k < 1:
            raise ValueError("rrf_k must be at least 1")
        if bm25_weight < 0 or embedding_weight < 0:
            raise ValueError("fusion weights must not be negative")
        if bm25_weight == 0 and (embedding_callback is None or embedding_weight == 0):
            raise ValueError("at least one retrieval channel must have a positive weight")
        if (
            not isinstance(embedding_version_key, str)
            or not embedding_version_key.strip()
            or len(embedding_version_key) > 200
        ):
            raise ValueError(
                "embedding_version_key must be a non-empty string up to 200 characters"
            )
        self.documents = tuple(documents)
        self.bm25 = BM25Index(self.documents)
        self.embedding_callback = embedding_callback
        self.rrf_k = rrf_k
        self.bm25_weight = float(bm25_weight)
        self.embedding_weight = float(embedding_weight)
        self.query_expander = query_expander
        self.corpus_sha256 = corpus_sha256(self.documents)
        cache_payload = json.dumps(
            {
                "corpus_sha256": self.corpus_sha256,
                "embedding_version_key": embedding_version_key,
                "schema": "retrieval-embeddings-v1",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        # This is a version key only; this package does not persist an embedding cache.
        self.embedding_cache_version_key = hashlib.sha256(cache_payload).hexdigest()
        self._document_embeddings: tuple[tuple[float, ...], ...] | None = None
        if embedding_callback is not None:
            vectors = embedding_callback([document.text for document in self.documents])
            self._document_embeddings = self._validate_vectors(
                vectors, expected_count=len(self.documents)
            )

    @staticmethod
    def _validate_vectors(
        vectors: Sequence[Sequence[float]], *, expected_count: int
    ) -> tuple[tuple[float, ...], ...]:
        materialized = tuple(tuple(float(value) for value in vector) for vector in vectors)
        if len(materialized) != expected_count:
            raise ValueError("embedding callback returned an unexpected vector count")
        if not materialized:
            return materialized
        dimensions = len(materialized[0])
        if dimensions == 0 or any(len(vector) != dimensions for vector in materialized):
            raise ValueError("embeddings must be non-empty and have equal dimensions")
        if any(not math.isfinite(value) for vector in materialized for value in vector):
            raise ValueError("embeddings must contain only finite values")
        return materialized

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: SearchFilters | None = None,
        candidate_limit: int | None = None,
    ) -> list[RetrievalResult]:
        return list(
            self.search_with_debug(
                query,
                limit=limit,
                filters=filters,
                candidate_limit=candidate_limit,
            ).results
        )

    def search_with_debug(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: SearchFilters | None = None,
        candidate_limit: int | None = None,
    ) -> DebugSearchResult:
        if limit < 0:
            raise ValueError("limit must not be negative")
        if filters is not None and not isinstance(filters, SearchFilters):
            raise TypeError("filters must be a SearchFilters instance")
        expansion = (
            self.query_expander.expand(query)
            if self.query_expander is not None
            else QueryExpander(synonym_groups=()).expand(query)
        )
        active_filters = filters if filters is not None else SearchFilters()
        exclusions = tuple(
            (document.source_id, "active_filters")
            for document in self.documents
            if not active_filters.matches(document)
        )
        if limit == 0 or not expansion.original_terms:
            return self._debug_result(
                (), expansion.original_terms, expansion.expanded_terms, active_filters,
                (), exclusions, (), expansion.query, limit, 0,
            )
        pool_size = max(limit * 4, 20) if candidate_limit is None else candidate_limit
        if pool_size <= 0:
            raise ValueError("candidate_limit must be positive")
        if pool_size < limit:
            raise ValueError("candidate_limit must be at least limit")
        expanded_query = expansion.query

        lexical, semantic = self._retrieve_channels(
            expanded_query, active_filters, pool_size
        )
        by_id = {document.source_id: document for document in self.documents}
        fusion, channel_scores, channel_ranks, ordered = self._fuse(lexical, semantic)
        kept, deduplications = self._deduplicate(ordered, by_id)
        if (
            candidate_limit is None
            and len(kept) < limit
            and pool_size < len(self.documents)
        ):
            pool_size = len(self.documents)
            lexical, semantic = self._retrieve_channels(
                expanded_query, active_filters, pool_size
            )
            fusion, channel_scores, channel_ranks, ordered = self._fuse(
                lexical, semantic
            )
            kept, deduplications = self._deduplicate(ordered, by_id)
        results = tuple(
            RetrievalResult(
                document=by_id[source_id],
                score=fusion[source_id],
                rank=rank,
                channel_scores=channel_scores[source_id],
                channel_ranks=channel_ranks[source_id],
            )
            for rank, source_id in enumerate(kept[:limit], start=1)
        )
        candidates = tuple(
            ChannelCandidate(channel, result.source_id, result.rank, result.score)
            for channel, results_for_channel in (("bm25", lexical), ("embedding", semantic))
            for result in results_for_channel
        )
        return self._debug_result(
            results,
            expansion.original_terms,
            expansion.expanded_terms,
            active_filters,
            candidates,
            exclusions,
            deduplications,
            expanded_query,
            limit,
            pool_size,
        )

    def _retrieve_channels(
        self,
        query: str,
        filters: SearchFilters,
        pool_size: int,
    ) -> tuple[list[RetrievalResult], list[RetrievalResult]]:
        lexical = (
            self.bm25.search(query, limit=pool_size, filters=filters)
            if self.bm25_weight > 0
            else []
        )
        semantic = self._semantic_search(query, filters=filters, limit=pool_size)
        return lexical, semantic

    def _fuse(
        self,
        lexical: list[RetrievalResult],
        semantic: list[RetrievalResult],
    ) -> tuple[
        dict[str, float],
        dict[str, dict[str, float]],
        dict[str, dict[str, int]],
        list[str],
    ]:
        fusion: dict[str, float] = {}
        channel_scores: dict[str, dict[str, float]] = {}
        channel_ranks: dict[str, dict[str, int]] = {}
        for channel, weight, results in (
            ("bm25", self.bm25_weight, lexical),
            ("embedding", self.embedding_weight, semantic),
        ):
            for result in results:
                source_id = result.source_id
                fusion[source_id] = fusion.get(source_id, 0.0) + weight / (
                    self.rrf_k + result.rank
                )
                channel_scores.setdefault(source_id, {})[channel] = result.score
                channel_ranks.setdefault(source_id, {})[channel] = result.rank
        ordered = sorted(fusion, key=lambda source_id: (-fusion[source_id], source_id))
        return fusion, channel_scores, channel_ranks, ordered

    def _debug_result(
        self,
        results: tuple[RetrievalResult, ...],
        original_terms: tuple[str, ...],
        expanded_terms: tuple[str, ...],
        filters: SearchFilters,
        candidates: tuple[ChannelCandidate, ...],
        exclusions: tuple[tuple[str, str], ...],
        deduplications: tuple[tuple[str, str, str], ...],
        expanded_query: str,
        limit: int,
        candidate_limit: int,
    ) -> DebugSearchResult:
        active_filters = {
            item.name: (
                getattr(filters, item.name).isoformat()
                if hasattr(getattr(filters, item.name), "isoformat")
                else getattr(filters, item.name)
            )
            for item in fields(filters)
            if getattr(filters, item.name) is not None
        }
        config = {
            "rrf_k": self.rrf_k,
            "bm25_weight": self.bm25_weight,
            "embedding_weight": self.embedding_weight,
            "query_expansion": self.query_expander is not None,
            "embedding_cache_version_key": self.embedding_cache_version_key,
            "expanded_query": expanded_query,
            "limit": limit,
            "candidate_limit": candidate_limit,
            "result_underfill": len(results) < limit,
        }
        return DebugSearchResult(
            results=results,
            trace=RetrievalDebugTrace(
                original_terms=original_terms,
                expanded_terms=expanded_terms,
                active_filters=active_filters,
                channel_candidates=candidates,
                exclusions=exclusions,
                deduplications=deduplications,
                corpus_sha256=self.corpus_sha256,
                retriever_config=config,
            ),
        )

    @staticmethod
    def _deduplicate(
        ordered: list[str], by_id: dict[str, RetrievalDocument]
    ) -> tuple[list[str], tuple[tuple[str, str, str], ...]]:
        kept: list[str] = []
        events: list[tuple[str, str, str]] = []
        for source_id in ordered:
            duplicate_of = next(
                (
                    kept_id
                    for kept_id in kept
                    if _overlapping_chunks(by_id[kept_id], by_id[source_id])
                ),
                None,
            )
            if duplicate_of is None:
                kept.append(source_id)
            else:
                events.append((source_id, duplicate_of, "overlapping_chunk"))
        return kept, tuple(events)

    def _semantic_search(
        self, query: str, *, filters: SearchFilters | None, limit: int
    ) -> list[RetrievalResult]:
        if (
            self.embedding_callback is None
            or self._document_embeddings is None
            or self.embedding_weight == 0
            or not self.documents
        ):
            return []
        query_vectors = self._validate_vectors(
            self.embedding_callback([query]), expected_count=1
        )
        query_vector = query_vectors[0]
        active_filters = filters or SearchFilters()
        scored = []
        for document, vector in zip(self.documents, self._document_embeddings):
            if not active_filters.matches(document):
                continue
            score = _cosine(query_vector, vector)
            # Zero/negative similarity is not retrieval evidence and must not gain a
            # positive reciprocal-rank score merely by appearing in a sorted list.
            if score > 0:
                scored.append((score, document))
        scored.sort(key=lambda item: (-item[0], item[1].source_id))
        return [
            RetrievalResult(
                document=document,
                score=score,
                rank=rank,
                channel_scores={"embedding": score},
                channel_ranks={"embedding": rank},
            )
            for rank, (score, document) in enumerate(scored[:limit], start=1)
        ]


def _overlapping_chunks(left: RetrievalDocument, right: RetrievalDocument) -> bool:
    """Return true only for provenance-compatible chunks with explicit overlap."""

    identity_keys = ("jurisdiction", "act", "section", "language")
    if any(
        not left.metadata.get(key)
        or left.metadata.get(key) != right.metadata.get(key)
        for key in identity_keys
    ):
        return False
    isolation_keys = ("status", "effective_from", "effective_to", "document_type")
    if any(left.metadata.get(key) != right.metadata.get(key) for key in isolation_keys):
        return False

    def page_range(document: RetrievalDocument) -> tuple[int, int] | None:
        start = document.metadata.get("page_start", document.metadata.get("page"))
        end = document.metadata.get("page_end", start)
        try:
            return (int(start), int(end)) if start is not None else None
        except (TypeError, ValueError):
            return None

    left_pages, right_pages = page_range(left), page_range(right)
    page_overlap = bool(
        left_pages
        and right_pages
        and left_pages[0] <= right_pages[1]
        and right_pages[0] <= left_pages[1]
    )
    normalized_left = " ".join(tokenize(left.text))
    normalized_right = " ".join(tokenize(right.text))
    left_terms, right_terms = set(normalized_left.split()), set(normalized_right.split())
    smaller = min(len(left_terms), len(right_terms))
    text_overlap = bool(
        smaller >= 4 and len(left_terms.intersection(right_terms)) / smaller >= 0.8
    )
    pages_compatible = left_pages is None or right_pages is None or page_overlap
    exact_text = bool(normalized_left and normalized_left == normalized_right)
    return (exact_text or text_overlap) and pages_compatible

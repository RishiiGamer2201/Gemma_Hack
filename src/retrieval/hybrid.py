"""Offline hybrid retrieval using BM25 and optional local embeddings."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
import math

from .bm25 import BM25Index
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
    ) -> None:
        if rrf_k < 1:
            raise ValueError("rrf_k must be at least 1")
        if bm25_weight < 0 or embedding_weight < 0:
            raise ValueError("fusion weights must not be negative")
        if bm25_weight == 0 and (embedding_callback is None or embedding_weight == 0):
            raise ValueError("at least one retrieval channel must have a positive weight")
        self.documents = tuple(documents)
        self.bm25 = BM25Index(self.documents)
        self.embedding_callback = embedding_callback
        self.rrf_k = rrf_k
        self.bm25_weight = float(bm25_weight)
        self.embedding_weight = float(embedding_weight)
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
        if limit < 0:
            raise ValueError("limit must not be negative")
        if limit == 0:
            return []
        if not self.bm25.tokenizer(query):
            return []
        pool_size = max(limit * 4, 20) if candidate_limit is None else candidate_limit
        if pool_size <= 0:
            raise ValueError("candidate_limit must be positive")
        if pool_size < limit:
            raise ValueError("candidate_limit must be at least limit")

        lexical = (
            self.bm25.search(query, limit=pool_size, filters=filters)
            if self.bm25_weight > 0
            else []
        )
        semantic = self._semantic_search(query, filters=filters, limit=pool_size)
        by_id = {document.source_id: document for document in self.documents}
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
        return [
            RetrievalResult(
                document=by_id[source_id],
                score=fusion[source_id],
                rank=rank,
                channel_scores=channel_scores[source_id],
                channel_ranks=channel_ranks[source_id],
            )
            for rank, source_id in enumerate(ordered[:limit], start=1)
        ]

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

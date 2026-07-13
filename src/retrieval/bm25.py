"""A small dependency-free Okapi BM25 implementation."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Sequence

from .tokenize import tokenize
from .types import RetrievalDocument, RetrievalResult, SearchFilters

Tokenizer = Callable[[str], list[str]]


class BM25Index:
    """Immutable in-memory BM25 index with deterministic result ordering."""

    def __init__(
        self,
        documents: Sequence[RetrievalDocument] | Iterable[RetrievalDocument],
        *,
        k1: float = 1.5,
        b: float = 0.75,
        tokenizer: Tokenizer = tokenize,
    ) -> None:
        if k1 <= 0:
            raise ValueError("k1 must be positive")
        if not 0 <= b <= 1:
            raise ValueError("b must be between 0 and 1")
        self.documents = tuple(documents)
        if len({document.source_id for document in self.documents}) != len(
            self.documents
        ):
            raise ValueError("source_id values must be unique within an index")
        self.k1 = float(k1)
        self.b = float(b)
        self.tokenizer = tokenizer
        self._term_frequencies: list[Counter[str]] = []
        self._document_lengths: list[int] = []
        document_frequency: defaultdict[str, int] = defaultdict(int)

        for document in self.documents:
            frequencies = Counter(tokenizer(document.text))
            self._term_frequencies.append(frequencies)
            length = sum(frequencies.values())
            self._document_lengths.append(length)
            for term in frequencies:
                document_frequency[term] += 1

        count = len(self.documents)
        self._average_length = (
            sum(self._document_lengths) / count if count else 0.0
        )
        # Robertson/Sparck Jones IDF with a +1 guard, always non-negative.
        self._idf = {
            term: math.log(1.0 + (count - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: SearchFilters | None = None,
        include_zero_scores: bool = False,
    ) -> list[RetrievalResult]:
        if limit < 0:
            raise ValueError("limit must not be negative")
        if filters is not None and not isinstance(filters, SearchFilters):
            raise TypeError("filters must be a SearchFilters instance")
        if limit == 0 or not self.documents:
            return []
        query_terms = tuple(dict.fromkeys(self.tokenizer(query)))
        if not query_terms and not include_zero_scores:
            return []
        active_filters = filters if filters is not None else SearchFilters()
        scored: list[tuple[float, RetrievalDocument]] = []

        for position, document in enumerate(self.documents):
            if not active_filters.matches(document):
                continue
            score = self._score(position, query_terms)
            if score > 0 or include_zero_scores:
                scored.append((score, document))

        scored.sort(key=lambda item: (-item[0], item[1].source_id))
        return [
            RetrievalResult(
                document=document,
                score=score,
                rank=rank,
                channel_scores={"bm25": score},
                channel_ranks={"bm25": rank},
            )
            for rank, (score, document) in enumerate(scored[:limit], start=1)
        ]

    def _score(self, position: int, query_terms: Sequence[str]) -> float:
        frequencies = self._term_frequencies[position]
        document_length = self._document_lengths[position]
        average_length = self._average_length or 1.0
        normalization = self.k1 * (
            1.0 - self.b + self.b * document_length / average_length
        )
        score = 0.0
        for term in query_terms:
            frequency = frequencies.get(term, 0)
            if frequency:
                score += self._idf[term] * (
                    frequency * (self.k1 + 1.0) / (frequency + normalization)
                )
        return score

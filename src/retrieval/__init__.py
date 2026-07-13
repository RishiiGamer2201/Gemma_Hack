"""Deterministic, offline retrieval primitives for official-source corpora."""

from .bm25 import BM25Index
from .debug import DebugSearchResult, RetrievalDebugTrace, corpus_sha256
from .hybrid import HybridRetriever
from .query import REVIEWED_LEGAL_SYNONYM_GROUPS, QueryExpander, QueryExpansion
from .types import RetrievalDocument, RetrievalResult, SearchFilters

__all__ = [
    "BM25Index",
    "DebugSearchResult",
    "HybridRetriever",
    "QueryExpander",
    "QueryExpansion",
    "REVIEWED_LEGAL_SYNONYM_GROUPS",
    "RetrievalDebugTrace",
    "RetrievalDocument",
    "RetrievalResult",
    "SearchFilters",
    "corpus_sha256",
]

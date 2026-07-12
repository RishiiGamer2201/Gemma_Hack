# Retrieval quality controls

The deterministic retrieval layer now provides the metadata, expansion, provenance,
and debugging controls required before integrating EmbeddingGemma and FAISS.

## Query expansion

Expansion is opt-in. The built-in vocabulary contains a small reviewed set of
ordinary Hindi, English, and Romanized-Hindi retrieval synonyms. It does not contain
an IPC/BNS mapping.

```python
from src.retrieval import HybridRetriever, QueryExpander

expander = QueryExpander(
    reviewed_mapping_aliases={"IPC 420": ("BNS 318",)},
)
retriever = HybridRetriever(documents, query_expander=expander)
```

Mapping aliases must be supplied by a caller after human review. Equivalent
normalized keys are rejected rather than silently overwritten.

## Filters and deduplication

`SearchFilters` supports jurisdiction, language, act, status, document type, and an
inclusive effective date. Malformed or missing effective dates are excluded when a
date filter is active.

Overlap deduplication requires matching jurisdiction, act, section, language,
status, effective period, and document type. Text must be identical or strongly
overlapping, and explicit page ranges must be compatible. When default candidates
are exhausted by duplicates, retrieval expands the pool to recover the requested
number of unique results where possible.

## Reproducibility and debugging

`HybridRetriever.search_with_debug()` returns immutable results plus a trace with:

- original and expanded terms;
- active filters and excluded source IDs;
- per-channel ranks and scores;
- deduplication events;
- corpus SHA-256 and embedding version key; and
- the resolved query, result limit, candidate pool, fusion configuration, and
  underfill status.

Corpus hashing covers searchable text and canonical provenance metadata, is stable
across document order, and rejects unsupported or non-deterministic metadata types.
The embedding key is versioning infrastructure only; persistent caching remains
pending.

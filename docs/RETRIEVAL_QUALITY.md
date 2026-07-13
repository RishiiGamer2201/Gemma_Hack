# Retrieval quality controls

The deterministic retrieval layer provides the metadata, expansion, provenance,
and debugging controls behind hybrid retrieval.

## Domain scoping is required, not cosmetic

Searching the whole 6,845-chunk corpus is unsafe, not merely slow. An unscoped
lexical query about unpaid wages ranked BNS and BNSS criminal sections above the
Code on Wages. `collection_for_domain` restricts retrieval to the sources a
confirmed domain may draw from. This is a retrieval-scoping decision, not a legal
conclusion about which law governs.

The Constitution is deliberately excluded from non-constitutional collections
despite being priority 1 and the supreme law. Measured on the labelled set below,
adding its ~4,900 chunks (English plus the Hindi-English diglot) to every domain
swamped the governing statute and halved Recall@5. A fundamental-rights issue
arising inside another domain is a human-review question; it is not worth
degrading every other search to paper over.

## Semantic channel

Embeddings come from EmbeddingGemma through the loopback-only Ollama runtime, so
no text leaves the device. Vectors are cached on disk, keyed by embedding model
and a hash of the exact text, so a changed chunk can never reuse a stale vector.

FAISS is not used. The corpus is ~7k chunks and a domain-scoped collection is far
smaller, so an exact cosine scan is fast, exactly accurate, and avoids a
dependency that will not install on this Python build.

## Measured retrieval quality

Provisional, on a 10-query labelled set (`Recall@5`, MRR), domain-scoped:

| System | Recall@5 | MRR |
|---|---:|---:|
| BM25 only | 0.50 | 0.383 |
| Hybrid (BM25 + EmbeddingGemma) | 0.80 | 0.570 |

Hybrid beats the lexical baseline, which is the comparison the plan requires.

These numbers are **not** the Phase E exit gate. The set is 10 queries written by
the implementer, and at least one gold label was wrong: for "seller refuses to
refund my money for a defective product" the retriever returned the product
liability sections (83, 84, 86), which are a better answer than the definitions
section that was labelled correct. Real quality is therefore somewhat higher than
0.80, and the honest conclusion is that the number is unreliable in both
directions. Certifying `Recall@5 >= 0.85` requires the reviewed 150–200 query
golden set in Phase L, with each item reviewed by someone other than its author.

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

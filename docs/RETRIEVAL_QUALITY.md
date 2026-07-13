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

Reproduce with:

```powershell
python scripts/evaluate_retrieval.py --k 5
```

On the 20-query set in `fixtures/eval_queries.json`, domain-scoped:

| System | Recall@5 | MRR |
|---|---:|---:|
| BM25 only | 0.700 | 0.496 |
| Vector only (EmbeddingGemma) | 0.800 | 0.717 |
| Hybrid (BM25 + EmbeddingGemma) | **0.850** | 0.652 |

Read this honestly. Hybrid beats **both** baselines on Recall@5, which is the
metric that decides whether the right provision reaches the answer at all. It does
**not** beat vector-only on MRR: the semantic channel alone ranks its hits higher,
and reciprocal-rank fusion with a noisier lexical channel pushes the correct chunk
down a place or two. The plan's claim that hybrid beats both baselines is therefore
true on recall and false on MRR, and that item stays unchecked.

Why keep hybrid anyway: BM25 is the channel that catches exact section numbers and
act names ("BNS 303", "Section 17"), which is precisely the query a user types when
they are holding a notice. Vector-only missed the two tenancy queries and the
consumer-forum jurisdiction query; BM25-only missed the Hinglish and paraphrase
queries. They fail on different things, and recall is what the verifier needs.

Both figures are **provisional**. The query set was written by the implementer and
is marked `pending_independent_review`. Phase L requires a reviewer other than the
author, so `Recall@5 >= 0.85` is not certified even though the measured value meets
it, and the exit-gate items stay unchecked.

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

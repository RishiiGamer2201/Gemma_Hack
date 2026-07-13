# Evaluation

Two harnesses, both running entirely on device against the real corpus and the real
model. Reproduce with:

```powershell
python scripts/evaluate_retrieval.py --k 5
python scripts/evaluate_answers.py
```

Both print `NOT CERTIFIED` with their results. The query and scenario sets were
written by the implementer, and `IMPLEMENTATION_PLAN.md` Phase L requires review by
someone other than the author before any of these numbers are quoted in a writeup or
a deck. They are reproducible, not certified.

## Retrieval

20 queries, domain-scoped. See `docs/RETRIEVAL_QUALITY.md` for why hybrid is kept.

| System | Recall@5 | MRR |
|---|---:|---:|
| BM25 only | 0.700 | 0.496 |
| Vector only (EmbeddingGemma) | 0.800 | 0.717 |
| Hybrid + reranker | **0.850** | **0.729** |

## End-to-end answers

12 scenarios: 4 that must publish, 4 outcome-prediction requests that must be
refused, 2 that must route to human help, 2 that must ask for a missing fact.

| Metric | Value |
|---|---:|
| Fabricated citations | **0** |
| Unsupported claims shown to a user | **0** |
| Unsupported-claim rate | **0.000** |
| Citation precision | **1.000** |
| Correct act rate | 1.000 |
| Route / abstention accuracy | 1.000 (12/12) |
| Median answer latency | 8.6 s |
| Max answer latency | 11.4 s |

The first two lines are the ones that matter, and they are zero **by construction,
not by luck**. A claim that fails verification is never published: the pipeline
repairs once, and if the claim still cannot be supported the answer is withheld. So
these numbers are not a score to be tuned — if they are ever non-zero, that is a
hole in the safety story, and `evaluate_answers.py` exits non-zero to say so.

The reported latency is for a **published** answer, which is what a person actually
waits for. The overall median across all scenarios is ~0 s because a refused or
urgent case short-circuits before the model is ever called — that is the safety
design working, not a fast answer.

## What is deliberately not measured

* **Win probability, case strength, settlement odds.** The system refuses to produce
  them, so there is nothing to score. This is the one number a legal tool must not
  have.
* **Confidence scores.** No output contract carries one. A number would imply a
  reliability the system cannot honestly claim.

## Gaps

* The scenario and query sets need an independent reviewer (Phase L).
* The IPC/BNS temporal-routing accuracy gate cannot be measured yet: no human-approved
  mapping exists, and the IPC itself is not in the corpus. See
  `docs/ipc_bns_worksheet.md`.
* ASR/OCR critical-field error rate is not yet a harness. It is, however, already
  demonstrated: on the scanned-PDF fixture Tesseract read "10 April 2026" as
  "10 Aprit 2028", which is exactly why OCR output is a draft the user must confirm.

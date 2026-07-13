from __future__ import annotations

import unittest
from datetime import date

from src.retrieval import BM25Index, HybridRetriever, RetrievalDocument, SearchFilters
from src.retrieval.tokenize import tokenize

DOCUMENTS = (
    RetrievalDocument(
        source_id="current",
        text="BNS section 316 current breach of trust provision",
        metadata={
            "jurisdiction": "India",
            "language": "en",
            "status": "in_force",
            "effective_from": "2024-07-01",
        },
    ),
    RetrievalDocument(
        source_id="historical",
        text="IPC section 420 historical cheating provision",
        metadata={
            "jurisdiction": "India",
            "language": "en",
            "status": "repealed",
            "effective_from": "1860-01-01",
            "effective_to": "2024-06-30",
        },
    ),
)


class RetrievalTests(unittest.TestCase):
    def test_tokenizer_preserves_legal_identifier(self) -> None:
        self.assertIn("316(2)(a)", tokenize("Apply BNS 316(2)(a), please."))

    def test_bm25_ranks_exact_section(self) -> None:
        results = BM25Index(DOCUMENTS).search("IPC 420")
        self.assertEqual(results[0].source_id, "historical")

    def test_effective_date_excludes_repealed_source(self) -> None:
        results = BM25Index(DOCUMENTS).search(
            "provision",
            filters=SearchFilters(effective_on=date(2025, 1, 1)),
        )
        self.assertEqual([result.source_id for result in results], ["current"])

    def test_effective_date_boundaries_are_inclusive(self) -> None:
        on_last_historical_day = BM25Index(DOCUMENTS).search(
            "provision",
            filters=SearchFilters(effective_on="2024-06-30"),
        )
        on_first_current_day = BM25Index(DOCUMENTS).search(
            "provision",
            filters=SearchFilters(effective_on="2024-07-01"),
        )
        self.assertEqual([item.source_id for item in on_last_historical_day], ["historical"])
        self.assertEqual([item.source_id for item in on_first_current_day], ["current"])

    def test_malformed_or_missing_effective_date_is_excluded(self) -> None:
        malformed = (
            RetrievalDocument(
                source_id="bad-date",
                text="legal provision",
                metadata={"effective_from": "July 2024"},
            ),
            RetrievalDocument(
                source_id="missing-date",
                text="legal provision",
                metadata={},
            ),
        )
        results = BM25Index(malformed).search(
            "provision", filters=SearchFilters(effective_on="2025-01-01")
        )
        self.assertEqual(results, [])

    def test_duplicate_source_ids_are_rejected(self) -> None:
        duplicate = RetrievalDocument(source_id="current", text="different", metadata={})
        with self.assertRaisesRegex(ValueError, "source_id values must be unique"):
            BM25Index((*DOCUMENTS, duplicate))

    def test_empty_and_zero_limit_searches_return_no_results(self) -> None:
        self.assertEqual(BM25Index(()).search("anything"), [])
        self.assertEqual(BM25Index(DOCUMENTS).search("IPC", limit=0), [])

    def test_invalid_embedding_shapes_are_rejected(self) -> None:
        callbacks = (
            lambda texts: [[1.0]],
            lambda texts: [[1.0], [1.0, 2.0]],
            lambda texts: [[float("nan")], [1.0]],
        )
        for callback in callbacks:
            with self.subTest(callback=callback):
                with self.assertRaises(ValueError):
                    HybridRetriever(DOCUMENTS, embedding_callback=callback)

    def test_hybrid_fusion_preserves_metadata(self) -> None:
        def embeddings(texts: list[str]) -> list[list[float]]:
            return [
                [float("420" in text), float("316" in text), 1.0]
                for text in texts
            ]

        result = HybridRetriever(DOCUMENTS, embedding_callback=embeddings).search(
            "IPC 420", limit=1
        )[0]
        self.assertEqual(result.source_id, "historical")
        self.assertEqual(result.metadata["status"], "repealed")

    def test_blank_or_zero_vector_query_returns_no_semantic_evidence(self) -> None:
        def zero_embeddings(texts: list[str]) -> list[list[float]]:
            return [[0.0, 0.0] for _ in texts]

        retriever = HybridRetriever(DOCUMENTS, embedding_callback=zero_embeddings)
        self.assertEqual(retriever.search(""), [])
        self.assertEqual(retriever.search("unmatched"), [])

    def test_zero_candidate_limit_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "candidate_limit must be positive"):
            HybridRetriever(DOCUMENTS).search("IPC", candidate_limit=0)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from datetime import UTC, date, datetime

from src.retrieval import (
    HybridRetriever,
    QueryExpander,
    RetrievalDocument,
    SearchFilters,
    corpus_sha256,
)


def doc(
    source_id: str,
    text: str = "shared legal remedy text",
    **metadata: object,
) -> RetrievalDocument:
    base: dict[str, object] = {
        "jurisdiction": "India",
        "act": "Example Act",
        "section": "1",
        "language": "en",
        "status": "in_force",
        "effective_from": "2024-07-01",
        "effective_to": None,
        "document_type": "statute",
        "page_start": 1,
        "page_end": 1,
    }
    base.update(metadata)
    return RetrievalDocument(source_id=source_id, text=text, metadata=base)


class RetrievalQualityReviewTests(unittest.TestCase):
    def test_backward_compatible_search_returns_list_and_debug_returns_tuple(self) -> None:
        retriever = HybridRetriever((doc("one", "tenant remedy"),))
        self.assertIsInstance(retriever.search("tenant"), list)
        self.assertIsInstance(retriever.search_with_debug("tenant").results, tuple)

    def test_empty_query_and_zero_limit_do_not_call_query_embedding(self) -> None:
        calls: list[list[str]] = []

        def embedding(texts):
            calls.append(list(texts))
            return [[1.0] for _ in texts]

        retriever = HybridRetriever((doc("one"),), embedding_callback=embedding)
        self.assertEqual(calls, [["shared legal remedy text"]])
        self.assertEqual(retriever.search("   "), [])
        self.assertEqual(retriever.search("legal", limit=0, candidate_limit=0), [])
        self.assertEqual(len(calls), 1)

    def test_candidate_limit_validation_boundaries(self) -> None:
        retriever = HybridRetriever((doc("one"),))
        for candidate_limit in (0, -1):
            with self.subTest(candidate_limit=candidate_limit):
                with self.assertRaisesRegex(ValueError, "must be positive"):
                    retriever.search("legal", candidate_limit=candidate_limit)
        with self.assertRaisesRegex(ValueError, "at least limit"):
            retriever.search("legal", limit=2, candidate_limit=1)

    def test_all_filter_dimensions_are_exact_case_insensitive_boundaries(self) -> None:
        documents = (
            doc("base"),
            doc("jurisdiction", jurisdiction="Delhi"),
            doc("act", act="Other Act"),
            doc("section", section="2"),
            doc("language", language="hi"),
            doc("status", status="repealed"),
            doc("period", effective_from="2025-01-01"),
            doc("type", document_type="rules"),
        )
        result = HybridRetriever(documents).search(
            "legal remedy",
            filters=SearchFilters(
                jurisdiction="india",
                act="example act",
                language="EN",
                status="IN_FORCE",
                document_type="STATUTE",
                effective_on="2024-12-31",
            ),
            limit=8,
        )
        self.assertEqual({item.source_id for item in result}, {"base", "section"})

    def test_effective_date_range_is_inclusive_and_malformed_metadata_is_excluded(self) -> None:
        documents = (
            doc("bounded", effective_from="2024-01-01", effective_to="2024-12-31"),
            doc("bad", effective_from="not-a-date"),
            doc("missing", effective_from=None),
        )
        retriever = HybridRetriever(documents)
        for effective_on in ("2024-01-01", "2024-12-31"):
            with self.subTest(effective_on=effective_on):
                self.assertEqual(
                    [
                        item.source_id
                        for item in retriever.search(
                            "legal",
                            filters=SearchFilters(effective_on=effective_on),
                        )
                    ],
                    ["bounded"],
                )

    def test_query_expansion_supports_multiword_alias_without_implicit_mapping(
        self,
    ) -> None:
        expander = QueryExpander(
            synonym_groups=(),
            reviewed_mapping_aliases={"old section 420": ("new section 318", "cheating offence")},
        )
        absent = QueryExpander(synonym_groups=()).expand("old section 420")
        present = expander.expand("old section 420")
        self.assertNotIn("318", absent.expanded_terms)
        self.assertEqual(present.original_terms, ("old", "section", "420"))
        self.assertTrue({"new", "318", "cheating", "offence"}.issubset(present.expanded_terms))

    def test_query_expansion_deduplicates_terms_in_stable_order(self) -> None:
        expansion = QueryExpander(
            synonym_groups=(("wages", "salary", "wages"),),
            reviewed_mapping_aliases={"wages": ("salary", "pay")},
        ).expand("wages wages")
        self.assertEqual(expansion.expanded_terms, ("wages", "salary", "pay"))

    def test_malformed_empty_alias_keys_and_values_are_rejected(self) -> None:
        for aliases in ({"": ("value",)}, {"key": ("",)}):
            with self.subTest(aliases=aliases):
                with self.assertRaisesRegex(ValueError, "must contain searchable text"):
                    QueryExpander(reviewed_mapping_aliases=aliases)

    def test_semantic_callback_receives_document_batch_then_expanded_query(self) -> None:
        calls: list[list[str]] = []

        def embedding(texts):
            calls.append(list(texts))
            return [[1.0, 0.0] for _ in texts]

        retriever = HybridRetriever(
            (doc("a", "tenant remedy"), doc("b", "other text")),
            embedding_callback=embedding,
            query_expander=QueryExpander(synonym_groups=(("tenant", "renter"),)),
        )
        retriever.search("tenant")
        self.assertEqual(calls[0], ["tenant remedy", "other text"])
        self.assertEqual(calls[1], ["tenant renter"])

    def test_deduplication_never_crosses_any_provenance_isolation_boundary(self) -> None:
        variants = (
            doc("jurisdiction", jurisdiction="Delhi"),
            doc("act", act="Other Act"),
            doc("section", section="2"),
            doc("language", language="hi"),
            doc("status", status="repealed"),
            doc("from", effective_from="2025-01-01"),
            doc("to", effective_to="2025-12-31"),
            doc("type", document_type="rules"),
            doc("page", page_start=10, page_end=10, text="shared legal remedy text extra"),
        )
        response = HybridRetriever((doc("base"), *variants)).search_with_debug(
            "shared legal remedy extra", limit=20
        )
        self.assertEqual(len(response.results), 10)
        self.assertEqual(response.trace.deduplications, ())

    def test_debug_trace_covers_candidates_filters_exclusions_dedupe_and_config(self) -> None:
        response = HybridRetriever(
            (
                doc("a", "tenant deposit remedy evidence", page_start=1, page_end=2),
                doc("b", "tenant deposit remedy evidence copy", page_start=2, page_end=3),
                doc("excluded", "tenant deposit", status="repealed"),
            )
        ).search_with_debug(
            "tenant deposit",
            filters=SearchFilters(status="in_force", effective_on=date(2026, 1, 1)),
        )
        trace = response.trace
        self.assertEqual(trace.original_terms, ("tenant", "deposit"))
        self.assertEqual(trace.active_filters["effective_on"], "2026-01-01")
        self.assertIn(("excluded", "active_filters"), trace.exclusions)
        self.assertTrue(trace.channel_candidates)
        self.assertEqual(trace.deduplications, (("b", "a", "overlapping_chunk"),))
        self.assertEqual(len(trace.corpus_sha256), 64)
        self.assertIn("embedding_cache_version_key", trace.retriever_config)

    def test_corpus_hash_is_deterministic_for_nested_metadata_and_collection_order(self) -> None:
        first = RetrievalDocument(
            source_id="nested",
            text="text",
            metadata={
                "map": {"b": 2, "a": [date(2026, 1, 1), {"z", "a"}]},
                "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
            },
        )
        second = RetrievalDocument(
            source_id="nested",
            text="text",
            metadata={
                "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
                "map": {"a": [date(2026, 1, 1), {"a", "z"}], "b": 2},
            },
        )
        self.assertEqual(corpus_sha256((first,)), corpus_sha256((second,)))

    def test_corpus_hash_rejects_nonfinite_nonstring_keys_and_unsupported_values(self) -> None:
        invalid_metadata = (
            {"float": float("nan")},
            {1: "non-string-key"},
            {"bytes": b"unsupported"},
        )
        for metadata in invalid_metadata:
            with self.subTest(metadata=metadata):
                with self.assertRaises((TypeError, ValueError)):
                    corpus_sha256((RetrievalDocument("bad", "text", metadata),))

    def test_cache_version_changes_with_corpus_or_model_deterministically(self) -> None:
        one = HybridRetriever((doc("a"),), embedding_version_key="model-v1")
        same = HybridRetriever((doc("a"),), embedding_version_key="model-v1")
        model_changed = HybridRetriever((doc("a"),), embedding_version_key="model-v2")
        corpus_changed = HybridRetriever(
            (doc("a", "changed text"),),
            embedding_version_key="model-v1",
        )
        self.assertEqual(one.embedding_cache_version_key, same.embedding_cache_version_key)
        self.assertNotEqual(
            one.embedding_cache_version_key,
            model_changed.embedding_cache_version_key,
        )
        self.assertNotEqual(
            one.embedding_cache_version_key,
            corpus_changed.embedding_cache_version_key,
        )


if __name__ == "__main__":
    unittest.main()

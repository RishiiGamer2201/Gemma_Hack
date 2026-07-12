from __future__ import annotations

from dataclasses import FrozenInstanceError
import unittest

from src.retrieval import (
    HybridRetriever,
    QueryExpander,
    RetrievalDocument,
    SearchFilters,
    corpus_sha256,
)


def document(
    source_id: str,
    text: str,
    *,
    act: str = "Example Act",
    section: str = "1",
    status: str = "in_force",
    effective_from: str = "2024-07-01",
    effective_to: str | None = None,
    document_type: str = "statute",
    page: int = 1,
) -> RetrievalDocument:
    return RetrievalDocument(
        source_id=source_id,
        text=text,
        metadata={
            "jurisdiction": "India",
            "language": "en",
            "act": act,
            "section": section,
            "status": status,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "document_type": document_type,
            "page": page,
        },
    )


class RetrievalQualityTests(unittest.TestCase):
    def test_status_temporal_act_and_document_type_are_isolated(self) -> None:
        documents = (
            document("current", "shared remedy words"),
            document(
                "old",
                "shared remedy words",
                status="repealed",
                effective_from="1900-01-01",
                effective_to="2024-06-30",
            ),
            document("rules", "shared remedy words", document_type="rules"),
            document("other-act", "shared remedy words", act="Other Act"),
        )
        results = HybridRetriever(documents).search(
            "remedy",
            filters=SearchFilters(
                act="Example Act",
                status="in_force",
                document_type="statute",
                effective_on="2025-01-01",
            ),
        )
        self.assertEqual([item.source_id for item in results], ["current"])

    def test_reviewed_hindi_english_synonym_expansion(self) -> None:
        documents = (document("hindi", "किरायेदार शिकायत", section="2"),)
        plain = HybridRetriever(documents).search("tenant complaint")
        expanded = HybridRetriever(
            documents, query_expander=QueryExpander()
        ).search("tenant complaint")
        self.assertEqual(plain, [])
        self.assertEqual([item.source_id for item in expanded], ["hindi"])

    def test_statute_mapping_aliases_are_caller_reviewed_only(self) -> None:
        documents = (document("new", "BNS 318 text", act="BNS", section="318"),)
        without_review = HybridRetriever(
            documents, query_expander=QueryExpander()
        ).search("IPC 420")
        with_review = HybridRetriever(
            documents,
            query_expander=QueryExpander(
                reviewed_mapping_aliases={"IPC 420": ("BNS 318",)}
            ),
        ).search("IPC 420")
        self.assertEqual(without_review, [])
        self.assertEqual([item.source_id for item in with_review], ["new"])

    def test_query_expander_rejects_ambiguous_or_malformed_alias_inputs(self) -> None:
        invalid = (
            {"IPC 420": "BNS 318"},
            {"IPC 420": ()},
            {"IPC 420": (7,)},
        )
        for aliases in invalid:
            with self.subTest(aliases=aliases):
                with self.assertRaises((TypeError, ValueError)):
                    QueryExpander(reviewed_mapping_aliases=aliases)
        with self.assertRaises(TypeError):
            QueryExpander(synonym_groups=("arrest",))
        with self.assertRaisesRegex(ValueError, "unique after normalization"):
            QueryExpander(reviewed_mapping_aliases={
                "IPC-420": ("BNS 318",),
                "ipc 420": ("BNS 319",),
            })

    def test_overlap_dedupe_keeps_highest_ranked_chunk(self) -> None:
        documents = (
            document("a", "tenant notice deposit evidence", page=5),
            document("b", "tenant notice deposit evidence copy", page=5),
        )
        response = HybridRetriever(documents).search_with_debug("tenant deposit")
        self.assertEqual(len(response.results), 1)
        self.assertEqual(response.trace.deduplications, (("b", "a", "overlapping_chunk"),))

    def test_same_page_unrelated_chunks_and_other_jurisdiction_are_not_deduplicated(self) -> None:
        unrelated = (
            document("a", "tenant notice deposit evidence", page=5),
            document("b", "arrest procedure police custody", page=5),
        )
        other_jurisdiction = document("c", "tenant notice deposit evidence", page=5)
        other_jurisdiction = RetrievalDocument(
            source_id=other_jurisdiction.source_id,
            text=other_jurisdiction.text,
            metadata={**other_jurisdiction.metadata, "jurisdiction": "Maharashtra"},
        )
        response = HybridRetriever((*unrelated, other_jurisdiction)).search_with_debug(
            "tenant arrest deposit custody", limit=3
        )
        self.assertEqual(len(response.results), 3)

    def test_identical_text_on_distant_pages_is_not_deduplicated(self) -> None:
        documents = (
            document("page-1", "identical legal boilerplate text", page=1),
            document("page-100", "identical legal boilerplate text", page=100),
        )
        self.assertEqual(
            len(HybridRetriever(documents).search("legal boilerplate", limit=2)),
            2,
        )

    def test_default_candidate_pool_replenishes_after_overlap_deduplication(self) -> None:
        duplicates = tuple(
            document(
                f"duplicate-{index:02d}",
                "tenant deposit tenant deposit tenant deposit shared remedy",
                page=5,
            )
            for index in range(20)
        )
        unique = tuple(
            document(
                f"unique-{index}",
                f"shared remedy unique topic {index}",
                section=str(index + 2),
                page=10 + index,
            )
            for index in range(5)
        )
        response = HybridRetriever((*duplicates, *unique)).search_with_debug(
            "tenant deposit shared remedy", limit=5
        )
        self.assertEqual(len(response.results), 5)
        self.assertEqual(response.trace.retriever_config["candidate_limit"], 25)
        self.assertFalse(response.trace.retriever_config["result_underfill"])

    def test_dedupe_never_crosses_act_status_or_effective_period(self) -> None:
        documents = (
            document("base", "same shared legal text"),
            document("act", "same shared legal text", act="Other Act"),
            document("status", "same shared legal text", status="repealed"),
            document("period", "same shared legal text", effective_from="2025-01-01"),
        )
        results = HybridRetriever(documents).search("shared legal", limit=4)
        self.assertEqual(len(results), 4)

    def test_debug_trace_and_provenance_are_immutable(self) -> None:
        response = HybridRetriever((document("one", "tenant notice"),)).search_with_debug(
            "tenant", filters=SearchFilters(status="in_force")
        )
        self.assertEqual(response.trace.original_terms, ("tenant",))
        self.assertEqual(response.trace.active_filters["status"], "in_force")
        self.assertEqual(response.trace.channel_candidates[0].source_id, "one")
        with self.assertRaises(TypeError):
            response.trace.active_filters["status"] = "repealed"
        with self.assertRaises(FrozenInstanceError):
            response.trace.corpus_sha256 = "changed"
        with self.assertRaises(TypeError):
            response.results[0].metadata["act"] = "changed"

        nested = RetrievalDocument(
            source_id="nested",
            text="nested provenance",
            metadata={"labels": ["official"], "receipt": {"sha256": "0" * 64}},
        )
        with self.assertRaises(TypeError):
            nested.metadata["receipt"]["sha256"] = "changed"
        with self.assertRaises(AttributeError):
            nested.metadata["labels"].append("changed")

    def test_corpus_hash_is_order_independent_and_provenance_sensitive(self) -> None:
        first = document("a", "alpha text")
        second = document("b", "beta text")
        self.assertEqual(corpus_sha256((first, second)), corpus_sha256((second, first)))
        changed_text = document("a", "changed text")
        changed_metadata = document("a", "alpha text", status="repealed")
        self.assertNotEqual(corpus_sha256((first,)), corpus_sha256((changed_text,)))
        self.assertNotEqual(corpus_sha256((first,)), corpus_sha256((changed_metadata,)))

    def test_corpus_hash_rejects_non_deterministic_metadata(self) -> None:
        invalid = RetrievalDocument(
            source_id="invalid",
            text="text",
            metadata={"object": object()},
        )
        with self.assertRaisesRegex(TypeError, "unsupported retrieval metadata type"):
            corpus_sha256((invalid,))
        duplicate = document("same", "other text")
        with self.assertRaisesRegex(ValueError, "source_id values must be unique"):
            corpus_sha256((document("same", "text"), duplicate))

    def test_search_api_remains_a_list_and_expansion_defaults_off(self) -> None:
        retriever = HybridRetriever((document("one", "tenant notice"),))
        result = retriever.search("tenant")
        self.assertIsInstance(result, list)
        self.assertEqual([item.source_id for item in result], ["one"])
        self.assertEqual(retriever.search("किरायेदार"), [])
        self.assertEqual(retriever.search("tenant", limit=0), [])
        self.assertEqual(len(retriever.embedding_cache_version_key), 64)

    def test_filters_reject_blank_values_and_wrong_container_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be blank"):
            SearchFilters(status="   ")
        with self.assertRaisesRegex(TypeError, "SearchFilters"):
            HybridRetriever((document("one", "tenant"),)).search(
                "tenant", filters={}
            )

    def test_debug_config_records_search_specific_limits_and_expanded_query(self) -> None:
        retriever = HybridRetriever(
            (document("one", "tenant notice"),),
            query_expander=QueryExpander(),
        )
        trace = retriever.search_with_debug(
            "tenant", limit=1, candidate_limit=3
        ).trace
        self.assertEqual(trace.retriever_config["limit"], 1)
        self.assertEqual(trace.retriever_config["candidate_limit"], 3)
        self.assertIn("tenant", trace.retriever_config["expanded_query"])


if __name__ == "__main__":
    unittest.main()

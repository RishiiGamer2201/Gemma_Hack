"""Local embedding provider: caching, integrity, and hybrid fusion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.agents.ollama import OllamaError
from src.retrieval import HybridRetriever, RetrievalDocument
from src.retrieval.embeddings import EmbeddingError, LocalEmbedder


class FakeEmbedClient:
    """Returns a deterministic vector per text and counts calls."""

    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self.embedded: list[str] = []
        self.fail = fail

    def embed(self, *, model: str, inputs: Any, keep_alive: Any = None) -> tuple:
        if self.fail:
            raise OllamaError("connection_error", "runtime down")
        self.calls += 1
        texts = list(inputs)
        self.embedded.extend(texts)
        return tuple(
            (float(len(text)), float(text.count("a")), 1.0) for text in texts
        )


def test_vectors_are_cached_on_disk_and_reused(tmp_path: Path) -> None:
    client = FakeEmbedClient()
    embedder = LocalEmbedder(client, cache_dir=tmp_path, model="test-model")

    first = embedder(["unpaid wages", "criminal breach"])
    assert client.calls == 1
    assert len(first) == 2

    # Same instance: served from memory, no second round trip.
    embedder(["unpaid wages"])
    assert client.calls == 1

    # New instance over the same cache directory: served from disk.
    reloaded = LocalEmbedder(client, cache_dir=tmp_path, model="test-model")
    assert reloaded(["unpaid wages", "criminal breach"]) == first
    assert client.calls == 1


def test_only_uncached_texts_are_sent_to_the_runtime(tmp_path: Path) -> None:
    client = FakeEmbedClient()
    embedder = LocalEmbedder(client, cache_dir=tmp_path, model="test-model")

    embedder(["a"])
    client.embedded.clear()
    embedder(["a", "b", "a"])

    # "a" is cached; only "b" crosses the boundary, and only once despite repeats.
    assert client.embedded == ["b"]


def test_a_different_model_does_not_reuse_another_models_vectors(tmp_path: Path) -> None:
    client = FakeEmbedClient()
    LocalEmbedder(client, cache_dir=tmp_path, model="model-a")(["wages"])
    client.embedded.clear()

    LocalEmbedder(client, cache_dir=tmp_path, model="model-b")(["wages"])

    # A vector from one embedding space must never be served for another.
    assert client.embedded == ["wages"]


def test_a_corrupt_cache_is_discarded_rather_than_trusted(tmp_path: Path) -> None:
    client = FakeEmbedClient()
    embedder = LocalEmbedder(client, cache_dir=tmp_path, model="test-model")
    embedder(["wages"])
    embedder.cache_path.write_bytes(b"not an npz archive")

    rebuilt = LocalEmbedder(client, cache_dir=tmp_path, model="test-model")
    assert rebuilt(["wages"]) is not None


def test_batch_size_is_bounded(tmp_path: Path) -> None:
    with pytest.raises(EmbeddingError):
        LocalEmbedder(FakeEmbedClient(), cache_dir=tmp_path, batch_size=0)
    with pytest.raises(EmbeddingError):
        LocalEmbedder(FakeEmbedClient(), cache_dir=tmp_path, batch_size=10_000)


def test_a_runtime_failure_propagates_rather_than_returning_a_wrong_vector(
    tmp_path: Path,
) -> None:
    embedder = LocalEmbedder(FakeEmbedClient(fail=True), cache_dir=tmp_path)
    with pytest.raises(OllamaError):
        embedder(["wages"])


def test_semantic_channel_can_retrieve_where_the_words_do_not_match(
    tmp_path: Path,
) -> None:
    """A paraphrase with no shared terms is invisible to BM25 but not to embeddings."""

    documents = [
        RetrievalDocument(source_id="s:1", text="remuneration payable to a workman"),
        RetrievalDocument(source_id="s:2", text="theft of movable property"),
    ]

    class Paraphrase:
        """Maps the query and s:1 into the same direction; s:2 elsewhere."""

        def __call__(self, texts: Any) -> list[list[float]]:
            vectors = []
            for text in texts:
                if "theft" in text:
                    vectors.append([0.0, 1.0])
                else:
                    vectors.append([1.0, 0.0])
            return vectors

    lexical_only = HybridRetriever(documents)
    assert lexical_only.search("unpaid salary") == []

    hybrid = HybridRetriever(
        documents, embedding_callback=Paraphrase(), embedding_version_key="test"
    )
    found = hybrid.search("unpaid salary", limit=1)
    assert [item.source_id for item in found] == ["s:1"]


def test_reranker_reorders_the_selected_set_without_changing_it() -> None:
    """Fusion picks the set; the reranker picks the order. Recall@k cannot change.

    Reciprocal-rank fusion throws away the actual scores. Measured on the evaluation
    set that cost ranking quality (vector-only beat hybrid on MRR), so the selected
    results are reordered by semantic similarity.
    """

    documents = [
        RetrievalDocument(source_id="s:lexical", text="wages wages wages payable"),
        RetrievalDocument(source_id="s:semantic", text="remuneration due to a workman"),
    ]

    class Semantic:
        """The query is close to s:semantic, far from s:lexical."""

        def __call__(self, texts: Any) -> list[list[float]]:
            vectors = []
            for text in texts:
                if "remuneration" in text:
                    vectors.append([1.0, 0.0])
                elif "wages" in text:
                    vectors.append([0.6, 0.8])
                else:  # the query
                    vectors.append([1.0, 0.0])
            return vectors

    hybrid = HybridRetriever(
        documents, embedding_callback=Semantic(), embedding_version_key="test"
    )
    found = [item.source_id for item in hybrid.search("remuneration", limit=2)]

    # Both survive (the set is unchanged), but the semantically closer one leads.
    assert set(found) == {"s:lexical", "s:semantic"}
    assert found[0] == "s:semantic"


def test_without_an_embedding_channel_the_fused_order_stands(tmp_path: Path) -> None:
    documents = [
        RetrievalDocument(source_id="s:1", text="wages payable to the employee"),
        RetrievalDocument(source_id="s:2", text="wages"),
    ]
    lexical_only = HybridRetriever(documents)
    found = [item.source_id for item in lexical_only.search("wages", limit=2)]

    # No independent signal to rerank by: nothing is dropped or reordered arbitrarily.
    assert set(found) == {"s:1", "s:2"}

"""Local EmbeddingGemma vectors with a persistent, hash-keyed cache.

Embeddings are produced by the loopback-only Ollama runtime, so no text leaves the
device. Vectors are cached on disk keyed by the embedding model and a hash of the
exact text, which makes repeated domain-scoped retrievers cheap without ever
reusing a vector for text that has changed.

FAISS is deliberately not used. The reviewed corpus is ~7k chunks and a
domain-scoped collection is far smaller, so an exact cosine scan is fast, exactly
accurate, and removes a dependency that cannot be installed on this Python build.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from src.agents.ollama import OllamaClient

DEFAULT_EMBEDDING_MODEL = "embeddinggemma"
DEFAULT_BATCH_SIZE = 32
MAX_BATCH_SIZE = 128


class EmbeddingError(RuntimeError):
    """A bounded failure while producing or caching local embeddings."""


def _safe_name(model: str) -> str:
    return "".join(character if character.isalnum() else "-" for character in model).strip("-")


def _key(model: str, text: str) -> str:
    digest = hashlib.sha256()
    digest.update(model.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(text.encode("utf-8"))
    return digest.hexdigest()


class LocalEmbedder:
    """Callable embedding provider compatible with ``HybridRetriever``.

    Instances are safe to reuse across domain collections: overlapping chunks such
    as the Constitution are embedded once and served from cache thereafter.
    """

    def __init__(
        self,
        client: OllamaClient | None = None,
        *,
        model: str = DEFAULT_EMBEDDING_MODEL,
        cache_dir: str | Path = "data/indexes",
        batch_size: int = DEFAULT_BATCH_SIZE,
        persist: bool = True,
    ) -> None:
        if not 1 <= batch_size <= MAX_BATCH_SIZE:
            raise EmbeddingError(f"batch_size must be between 1 and {MAX_BATCH_SIZE}")
        self.client = client if client is not None else OllamaClient(timeout=300.0)
        self.model = model
        self.batch_size = batch_size
        self.persist = persist
        self.cache_dir = Path(cache_dir)
        self.cache_path = self.cache_dir / f"embeddings-{_safe_name(model)}.npz"
        self._vectors: dict[str, np.ndarray] = {}
        self._dirty = False
        self._load_cache()

    @property
    def version_key(self) -> str:
        """Identifies the embedding space so a stale cache cannot be reused silently."""

        return f"{self.model}:{len(self._vectors)}"

    def _load_cache(self) -> None:
        if not self.persist or not self.cache_path.is_file():
            return
        try:
            with np.load(self.cache_path, allow_pickle=False) as payload:
                keys = json.loads(str(payload["keys"].item()))
                matrix = payload["vectors"]
                if len(keys) != matrix.shape[0]:
                    raise EmbeddingError("embedding cache keys and vectors disagree")
                self._vectors = {key: matrix[index] for index, key in enumerate(keys)}
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            # A corrupt or stale cache is discarded, never trusted. Recomputing is
            # cheap; serving a wrong vector is not.
            self._vectors = {}

    def save(self) -> None:
        if not self.persist or not self._dirty or not self._vectors:
            return
        keys = list(self._vectors)
        matrix = np.stack([self._vectors[key] for key in keys]).astype(np.float32)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{self.cache_path.name}.", dir=self.cache_dir
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                np.savez(handle, keys=np.array(json.dumps(keys)), vectors=matrix)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.cache_path)
            self._dirty = False
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        items = list(texts)
        missing = [
            text for text in dict.fromkeys(items) if _key(self.model, text) not in self._vectors
        ]
        for start in range(0, len(missing), self.batch_size):
            batch = missing[start : start + self.batch_size]
            vectors = self.client.embed(model=self.model, inputs=batch)
            for text, vector in zip(batch, vectors, strict=True):
                self._vectors[_key(self.model, text)] = np.asarray(vector, dtype=np.float32)
            self._dirty = True
        if self._dirty:
            self.save()
        return [self._vectors[_key(self.model, text)].tolist() for text in items]

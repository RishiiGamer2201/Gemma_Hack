"""Immutable retrieval diagnostics and deterministic corpus provenance."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType
from typing import Any

from .types import RetrievalDocument, RetrievalResult


def _canonical_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("retrieval metadata keys must be strings")
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        canonical = (_canonical_value(item) for item in value)
        return sorted(
            canonical,
            key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False),
        )
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("retrieval metadata floats must be finite")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported retrieval metadata type: {type(value).__name__}")


def corpus_sha256(documents: Sequence[RetrievalDocument]) -> str:
    """Hash searchable text and canonical provenance, independent of input order."""

    source_ids = [document.source_id for document in documents]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("corpus source_id values must be unique")
    records = [
        {
            "source_id": document.source_id,
            "text": document.text,
            "metadata": _canonical_value(document.metadata),
        }
        for document in sorted(documents, key=lambda item: item.source_id)
    ]
    payload = json.dumps(
        records, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class ChannelCandidate:
    channel: str
    source_id: str
    rank: int
    score: float


@dataclass(frozen=True, slots=True)
class RetrievalDebugTrace:
    original_terms: tuple[str, ...]
    expanded_terms: tuple[str, ...]
    active_filters: Mapping[str, Any]
    channel_candidates: tuple[ChannelCandidate, ...]
    exclusions: tuple[tuple[str, str], ...]
    deduplications: tuple[tuple[str, str, str], ...]
    corpus_sha256: str
    retriever_config: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "active_filters", MappingProxyType(dict(self.active_filters))
        )
        object.__setattr__(
            self, "retriever_config", MappingProxyType(dict(self.retriever_config))
        )


@dataclass(frozen=True, slots=True)
class DebugSearchResult:
    results: tuple[RetrievalResult, ...]
    trace: RetrievalDebugTrace

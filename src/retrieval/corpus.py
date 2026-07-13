"""Load reviewed corpus chunks into retrieval documents and typed evidence.

This module is the boundary between the offline corpus build and the retrieval
layer. It performs no legal inference: it copies provenance that the build
pipeline already verified, and it refuses any chunk that cannot supply the
citation fields a later claim-verification step requires.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models.schemas import SourceEvidence

from .types import RetrievalDocument, RetrievalResult

# SourceEvidence.excerpt is bounded. Preamble and schedule chunks can exceed it,
# so an over-long excerpt is cut at a whitespace boundary and explicitly flagged
# rather than silently shortened into what looks like a complete provision.
MAX_EXCERPT_CHARACTERS = 20_000


class CorpusLoadError(RuntimeError):
    """A bounded failure while loading a processed corpus chunk."""


def _searchable_text(record: dict[str, Any], metadata: dict[str, Any]) -> str:
    """Index citation-bearing labels alongside the body text."""

    parts = (
        metadata.get("act"),
        record.get("section_id"),
        record.get("heading"),
        record.get("text"),
    )
    return " ".join(str(part) for part in parts if part)


def _document_from_record(record: dict[str, Any], origin: Path) -> RetrievalDocument | None:
    chunk_id = record.get("chunk_id")
    body = record.get("text")
    raw_metadata = record.get("metadata")
    if not isinstance(chunk_id, str) or not isinstance(raw_metadata, dict):
        raise CorpusLoadError(f"{origin.name}: chunk requires a string chunk_id and metadata")
    if not isinstance(body, str) or not body.strip():
        # An empty chunk carries no retrievable text. The build report already
        # records empty and scan-review pages; skipping here is not data loss.
        return None

    metadata = dict(raw_metadata)
    # The build pipeline stores the section identifier and page span outside the
    # metadata mapping, but SearchFilters and overlap deduplication read them from
    # metadata. Copy them in so filtering and dedup see the real provenance.
    metadata["section"] = record.get("section_id")
    metadata["heading"] = record.get("heading")
    metadata["page_start"] = record.get("page_start")
    metadata["page_end"] = record.get("page_end")
    metadata["source_text"] = body
    metadata["corpus_source_id"] = record.get("source_id")

    return RetrievalDocument(
        source_id=chunk_id,
        text=_searchable_text(record, metadata),
        metadata=metadata,
    )


def load_processed_corpus(
    sections_dir: str | Path,
    *,
    source_ids: Iterable[str] | None = None,
) -> tuple[RetrievalDocument, ...]:
    """Load every reviewed JSONL chunk file into immutable retrieval documents."""

    directory = Path(sections_dir)
    if not directory.is_dir():
        raise CorpusLoadError(f"processed corpus directory does not exist: {directory}")

    wanted = set(source_ids) if source_ids is not None else None
    documents: list[RetrievalDocument] = []
    seen: set[str] = set()

    for path in sorted(directory.glob("*.jsonl")):
        if wanted is not None and path.stem not in wanted:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            raise CorpusLoadError(f"could not read corpus file: {path.name}") from exc
        for number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CorpusLoadError(f"{path.name}:{number} is not valid JSON") from exc
            if not isinstance(record, dict):
                raise CorpusLoadError(f"{path.name}:{number} must be a JSON object")
            document = _document_from_record(record, path)
            if document is None:
                continue
            if document.source_id in seen:
                raise CorpusLoadError(f"duplicate chunk_id across corpus: {document.source_id}")
            seen.add(document.source_id)
            documents.append(document)

    if wanted is not None:
        missing = sorted(wanted - {path.stem for path in directory.glob("*.jsonl")})
        if missing:
            raise CorpusLoadError("unknown corpus source_id value(s): " + ", ".join(missing))
    if not documents:
        raise CorpusLoadError(f"no retrievable chunks were found in {directory}")
    return tuple(documents)


def _bounded_excerpt(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_EXCERPT_CHARACTERS:
        return text, False
    window = text[:MAX_EXCERPT_CHARACTERS]
    boundary = window.rfind(" ")
    cut = window[:boundary] if boundary > MAX_EXCERPT_CHARACTERS // 2 else window
    return cut.rstrip(), True


def to_source_evidence(result: RetrievalResult) -> SourceEvidence:
    """Convert a ranked chunk into the typed evidence contract used downstream.

    Every field required for a displayable citation must already be present in the
    chunk. A chunk that cannot prove act, jurisdiction, URL, hash, and retrieval
    time is rejected rather than cited with invented provenance.
    """

    metadata = result.metadata
    body = metadata.get("source_text")
    if not isinstance(body, str) or not body.strip():
        raise CorpusLoadError(f"{result.source_id} has no citable source text")

    excerpt, truncated = _bounded_excerpt(body)
    retrieved_at = metadata.get("retrieved_at")
    if not isinstance(retrieved_at, str):
        raise CorpusLoadError(f"{result.source_id} has no retrieved_at provenance")
    try:
        parsed_retrieved_at = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CorpusLoadError(f"{result.source_id} has an invalid retrieved_at") from exc

    try:
        return SourceEvidence(
            source_id=result.source_id,
            jurisdiction=str(metadata["jurisdiction"]),
            act=str(metadata["act"]),
            section=_optional_text(metadata.get("section")),
            heading=_optional_text(metadata.get("heading")),
            language=str(metadata.get("language") or "en"),
            excerpt=excerpt,
            excerpt_truncated=truncated,
            effective_from=metadata.get("effective_from"),
            effective_to=metadata.get("effective_to"),
            status=str(metadata.get("status") or "unknown"),
            priority=int(metadata.get("priority") or 3),
            official_url=str(metadata["official_url"]),
            page=metadata.get("page_start"),
            retrieved_at=parsed_retrieved_at,
            sha256=str(metadata["sha256"]),
            ocr_used=bool(metadata.get("ocr_used", False)),
        )
    except KeyError as exc:
        raise CorpusLoadError(
            f"{result.source_id} is missing required citation provenance: {exc.args[0]}"
        ) from exc
    except (TypeError, ValueError) as exc:
        raise CorpusLoadError(
            f"{result.source_id} failed evidence validation: {exc}"
        ) from exc


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:500] if text else None

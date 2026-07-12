"""Heuristic, deterministic section chunking with page provenance."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .extract import ExtractedDocument

_SECTION = re.compile(
    r"^\s*(?:(?:section|sec\.)\s+)?(?P<number>\d+[A-Za-z]?)\.\s+(?P<title>\S.*)$",
    re.IGNORECASE,
)
_CONTENTS_MARKER = re.compile(r"\b(arrangement\s+of\s+sections|table\s+of\s+contents)\b", re.I)
_ENACTING_MARKER = re.compile(r"\bbe\s+it\s+enacted\b", re.I)
_DOT_LEADER = re.compile(r"\.{3,}\s*\d*\s*$")


@dataclass(frozen=True, slots=True)
class SectionChunk:
    chunk_id: str
    source_id: str
    section_id: str | None
    heading: str
    text: str
    page_start: int
    page_end: int
    metadata: Mapping[str, Any]

    def as_record(self) -> dict[str, Any]:
        return asdict(self)


def _clean(lines: Iterable[str]) -> str:
    return "\n".join(line.rstrip() for line in lines).strip()


def chunk_sections(
    document: ExtractedDocument,
    *,
    source_id: str,
    metadata: Mapping[str, Any] | None = None,
) -> list[SectionChunk]:
    """Split extracted pages on common Indian statute section headings.

    Pages explicitly labelled as an arrangement/table of sections are ignored
    when detecting boundaries, reducing duplicate chunks from a PDF's contents.
    Their text remains in the preamble so provenance is not silently discarded.
    """

    if not source_id.strip():
        raise ValueError("source_id must not be empty")
    base_metadata = dict(metadata or {})
    document_scan_review_pages = list(document.scan_review_pages)
    document_ocr_pages = list(document.ocr_pages)
    lines: list[tuple[int, str]] = []
    boundary_indices: list[tuple[int, str, str]] = []
    contents_mode = False
    for page in document.pages:
        page_lines = page.text.splitlines()
        for line in page_lines:
            index = len(lines)
            lines.append((page.page_number, line))
            # Transition in document order. A page can contain both the end of the
            # contents and the start of the enacted text.
            if _CONTENTS_MARKER.search(line):
                contents_mode = True
            if _ENACTING_MARKER.search(line):
                contents_mode = False
            match = _SECTION.match(line)
            if match and not contents_mode and not _DOT_LEADER.search(line):
                boundary_indices.append((index, match.group("number"), line.strip()))

    if not lines:
        return []
    chunks: list[SectionChunk] = []
    starts = [item[0] for item in boundary_indices]
    duplicate_count: dict[str, int] = {}

    def add_chunk(start: int, end: int, section_id: str | None, heading: str, slug: str) -> None:
        text = _clean(line for _, line in lines[start:end])
        if not text:
            return
        pages = [page for page, _ in lines[start:end]]
        page_start = min(pages)
        page_end = max(pages)
        span_pages = tuple(
            page for page in document.pages if page_start <= page.page_number <= page_end
        )
        chunk_metadata = dict(base_metadata)
        chunk_metadata.update(
            {
                # `ocr_used` is true only when a contributing page explicitly
                # declares that supplied text came from OCR.
                "ocr_used": any(page.ocr_used for page in span_pages),
                "document_ocr_used": bool(document_ocr_pages),
                "ocr_pages": document_ocr_pages,
                "scan_review_required": bool(document_scan_review_pages),
                "scan_review_pages": document_scan_review_pages,
                "chunk_scan_review_required": any(page.scan_review_required for page in span_pages),
                "page_extraction": [page.extraction_record() for page in span_pages],
            }
        )
        count = duplicate_count.get(slug, 0) + 1
        duplicate_count[slug] = count
        suffix = "" if count == 1 else f"-{count}"
        chunks.append(
            SectionChunk(
                chunk_id=f"{source_id}:{slug}{suffix}",
                source_id=source_id,
                section_id=section_id,
                heading=heading,
                text=text,
                page_start=page_start,
                page_end=page_end,
                metadata=chunk_metadata,
            )
        )

    first_boundary = starts[0] if starts else len(lines)
    if first_boundary:
        add_chunk(0, first_boundary, None, "Preamble", "preamble")
    for position, (start, section_id, heading) in enumerate(boundary_indices):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        add_chunk(start, end, section_id, heading, f"section-{section_id.casefold()}")
    if not chunks:
        add_chunk(0, len(lines), None, "Preamble", "preamble")
    return chunks


def write_jsonl(chunks: Iterable[SectionChunk], path: str | Path) -> None:
    """Write stable UTF-8 JSONL in the caller-provided chunk order."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    records = [
        json.dumps(chunk.as_record(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for chunk in chunks
    ]
    output_path.write_text("".join(record + "\n" for record in records), encoding="utf-8")

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
_NUMBERED_RULE = re.compile(r"^\s*(?P<number>\d+)\.\s*(?P<title>.*)$")
_SHORT_TITLE_EN = re.compile(r"\bshort\s+title\s+and\s+commencement\b", re.I)
_CALLED_RULES_EN = re.compile(r"\bthese\s+rules\s+may\s+be\s+called\b", re.I)
_SHORT_TITLE_HI = re.compile(r"(?:संक्षिप्त|संजक्षप्त)\s+(?:नाम|िाम)")
_RULE_HEADING_DELIMITER = re.compile(r"[A-Za-z]\.?\s*[—–-]+\s*(?=\(|[A-Z])")
_AMENDMENT_RULE_BODY = re.compile(r"^(?:in|for)\s+the\b", re.I)
_TABLE_VALUE_TERMS = re.compile(r"\b(?:rs\.?|rupees?|lakh|crore)\b", re.I)
_ENGLISH_GAZETTE_NOISE = re.compile(
    r"(?:भारत\s+का\s+रा\S*पत्र|\[?भाग\s*II|THE GAZETTE OF INDIA\s*:\s*EXTRAORDINARY|"
    r"\[?PART\s+II[—-]SEC\.)",
    re.I,
)
_PRIVATE_USE = re.compile(r"[\ue000-\uf8ff]")


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


def chunk_gazette_rules_english(
    document: ExtractedDocument,
    *,
    source_id: str,
    metadata: Mapping[str, Any] | None = None,
) -> list[SectionChunk]:
    """Chunk English rule/regulation instruments in bilingual Gazette PDFs.

    Gazette artifacts commonly print the complete Hindi instrument followed by
    the complete English instrument. Some Department PDFs bundle more than one
    instrument. This strategy starts only at an English ``Short title and
    commencement`` rule 1, stops before the next Hindi or English instrument,
    and accepts only monotonically increasing top-level rule numbers. Numbered
    table rows therefore remain attached to their parent rule.

    If no English instrument boundary can be proved (for example a one-page
    corrigendum), the conservative generic chunker is used instead.
    """

    if not source_id.strip():
        raise ValueError("source_id must not be empty")
    base_metadata = dict(metadata or {})
    lines = [
        (page.page_number, line)
        for page in document.pages
        for line in page.text.splitlines()
    ]
    if not lines:
        return []

    rule_ones: list[tuple[int, str]] = []
    for index, (_, line) in enumerate(lines):
        match = _NUMBERED_RULE.match(line)
        if not match or match.group("number") != "1":
            continue
        title_context = _candidate_title(lines, index, match.group("title"))
        if _SHORT_TITLE_EN.search(title_context) or _CALLED_RULES_EN.search(title_context):
            rule_ones.append((index, "en"))
        elif _SHORT_TITLE_HI.search(title_context):
            rule_ones.append((index, "hi"))

    english_starts = [index for index, language in rule_ones if language == "en"]
    if not english_starts:
        return chunk_sections(document, source_id=source_id, metadata=base_metadata)

    chunks: list[SectionChunk] = []
    for instrument_index, start in enumerate(english_starts, start=1):
        later_instruments = [index for index, _ in rule_ones if index > start]
        end = min(later_instruments) if later_instruments else len(lines)
        boundaries = _monotonic_rule_boundaries(lines, start, end)
        end = _trim_next_hindi_preamble(lines, boundaries, end)
        instrument_title = _instrument_title(lines, start)
        for boundary_index, (rule_start, rule_number, heading) in enumerate(boundaries):
            rule_end = (
                boundaries[boundary_index + 1][0]
                if boundary_index + 1 < len(boundaries)
                else end
            )
            text = _clean(
                line
                for _, line in lines[rule_start:rule_end]
                if not _ENGLISH_GAZETTE_NOISE.search(line) and not _PRIVATE_USE.search(line)
            )
            if not text:
                continue
            pages = [page for page, _ in lines[rule_start:rule_end]]
            page_start, page_end = min(pages), max(pages)
            span_pages = tuple(
                page for page in document.pages if page_start <= page.page_number <= page_end
            )
            chunk_metadata = dict(base_metadata)
            chunk_metadata.update(
                {
                    "language": "en",
                    "source_language": base_metadata.get("language"),
                    "translation_available_in_source": base_metadata.get("language") == "hi-en",
                    "instrument_index": instrument_index,
                    "instrument_title": instrument_title,
                    "ocr_used": any(page.ocr_used for page in span_pages),
                    "document_ocr_used": bool(document.ocr_pages),
                    "ocr_pages": list(document.ocr_pages),
                    "scan_review_required": bool(document.scan_review_pages),
                    "scan_review_pages": list(document.scan_review_pages),
                    "chunk_scan_review_required": any(
                        page.scan_review_required for page in span_pages
                    ),
                    "page_extraction": [page.extraction_record() for page in span_pages],
                }
            )
            chunks.append(
                SectionChunk(
                    chunk_id=(
                        f"{source_id}:instrument-{instrument_index}:rule-{rule_number}"
                    ),
                    source_id=source_id,
                    section_id=rule_number,
                    heading=heading,
                    text=text,
                    page_start=page_start,
                    page_end=page_end,
                    metadata=chunk_metadata,
                )
            )
    return chunks


def _candidate_title(
    lines: list[tuple[int, str]], index: int, inline_title: str
) -> str:
    parts = [inline_title.strip()] if inline_title.strip() else []
    if parts and (
        _RULE_HEADING_DELIMITER.search(parts[0])
        or _SHORT_TITLE_EN.search(parts[0])
        or _CALLED_RULES_EN.search(parts[0])
    ):
        return parts[0]
    for _, line in lines[index + 1 : min(index + 5, len(lines))]:
        stripped = line.strip()
        if not stripped:
            continue
        if parts and _NUMBERED_RULE.match(stripped):
            break
        parts.append(stripped)
        candidate = " ".join(parts)
        if (
            _RULE_HEADING_DELIMITER.search(candidate)
            or _SHORT_TITLE_EN.search(candidate)
            or _CALLED_RULES_EN.search(candidate)
        ):
            break
    return " ".join(parts)


def _monotonic_rule_boundaries(
    lines: list[tuple[int, str]], start: int, end: int
) -> list[tuple[int, str, str]]:
    first = _NUMBERED_RULE.match(lines[start][1])
    if not first:
        return []
    first_title = _candidate_title(lines, start, first.group("title"))
    boundaries = [(start, "1", f"1. {first_title}")]
    cursor = start + 1
    expected = 2
    while cursor < end:
        candidates: list[tuple[int, int, str]] = []
        for index in range(cursor, end):
            match = _NUMBERED_RULE.match(lines[index][1])
            if not match or int(match.group("number")) != expected:
                continue
            title = _candidate_title(lines, index, match.group("title"))
            score = _rule_boundary_score(title)
            if score > 0:
                candidates.append((score, index, title))
        if not candidates:
            break
        # Strong heading punctuation wins; ties retain the earliest source occurrence.
        score, index, title = max(candidates, key=lambda item: (item[0], -item[1]))
        del score
        boundaries.append((index, str(expected), f"{expected}. {title}"))
        cursor = index + 1
        expected += 1
    return boundaries


def _rule_boundary_score(title: str) -> int:
    """Prefer legal headings over same-number table rows without requiring one layout."""

    if not title:
        return 0
    if _RULE_HEADING_DELIMITER.search(title):
        return 10
    if _AMENDMENT_RULE_BODY.search(title):
        return 9
    if _TABLE_VALUE_TERMS.search(title):
        return 0
    if title[0].isupper() and len(title) <= 500:
        return 1
    return 0


def _instrument_title(lines: list[tuple[int, str]], start: int) -> str:
    sample = " ".join(line for _, line in lines[start : min(start + 8, len(lines))])
    match = re.search(r"called\s+the\s+(.+?)(?:\.\s|\.\(|$)", sample, re.I)
    if match:
        return " ".join(match.group(1).split()).rstrip(".")
    return "English Gazette instrument"


def _trim_next_hindi_preamble(
    lines: list[tuple[int, str]],
    boundaries: list[tuple[int, str, str]],
    end: int,
) -> int:
    """Exclude a following bundled Hindi instrument's preamble from the last English rule."""

    if not boundaries:
        return end
    run_start: int | None = None
    run_length = 0
    for index in range(boundaries[-1][0] + 1, end):
        text = lines[index][1].strip()
        if not text:
            continue
        letters = [character for character in text if character.isalpha()]
        devanagari = sum("\u0900" <= character <= "\u097f" for character in letters)
        is_hindi_heavy = bool(letters) and devanagari / len(letters) >= 0.55
        if is_hindi_heavy:
            run_start = index if run_start is None else run_start
            run_length += 1
            if run_length >= 3:
                return run_start
        else:
            run_start = None
            run_length = 0
    return end

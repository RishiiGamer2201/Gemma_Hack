"""Text extraction interface with optional local PDF adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


class ExtractionError(RuntimeError):
    """Raised when a requested local extraction backend is unavailable or fails."""


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    path: Path
    parser: str
    pages: tuple[ExtractedPage, ...]


def _extract_text(path: Path) -> ExtractedDocument:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractionError("plain-text source must be UTF-8") from exc
    except OSError as exc:
        raise ExtractionError(f"could not read source: {path}") from exc
    parts = text.split("\f")
    pages = tuple(ExtractedPage(index, part) for index, part in enumerate(parts, start=1))
    return ExtractedDocument(path=path, parser="text", pages=pages)


def _extract_pypdf(path: Path) -> ExtractedDocument:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ExtractionError("pypdf is not installed; install the optional PDF adapter") from exc
    try:
        reader = PdfReader(path)
        pages = tuple(
            ExtractedPage(index, page.extract_text() or "")
            for index, page in enumerate(reader.pages, start=1)
        )
    except Exception as exc:
        raise ExtractionError(f"pypdf could not extract {path.name}: {exc}") from exc
    return ExtractedDocument(path=path, parser="pypdf", pages=pages)


def _extract_pymupdf(path: Path) -> ExtractedDocument:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ExtractionError("PyMuPDF is not installed; install the optional PDF adapter") from exc
    try:
        with fitz.open(path) as document:
            pages = tuple(
                ExtractedPage(index, page.get_text("text"))
                for index, page in enumerate(document, start=1)
            )
    except Exception as exc:
        raise ExtractionError(f"PyMuPDF could not extract {path.name}: {exc}") from exc
    return ExtractedDocument(path=path, parser="pymupdf", pages=pages)


_EXTRACTORS: dict[str, Callable[[Path], ExtractedDocument]] = {
    "text": _extract_text,
    "pypdf": _extract_pypdf,
    "pymupdf": _extract_pymupdf,
}


def extract_document(path: str | Path, *, parser: str = "auto") -> ExtractedDocument:
    source_path = Path(path)
    if not source_path.is_file():
        raise ExtractionError(f"source file does not exist: {source_path}")
    if parser == "auto":
        if source_path.suffix.casefold() in {".txt", ".text"}:
            return _extract_text(source_path)
        failures: list[str] = []
        for name in ("pypdf", "pymupdf"):
            try:
                return _EXTRACTORS[name](source_path)
            except ExtractionError as exc:
                failures.append(str(exc))
        raise ExtractionError("no PDF extraction adapter succeeded: " + " | ".join(failures))
    try:
        extractor = _EXTRACTORS[parser]
    except KeyError as exc:
        raise ExtractionError(f"unsupported parser: {parser}") from exc
    return extractor(source_path)

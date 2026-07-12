"""Text extraction interface with optional local PDF adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# A page with fewer than both of these counts is not trusted as digitally
# extractable. The conservative thresholds catch image-only/blank pages while
# keeping short headings and numbered provisions as digital text. This is a
# review signal, not proof that a page is scanned.
MIN_DIGITAL_NON_WHITESPACE_CHARACTERS = 20
MIN_DIGITAL_ALPHANUMERIC_CHARACTERS = 5


class ExtractionError(RuntimeError):
    """Raised when a requested local extraction backend is unavailable or fails."""


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    page_number: int
    text: str
    ocr_used: bool = False

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise ValueError("page_number must be at least 1")
        if self.ocr_used and not self.text.strip():
            raise ValueError("ocr_used requires supplied non-empty OCR text")

    @property
    def non_whitespace_character_count(self) -> int:
        return sum(not character.isspace() for character in self.text)

    @property
    def alphanumeric_character_count(self) -> int:
        return sum(character.isalnum() for character in self.text)

    @property
    def extraction_status(self) -> str:
        """Return a deterministic, non-diagnostic page extraction signal."""

        if self.ocr_used:
            return "ocr_text_supplied"
        if not self.text.strip():
            return "no_extracted_text"
        if (
            self.non_whitespace_character_count < MIN_DIGITAL_NON_WHITESPACE_CHARACTERS
            and self.alphanumeric_character_count < MIN_DIGITAL_ALPHANUMERIC_CHARACTERS
        ):
            return "insufficient_extracted_text"
        return "digital_text"

    @property
    def scan_review_required(self) -> bool:
        """Flag likely scanned/blank pages without claiming scan certainty."""

        return self.extraction_status in {
            "no_extracted_text",
            "insufficient_extracted_text",
        }

    def extraction_record(self) -> dict[str, int | bool | str]:
        return {
            "page_number": self.page_number,
            "status": self.extraction_status,
            "ocr_used": self.ocr_used,
            "non_whitespace_character_count": self.non_whitespace_character_count,
            "alphanumeric_character_count": self.alphanumeric_character_count,
        }


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    path: Path
    parser: str
    pages: tuple[ExtractedPage, ...]

    @property
    def scan_review_pages(self) -> tuple[int, ...]:
        return tuple(page.page_number for page in self.pages if page.scan_review_required)

    @property
    def ocr_pages(self) -> tuple[int, ...]:
        return tuple(page.page_number for page in self.pages if page.ocr_used)


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

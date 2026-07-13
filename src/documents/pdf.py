"""Bounded, in-memory text extraction from a citizen-uploaded PDF.

A user photographs or downloads a notice, FIR, or summons and hands it to the app.
The bytes are read once into memory, never written to disk, and the recognised text
goes into the intake box for the user to correct. It is a draft, not a confirmed
fact, and it never bypasses the confirmation gate.

Only digitally readable PDFs are handled here. A scanned PDF carries no extractable
text, and this module says so plainly rather than returning an empty string that
would look like an empty document.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from pathlib import Path

MAX_PDF_BYTES = 15 * 1024 * 1024
MAX_PAGES = 30
MAX_TEXT_CHARACTERS = 100_000

# A page below both thresholds is not trusted as digitally extractable. Mirrors the
# corpus pipeline's scan-review signal so the two agree on what "scanned" means.
MIN_PAGE_NON_WHITESPACE = 20
MIN_PAGE_ALPHANUMERIC = 5
MAX_IMAGES_PER_PAGE = 4


class PdfErrorCode(StrEnum):
    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED_FORMAT = "unsupported_format"
    PDF_LIMIT_EXCEEDED = "pdf_limit_exceeded"
    ENCRYPTED_PDF = "encrypted_pdf"
    INVALID_PDF = "invalid_pdf"
    NO_EXTRACTABLE_TEXT = "no_extractable_text"
    BACKEND_UNAVAILABLE = "backend_unavailable"


class PdfError(RuntimeError):
    def __init__(self, code: PdfErrorCode, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


@dataclass(frozen=True, slots=True)
class PdfExtraction:
    text: str
    page_count: int
    pages_with_text: int
    scanned_pages: tuple[int, ...]
    truncated: bool
    # Pages whose text came from OCR of an embedded scan, not from the PDF's own
    # text layer. OCR misreads dates and section numbers, and those change the legal
    # answer, so the caller must tell the user which pages were guessed at.
    ocr_pages: tuple[int, ...] = ()

    @property
    def looks_scanned(self) -> bool:
        return self.pages_with_text == 0


def _ocr_page_images(page, ocr_config) -> str:  # noqa: ANN001
    """OCR the raster images embedded in a scanned page.

    A scanned PDF is a picture of a page: the text layer is empty and the content is
    one big JPEG. pypdf hands back that image, and the same pinned Tesseract that
    reads an uploaded photo reads it here. Nothing touches disk.
    """

    from src.ocr import OCRError, extract_image_bytes

    pieces: list[str] = []
    try:
        images = list(page.images)
    except Exception:
        return ""
    for number, image in enumerate(images[:MAX_IMAGES_PER_PAGE], start=1):
        raw = bytes(image.data)
        if not raw or len(raw) > MAX_PDF_BYTES:
            continue
        name = str(getattr(image, "name", "") or "")
        suffix = Path(name).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg"}:
            # pypdf can hand back a raw bitmap with no recognisable container. The
            # OCR adapter only accepts PNG/JPEG, and guessing a format would be a
            # decoding bug waiting to happen.
            continue
        try:
            result = extract_image_bytes(raw, f"page-{number}{suffix}", ocr_config)
        except OCRError:
            # OCR is a fallback. If it is unavailable or fails, the page stays
            # reported as scanned rather than the whole upload failing.
            continue
        if result.text.strip():
            pieces.append(result.text.strip())
    return "\n".join(pieces)


def extract_pdf_text(
    data: bytes,
    filename: str,
    ocr_config=None,  # noqa: ANN001
) -> PdfExtraction:
    """Extract text from PDF bytes held in memory. Nothing is written to disk.

    When ``ocr_config`` is supplied, a page with no text layer is treated as a scan:
    its embedded image is run through the same pinned Tesseract used for photo
    uploads. Those pages are reported in ``ocr_pages`` so the user can be told the
    text was read from a picture and must be checked.
    """

    if type(data) is not bytes:  # noqa: E721 - a mutable buffer is rejected on purpose
        raise PdfError(PdfErrorCode.INVALID_REQUEST, "PDF data must be immutable bytes")
    if not filename.lower().endswith(".pdf"):
        raise PdfError(
            PdfErrorCode.UNSUPPORTED_FORMAT, "only PDF files are accepted", field="file"
        )
    if not data:
        raise PdfError(PdfErrorCode.INVALID_PDF, "the PDF is empty", field="file")
    if len(data) > MAX_PDF_BYTES:
        raise PdfError(
            PdfErrorCode.PDF_LIMIT_EXCEEDED,
            f"the PDF exceeds the {MAX_PDF_BYTES}-byte limit",
            field="file",
        )
    if not data.startswith(b"%PDF-"):
        raise PdfError(
            PdfErrorCode.INVALID_PDF, "the file does not have a PDF signature", field="file"
        )

    try:
        pypdf = importlib.import_module("pypdf")
    except ImportError as exc:
        raise PdfError(
            PdfErrorCode.BACKEND_UNAVAILABLE,
            "pypdf is not installed; install the project's corpus extra",
        ) from exc

    try:
        reader = pypdf.PdfReader(BytesIO(data))
        if reader.is_encrypted:
            # Do not attempt an empty-password unlock: a protected document is the
            # owner's decision, not ours to work around.
            raise PdfError(
                PdfErrorCode.ENCRYPTED_PDF,
                "the PDF is password-protected; unlock it and upload again",
                field="file",
            )
        pages = reader.pages
    except PdfError:
        raise
    except Exception as exc:
        raise PdfError(PdfErrorCode.INVALID_PDF, "the PDF could not be read") from exc

    page_count = len(pages)
    if page_count == 0:
        raise PdfError(PdfErrorCode.INVALID_PDF, "the PDF has no pages", field="file")

    parts: list[str] = []
    scanned: list[int] = []
    ocr_pages: list[int] = []
    with_text = 0
    total = 0
    truncated = page_count > MAX_PAGES

    for number, page in enumerate(pages[:MAX_PAGES], start=1):
        try:
            page_text = (page.extract_text() or "").strip()
        except Exception:
            # One unreadable page must not lose the rest of the document.
            page_text = ""
        non_space = sum(not character.isspace() for character in page_text)
        alphanumeric = sum(character.isalnum() for character in page_text)
        if non_space < MIN_PAGE_NON_WHITESPACE and alphanumeric < MIN_PAGE_ALPHANUMERIC:
            recognised = _ocr_page_images(page, ocr_config) if ocr_config else ""
            if not recognised.strip():
                scanned.append(number)
                continue
            page_text = recognised.strip()
            ocr_pages.append(number)
        with_text += 1
        if total + len(page_text) > MAX_TEXT_CHARACTERS:
            page_text = page_text[: max(0, MAX_TEXT_CHARACTERS - total)]
            truncated = True
        parts.append(page_text)
        total += len(page_text)
        if total >= MAX_TEXT_CHARACTERS:
            break

    if with_text == 0:
        raise PdfError(
            PdfErrorCode.NO_EXTRACTABLE_TEXT,
            "This PDF has no readable text — it is probably a scan. Take a photo of "
            "the page and upload it as an image instead, or type the text.",
            field="file",
        )

    return PdfExtraction(
        text="\n\n".join(parts).strip(),
        page_count=page_count,
        pages_with_text=with_text,
        scanned_pages=tuple(scanned),
        truncated=truncated,
        ocr_pages=tuple(ocr_pages),
    )

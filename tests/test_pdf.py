"""PDF intake: bounded, in-memory, never persisted, honest about scans."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from src.documents.pdf import (
    MAX_PDF_BYTES,
    PdfError,
    PdfErrorCode,
    extract_pdf_text,
)

pypdf = pytest.importorskip("pypdf")


def make_pdf(pages: list[str]) -> bytes:
    writer = pypdf.PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        if text:
            # pypdf cannot draw text, so a page is "digital" only when a real PDF
            # supplies a content stream. Blank pages stand in for scanned pages.
            del page
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def real_pdf() -> bytes:
    source = Path("pdf.pdf")
    if not source.is_file():
        pytest.skip("the sample PDF is not present")
    return source.read_bytes()


def test_a_digital_page_is_extracted_and_scanned_pages_are_flagged() -> None:
    result = extract_pdf_text(real_pdf(), "notice.pdf")

    assert result.page_count == 5
    assert result.pages_with_text >= 1
    # The handwritten pages carry no extractable text and must be reported as such,
    # not silently returned as empty content.
    assert result.scanned_pages
    assert result.text.strip()


def test_a_fully_scanned_pdf_is_refused_with_an_instruction() -> None:
    blank = make_pdf(["", ""])

    with pytest.raises(PdfError) as caught:
        extract_pdf_text(blank, "scan.pdf")

    assert caught.value.code is PdfErrorCode.NO_EXTRACTABLE_TEXT
    # An empty string would look like an empty document. Tell the user what to do.
    assert "photo" in caught.value.message


def test_non_pdf_and_oversized_input_are_rejected() -> None:
    with pytest.raises(PdfError) as wrong_type:
        extract_pdf_text(b"%PDF-1.4 fake", "notice.png")
    assert wrong_type.value.code is PdfErrorCode.UNSUPPORTED_FORMAT

    with pytest.raises(PdfError) as not_a_pdf:
        extract_pdf_text(b"\x89PNG\r\n", "notice.pdf")
    assert not_a_pdf.value.code is PdfErrorCode.INVALID_PDF

    with pytest.raises(PdfError) as too_big:
        extract_pdf_text(b"%PDF-" + b"0" * (MAX_PDF_BYTES + 1), "notice.pdf")
    assert too_big.value.code is PdfErrorCode.PDF_LIMIT_EXCEEDED

    with pytest.raises(PdfError):
        extract_pdf_text(bytearray(b"%PDF-1.4"), "notice.pdf")  # type: ignore[arg-type]


def test_an_encrypted_pdf_is_not_silently_unlocked() -> None:
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("secret")
    buffer = io.BytesIO()
    writer.write(buffer)

    with pytest.raises(PdfError) as caught:
        extract_pdf_text(buffer.getvalue(), "protected.pdf")

    # A protected document is the owner's decision; do not try an empty password.
    assert caught.value.code is PdfErrorCode.ENCRYPTED_PDF


def scanned_pdf() -> bytes:
    """A real scan: an image of a page, with no text layer at all."""

    Image = pytest.importorskip("PIL.Image")
    ImageDraw = pytest.importorskip("PIL.ImageDraw")

    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    draw.text((110, 120), "LEGAL NOTICE", fill="black")
    draw.text((110, 200), "Date: 10 April 2026", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, "PDF", resolution=150)
    return buffer.getvalue()


def test_a_scan_is_refused_when_no_ocr_is_available() -> None:
    with pytest.raises(PdfError) as caught:
        extract_pdf_text(scanned_pdf(), "notice.pdf")

    # Without OCR there is genuinely nothing to read. Say so; do not return "".
    assert caught.value.code is PdfErrorCode.NO_EXTRACTABLE_TEXT


def test_a_scanned_page_is_read_by_ocr_and_reported_as_ocr() -> None:
    """The text is a guess from a picture. The user must be told which pages."""

    tessdata = Path("models/ocr/tessdata")
    if not tessdata.is_dir():
        pytest.skip("the pinned tessdata is not present")
    from src.ocr import OCRConfig, OCRError, OCRLanguage

    config = OCRConfig(tessdata_dir=tessdata, language=OCRLanguage.ENGLISH)
    try:
        result = extract_pdf_text(scanned_pdf(), "notice.pdf", config)
    except OCRError:
        pytest.skip("the pinned Tesseract is not installed on this machine")

    assert result.ocr_pages == (1,)
    assert result.scanned_pages == ()
    assert "LEGAL NOTICE" in result.text

    # Deliberately NOT asserting the date round-trips. On this very fixture Tesseract
    # read "10 April 2026" as "10 Aprit 2028" -- a two-year error on the one field
    # that decides whether the IPC or the BNS applies. That is not a bug to be fixed
    # by a better assertion; it is the reason OCR output is a draft and the user must
    # confirm it. What the contract must guarantee is that the page is FLAGGED as
    # OCR-derived, so the UI can tell them to check it.
    assert 1 in result.ocr_pages

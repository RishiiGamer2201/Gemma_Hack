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

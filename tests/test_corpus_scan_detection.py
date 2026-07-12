from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.corpus.chunker import chunk_sections
from src.corpus.extract import (
    MIN_DIGITAL_ALPHANUMERIC_CHARACTERS,
    MIN_DIGITAL_NON_WHITESPACE_CHARACTERS,
    ExtractedDocument,
    ExtractedPage,
)
from src.corpus.pipeline import build_corpus
from tests.test_corpus_pipeline import PipelineFixture


class ScanDetectionTests(unittest.TestCase):
    def test_thresholds_and_page_signals_are_deterministic(self) -> None:
        empty = ExtractedPage(1, " \n")
        short = ExtractedPage(2, "I.")
        digital_by_characters = ExtractedPage(3, "-" * MIN_DIGITAL_NON_WHITESPACE_CHARACTERS)
        digital_by_alphanumerics = ExtractedPage(4, "a" * MIN_DIGITAL_ALPHANUMERIC_CHARACTERS)

        self.assertEqual(empty.extraction_status, "no_extracted_text")
        self.assertEqual(short.extraction_status, "insufficient_extracted_text")
        self.assertTrue(empty.scan_review_required)
        self.assertTrue(short.scan_review_required)
        self.assertEqual(digital_by_characters.extraction_status, "digital_text")
        self.assertEqual(digital_by_alphanumerics.extraction_status, "digital_text")

    def test_ocr_is_never_inferred_and_requires_supplied_text(self) -> None:
        likely_scan = ExtractedPage(1, "")
        supplied_ocr = ExtractedPage(2, "OCR supplied legal text", ocr_used=True)

        self.assertFalse(likely_scan.ocr_used)
        self.assertEqual(supplied_ocr.extraction_status, "ocr_text_supplied")
        self.assertFalse(supplied_ocr.scan_review_required)
        with self.assertRaisesRegex(ValueError, "supplied non-empty OCR text"):
            ExtractedPage(3, "", ocr_used=True)

    def test_chunks_preserve_page_numbers_and_document_review_flags(self) -> None:
        document = ExtractedDocument(
            path=Path("mixed.pdf"),
            parser="mock-local",
            pages=(
                ExtractedPage(1, "Be it enacted\n1. Right\nDigital legal text"),
                ExtractedPage(2, ""),
                ExtractedPage(3, "Continuation from supplied OCR", ocr_used=True),
            ),
        )
        chunks = chunk_sections(document, source_id="mixed")
        section = next(chunk for chunk in chunks if chunk.section_id == "1")

        self.assertEqual((section.page_start, section.page_end), (1, 3))
        self.assertTrue(section.metadata["ocr_used"])
        self.assertTrue(section.metadata["document_ocr_used"])
        self.assertTrue(section.metadata["scan_review_required"])
        self.assertTrue(section.metadata["chunk_scan_review_required"])
        self.assertEqual(section.metadata["scan_review_pages"], [2])
        self.assertEqual(
            [item["page_number"] for item in section.metadata["page_extraction"]],
            [1, 2, 3],
        )

    def test_existing_digital_text_chunking_remains_unflagged(self) -> None:
        document = ExtractedDocument(
            path=Path("digital.pdf"),
            parser="mock-local",
            pages=(ExtractedPage(1, "Be it enacted\n1. Right\nDigital legal text"),),
        )
        chunks = chunk_sections(document, source_id="digital")
        section = next(chunk for chunk in chunks if chunk.section_id == "1")

        self.assertEqual(section.text, "1. Right\nDigital legal text")
        self.assertFalse(section.metadata["ocr_used"])
        self.assertFalse(section.metadata["document_ocr_used"])
        self.assertFalse(section.metadata["scan_review_required"])
        self.assertFalse(section.metadata["chunk_scan_review_required"])
        self.assertEqual(section.metadata["scan_review_pages"], [])

    def test_pipeline_rejects_empty_pages_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = PipelineFixture(Path(directory))
            fixture.install_verified_artifact()
            mixed = ExtractedDocument(
                fixture.source_path,
                "mock-local",
                (ExtractedPage(1, "Digital legal text long enough"), ExtractedPage(2, "")),
            )
            with patch("src.corpus.pipeline.extract_document", return_value=mixed):
                report = build_corpus(fixture.manifest, fixture.raw, fixture.output)

        self.assertEqual(report.required_failures, 1)
        self.assertIn("possible scanned pages require review", report.failures[0].error)

    def test_low_text_page_is_retained_but_explicitly_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = PipelineFixture(Path(directory))
            fixture.install_verified_artifact()
            low_text = ExtractedDocument(
                fixture.source_path,
                "mock-local",
                (ExtractedPage(1, "I."),),
            )
            with patch("src.corpus.pipeline.extract_document", return_value=low_text):
                report = build_corpus(fixture.manifest, fixture.raw, fixture.output)
            record = json.loads(
                (fixture.output / f"{fixture.source_id}.jsonl").read_text(encoding="utf-8").strip()
            )

        self.assertEqual(report.required_failures, 0)
        self.assertEqual(report.successes[0].scan_review_page_count, 1)
        self.assertTrue(record["metadata"]["scan_review_required"])
        self.assertEqual(
            record["metadata"]["page_extraction"][0]["status"],
            "insufficient_extracted_text",
        )

    def test_all_empty_document_fails_even_when_empty_pages_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = PipelineFixture(Path(directory))
            fixture.install_verified_artifact()
            empty = ExtractedDocument(
                fixture.source_path,
                "mock-local",
                (ExtractedPage(1, ""), ExtractedPage(2, " \n")),
            )
            with patch("src.corpus.pipeline.extract_document", return_value=empty):
                report = build_corpus(
                    fixture.manifest,
                    fixture.raw,
                    fixture.output,
                    allow_empty_pages=True,
                )

        self.assertEqual(report.required_failures, 1)
        self.assertIn("no non-empty chunks", report.failures[0].error)

    def test_allowed_mixed_document_retains_review_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = PipelineFixture(Path(directory))
            fixture.install_verified_artifact()
            mixed = ExtractedDocument(
                fixture.source_path,
                "mock-local",
                (
                    ExtractedPage(1, "Be it enacted\n1. Right\nDigital legal text"),
                    ExtractedPage(2, ""),
                ),
            )
            with patch("src.corpus.pipeline.extract_document", return_value=mixed):
                report = build_corpus(
                    fixture.manifest,
                    fixture.raw,
                    fixture.output,
                    allow_empty_pages=True,
                )
            records = [
                json.loads(line)
                for line in (fixture.output / f"{fixture.source_id}.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]

        result = report.successes[0]
        self.assertEqual(result.empty_page_count, 1)
        self.assertEqual(result.scan_review_page_count, 1)
        self.assertEqual(result.ocr_page_count, 0)
        self.assertTrue(result.scan_review_required)
        self.assertTrue(all(record["metadata"]["scan_review_required"] for record in records))
        self.assertTrue(all(not record["metadata"]["ocr_used"] for record in records))


if __name__ == "__main__":
    unittest.main()

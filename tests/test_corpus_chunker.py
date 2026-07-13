from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.corpus.chunker import chunk_sections, write_jsonl
from src.corpus.extract import ExtractedDocument, ExtractedPage


def document(*pages: str) -> ExtractedDocument:
    return ExtractedDocument(
        path=Path("synthetic.pdf"),
        parser="test",
        pages=tuple(ExtractedPage(index, text) for index, text in enumerate(pages, 1)),
    )


class ChunkerTests(unittest.TestCase):
    def test_same_page_contents_end_does_not_create_duplicate_section(self) -> None:
        chunks = chunk_sections(
            document(
                "ARRANGEMENT OF SECTIONS\n1. Contents entry\n"
                "Be it enacted\n1. Operative heading\nActual law"
            ),
            source_id="synthetic",
        )
        sections = [chunk for chunk in chunks if chunk.section_id == "1"]
        self.assertEqual(len(sections), 1)
        self.assertIn("Operative heading", sections[0].heading)

    def test_sections_preserve_page_span_and_metadata(self) -> None:
        chunks = chunk_sections(
            document(
                "THE SYNTHETIC ACT\nBe it enacted\n1. First provision\nBody on page one",
                "Continuation of first\n2. Second provision\nSecond body",
            ),
            source_id="synthetic",
            metadata={"language": "en", "effective_from": "2024-07-01"},
        )
        first = next(chunk for chunk in chunks if chunk.section_id == "1")
        self.assertEqual((first.page_start, first.page_end), (1, 2))
        self.assertEqual(first.metadata["language"], "en")

    def test_table_of_contents_headings_do_not_create_section_chunks(self) -> None:
        chunks = chunk_sections(
            document(
                "ARRANGEMENT OF SECTIONS\n1. Contents entry ..... 1\n2. Another entry ..... 2",
                "Be it enacted\n1. Operative first\nActual law\n2. Operative second\nMore law",
            ),
            source_id="synthetic",
        )
        self.assertEqual([chunk.section_id for chunk in chunks], [None, "1", "2"])
        self.assertEqual(sum(chunk.section_id == "1" for chunk in chunks), 1)

    def test_duplicate_section_numbers_receive_stable_unique_ids(self) -> None:
        chunks = chunk_sections(
            document("Be it enacted\n1. First\nBody\n1. Repeated\nBody"),
            source_id="synthetic",
        )
        section_ids = [chunk.chunk_id for chunk in chunks if chunk.section_id == "1"]
        self.assertEqual(section_ids, ["synthetic:section-1", "synthetic:section-1-2"])

    def test_empty_document_produces_no_chunks(self) -> None:
        self.assertEqual(chunk_sections(document(), source_id="synthetic"), [])

    def test_jsonl_is_deterministic_utf8_and_round_trippable(self) -> None:
        chunks = chunk_sections(
            document("Be it enacted\n1. अधिकार\nनागरिक का अधिकार"),
            source_id="synthetic",
            metadata={"z": 1, "a": 2},
        )
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jsonl"
            second = Path(directory) / "second.jsonl"
            write_jsonl(chunks, first)
            write_jsonl(chunks, second)
            first_bytes = first.read_bytes()
            self.assertEqual(first_bytes, second.read_bytes())
            records = [json.loads(line) for line in first.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(records[-1]["section_id"], "1")
        self.assertIn("अधिकार", records[-1]["text"])


if __name__ == "__main__":
    unittest.main()

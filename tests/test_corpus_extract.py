from __future__ import annotations

import builtins
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.corpus.extract import ExtractionError, extract_document


class ExtractionTests(unittest.TestCase):
    def test_text_extraction_preserves_form_feed_page_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "act.txt"
            path.write_text("page one\fpage two", encoding="utf-8")
            document = extract_document(path, parser="text")
        self.assertEqual(document.parser, "text")
        self.assertEqual([(page.page_number, page.text) for page in document.pages], [(1, "page one"), (2, "page two")])

    def test_non_utf8_text_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "act.txt"
            path.write_bytes(b"\xff\xfe")
            with self.assertRaisesRegex(ExtractionError, "must be UTF-8"):
                extract_document(path, parser="text")

    def test_missing_source_and_unknown_parser_are_bounded_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.pdf"
            with self.assertRaisesRegex(ExtractionError, "does not exist"):
                extract_document(missing)
            existing = Path(directory) / "existing.pdf"
            existing.write_bytes(b"%PDF-")
            with self.assertRaisesRegex(ExtractionError, "unsupported parser"):
                extract_document(existing, parser="cloud")

    def test_missing_optional_pypdf_adapter_has_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "act.pdf"
            path.write_bytes(b"%PDF-")
            original_import = builtins.__import__

            def blocked_import(name: str, *args: object, **kwargs: object):
                if name == "pypdf":
                    raise ImportError("blocked for test")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=blocked_import):
                with self.assertRaisesRegex(ExtractionError, "pypdf is not installed"):
                    extract_document(path, parser="pypdf")


if __name__ == "__main__":
    unittest.main()

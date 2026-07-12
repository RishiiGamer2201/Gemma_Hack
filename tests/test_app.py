from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.app import load_documents


class CorpusLoadingTests(unittest.TestCase):
    def _write(self, content: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "corpus.json"
        path.write_text(content, encoding="utf-8")
        return path

    def test_missing_corpus_is_reported_as_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            with self.assertRaisesRegex(ValueError, "does not exist"):
                load_documents(missing)

    def test_invalid_json_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            load_documents(self._write("[not-json"))

    def test_top_level_object_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be a list"):
            load_documents(self._write("{}"))

    def test_non_object_record_is_rejected_with_position(self) -> None:
        with self.assertRaisesRegex(ValueError, "item 1 must be an object"):
            load_documents(self._write('[{"source_id":"one","text":"valid"}, 7]'))

    def test_missing_or_non_string_required_fields_are_rejected(self) -> None:
        for payload in (
            [{"text": "body"}],
            [{"source_id": "one"}],
            [{"source_id": 1, "text": "body"}],
            [{"source_id": "one", "text": ["body"]}],
        ):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, "requires string source_id and text"):
                    load_documents(self._write(json.dumps(payload)))

    def test_source_body_and_provenance_are_preserved(self) -> None:
        payload = [{
            "source_id": "fixture.1",
            "text": "Exact official excerpt.",
            "act": "Synthetic Act",
            "section": "7",
            "heading": "Synthetic heading",
            "status": "in_force",
        }]
        document = load_documents(self._write(json.dumps(payload)))[0]
        self.assertEqual(document.metadata["source_text"], "Exact official excerpt.")
        self.assertIn("Synthetic Act 7 Synthetic heading Exact official excerpt.", document.text)


if __name__ == "__main__":
    unittest.main()

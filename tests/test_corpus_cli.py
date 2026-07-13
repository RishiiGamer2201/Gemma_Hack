from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.download_official_sources import main
from tests.test_corpus_manifest import source_payload


class CorpusCliTests(unittest.TestCase):
    def _manifest(self, directory: str) -> Path:
        path = Path(directory) / "manifest.json"
        path.write_text(
            json.dumps({"schema_version": 1, "sources": [source_payload()]}),
            encoding="utf-8",
        )
        return path

    def test_list_validates_and_prints_without_network_or_downloader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = self._manifest(directory)
            output = io.StringIO()
            with patch(
                "scripts.download_official_sources.download_source",
                side_effect=AssertionError("list mode must remain network-free"),
            ) as downloader, redirect_stdout(output):
                result = main(["--manifest", str(manifest), "--list"])
        self.assertEqual(result, 0)
        self.assertIn("synthetic_act_en", output.getvalue())
        downloader.assert_not_called()

    def test_unknown_selected_source_fails_without_downloading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = self._manifest(directory)
            error = io.StringIO()
            with patch("scripts.download_official_sources.download_source") as downloader, redirect_stderr(error):
                result = main(
                    ["--manifest", str(manifest), "--source-id", "unknown", "--list"]
                )
        self.assertEqual(result, 2)
        self.assertIn("Unknown source_id", error.getvalue())
        downloader.assert_not_called()


if __name__ == "__main__":
    unittest.main()

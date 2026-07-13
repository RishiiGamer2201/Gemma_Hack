from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from scripts.download_public_datasets import main


class PublicDatasetTests(unittest.TestCase):
    def _manifest(self, root: Path) -> Path:
        path = root / "manifest.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "datasets": [
                        {
                            "dataset_id": "sample",
                            "repository": "example/sample",
                            "revision": "a" * 40,
                            "output_directory": "sample",
                            "purpose": "Evaluation only",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_list_is_network_free(self) -> None:
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()) as output:
            code = main(["--manifest", str(self._manifest(Path(directory))), "--list"])
        self.assertEqual(code, 0)
        self.assertIn("example/sample@", output.getvalue())

    def test_verify_existing_hashes_files_and_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            root = Path(directory)
            dataset = root / "output" / "sample"
            dataset.mkdir(parents=True)
            (dataset / "data.json").write_text("[]", encoding="utf-8")
            code = main(
                [
                    "--manifest", str(self._manifest(root)),
                    "--output-root", str(root / "output"),
                    "--verify-existing",
                ]
            )
            receipt = json.loads((dataset / "download_receipt.json").read_text())
        self.assertEqual(code, 0)
        self.assertEqual(receipt["file_count"], 1)

    def test_unknown_dataset_id_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory, redirect_stderr(io.StringIO()):
            code = main(
                ["--manifest", str(self._manifest(Path(directory))), "--dataset-id", "missing", "--list"]
            )
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()

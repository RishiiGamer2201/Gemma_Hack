from __future__ import annotations

import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from src.corpus.snapshots import SnapshotSource, download_snapshot, load_snapshot_manifest


def source(**updates: object) -> SnapshotSource:
    payload = {
        "source_id": "official_page",
        "title": "Official page",
        "url": "https://law.gov.in/page",
        "official_landing_url": "https://law.gov.in/",
        "filename": "official_page.html",
        "category": "law",
        "required_text": ["official"],
        "allowed_hosts": ["law.gov.in"],
    }
    payload.update(updates)
    return SnapshotSource.model_validate(payload)


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.headers = Message()
        self.headers["Content-Type"] = "text/html; charset=utf-8"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def geturl(self) -> str:
        return "https://law.gov.in/page"

    def read(self, size: int) -> bytes:
        return self.body


class SnapshotTests(unittest.TestCase):
    def test_manifest_rejects_unapproved_or_unsafe_urls(self) -> None:
        for updates in (
            {"url": "http://law.gov.in/page"},
            {"official_landing_url": "https://other.gov.in/"},
            {"filename": "../page.html"},
        ):
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                source(**updates)

    def test_download_writes_hash_verified_html_and_receipt(self) -> None:
        body = b"<!doctype html><html><body>official</body></html>"
        opener = type("Opener", (), {"open": lambda self, request, timeout: FakeResponse(body)})()
        with tempfile.TemporaryDirectory() as directory, patch(
            "src.corpus.snapshots.build_opener", return_value=opener
        ):
            receipt = download_snapshot(source(), directory)
            stored = Path(directory) / "official_page.html"
            metadata = json.loads(stored.with_suffix(".html.receipt.json").read_text())
        self.assertEqual(receipt.byte_count, len(body))
        self.assertEqual(metadata["sha256"], receipt.sha256)

    def test_committed_snapshot_manifest_is_valid(self) -> None:
        manifest = load_snapshot_manifest("config/official_web_sources.json")
        self.assertEqual(len(manifest.sources), 7)


if __name__ == "__main__":
    unittest.main()

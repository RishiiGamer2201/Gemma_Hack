from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from src.legal_time.sankalan import SankalanError, parse_verified_sankalan


class SankalanTests(unittest.TestCase):
    def _fixture(self, root: Path) -> Path:
        rows = "".join(
            f"<tr><td id='{number}'>{number}. BNS title</td><td>420. IPC title.</td></tr>"
            for number in range(1, 302)
        )
        body = f"<!doctype html><html><table>{rows}</table></html>".encode()
        path = root / "ncrb.html"
        path.write_bytes(body)
        path.with_suffix(".html.receipt.json").write_text(
            json.dumps(
                {
                    "source_id": "ncrb_sankalan_ipc_bns",
                    "url": "https://cytrain.ncrb.gov.in/table",
                    "retrieved_at": "2026-07-12T00:00:00+00:00",
                    "byte_count": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_verified_table_builds_pending_review_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidates = parse_verified_sankalan(self._fixture(Path(directory)))
        self.assertEqual(len(candidates), 301)
        self.assertEqual(candidates[0].ipc_references, ("420",))
        self.assertEqual(candidates[0].audit_status, "pending_human_review")

    def test_tampered_snapshot_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._fixture(Path(directory))
            path.write_bytes(path.read_bytes() + b"tamper")
            with self.assertRaisesRegex(SankalanError, "do not match"):
                parse_verified_sankalan(path)


if __name__ == "__main__":
    unittest.main()

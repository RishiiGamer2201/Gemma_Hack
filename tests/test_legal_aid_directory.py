from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from src.legal_aid.directory import (
    build_delhi_contacts,
    build_nalsa_fallback,
    build_tele_law_fallback,
)


def write_snapshot(root: Path, name: str, source_id: str, body: bytes) -> Path:
    path = root / name
    path.write_bytes(body)
    path.with_suffix(".html.receipt.json").write_text(
        json.dumps(
            {
                "source_id": source_id,
                "url": f"https://example.gov.in/{name}",
                "retrieved_at": "2026-07-12T00:00:00+00:00",
                "byte_count": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    return path


class LegalAidDirectoryTests(unittest.TestCase):
    def test_builds_district_contacts_and_deobfuscates_email(self) -> None:
        rows = "".join(
            f"<tr><td>Officer {i}</td><td>Secretary, District {i} DLSA</td>"
            f"<td>district{i}[at]nic[dot]in</td><td>12345{i}</td></tr>"
            for i in range(10)
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_snapshot(
                Path(directory), "directory.html", "dslsa_directory", f"<html><table>{rows}</table></html>".encode()
            )
            contacts = build_delhi_contacts(path)
        self.assertEqual(len(contacts), 10)
        self.assertEqual(contacts[0].email, "district0@nic.in")
        self.assertTrue(contacts[0].needs_address_review)

    def test_tele_law_fallback_requires_verified_helpline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_snapshot(
                Path(directory),
                "tele.html",
                "tele_law_pib_2026",
                b"<html>Tele-Law toll free 14454</html>",
            )
            fallback = build_tele_law_fallback(path)
        self.assertEqual(fallback.phone, "14454")

    def test_nalsa_fallback_requires_verified_national_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_snapshot(
                Path(directory),
                "nalsa.html",
                "nalsa_directory",
                b"<html>NATIONAL LEGAL SERVICES AUTHORITY helpline 15100</html>",
            )
            fallback = build_nalsa_fallback(path)
        self.assertEqual(fallback.phone, "15100")


if __name__ == "__main__":
    unittest.main()

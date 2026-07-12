from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from pydantic import ValidationError

from src.corpus.manifest import OfficialSource, SourceManifest, load_manifest


def source_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_id": "synthetic_act_en",
        "title": "Synthetic Act",
        "url": "https://law.gov.in/files/act.pdf",
        "official_landing_url": "https://law.gov.in/acts/synthetic",
        "filename": "synthetic_act.pdf",
        "language": "en",
        "jurisdiction": "India",
        "document_type": "act",
        "effective_from": "2024-07-01",
        "effective_to": None,
        "status": "in_force",
        "priority": 1,
        "parser": "auto",
        "required": True,
        "allowed_hosts": ["law.gov.in"],
    }
    payload.update(updates)
    return payload


class ManifestTests(unittest.TestCase):
    def test_windows_reserved_device_filenames_are_rejected(self) -> None:
        for filename in ("CON.pdf", "nul.txt", "COM1.data.pdf", "LPT9.pdf"):
            with self.subTest(filename=filename), self.assertRaisesRegex(
                ValidationError, "reserved device"
            ):
                OfficialSource.model_validate(source_payload(filename=filename))

    def test_source_id_is_safe_when_used_as_an_output_filename(self) -> None:
        for source_id in ("act:en", "CON", "nul.v1"):
            with self.subTest(source_id=source_id), self.assertRaises(ValidationError):
                OfficialSource.model_validate(source_payload(source_id=source_id))

    def test_manifest_requires_unique_ids_and_case_insensitive_filenames(self) -> None:
        first = source_payload()
        for key, value in (("source_id", "synthetic_act_en"), ("filename", "SYNTHETIC_ACT.PDF")):
            second = deepcopy(first)
            second["source_id"] = "second_source"
            second["filename"] = "second.pdf"
            second[key] = value
            with self.subTest(key=key):
                with self.assertRaises(ValidationError):
                    SourceManifest.model_validate({"sources": [first, second]})

    def test_urls_must_be_https_without_credentials_or_fragments(self) -> None:
        bad_urls = (
            "http://law.gov.in/files/act.pdf",
            "https://user:secret@law.gov.in/files/act.pdf",
            "https://law.gov.in/files/act.pdf#fragment",
            "/relative/act.pdf",
        )
        for value in bad_urls:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    OfficialSource.model_validate(source_payload(url=value))

    def test_download_and_landing_hosts_must_be_allowlisted(self) -> None:
        for updates in (
            {"allowed_hosts": ["other.gov.in"]},
            {
                "official_landing_url": "https://landing.gov.in/act",
                "allowed_hosts": ["law.gov.in"],
            },
        ):
            with self.subTest(updates=updates):
                with self.assertRaises(ValidationError):
                    OfficialSource.model_validate(source_payload(**updates))

    def test_hosts_are_normalized_and_deduplicated(self) -> None:
        source = OfficialSource.model_validate(
            source_payload(allowed_hosts=[" LAW.GOV.IN. ", "law.gov.in"])
        )
        self.assertEqual(source.allowed_hosts, ("law.gov.in",))

    def test_filename_must_be_safe_supported_basename(self) -> None:
        for filename in ("../act.pdf", "folder/act.pdf", ".", "act.exe", "act"):
            with self.subTest(filename=filename):
                with self.assertRaises(ValidationError):
                    OfficialSource.model_validate(source_payload(filename=filename))

    def test_text_filename_requires_text_parser(self) -> None:
        with self.assertRaises(ValidationError):
            OfficialSource.model_validate(source_payload(filename="act.txt", parser="auto"))

    def test_effective_range_must_be_ordered(self) -> None:
        with self.assertRaises(ValidationError):
            OfficialSource.model_validate(
                source_payload(effective_from="2025-01-01", effective_to="2024-12-31")
            )

    def test_load_manifest_reports_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not valid JSON"):
                load_manifest(path)

    def test_committed_manifest_passes_validation(self) -> None:
        manifest = load_manifest("config/official_sources.json")
        self.assertGreater(len(manifest.sources), 0)
        self.assertTrue(all(source.allows_url(source.url) for source in manifest.sources))


if __name__ == "__main__":
    unittest.main()

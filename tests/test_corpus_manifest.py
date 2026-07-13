from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

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

    def test_amendment_relationships_must_be_explicit_and_resolvable(self) -> None:
        principal = source_payload()
        amendment = source_payload(
            source_id="synthetic_amendment_en",
            filename="synthetic_amendment.pdf",
            relationship="amendment",
            modifies_source_ids=["synthetic_act_en"],
            target_instrument_title="Synthetic Act",
        )
        manifest = SourceManifest.model_validate({"sources": [principal, amendment]})
        self.assertEqual(manifest.sources[1].modifies_source_ids, ("synthetic_act_en",))

        for update, message in (
            ({"relationship": "amendment"}, "require modifies_source_ids"),
            ({"modifies_source_ids": ["synthetic_act_en"]}, "principal sources"),
            (
                {
                    "relationship": "corrigendum",
                    "modifies_source_ids": ["missing_source"],
                    "target_instrument_title": "Missing source",
                },
                "unknown source_id",
            ),
        ):
            with self.subTest(update=update), self.assertRaisesRegex(ValidationError, message):
                SourceManifest.model_validate({"sources": [source_payload(**update)]})

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

    def test_committed_consumer_rules_preserve_current_amendment_chain(self) -> None:
        manifest = load_manifest("config/official_sources.json")
        sources = {source.source_id: source for source in manifest.sources}
        consumer_rules = [
            source
            for source in manifest.sources
            if source.source_id.startswith("consumer_")
            and source.source_id != "consumer_protection_act_2019_en"
        ]

        self.assertEqual(len(consumer_rules), 12)
        self.assertTrue(
            all(source.chunking_strategy == "gazette_rules_en" for source in consumer_rules)
        )
        self.assertTrue(all(source.language == "hi-en" for source in consumer_rules))
        current_fee_table = sources["consumer_cdrc_amendment_rules_2023_hi_en"]
        self.assertEqual(current_fee_table.gazette_reference, "G.S.R. 606(E)")
        self.assertEqual(
            current_fee_table.modifies_source_ids,
            ("consumer_cdrc_general_rules_2020_hi_en",),
        )
        self.assertIn("G.S.R. 892(E)", current_fee_table.review_note or "")
        self.assertEqual(
            current_fee_table.target_instrument_title,
            "Consumer Protection (Consumer Disputes Redressal Commissions) Rules, 2020",
        )
        corrigendum = sources["consumer_ecommerce_corrigendum_2020_hi_en"]
        self.assertIsNone(corrigendum.effective_from)
        self.assertEqual(corrigendum.relationship, "corrigendum")

    def test_only_delhi_rent_source_uses_the_drc_applicability_profile(self) -> None:
        manifest = load_manifest("config/official_sources.json")
        profiled = [
            source.source_id for source in manifest.sources if source.applicability_profile_id
        ]
        self.assertEqual(profiled, ["delhi_rent_control_act_1958_en"])
        source = next(source for source in manifest.sources if source.source_id == profiled[0])
        self.assertEqual(source.applicability_profile_id, "delhi_rent_control_act_1958")
        self.assertEqual(source.effective_from.isoformat(), "1959-02-09")


if __name__ == "__main__":
    unittest.main()

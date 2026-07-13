from __future__ import annotations

import unittest
from datetime import date

from pydantic import ValidationError

from src.legal_time import (
    LegalCode,
    LegalMapping,
    MappingCatalog,
    MappingLookupStatus,
    MappingType,
    ProvisionReference,
)


def sample_mapping() -> LegalMapping:
    return LegalMapping(
        mapping_id="demo.ipc420",
        source_provisions=(ProvisionReference(code=LegalCode.IPC, section="420"),),
        target_provisions=(ProvisionReference(code=LegalCode.BNS, section="DEMO"),),
        mapping_type=MappingType.PARTIAL,
        offence_names=("synthetic cheating mapping",),
        aliases=("IPC 420",),
        plain_language_description="Synthetic mapping for workflow tests only.",
        change_notes="Not legal data; target section intentionally non-numeric.",
        official_source_url="https://example.invalid/source",
        official_source_id="synthetic-source",
        reviewed_by="test fixture",
        reviewed_at=date(2026, 7, 12),
    )


class LegalTimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = MappingCatalog([sample_mapping()])

    def test_missing_date_never_selects_applicable_code(self) -> None:
        result = self.catalog.lookup("IPC 420")
        self.assertEqual(result.status, MappingLookupStatus.INCIDENT_DATE_REQUIRED)
        self.assertEqual(result.applicable_provisions, ())
        self.assertTrue(result.requires_incident_date_clarification)

    def test_historical_date_selects_ipc(self) -> None:
        result = self.catalog.lookup("IPC 420", incident_date=date(2024, 6, 30))
        self.assertEqual(result.status, MappingLookupStatus.HISTORICAL_IPC)
        self.assertEqual(result.applicable_provisions[0].code, LegalCode.IPC)

    def test_current_date_selects_reviewed_bns_target(self) -> None:
        result = self.catalog.lookup("IPC 420", incident_date=date(2024, 7, 1))
        self.assertEqual(result.status, MappingLookupStatus.CURRENT_BNS)
        self.assertEqual(result.applicable_provisions[0].code, LegalCode.BNS)

    def test_duplicate_mapping_ids_are_rejected(self) -> None:
        mapping = sample_mapping()
        with self.assertRaisesRegex(ValueError, "mapping_id values must be unique"):
            MappingCatalog([mapping, mapping])

    def test_exact_mapping_requires_one_source_and_one_target(self) -> None:
        payload = sample_mapping().model_dump()
        payload["mapping_type"] = MappingType.EXACT
        payload["target_provisions"] = (
            {"code": "BNS", "section": "1"},
            {"code": "BNS", "section": "2"},
        )
        with self.assertRaisesRegex(ValidationError, "exact mapping must explicitly contain"):
            LegalMapping.model_validate(payload)

    def test_omitted_mapping_cannot_claim_a_target(self) -> None:
        payload = sample_mapping().model_dump()
        payload["mapping_type"] = MappingType.OMITTED
        with self.assertRaisesRegex(ValidationError, "cannot claim target provisions"):
            LegalMapping.model_validate(payload)

    def test_source_and_target_codes_cannot_be_reversed(self) -> None:
        payload = sample_mapping().model_dump()
        payload["source_provisions"] = ({"code": "BNS", "section": "1"},)
        with self.assertRaisesRegex(ValidationError, "source_provisions must contain reviewed IPC"):
            LegalMapping.model_validate(payload)

    def test_blank_lookup_is_rejected_and_unknown_lookup_does_not_guess(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be blank"):
            self.catalog.lookup("  ")
        result = self.catalog.lookup("unrelated offence 999")
        self.assertEqual(result.status, MappingLookupStatus.NOT_FOUND)
        self.assertEqual(result.candidates, ())

    def test_section_prefix_does_not_match_longer_section(self) -> None:
        result = self.catalog.lookup("IPC 42")
        self.assertEqual(result.status, MappingLookupStatus.NOT_FOUND)
        result = self.catalog.lookup("section 42")
        self.assertEqual(result.status, MappingLookupStatus.NOT_FOUND)


if __name__ == "__main__":
    unittest.main()

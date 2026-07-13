from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import date
from pathlib import Path

from scripts.find_legal_aid import main as finder_cli
from src.legal_aid import LegalAidFinder, LegalAidFinderError, MatchStatus

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "data" / "processed" / "contacts" / "delhi_dlsa.json"


def committed_payload() -> dict[str, object]:
    return json.loads(DIRECTORY.read_text(encoding="utf-8"))


class LegalAidFinderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.finder = LegalAidFinder(DIRECTORY)

    def _write_payload(self, payload: object) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "directory.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return directory, path

    def test_generated_directory_matches_central_two_and_rouse_avenue_aliases(self) -> None:
        for query in ("Central-II", "central ii", "Central 2", "Rouse Avenue", "rouse-avenue court"):
            with self.subTest(query=query):
                result = self.finder.find(query, state="NCT of Delhi")
                self.assertEqual(result.match_status, MatchStatus.MATCHED)
                self.assertEqual(result.contacts[0].district, "Central-II")
                self.assertEqual(result.contacts[0].email, "rouseavenue-dlsa@delhi.gov.in")

    def test_hyphenated_and_compact_directional_aliases_are_equivalent(self) -> None:
        for query, expected in (
            ("North-East", "North-East"),
            ("northeast delhi", "North-East"),
            ("NorthWest", "North-West"),
            ("south-east delhi", "South-East"),
            ("SouthWest", "South-West"),
        ):
            with self.subTest(query=query):
                result = self.finder.find(query, state="Delhi")
                self.assertEqual(result.match_status, MatchStatus.MATCHED)
                self.assertEqual(result.contacts[0].district, expected)

    def test_exact_unmatched_delhi_never_guesses_a_contact(self) -> None:
        result = self.finder.find("Old Delhi", state="Delhi")
        self.assertEqual(result.match_status, MatchStatus.UNMATCHED_DELHI)
        self.assertEqual(result.contacts, ())
        self.assertIn("No exact reviewed Delhi district match", result.warnings[0])

    def test_unknown_location_without_state_is_not_assumed_to_be_delhi(self) -> None:
        result = self.finder.find("Indore")
        self.assertEqual(result.match_status, MatchStatus.UNKNOWN_LOCATION)
        self.assertEqual(result.contacts, ())

    def test_outside_delhi_returns_the_state_authority_when_one_is_known(self) -> None:
        """Superseded behaviour: this used to return national fallbacks only.

        The NALSA directory lists every State Legal Services Authority with a phone,
        so a citizen in Maharashtra is given Maharashtra's authority rather than a
        national switchboard. Where no state authority is known, the old
        fallback-only behaviour still applies.
        """

        result = self.finder.find("Mumbai", state="Maharashtra")
        self.assertEqual(result.match_status, MatchStatus.OUTSIDE_DELHI)
        if self.finder.state_contacts:
            self.assertTrue(result.contacts)
            self.assertIn("Maharashtra", result.contacts[0].authority)
            self.assertIn("State Legal Services Authority", result.warnings[0])
        else:
            self.assertEqual(result.contacts, ())
            self.assertIn("covers Delhi only", result.warnings[0])

    def test_every_search_status_includes_nalsa_and_tele_law_fallbacks(self) -> None:
        results = (
            self.finder.find("Central", state="Delhi"),
            self.finder.find("Old Delhi", state="Delhi"),
            self.finder.find("Indore"),
            self.finder.find("Mumbai", state="Maharashtra"),
        )
        for result in results:
            with self.subTest(status=result.match_status):
                self.assertEqual(
                    {fallback.fallback_id for fallback in result.fallbacks},
                    {"nalsa-15100", "tele-law-14454"},
                )

    def test_freshness_summarizes_all_committed_records(self) -> None:
        freshness = self.finder.source_freshness
        self.assertEqual(freshness.directory_filename, "delhi_dlsa.json")
        # Freshness covers every record a user could be shown, including the state
        # authorities, so "last verified" is not silently older than what is displayed.
        self.assertEqual(
            freshness.record_count,
            len(self.finder.contacts)
            + len(self.finder.state_contacts)
            + len(self.finder.fallbacks),
        )
        self.assertEqual(freshness.oldest_verified_date, date(2026, 7, 12))
        self.assertEqual(freshness.newest_verified_date, date(2026, 7, 12))
        self.assertEqual(len(freshness.source_sha256), 3)

    def test_malformed_json_duplicate_keys_and_oversize_files_are_rejected(self) -> None:
        cases = (
            ("{not-json", "invalid_json"),
            ('{"schema_version":1,"schema_version":1,"contacts":[],"fallbacks":[]}', "duplicate_key"),
        )
        for text, code in cases:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "directory.json"
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(LegalAidFinderError) as context:
                    LegalAidFinder(path)
                self.assertEqual(context.exception.code, code)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "directory.json"
            path.write_bytes(b" " * (2 * 1024 * 1024 + 1))
            with self.assertRaises(LegalAidFinderError) as context:
                LegalAidFinder(path)
            self.assertEqual(context.exception.code, "directory_too_large")

    def test_unknown_or_missing_top_level_keys_and_bad_shapes_are_rejected(self) -> None:
        payload = committed_payload()
        variants = []
        unknown = deepcopy(payload)
        unknown["unexpected"] = True
        variants.append((unknown, "unknown_keys"))
        missing = deepcopy(payload)
        missing.pop("fallbacks")
        variants.append((missing, "missing_keys"))
        bad_shape = deepcopy(payload)
        bad_shape["contacts"] = {}
        variants.append((bad_shape, "invalid_shape"))
        for variant, code in variants:
            with self.subTest(code=code):
                directory, path = self._write_payload(variant)
                with directory:
                    with self.assertRaises(LegalAidFinderError) as context:
                        LegalAidFinder(path)
                    self.assertEqual(context.exception.code, code)

    def test_duplicate_contact_ids_fallback_ids_and_normalized_districts_are_rejected(self) -> None:
        payload = committed_payload()
        variants: list[tuple[dict[str, object], str]] = []
        duplicate_contact = deepcopy(payload)
        duplicate_contact["contacts"].append(deepcopy(duplicate_contact["contacts"][0]))  # type: ignore[index,union-attr]
        variants.append((duplicate_contact, "duplicate_contact"))
        duplicate_fallback = deepcopy(payload)
        duplicate_fallback["fallbacks"].append(deepcopy(duplicate_fallback["fallbacks"][0]))  # type: ignore[index,union-attr]
        variants.append((duplicate_fallback, "duplicate_fallback"))
        duplicate_district = deepcopy(payload)
        contact = deepcopy(duplicate_district["contacts"][0])  # type: ignore[index]
        contact["contact_id"] = "different-id"
        contact["district"] = "CENTRAL"
        duplicate_district["contacts"].append(contact)  # type: ignore[union-attr]
        variants.append((duplicate_district, "duplicate_district"))
        for variant, code in variants:
            with self.subTest(code=code):
                directory, path = self._write_payload(variant)
                with directory:
                    with self.assertRaises(LegalAidFinderError) as context:
                        LegalAidFinder(path)
                    self.assertEqual(context.exception.code, code)

    def test_pydantic_invalid_contact_and_fallback_records_are_bounded(self) -> None:
        payload = committed_payload()
        variants = []
        invalid_contact = deepcopy(payload)
        invalid_contact["contacts"][0]["phone"] = "1"  # type: ignore[index]
        variants.append((invalid_contact, "invalid_contact"))
        invalid_fallback = deepcopy(payload)
        invalid_fallback["fallbacks"][0]["extra"] = "forbidden"  # type: ignore[index]
        variants.append((invalid_fallback, "invalid_fallback"))
        for variant, code in variants:
            with self.subTest(code=code):
                directory, path = self._write_payload(variant)
                with directory:
                    with self.assertRaises(LegalAidFinderError) as context:
                        LegalAidFinder(path)
                    self.assertEqual(context.exception.code, code)

    def test_required_national_fallbacks_cannot_be_removed_or_rewritten(self) -> None:
        payload = committed_payload()
        missing = deepcopy(payload)
        missing["fallbacks"] = [
            item for item in missing["fallbacks"] if item["fallback_id"] != "tele-law-14454"  # type: ignore[index]
        ]
        wrong_phone = deepcopy(payload)
        wrong_phone["fallbacks"][0]["phone"] = "99999"  # type: ignore[index]
        for variant, code in (
            (missing, "missing_required_fallback"),
            (wrong_phone, "invalid_required_fallback"),
        ):
            with self.subTest(code=code):
                directory, path = self._write_payload(variant)
                with directory, self.assertRaises(LegalAidFinderError) as context:
                    LegalAidFinder(path)
                self.assertEqual(context.exception.code, code)

    def test_cli_emits_json_and_uses_zero_and_two_exit_codes(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = finder_cli(["--directory", str(DIRECTORY), "--district", "Rouse Avenue"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["match_status"], "matched")

        error = io.StringIO()
        with redirect_stderr(error):
            code = finder_cli(["--directory", str(DIRECTORY.with_name("missing.json")), "--district", "Central"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(error.getvalue())["error"]["code"], "directory_unreadable")


if __name__ == "__main__":
    unittest.main()


def test_a_district_outside_delhi_gets_its_own_state_authority(tmp_path) -> None:
    """A citizen outside Delhi used to get only the national helpline number.

    The NALSA directory already lists every State Legal Services Authority with a
    phone and an email, so there is no reason to send someone in Karnataka to a
    national switchboard when their own state authority is on the official page.
    """

    from pathlib import Path

    directory = Path("data/processed/contacts/delhi_dlsa.json")
    if not directory.is_file():
        pytest.skip("the built directory is not present")

    finder = LegalAidFinder(directory)
    result = finder.find("Whitefield", state="Karnataka")

    assert result.match_status is MatchStatus.OUTSIDE_DELHI
    assert result.contacts
    contact = result.contacts[0]
    assert "Karnataka" in contact.authority
    assert contact.phone != "not published"
    # The national fallbacks stay available alongside it.
    assert {item.phone for item in result.fallbacks} >= {"15100", "14454"}
    assert any("State Legal Services Authority" in w for w in result.warnings)


def test_delhi_district_lookup_is_unchanged_by_the_state_tier() -> None:
    from pathlib import Path

    directory = Path("data/processed/contacts/delhi_dlsa.json")
    if not directory.is_file():
        pytest.skip("the built directory is not present")

    finder = LegalAidFinder(directory)
    result = finder.find("Rouse Avenue", state="Delhi")

    assert result.match_status is MatchStatus.MATCHED
    assert "District Legal Services Authority" in result.contacts[0].authority

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.get_evidence_checklist import main as checklist_cli
from src.actions.checklists import ChecklistCatalog, ChecklistError


ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "config" / "evidence_checklists.json"


def committed_payload() -> dict[str, object]:
    return json.loads(CATALOGUE.read_text(encoding="utf-8"))


class EvidenceChecklistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = ChecklistCatalog(CATALOGUE)

    def _write(self, payload: object) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "checklists.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return directory, path

    def test_committed_catalogue_has_exactly_three_expected_templates(self) -> None:
        self.assertEqual(len(self.catalog.templates), 3)
        self.assertEqual(
            {template.template_id for template in self.catalog.templates},
            {"unpaid_wages", "fir_or_legal_notice", "security_deposit"},
        )

    def test_every_template_is_labeled_as_guidance_and_flags_sensitive_items(self) -> None:
        for template in self.catalog.templates:
            with self.subTest(template=template.template_id):
                self.assertIn("guidance", template.guidance_label.casefold())
                self.assertTrue(any(item.sensitive for item in template.items))
                self.assertTrue(all(type(item.sensitive) is bool for item in template.items))

    def test_lookup_is_normalized_but_never_fuzzy(self) -> None:
        self.assertEqual(self.catalog.get(" unpaid-wages ").template_id, "unpaid_wages")
        with self.assertRaisesRegex(ChecklistError, "unknown checklist template_id"):
            self.catalog.get("unpaid_wage")
        with self.assertRaisesRegex(ChecklistError, "must not be blank"):
            self.catalog.get("  ")

    def test_malformed_root_shapes_unknown_keys_and_schema_are_rejected(self) -> None:
        variants = (
            ([], "invalid root shape"),
            ({"schema_version": 1, "templates": [], "extra": True}, "invalid root shape"),
            ({"schema_version": True, "templates": []}, "unsupported checklist schema_version"),
            ({"schema_version": 1, "templates": {}}, "templates must be a JSON array"),
        )
        for payload, message in variants:
            with self.subTest(message=message):
                directory, path = self._write(payload)
                with directory:
                    with self.assertRaisesRegex(ChecklistError, message):
                        ChecklistCatalog(path)

    def test_malformed_json_and_duplicate_json_keys_are_rejected(self) -> None:
        cases = (
            ("not-json", "could not load a valid checklist catalogue"),
            ('{"schema_version":1,"schema_version":1,"templates":[]}', "duplicate JSON key"),
        )
        for text, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "checklists.json"
                path.write_text(text, encoding="utf-8")
                with self.assertRaisesRegex(ChecklistError, message):
                    ChecklistCatalog(path)

    def test_duplicate_template_and_item_ids_are_rejected(self) -> None:
        payload = committed_payload()
        duplicate_template = deepcopy(payload)
        duplicate_template["templates"].append(deepcopy(duplicate_template["templates"][0]))  # type: ignore[index,union-attr]
        duplicate_item = deepcopy(payload)
        duplicate_item["templates"][0]["items"].append(  # type: ignore[index,union-attr]
            deepcopy(duplicate_item["templates"][0]["items"][0])  # type: ignore[index]
        )
        for variant, message in (
            (duplicate_template, "duplicate checklist template_id"),
            (duplicate_item, "failed schema validation"),
        ):
            with self.subTest(message=message):
                directory, path = self._write(variant)
                with directory:
                    with self.assertRaisesRegex(ChecklistError, message):
                        ChecklistCatalog(path)

    def test_pydantic_invalid_templates_are_bounded(self) -> None:
        payload = committed_payload()
        variants = []
        wrong_domain = deepcopy(payload)
        wrong_domain["templates"][0]["domain"] = "tax"  # type: ignore[index]
        variants.append(wrong_domain)
        missing_sensitive = deepcopy(payload)
        missing_sensitive["templates"][0]["items"][0].pop("sensitive")  # type: ignore[index]
        variants.append(missing_sensitive)
        coercive_sensitive = deepcopy(payload)
        coercive_sensitive["templates"][0]["items"][0]["sensitive"] = "false"  # type: ignore[index]
        variants.append(coercive_sensitive)
        unlabeled = deepcopy(payload)
        unlabeled["templates"][0]["guidance_label"] = "Preparation list only."  # type: ignore[index]
        variants.append(unlabeled)
        extra = deepcopy(payload)
        extra["templates"][0]["extra"] = True  # type: ignore[index]
        variants.append(extra)
        for variant in variants:
            with self.subTest(variant=variant):
                directory, path = self._write(variant)
                with directory:
                    with self.assertRaisesRegex(ChecklistError, "failed schema validation"):
                        ChecklistCatalog(path)

    def test_cli_returns_json_on_success_and_two_for_bad_catalogue(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = checklist_cli(["--catalogue", str(CATALOGUE), "--template", "unpaid_wages"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["template_id"], "unpaid_wages")

        normalized_output = io.StringIO()
        with redirect_stdout(normalized_output):
            code = checklist_cli(
                ["--catalogue", str(CATALOGUE), "--template", "unpaid-wages"]
            )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(normalized_output.getvalue())["template_id"], "unpaid_wages")

        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "bad.json"
            bad.write_text("{}", encoding="utf-8")
            error = io.StringIO()
            with redirect_stderr(error):
                code = checklist_cli(["--catalogue", str(bad), "--template", "security_deposit"])
        self.assertEqual(code, 2)
        self.assertIn("invalid root shape", json.loads(error.getvalue())["error"])


if __name__ == "__main__":
    unittest.main()

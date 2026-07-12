from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import unittest

from pydantic import ValidationError

from scripts.process_text_intake import run
from src.intake import (
    DetectedLanguage,
    IntakeFacts,
    MAX_INPUT_CHARACTERS,
    TextIntakeResult,
    UrgencyCategory,
    detect_language,
    normalize_intake_text,
    process_text_intake,
)
from src.models import LegalDomain
from src.workflow import LegalWorkflow, WorkflowError


class TextIntakeTests(unittest.TestCase):
    def test_detects_english_hindi_hinglish_and_undetermined(self) -> None:
        cases = {
            "My wages are unpaid": DetectedLanguage.ENGLISH,
            "मेरा वेतन नहीं मिला": DetectedLanguage.HINDI,
            "मेरा rent वापस नहीं मिला": DetectedLanguage.HINGLISH,
            "Mera rent nahi mila": DetectedLanguage.HINGLISH,
            "2026 ₹500": DetectedLanguage.UNDETERMINED,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(detect_language(text).language, expected)

    def test_normalization_preserves_material_tokens_and_quoted_spacing(self) -> None:
        text = '  R. K. Sharma said "pay  ₹12,500  by 01/07/2026" under IPC 420.\r\nNext line.  '
        normalized = normalize_intake_text(text)
        self.assertEqual(
            normalized,
            'R. K. Sharma said "pay  ₹12,500  by 01/07/2026" under IPC 420.\nNext line.',
        )

    def test_blank_oversized_and_control_character_input_is_rejected(self) -> None:
        for text in ("   ", "x" * (MAX_INPUT_CHARACTERS + 1), "hello\x00world"):
            with self.subTest(length=len(text)):
                with self.assertRaises((TypeError, ValueError)):
                    normalize_intake_text(text)

    def test_process_uses_only_explicit_structured_fields(self) -> None:
        result = process_text_intake(
            "My employer has not paid me.",
            incident_summary="Two monthly wage payments are reported unpaid.",
            location="Delhi",
            domain=LegalDomain.LABOUR,
            parties=("Worker", "ABC Pvt Ltd"),
            documents=("Appointment letter",),
            missing_material_facts=("Exact wage period",),
        )
        self.assertEqual(result.facts.location, "Delhi")
        self.assertEqual(result.facts.documents, ("Appointment letter",))
        self.assertNotIn("section", result.restatement.casefold())
        self.assertFalse(result.confirmed)

    def test_hindi_restatement_preserves_supplied_values(self) -> None:
        result = process_text_intake(
            "मकान मालिक deposit नहीं लौटा रहा",
            location="दिल्ली",
            parties=("श्री राम",),
        )
        self.assertTrue(result.restatement.startswith("Here is what I understood:"))
        self.assertIn("श्री राम", result.restatement)

    def test_urgency_matches_are_signals_not_conclusions(self) -> None:
        result = process_text_intake("I am under arrest and this is a medical emergency")
        self.assertEqual(
            {signal.category for signal in result.urgency_signals},
            {UrgencyCategory.ARREST_OR_DETENTION, UrgencyCategory.MEDICAL_EMERGENCY},
        )
        self.assertTrue(all(signal.requires_user_confirmation for signal in result.urgency_signals))

    def test_ordinary_dispute_does_not_trigger_alarmist_signal(self) -> None:
        result = process_text_intake("My landlord has not returned my deposit for two months.")
        self.assertEqual(result.urgency_signals, ())

    def test_duplicate_structured_values_and_extra_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "duplicate"):
            IntakeFacts(incident_summary="Test", parties=("A", "A"))
        with self.assertRaises(ValidationError):
            IntakeFacts(incident_summary="Test", unexpected="value")
        with self.assertRaisesRegex(ValidationError, "must not be blank"):
            IntakeFacts(incident_summary="   ")

    def test_result_cannot_be_constructed_as_confirmed(self) -> None:
        base = process_text_intake("Test narrative")
        with self.assertRaisesRegex(ValidationError, "confirmed explicitly"):
            TextIntakeResult(**{**base.model_dump(), "confirmed": True})

    def test_conversion_enters_workflow_as_unconfirmed(self) -> None:
        result = process_text_intake("My wages are unpaid", domain=LegalDomain.LABOUR)
        facts = result.to_unconfirmed_facts()
        workflow = LegalWorkflow()
        snapshot = workflow.submit_extracted_facts(facts)
        self.assertFalse(snapshot.facts.confirmed)
        with self.assertRaises(WorkflowError):
            workflow.start_retrieval()

    def test_cli_emits_json_without_persistence(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = run([
                "--text", "My wages are unpaid",
                "--domain", "labour",
                "--party", "Worker",
                "--missing-fact", "Payment period",
            ])
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["facts"]["domain"], "labour")
        self.assertTrue(payload["requires_confirmation"])


if __name__ == "__main__":
    unittest.main()

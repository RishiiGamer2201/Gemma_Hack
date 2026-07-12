from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import json
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from scripts.process_text_intake import emit_json, run
from src.intake import (
    DetectedLanguage,
    IntakeFacts,
    LanguageAssessment,
    MAX_INPUT_CHARACTERS,
    TextIntakeResult,
    UrgencyCategory,
    detect_language,
    detect_urgency_signals,
    normalize_intake_text,
    process_text_intake,
)
from src.models import ConfirmedFacts, LegalDomain, WorkflowStage
from src.workflow import LegalWorkflow, WorkflowError


class TextIntakeReviewTests(unittest.TestCase):
    def test_normalization_requires_a_string_and_honours_exact_size_boundary(self) -> None:
        with self.assertRaisesRegex(TypeError, "must be a string"):
            normalize_intake_text(123)  # type: ignore[arg-type]
        self.assertEqual(
            len(normalize_intake_text("x" * MAX_INPUT_CHARACTERS)),
            MAX_INPUT_CHARACTERS,
        )
        with self.assertRaisesRegex(ValueError, "exceeds"):
            normalize_intake_text("x" * (MAX_INPUT_CHARACTERS + 1))

    def test_names_quotes_dates_money_and_sections_are_preserved_verbatim(self) -> None:
        narrative = (
            'Ms. Zoë D’Souza said “pay ₹12,500.75 by 01/07/2026” '
            'and quoted IPC 420, BNS 318(4), and BNSS § 173.'
        )
        result = process_text_intake(
            f"  {narrative}\r\nFIR No. 42/2026.  ",
            incident_summary=narrative,
            parties=("Ms. Zoë D’Souza", "A&B Pvt. Ltd."),
            documents=("FIR No. 42/2026",),
        )
        self.assertEqual(result.normalized_text, narrative + "\nFIR No. 42/2026.")
        tokens = (
            "Zoë D’Souza", "₹12,500.75", "01/07/2026", "IPC 420", "BNS 318(4)",
            "BNSS § 173",
        )
        for token in tokens:
            with self.subTest(token=token):
                self.assertIn(token, result.facts.incident_summary)
                self.assertIn(token, result.restatement)

    def test_normalization_changes_only_line_endings_and_outer_whitespace(self) -> None:
        self.assertEqual(
            normalize_intake_text("  first\t  value\rsecond\r\nthird  "),
            "first\t  value\nsecond\nthird",
        )

    def test_ascii_and_c1_controls_are_rejected_but_tab_and_newline_are_allowed(self) -> None:
        for character in ("\x00", "\x1b", "\x7f", "\x85", "\u202e", "\ud800"):
            with self.subTest(codepoint=ord(character)):
                with self.assertRaisesRegex(ValueError, "control character"):
                    normalize_intake_text(f"before{character}after")
        self.assertEqual(normalize_intake_text("one\ttwo\nthree"), "one\ttwo\nthree")

    def test_language_detection_handles_unicode_scripts_without_translating(self) -> None:
        cases = (
            ("वेतन नहीं मिला", DetectedLanguage.HINDI),
            ("मेरा rent वापस दो", DetectedLanguage.HINGLISH),
            ("Élodie paid wages", DetectedLanguage.ENGLISH),
            ("₹१२,५०० ⚖️", DetectedLanguage.UNDETERMINED),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                assessment = detect_language(text)
                self.assertEqual(assessment.language, expected)
                self.assertGreaterEqual(assessment.devanagari_letters, 0)
                self.assertGreaterEqual(assessment.latin_letters, 0)

    def test_urgency_detection_is_case_insensitive_and_deduplicated_per_category(self) -> None:
        signals = detect_urgency_signals(
            "UNDER ARREST in police custody; DEADLINE TOMORROW; needs an ambulance."
        )
        self.assertEqual(
            {signal.category for signal in signals},
            {
                UrgencyCategory.ARREST_OR_DETENTION,
                UrgencyCategory.EXPIRING_DEADLINE,
                UrgencyCategory.MEDICAL_EMERGENCY,
            },
        )
        self.assertEqual(len(signals), 3)
        self.assertTrue(all(signal.requires_user_confirmation for signal in signals))

    def test_related_but_nonurgent_legal_words_do_not_trigger_signals(self) -> None:
        narratives = (
            "The old arrest warrant was cancelled last year.",
            "My deadline is next month.",
            "I paid an ambulance service bill.",
            "The landlord discussed a possible eviction next year.",
            "I am not under arrest.",
            'The article says "thinking about suicide" prevention saves lives.',
            "This malformed token says notunder arrest.",
        )
        for narrative in narratives:
            with self.subTest(narrative=narrative):
                self.assertEqual(detect_urgency_signals(narrative), ())

    def test_intake_models_reject_unknown_fields_and_non_boolean_confirmation(self) -> None:
        with self.assertRaises(ValidationError):
            LanguageAssessment(
                language=DetectedLanguage.ENGLISH,
                devanagari_letters=0,
                latin_letters=4,
                extra="forbidden",  # type: ignore[call-arg]
            )
        base = process_text_intake("A valid narrative")
        for invalid in ("true", 1, None):
            with self.subTest(invalid=invalid):
                payload = base.model_dump()
                payload["confirmed"] = invalid
                with self.assertRaises(ValidationError):
                    TextIntakeResult.model_validate(payload)
        payload = base.model_dump()
        payload["requires_confirmation"] = False
        with self.assertRaises(ValidationError):
            TextIntakeResult.model_validate(payload)

    def test_structured_fields_reject_case_exact_duplicates_and_blank_members(self) -> None:
        for kwargs in (
            {"parties": ("Worker", "Worker")},
            {"documents": ("Notice", "Notice")},
            {"material_facts": ("Fact", "   ")},
            {"missing_material_facts": ("Date", "Date")},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValidationError):
                    IntakeFacts(incident_summary="Narrative", **kwargs)

    def test_cli_returns_json_error_for_blank_text_and_utf8_json_for_valid_text(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = run(["--text", "   "])
        self.assertEqual(code, 2)
        self.assertIn("must not be blank", json.loads(output.getvalue())["error"])

        output = io.StringIO()
        with redirect_stdout(output):
            code = run(
                [
                    "--text", "मेरा वेतन ₹१२,५०० नहीं मिला",
                    "--summary", "श्रीमती आशा का वेतन नहीं मिला",
                    "--party", "श्रीमती आशा",
                ]
            )
        payload = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["facts"]["parties"], ["श्रीमती आशा"])
        self.assertIn("₹१२,५००", payload["normalized_text"])

    def test_emit_json_writes_explicit_utf8_when_stdout_has_a_buffer(self) -> None:
        class BufferedStdout:
            def __init__(self) -> None:
                self.buffer = io.BytesIO()

        stream = BufferedStdout()
        with patch("scripts.process_text_intake.sys.stdout", stream):
            emit_json({"text": "हिंदी ₹"})
        self.assertEqual(json.loads(stream.buffer.getvalue().decode("utf-8")), {"text": "हिंदी ₹"})

    def test_argparse_rejects_invalid_date_and_domain_with_exit_two(self) -> None:
        for argv in (
            ["--text", "Narrative", "--incident-date", "01/07/2026"],
            ["--text", "Narrative", "--domain", "tax"],
        ):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as context:
                    run(argv)
                self.assertEqual(context.exception.code, 2)

    def test_intake_conversion_cannot_open_confirmation_or_retrieval_gates(self) -> None:
        result = process_text_intake(
            "My employer has not paid ₹12,500.",
            domain=LegalDomain.LABOUR,
            parties=("Worker", "Employer"),
        )
        unconfirmed = result.to_unconfirmed_facts()
        self.assertFalse(unconfirmed.confirmed)
        self.assertIsNone(unconfirmed.confirmed_at)

        workflow = LegalWorkflow()
        self.assertEqual(
            workflow.submit_extracted_facts(unconfirmed).stage,
            WorkflowStage.AWAITING_CONFIRMATION,
        )
        with self.assertRaises(WorkflowError):
            workflow.complete_safety_routing(immediate_human_help_required=False)
        with self.assertRaises(WorkflowError):
            workflow.start_retrieval()

    def test_only_a_separately_confirmed_fact_record_advances_the_workflow(self) -> None:
        result = process_text_intake("My wages are unpaid", jurisdiction="India")
        workflow = LegalWorkflow()
        workflow.submit_extracted_facts(result.to_unconfirmed_facts())
        with self.assertRaises(WorkflowError):
            workflow.confirm_facts(result.to_unconfirmed_facts())

        confirmed = ConfirmedFacts(
            **{
                **result.to_unconfirmed_facts().model_dump(exclude={"confirmed", "confirmed_at"}),
                "confirmed": True,
                "confirmed_at": datetime.now(timezone.utc),
            }
        )
        self.assertEqual(workflow.confirm_facts(confirmed).stage, WorkflowStage.CONFIRMED)

    def test_confirmation_rejects_coercive_boolean_and_naive_timestamp(self) -> None:
        base = {
            "incident_summary": "Test",
            "confirmed": "true",
            "confirmed_at": datetime.now(timezone.utc),
        }
        with self.assertRaises(ValidationError):
            ConfirmedFacts.model_validate(base)
        with self.assertRaises(ValidationError):
            ConfirmedFacts(
                incident_summary="Test",
                confirmed=True,
                confirmed_at=datetime.now(),
            )


if __name__ == "__main__":
    unittest.main()

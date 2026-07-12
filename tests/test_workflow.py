from __future__ import annotations

from datetime import date, datetime, timezone
import unittest

from src.models import (
    ClaimVerdict,
    ClaimVerification,
    ConfirmedFacts,
    LegalClaim,
    SourceEvidence,
    StructuredLegalAnswer,
    WorkflowStage,
)
from src.workflow import LegalWorkflow, WorkflowError


def facts(*, confirmed: bool) -> ConfirmedFacts:
    return ConfirmedFacts(
        incident_summary="Synthetic test incident.",
        incident_date=date(2025, 1, 1),
        jurisdiction="India",
        confirmed=confirmed,
        confirmed_at=datetime.now(timezone.utc) if confirmed else None,
    )


def evidence() -> SourceEvidence:
    return SourceEvidence(
        source_id="synthetic.source.1",
        jurisdiction="India",
        act="Synthetic Act",
        section="1",
        excerpt="Synthetic evidence used only for automated workflow tests.",
        effective_from=date(2025, 1, 1),
        status="in_force",
        official_url="https://example.invalid/source",
        retrieved_at=datetime.now(timezone.utc),
        sha256="0" * 64,
    )


def answer() -> StructuredLegalAnswer:
    return StructuredLegalAnswer(
        situation="Synthetic situation.",
        applicable_law=("Synthetic Act section 1.",),
        rights=(),
        options=(),
        evidence_to_preserve=(),
        deadlines=(),
        consequences_of_inaction=(),
        next_steps=("Use only for tests.",),
        limitations=("Not legal information.",),
        claims=(
            LegalClaim(
                claim_id="claim.1",
                text="Synthetic claim.",
                cited_source_ids=("synthetic.source.1",),
            ),
        ),
    )


class WorkflowTests(unittest.TestCase):
    def test_retrieval_is_blocked_before_confirmation(self) -> None:
        workflow = LegalWorkflow()
        workflow.submit_extracted_facts(facts(confirmed=False))
        with self.assertRaises(WorkflowError):
            workflow.start_retrieval()

    def test_supported_claim_can_be_published(self) -> None:
        workflow = LegalWorkflow()
        workflow.submit_extracted_facts(facts(confirmed=False))
        workflow.confirm_facts(facts(confirmed=True))
        workflow.complete_safety_routing(immediate_human_help_required=False)
        workflow.start_retrieval()
        workflow.complete_retrieval([evidence()])
        workflow.start_drafting()
        workflow.submit_draft(answer())
        workflow.complete_verification(
            [
                ClaimVerification(
                    claim_id="claim.1",
                    verdict=ClaimVerdict.SUPPORTED,
                    evidence_source_ids=("synthetic.source.1",),
                    reason="The synthetic source explicitly supports the test claim.",
                )
            ]
        )
        snapshot = workflow.publish()
        self.assertEqual(snapshot.stage, WorkflowStage.PUBLISHED)

    def test_insufficient_claim_forces_abstention(self) -> None:
        workflow = LegalWorkflow()
        workflow.submit_extracted_facts(facts(confirmed=False))
        workflow.confirm_facts(facts(confirmed=True))
        workflow.complete_safety_routing(immediate_human_help_required=False)
        workflow.start_retrieval()
        workflow.complete_retrieval([evidence()])
        workflow.start_drafting()
        workflow.submit_draft(answer())
        snapshot = workflow.complete_verification(
            [
                ClaimVerification(
                    claim_id="claim.1",
                    verdict=ClaimVerdict.INSUFFICIENT,
                    reason="Evidence is intentionally insufficient.",
                )
            ]
        )
        self.assertEqual(snapshot.stage, WorkflowStage.ABSTAINED)
        with self.assertRaises(WorkflowError):
            workflow.publish()

    def test_safety_routing_is_terminal_and_blocks_retrieval(self) -> None:
        workflow = LegalWorkflow()
        workflow.submit_extracted_facts(facts(confirmed=False))
        workflow.confirm_facts(facts(confirmed=True))
        snapshot = workflow.complete_safety_routing(immediate_human_help_required=True)
        self.assertEqual(snapshot.stage, WorkflowStage.SAFETY_ROUTED)
        with self.assertRaises(WorkflowError):
            workflow.start_retrieval()

    def test_duplicate_retrieved_sources_are_rejected(self) -> None:
        workflow = LegalWorkflow()
        workflow.submit_extracted_facts(facts(confirmed=False))
        workflow.confirm_facts(facts(confirmed=True))
        workflow.complete_safety_routing(immediate_human_help_required=False)
        workflow.start_retrieval()
        with self.assertRaisesRegex(WorkflowError, "duplicate source identifiers"):
            workflow.complete_retrieval([evidence(), evidence()])

    def test_draft_cannot_cite_unretrieved_source(self) -> None:
        workflow = LegalWorkflow()
        workflow.submit_extracted_facts(facts(confirmed=False))
        workflow.confirm_facts(facts(confirmed=True))
        workflow.complete_safety_routing(immediate_human_help_required=False)
        workflow.start_retrieval()
        workflow.complete_retrieval([evidence()])
        workflow.start_drafting()
        draft = answer().model_copy(
            update={
                "claims": (
                    LegalClaim(
                        claim_id="claim.1",
                        text="Synthetic claim.",
                        cited_source_ids=("not.retrieved",),
                    ),
                )
            }
        )
        with self.assertRaisesRegex(WorkflowError, "not retrieved"):
            workflow.submit_draft(draft)

    def test_verification_must_cover_each_claim_exactly_once(self) -> None:
        workflow = LegalWorkflow()
        workflow.submit_extracted_facts(facts(confirmed=False))
        workflow.confirm_facts(facts(confirmed=True))
        workflow.complete_safety_routing(immediate_human_help_required=False)
        workflow.start_retrieval()
        workflow.complete_retrieval([evidence()])
        workflow.start_drafting()
        workflow.submit_draft(answer())
        with self.assertRaisesRegex(WorkflowError, "cover every draft claim"):
            workflow.complete_verification([])

    def test_supported_verdict_cannot_use_undisplayed_evidence(self) -> None:
        second = evidence().model_copy(update={"source_id": "synthetic.source.2"})
        workflow = LegalWorkflow()
        workflow.submit_extracted_facts(facts(confirmed=False))
        workflow.confirm_facts(facts(confirmed=True))
        workflow.complete_safety_routing(immediate_human_help_required=False)
        workflow.start_retrieval()
        workflow.complete_retrieval([evidence(), second])
        workflow.start_drafting()
        workflow.submit_draft(answer())
        with self.assertRaisesRegex(WorkflowError, "displayed citations"):
            workflow.complete_verification(
                [
                    ClaimVerification(
                        claim_id="claim.1",
                        verdict=ClaimVerdict.SUPPORTED,
                        evidence_source_ids=("synthetic.source.2",),
                        reason="The wrong source was selected.",
                    )
                ]
            )


if __name__ == "__main__":
    unittest.main()

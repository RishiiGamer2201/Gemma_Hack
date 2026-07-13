"""Deterministic workflow enforcing confirmation and verification gates."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from src.models.schemas import (
    ClaimVerdict,
    ClaimVerification,
    ConfirmedFacts,
    SourceEvidence,
    StructuredLegalAnswer,
    WorkflowStage,
)


class WorkflowError(RuntimeError):
    """Safe, user-displayable error for an invalid workflow transition."""


@dataclass(frozen=True, slots=True)
class WorkflowSnapshot:
    """Read-only view of workflow state suitable for a UI controller."""

    stage: WorkflowStage
    facts: ConfirmedFacts | None
    evidence: tuple[SourceEvidence, ...]
    draft: StructuredLegalAnswer | None
    verifications: tuple[ClaimVerification, ...]
    terminal_reason: str | None


class LegalWorkflow:
    """In-memory state machine for one legal-information request.

    The controller contains no model calls, persistence, or network access.  Those
    components must supply typed results and can proceed only through these gates.
    """

    def __init__(self) -> None:
        self._stage = WorkflowStage.INTAKE
        self._facts: ConfirmedFacts | None = None
        self._evidence: tuple[SourceEvidence, ...] = ()
        self._draft: StructuredLegalAnswer | None = None
        self._verifications: tuple[ClaimVerification, ...] = ()
        self._terminal_reason: str | None = None

    @property
    def snapshot(self) -> WorkflowSnapshot:
        """Return an immutable view; sensitive intake content is never persisted here."""

        return WorkflowSnapshot(
            stage=self._stage,
            facts=self._facts,
            evidence=self._evidence,
            draft=self._draft,
            verifications=self._verifications,
            terminal_reason=self._terminal_reason,
        )

    def submit_extracted_facts(self, facts: ConfirmedFacts) -> WorkflowSnapshot:
        """Store an unconfirmed restatement and block downstream processing."""

        self._require(WorkflowStage.INTAKE, WorkflowStage.AWAITING_CONFIRMATION)
        if facts.confirmed:
            raise WorkflowError("Extracted facts must be shown to the user before confirmation.")
        self._facts = facts
        self._stage = WorkflowStage.AWAITING_CONFIRMATION
        return self.snapshot

    def confirm_facts(self, facts: ConfirmedFacts) -> WorkflowSnapshot:
        """Accept the corrected facts only after explicit user confirmation."""

        self._require(WorkflowStage.AWAITING_CONFIRMATION)
        if not facts.confirmed or facts.confirmed_at is None:
            raise WorkflowError("Explicit user confirmation is required before legal retrieval.")
        self._facts = facts
        self._stage = WorkflowStage.CONFIRMED
        return self.snapshot

    def complete_safety_routing(self, *, immediate_human_help_required: bool) -> WorkflowSnapshot:
        """Route urgent cases to help before enabling ordinary retrieval."""

        self._require(WorkflowStage.CONFIRMED)
        self._assert_confirmed()
        if immediate_human_help_required:
            self._stage = WorkflowStage.SAFETY_ROUTED
            self._terminal_reason = "Immediate safety or human-help routing was activated."
        else:
            self._stage = WorkflowStage.RETRIEVAL_READY
        return self.snapshot

    def start_retrieval(self) -> WorkflowSnapshot:
        """Open retrieval only after confirmation and safety routing."""

        self._require(WorkflowStage.RETRIEVAL_READY)
        self._assert_confirmed()
        self._stage = WorkflowStage.RETRIEVING
        return self.snapshot

    def complete_retrieval(self, evidence: Iterable[SourceEvidence]) -> WorkflowSnapshot:
        """Accept a non-empty, uniquely identified official evidence bundle."""

        self._require(WorkflowStage.RETRIEVING)
        records = tuple(evidence)
        if not records:
            raise WorkflowError("No official evidence was retrieved; the workflow must abstain or retry.")
        ids = [record.source_id for record in records]
        if len(ids) != len(set(ids)):
            raise WorkflowError("Retrieved evidence contains duplicate source identifiers.")
        self._evidence = records
        self._stage = WorkflowStage.EVIDENCE_READY
        return self.snapshot

    def start_drafting(self) -> WorkflowSnapshot:
        """Permit drafting from confirmed facts and retrieved evidence."""

        self._require(WorkflowStage.EVIDENCE_READY)
        self._assert_confirmed()
        self._stage = WorkflowStage.DRAFTING
        return self.snapshot

    def submit_draft(self, answer: StructuredLegalAnswer) -> WorkflowSnapshot:
        """Store an unpublished answer and move immediately to verification."""

        self._require(WorkflowStage.DRAFTING)
        retrieved_ids = {source.source_id for source in self._evidence}
        cited_ids = {
            source_id for claim in answer.claims for source_id in claim.cited_source_ids
        }
        if cited_ids - retrieved_ids:
            raise WorkflowError("The draft cites evidence not retrieved for this request.")
        self._draft = answer
        self._stage = WorkflowStage.VERIFYING
        return self.snapshot

    def complete_verification(
        self, verifications: Iterable[ClaimVerification]
    ) -> WorkflowSnapshot:
        """Verify every claim; unsupported or mismatched evidence causes abstention."""

        self._require(WorkflowStage.VERIFYING)
        if self._draft is None:
            raise WorkflowError("No draft is available for verification.")
        decisions = tuple(verifications)
        expected_ids = {claim.claim_id for claim in self._draft.claims}
        decision_ids = [decision.claim_id for decision in decisions]
        if len(decision_ids) != len(set(decision_ids)):
            raise WorkflowError("Each claim must have exactly one verification verdict.")
        if set(decision_ids) != expected_ids:
            raise WorkflowError("Verification verdicts must cover every draft claim exactly once.")

        retrieved_ids = {source.source_id for source in self._evidence}
        claims_by_id = {claim.claim_id: claim for claim in self._draft.claims}
        for decision in decisions:
            unknown = set(decision.evidence_source_ids) - retrieved_ids
            if unknown:
                raise WorkflowError("A verification verdict references evidence not retrieved for this request.")
            if decision.verdict is ClaimVerdict.SUPPORTED and not set(
                decision.evidence_source_ids
            ).issubset(claims_by_id[decision.claim_id].cited_source_ids):
                raise WorkflowError(
                    "Verified evidence must be included in the claim's displayed citations."
                )

        self._verifications = decisions
        if all(decision.verdict is ClaimVerdict.SUPPORTED for decision in decisions):
            self._stage = WorkflowStage.VERIFIED
        else:
            self._stage = WorkflowStage.ABSTAINED
            self._terminal_reason = (
                "One or more legal claims were contradicted or lacked sufficient official evidence."
            )
        return self.snapshot

    def publish(self) -> WorkflowSnapshot:
        """Publish only a fully verified answer."""

        self._require(WorkflowStage.VERIFIED)
        if not self._verifications or any(
            decision.verdict is not ClaimVerdict.SUPPORTED for decision in self._verifications
        ):
            raise WorkflowError("Only a fully supported answer can be published.")
        self._stage = WorkflowStage.PUBLISHED
        return self.snapshot

    def abstain(self, reason: str) -> WorkflowSnapshot:
        """Safely terminate a non-published workflow when evidence or scope is inadequate."""

        if self._stage in {
            WorkflowStage.PUBLISHED,
            WorkflowStage.SAFETY_ROUTED,
            WorkflowStage.ABSTAINED,
        }:
            raise WorkflowError(f"Cannot abstain after terminal stage '{self._stage.value}'.")
        clean_reason = reason.strip()
        if not clean_reason:
            raise WorkflowError("An abstention reason is required.")
        self._stage = WorkflowStage.ABSTAINED
        self._terminal_reason = clean_reason
        return self.snapshot

    def _assert_confirmed(self) -> None:
        if self._facts is None or not self._facts.confirmed:
            raise WorkflowError("Explicit user confirmation is required before legal retrieval.")

    def _require(self, *allowed: WorkflowStage) -> None:
        if self._stage not in allowed:
            expected = ", ".join(stage.value for stage in allowed)
            raise WorkflowError(
                f"Operation is not allowed at stage '{self._stage.value}'; expected: {expected}."
            )

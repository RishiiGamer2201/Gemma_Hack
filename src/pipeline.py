"""End-to-end orchestration of one legal-information request.

This is the only place that runs the full journey, and it runs it through the
deterministic workflow gates rather than around them: intake produces an
unconfirmed restatement, the user confirms, safety routing decides whether
ordinary legal content is permitted at all, retrieval supplies official evidence,
the drafter writes only from that evidence, and the verifier independently checks
every claim before anything can be published.

Nothing here decides law. Every legal proposition in the output came from a
retrieved official excerpt and survived verification, or it was removed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from src.agents.drafter import DraftError, draft_answer
from src.agents.ollama import OllamaClient
from src.agents.researcher import (
    MAX_EVIDENCE,
    EvidenceBundle,
    ResearchError,
    retrieve_evidence,
)
from src.agents.verifier import VerificationError, unsupported_claims, verify_answer
from src.intake import UrgencyCategory, process_text_intake
from src.intake.models import TextIntakeResult
from src.models.schemas import (
    ClaimVerification,
    ConfirmedFacts,
    StructuredLegalAnswer,
    WorkflowStage,
)
from src.retrieval.types import RetrievalDocument
from src.safety import SafetyRouteDecision, apply_route_decision, route_confirmed_case
from src.safety.models import RoutePriority
from src.workflow import LegalWorkflow, WorkflowSnapshot


class PipelineError(RuntimeError):
    """A bounded failure in the end-to-end legal-information journey."""


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Everything the interface may show, and nothing it may not."""

    stage: WorkflowStage
    route: SafetyRouteDecision
    snapshot: WorkflowSnapshot
    evidence_bundle: EvidenceBundle | None = None
    answer: StructuredLegalAnswer | None = None
    verifications: tuple[ClaimVerification, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def published(self) -> bool:
        return self.stage is WorkflowStage.PUBLISHED


def start_intake(text: str, **fields: object) -> TextIntakeResult:
    """Produce an unconfirmed restatement. This never retrieves or advises."""

    return process_text_intake(text, **fields)  # type: ignore[arg-type]


def run_confirmed_request(
    facts: ConfirmedFacts,
    documents: Sequence[RetrievalDocument],
    *,
    client: OllamaClient,
    model: str,
    confirmed_urgencies: Sequence[UrgencyCategory] = (),
    untrusted_document_texts: Sequence[str] = (),
    requested_output: str | None = None,
    approved_profiles: frozenset[str] = frozenset(),
    evidence_limit: int = 6,
) -> PipelineResult:
    """Run confirmed facts through safety routing, retrieval, drafting, verification."""

    if not facts.confirmed or facts.confirmed_at is None:
        raise PipelineError("the pipeline requires explicitly confirmed facts")

    workflow = LegalWorkflow()
    workflow.submit_extracted_facts(_as_unconfirmed(facts))
    workflow.confirm_facts(facts)

    route = route_confirmed_case(
        facts,
        confirmed_urgencies=confirmed_urgencies,
        untrusted_document_texts=untrusted_document_texts,
        requested_output=requested_output,
    )
    snapshot = apply_route_decision(workflow, route)

    # Urgency, refusal, and missing-information routes all stop here. Safety and
    # human help come before ordinary legal explanation, and an unanswerable
    # request is refused rather than answered badly.
    if route.priority is not RoutePriority.STANDARD:
        return PipelineResult(stage=snapshot.stage, route=route, snapshot=snapshot)

    try:
        bundle = retrieve_evidence(
            facts,
            documents,
            approved_profiles=approved_profiles,
            limit=evidence_limit,
        )
    except ResearchError as exc:
        return _abstain(workflow, route, f"Official evidence could not be retrieved: {exc}")

    if not bundle.evidence:
        return _abstain(
            workflow,
            route,
            "No official source in the reviewed corpus matched this situation, so no "
            "legal information can be grounded.",
            bundle=bundle,
        )

    # Draft, verify, and — if a claim could not be supported — repair once, before
    # anything is submitted to the workflow. A single unsupported claim used to
    # withhold the whole answer, which threw away everything the sources *did*
    # support. The repair pass tells the model exactly what failed and requires it to
    # drop that, so the retry can only ever say less.
    #
    # The gates are unchanged: whatever survives is submitted to the workflow, and
    # publication still requires every remaining claim to be verified as supported.
    repair_notes: list[str] = []
    try:
        bundle, answer, verifications = _draft_verify_repair(
            client,
            model=model,
            facts=facts,
            documents=documents,
            bundle=bundle,
            approved_profiles=approved_profiles,
            evidence_limit=evidence_limit,
            repair_notes=repair_notes,
        )
    except DraftError as exc:
        return _abstain(workflow, route, f"A grounded answer could not be drafted: {exc}", bundle)
    except VerificationError as exc:
        return _abstain(workflow, route, f"The answer could not be verified: {exc}", bundle)

    workflow.start_retrieval()
    workflow.complete_retrieval(bundle.evidence)
    workflow.start_drafting()
    workflow.submit_draft(answer)
    snapshot = workflow.complete_verification(verifications)

    warnings = [*bundle.warnings, *repair_notes]
    if snapshot.stage is WorkflowStage.ABSTAINED:
        failed = unsupported_claims(answer, verifications)
        warnings.append(
            f"{len(failed)} claim(s) still could not be supported by the retrieved "
            "official sources after a second attempt, so the answer was withheld "
            "rather than shown."
        )
        return PipelineResult(
            stage=snapshot.stage,
            route=route,
            snapshot=snapshot,
            evidence_bundle=bundle,
            answer=answer,
            verifications=verifications,
            warnings=tuple(warnings),
        )

    snapshot = workflow.publish()
    return PipelineResult(
        stage=snapshot.stage,
        route=route,
        snapshot=snapshot,
        evidence_bundle=bundle,
        answer=answer,
        verifications=verifications,
        warnings=tuple(warnings),
    )


def _draft_verify_repair(
    client: OllamaClient,
    *,
    model: str,
    facts: ConfirmedFacts,
    documents: Sequence[RetrievalDocument],
    bundle: EvidenceBundle,
    approved_profiles: frozenset[str],
    evidence_limit: int,
    repair_notes: list[str],
) -> tuple[EvidenceBundle, StructuredLegalAnswer, tuple[ClaimVerification, ...]]:
    """Draft and verify, with exactly one repair attempt. Never more than one."""

    answer = draft_answer(client, model=model, facts=facts, evidence=bundle.evidence)
    verifications = verify_answer(
        client, model=model, answer=answer, evidence=bundle.evidence
    )
    failed = unsupported_claims(answer, verifications)
    if not failed:
        return bundle, answer, verifications

    # One constrained re-retrieval: widen the evidence slightly in case the claim was
    # sound but its supporting provision simply was not retrieved. If widening fails,
    # keep what we have and still attempt the repair draft.
    wider = bundle
    if evidence_limit < MAX_EVIDENCE:
        try:
            candidate = retrieve_evidence(
                facts,
                documents,
                approved_profiles=approved_profiles,
                limit=min(MAX_EVIDENCE, evidence_limit + 2),
            )
            if candidate.evidence:
                wider = candidate
        except ResearchError:
            wider = bundle

    reasons = {item.claim_id: item.reason for item in verifications}
    rejected = tuple((claim.text, reasons.get(claim.claim_id, "unsupported")) for claim in failed)

    repaired = draft_answer(
        client,
        model=model,
        facts=facts,
        evidence=wider.evidence,
        rejected_claims=rejected,
    )
    repaired_verifications = verify_answer(
        client, model=model, answer=repaired, evidence=wider.evidence
    )
    repair_notes.append(
        f"{len(failed)} statement(s) in the first draft could not be supported by the "
        "official sources and were removed; the answer was rewritten using only what "
        "the sources support."
    )
    return wider, repaired, repaired_verifications


def _as_unconfirmed(facts: ConfirmedFacts) -> ConfirmedFacts:
    """Re-enter the workflow at intake without asserting confirmation."""

    payload = facts.model_dump()
    payload["confirmed"] = False
    payload["confirmed_at"] = None
    return ConfirmedFacts.model_validate(payload)


def _abstain(
    workflow: LegalWorkflow,
    route: SafetyRouteDecision,
    reason: str,
    bundle: EvidenceBundle | None = None,
    answer: StructuredLegalAnswer | None = None,
) -> PipelineResult:
    snapshot = workflow.abstain(reason)
    warnings = tuple(bundle.warnings) if bundle else ()
    return PipelineResult(
        stage=snapshot.stage,
        route=route,
        snapshot=snapshot,
        evidence_bundle=bundle,
        answer=answer,
        warnings=(*warnings, reason),
    )

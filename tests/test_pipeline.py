"""End-to-end journey: intake, confirmation, routing, retrieval, drafting, verification."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

import pytest

from src.agents.ollama import OllamaResponse
from src.intake import UrgencyCategory
from src.models.schemas import ConfirmedFacts, LegalDomain, WorkflowStage
from src.pipeline import PipelineError, run_confirmed_request, start_intake
from src.retrieval import RetrievalDocument
from src.safety.models import RoutePriority

WAGE_EXCERPT = "All wages shall be paid within the prescribed wage period by the employer."


class FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.calls = 0
        self.prompts: list[str] = []

    def generate(self, **kwargs: Any) -> OllamaResponse:
        self.calls += 1
        self.prompts.append(str(kwargs.get("prompt", "")))
        return OllamaResponse(
            text=self._responses.pop(0), model=kwargs["model"], done=True, raw={}
        )


def wage_document() -> RetrievalDocument:
    return RetrievalDocument(
        source_id="code_on_wages_2019_en:section-17",
        text=f"The Code on Wages, 2019 17 payment of wages {WAGE_EXCERPT}",
        metadata={
            "corpus_source_id": "code_on_wages_2019_en",
            "act": "The Code on Wages, 2019",
            "section": "17",
            "heading": "Time limit for payment of wages",
            "jurisdiction": "India",
            "language": "en",
            "status": "in_force",
            "priority": 3,
            "effective_from": "2019-08-08",
            "effective_to": None,
            "official_url": "https://www.indiacode.nic.in/example.pdf",
            "retrieved_at": "2026-07-12T10:00:00+00:00",
            "sha256": "a" * 64,
            "ocr_used": False,
            "page_start": 12,
            "source_text": WAGE_EXCERPT,
        },
    )


def facts(**updates: object) -> ConfirmedFacts:
    payload: dict[str, object] = {
        "incident_summary": "My employer has not paid my wages for two months.",
        "incident_date": date(2026, 5, 1),
        "jurisdiction": "Delhi",
        "domain": LegalDomain.LABOUR,
        "parties": ("Worker", "Employer"),
        "confirmed": True,
        "confirmed_at": datetime(2026, 7, 13, tzinfo=UTC),
    }
    payload.update(updates)
    return ConfirmedFacts.model_validate(payload)


def draft(claim_text: str) -> str:
    return json.dumps(
        {
            "situation": "Wages have not been paid for two months.",
            "applicable_law": ["The Code on Wages, 2019"],
            "rights": ["Wages must be paid within the wage period."],
            "options": ["Write to the employer."],
            "evidence_to_preserve": ["Payslips and bank statements."],
            "deadlines": ["See the cited provision."],
            "consequences_of_inaction": ["The dispute may remain unresolved."],
            "next_steps": ["Contact a District Legal Services Authority."],
            "limitations": ["This is legal information, not legal advice."],
            "claims": [
                {
                    "claim_id": "c1",
                    "text": claim_text,
                    "cited_source_ids": ["code_on_wages_2019_en:section-17"],
                }
            ],
        }
    )


def verdict(status: str, ids: list[str]) -> str:
    return json.dumps(
        {"verdict": status, "reason": "Checked against the excerpt.", "evidence_source_ids": ids}
    )


def test_intake_never_arrives_confirmed() -> None:
    result = start_intake("Mera employer ne do mahine se salary nahi di")

    assert result.requires_confirmation is True
    assert result.confirmed is False
    assert result.to_unconfirmed_facts().confirmed is False
    # The restatement must not contain law, only what the user said.
    assert "Section" not in result.restatement


def test_pipeline_refuses_unconfirmed_facts() -> None:
    unconfirmed = ConfirmedFacts(
        incident_summary="Wages unpaid.", domain=LegalDomain.LABOUR
    )
    with pytest.raises(PipelineError):
        run_confirmed_request(
            unconfirmed, [wage_document()], client=FakeClient([]), model="gemma4"
        )


def test_full_journey_publishes_only_a_verified_answer() -> None:
    client = FakeClient(
        [
            draft("Wages must be paid within the wage period."),
            verdict("supported", ["code_on_wages_2019_en:section-17"]),
        ]
    )
    result = run_confirmed_request(
        facts(), [wage_document()], client=client, model="gemma4"
    )

    assert result.published is True
    assert result.stage is WorkflowStage.PUBLISHED
    assert result.route.priority is RoutePriority.STANDARD
    assert result.answer is not None
    assert result.verifications[0].verdict.value == "supported"
    assert result.evidence_bundle is not None
    assert result.evidence_bundle.evidence[0].section == "17"


def test_a_claim_that_fails_twice_withholds_the_answer() -> None:
    """The repair pass gets one chance. A claim that fails again is never published."""

    client = FakeClient(
        [
            draft("You are entitled to compensation of three months' wages."),
            verdict("insufficient", []),
            draft("You are entitled to compensation of three months' wages."),
            verdict("insufficient", []),
        ]
    )
    result = run_confirmed_request(
        facts(), [wage_document()], client=client, model="gemma4"
    )

    assert result.published is False
    assert result.stage is WorkflowStage.ABSTAINED
    assert result.answer is not None  # withheld, not shown
    assert any("could not be supported" in warning for warning in result.warnings)


def test_confirmed_urgency_routes_to_human_help_before_any_retrieval() -> None:
    client = FakeClient([])
    result = run_confirmed_request(
        facts(incident_summary="My employer threatened to kill me if I ask for wages."),
        [wage_document()],
        client=client,
        model="gemma4",
        confirmed_urgencies=[UrgencyCategory.VIOLENCE],
    )

    assert result.stage is WorkflowStage.SAFETY_ROUTED
    assert result.route.human_help_required is True
    assert result.route.general_explanation_allowed is False
    assert result.answer is None
    # The model must never have been called for an urgent case.
    assert client.calls == 0


def test_outcome_prediction_request_is_refused_before_retrieval() -> None:
    client = FakeClient([])
    result = run_confirmed_request(
        facts(),
        [wage_document()],
        client=client,
        model="gemma4",
        requested_output="What is my chance of winning this case?",
    )

    assert result.stage is WorkflowStage.ABSTAINED
    assert result.route.priority is RoutePriority.HARD_ABSTAIN
    assert client.calls == 0


def test_missing_jurisdiction_asks_before_retrieving() -> None:
    client = FakeClient([])
    result = run_confirmed_request(
        facts(jurisdiction=None), [wage_document()], client=client, model="gemma4"
    )

    assert result.route.priority is RoutePriority.NEEDS_INFORMATION
    assert [q.fact_key for q in result.route.missing_questions] == ["jurisdiction"]
    assert result.answer is None
    assert client.calls == 0


def test_empty_retrieval_abstains_instead_of_answering_from_memory() -> None:
    unrelated = RetrievalDocument(
        source_id="k:1",
        text="constitutional rights",
        metadata={"corpus_source_id": "constitution_2026_en"},
    )
    client = FakeClient([])
    result = run_confirmed_request(
        facts(incident_summary="zzzz qqqq unmatched terms"),
        [unrelated],
        client=client,
        model="gemma4",
    )

    assert result.stage is WorkflowStage.ABSTAINED
    assert client.calls == 0


def test_an_unsupported_claim_is_repaired_and_the_rest_still_publishes() -> None:
    """One bad claim must not throw away everything the sources did support."""

    client = FakeClient(
        [
            # First draft: one supportable claim plus one that is not.
            draft("You are entitled to three months' compensation."),
            verdict("insufficient", []),
            # Repair draft: the unsupported assertion is dropped.
            draft("Wages must be paid within the wage period."),
            verdict("supported", ["code_on_wages_2019_en:section-17"]),
        ]
    )
    result = run_confirmed_request(
        facts(), [wage_document()], client=client, model="gemma4"
    )

    assert result.published is True
    assert result.verifications[0].verdict.value == "supported"
    assert any("were removed" in warning for warning in result.warnings)
    # The repair prompt must name the rejected claim so the model drops it.
    repair_prompt = client.prompts[2]
    assert "three months' compensation" in repair_prompt
    assert "Do NOT repeat those statements" in repair_prompt


def test_the_repair_runs_at_most_once_then_abstains() -> None:
    """A second failure must abstain, not loop. The retry can only ever say less."""

    client = FakeClient(
        [
            draft("You are entitled to compensation."),
            verdict("insufficient", []),
            draft("You are still entitled to compensation."),
            verdict("insufficient", []),
        ]
    )
    result = run_confirmed_request(
        facts(), [wage_document()], client=client, model="gemma4"
    )

    assert result.published is False
    assert result.stage is WorkflowStage.ABSTAINED
    assert any("after a second attempt" in warning for warning in result.warnings)
    # Exactly two drafts and two verifications: no third attempt.
    assert client.calls == 4

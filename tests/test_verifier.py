"""Grounded drafting and independent claim-to-source verification."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

import pytest

from src.agents.drafter import DraftError, draft_answer, uncited_section_references
from src.agents.ollama import OllamaError, OllamaResponse
from src.agents.verifier import (
    VerificationError,
    unsupported_claims,
    verify_answer,
)
from src.models.schemas import (
    ClaimVerdict,
    ConfirmedFacts,
    LegalDomain,
    SourceEvidence,
    StructuredLegalAnswer,
)
from src.workflow import LegalWorkflow


class FakeClient:
    """Records prompts and replays scripted local-model responses."""

    def __init__(self, responses: list[str] | Exception) -> None:
        self._responses = responses
        self.prompts: list[str] = []
        self.systems: list[str | None] = []

    def generate(self, **kwargs: Any) -> OllamaResponse:
        if isinstance(self._responses, Exception):
            raise self._responses
        self.prompts.append(kwargs["prompt"])
        self.systems.append(kwargs.get("system"))
        text = self._responses.pop(0)
        return OllamaResponse(text=text, model=kwargs["model"], done=True, raw={})


def evidence(
    source_id: str = "code_on_wages_2019_en:section-17",
    *,
    section: str | None = "17",
    excerpt: str = "All wages shall be paid within the prescribed wage period.",
    act: str = "The Code on Wages, 2019",
) -> SourceEvidence:
    return SourceEvidence(
        source_id=source_id,
        jurisdiction="India",
        act=act,
        section=section,
        heading="Time limit for payment of wages",
        excerpt=excerpt,
        status="in_force",
        priority=3,
        official_url="https://www.indiacode.nic.in/example.pdf",
        retrieved_at=datetime(2026, 7, 12, tzinfo=UTC),
        sha256="a" * 64,
    )


def facts() -> ConfirmedFacts:
    return ConfirmedFacts(
        incident_summary="My employer has not paid my wages for two months.",
        incident_date=date(2026, 5, 1),
        domain=LegalDomain.LABOUR,
        confirmed=True,
        confirmed_at=datetime(2026, 7, 13, tzinfo=UTC),
    )


def answer_payload(claim_text: str, cited: list[str]) -> str:
    return json.dumps(
        {
            "situation": "Wages have not been paid.",
            "applicable_law": ["The Code on Wages, 2019"],
            "rights": ["Wages must be paid within the wage period."],
            "options": ["Raise the matter with the employer in writing."],
            "evidence_to_preserve": ["Payslips"],
            "deadlines": ["See the cited provision."],
            "consequences_of_inaction": ["The dispute may remain unresolved."],
            "next_steps": ["Contact a legal-services authority."],
            "limitations": ["This is legal information, not legal advice."],
            "claims": [
                {"claim_id": "c1", "text": claim_text, "cited_source_ids": cited}
            ],
        }
    )


def structured(claim_text: str, cited: list[str]) -> StructuredLegalAnswer:
    return StructuredLegalAnswer.model_validate_json(answer_payload(claim_text, cited))


def test_drafter_rejects_a_citation_that_was_never_retrieved() -> None:
    client = FakeClient([answer_payload("Wages are due.", ["invented_source_id"])])

    with pytest.raises(DraftError):
        draft_answer(client, model="gemma4", facts=facts(), evidence=[evidence()])


def test_drafter_requires_confirmed_facts_and_evidence() -> None:
    unconfirmed = ConfirmedFacts(
        incident_summary="Wages unpaid.", domain=LegalDomain.LABOUR
    )
    with pytest.raises(DraftError):
        draft_answer(FakeClient([]), model="gemma4", facts=unconfirmed, evidence=[evidence()])
    with pytest.raises(DraftError):
        draft_answer(FakeClient([]), model="gemma4", facts=facts(), evidence=[])


def test_drafter_reports_a_local_model_failure_safely() -> None:
    client = FakeClient(OllamaError("connection_error", "runtime down"))
    with pytest.raises(DraftError):
        draft_answer(client, model="gemma4", facts=facts(), evidence=[evidence()])


def test_fabricated_provision_is_caught_without_the_model() -> None:
    """The png2.jpg failure mode: a section that does not exist in the cited source."""

    source = evidence(
        source_id="constitution_2026_en:article-300a",
        section="300A",
        act="The Constitution of India",
        excerpt="No person shall be deprived of his property save by authority of law.",
    )
    fabricated = structured(
        "Section 247A of the Indian Constitution allows you to reclaim your property.",
        ["constitution_2026_en:article-300a"],
    )

    offences = uncited_section_references(fabricated, [source])
    assert offences == (("c1", "247A"),)


def test_verifier_overrides_a_model_that_supports_a_fabricated_provision() -> None:
    source = evidence(
        source_id="constitution_2026_en:article-300a",
        section="300A",
        act="The Constitution of India",
        excerpt="No person shall be deprived of his property save by authority of law.",
    )
    fabricated = structured(
        "Section 247A of the Indian Constitution allows you to reclaim your property.",
        ["constitution_2026_en:article-300a"],
    )
    # The model is scripted to wrongly bless the claim. It must not be consulted:
    # the deterministic guard settles it first.
    client = FakeClient(
        [json.dumps({"verdict": "supported", "reason": "looks right", "evidence_source_ids": [source.source_id]})]
    )

    verdicts = verify_answer(client, model="gemma4", answer=fabricated, evidence=[source])

    assert verdicts[0].verdict is ClaimVerdict.INSUFFICIENT
    assert "247A" in verdicts[0].reason
    assert client.prompts == []


def test_supported_claim_records_the_excerpt_it_relied_on() -> None:
    source = evidence()
    answer = structured(
        "Wages must be paid within the wage period under the Code on Wages.",
        [source.source_id],
    )
    client = FakeClient(
        [
            json.dumps(
                {
                    "verdict": "supported",
                    "reason": "The excerpt states wages are paid within the wage period.",
                    "evidence_source_ids": [source.source_id],
                }
            )
        ]
    )

    verdicts = verify_answer(client, model="gemma4", answer=answer, evidence=[source])

    assert verdicts[0].verdict is ClaimVerdict.SUPPORTED
    assert verdicts[0].evidence_source_ids == (source.source_id,)
    # The verifier must never see the drafter's reasoning, only claim + excerpts.
    assert "Wages have not been paid." not in client.prompts[0]


def test_support_without_a_named_excerpt_is_downgraded() -> None:
    source = evidence()
    answer = structured("Wages must be paid on time.", [source.source_id])
    client = FakeClient(
        [json.dumps({"verdict": "supported", "reason": "yes", "evidence_source_ids": []})]
    )

    verdicts = verify_answer(client, model="gemma4", answer=answer, evidence=[source])

    assert verdicts[0].verdict is ClaimVerdict.INSUFFICIENT
    assert verdicts[0].evidence_source_ids == ()


def test_unknown_verdict_and_invalid_json_fail_closed() -> None:
    source = evidence()
    answer = structured("Wages must be paid on time.", [source.source_id])

    with pytest.raises(VerificationError):
        verify_answer(
            FakeClient(["not json"]), model="gemma4", answer=answer, evidence=[source]
        )
    with pytest.raises(VerificationError):
        verify_answer(
            FakeClient([json.dumps({"verdict": "probably", "reason": "x", "evidence_source_ids": []})]),
            model="gemma4",
            answer=answer,
            evidence=[source],
        )


def test_an_unsupported_claim_forces_the_workflow_to_abstain() -> None:
    source = evidence()
    answer = structured("Wages must be paid on time.", [source.source_id])
    client = FakeClient(
        [
            json.dumps(
                {
                    "verdict": "insufficient",
                    "reason": "The excerpt does not settle this.",
                    "evidence_source_ids": [],
                }
            )
        ]
    )
    verdicts = verify_answer(client, model="gemma4", answer=answer, evidence=[source])

    workflow = LegalWorkflow()
    workflow.submit_extracted_facts(
        ConfirmedFacts(incident_summary=facts().incident_summary, domain=LegalDomain.LABOUR)
    )
    workflow.confirm_facts(facts())
    workflow.complete_safety_routing(immediate_human_help_required=False)
    workflow.start_retrieval()
    workflow.complete_retrieval([source])
    workflow.start_drafting()
    workflow.submit_draft(answer)
    snapshot = workflow.complete_verification(verdicts)

    assert snapshot.stage.value == "abstained"
    assert unsupported_claims(answer, verdicts) == answer.claims

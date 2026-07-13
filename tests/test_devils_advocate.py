from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from src.agents import (
    AdvocateStage,
    DevilsAdvocateError,
    EventKind,
    OllamaStreamChunk,
    run_devils_advocate_stream,
)
from src.models import (
    ClaimVerdict,
    ClaimVerification,
    ConfirmedFacts,
    LegalClaim,
    SourceEvidence,
    StructuredLegalAnswer,
    WorkflowStage,
)
from src.workflow import WorkflowSnapshot


class FakeStreamingClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_stream(self, **kwargs: object):
        self.calls.append(kwargs)
        stage = len(self.calls)
        yield OllamaStreamChunk("wages_s1 stage ", "model", False, {})
        yield OllamaStreamChunk(str(stage), "model", True, {})


def confirmed_facts() -> ConfirmedFacts:
    return ConfirmedFacts(
        incident_summary="My employer has not paid two months of wages.",
        incident_date=date(2026, 6, 1),
        jurisdiction="India",
        material_facts=("Two wage payments are pending.",),
        confirmed=True,
        confirmed_at=datetime.now(UTC),
    )


def official_evidence() -> SourceEvidence:
    return SourceEvidence(
        source_id="wages_s1",
        jurisdiction="India",
        act="Code on Wages, 2019",
        section="1",
        excerpt="Synthetic official-source fixture excerpt.",
        official_url="https://labour.gov.in/example",
        retrieved_at=datetime.now(UTC),
        sha256="1" * 64,
    )


def verified_workflow(*, facts: ConfirmedFacts | None = None) -> WorkflowSnapshot:
    claim = LegalClaim(claim_id="claim_1", text="Fixture claim.", cited_source_ids=("wages_s1",))
    answer = StructuredLegalAnswer(
        situation="Fixture situation.",
        applicable_law=(),
        rights=(),
        options=(),
        evidence_to_preserve=(),
        deadlines=(),
        consequences_of_inaction=(),
        next_steps=(),
        limitations=(),
        claims=(claim,),
    )
    decision = ClaimVerification(
        claim_id="claim_1",
        verdict=ClaimVerdict.SUPPORTED,
        evidence_source_ids=("wages_s1",),
        reason="Supported by fixture evidence.",
    )
    return WorkflowSnapshot(
        stage=WorkflowStage.VERIFIED,
        facts=facts or confirmed_facts(),
        evidence=(official_evidence(),),
        draft=answer,
        verifications=(decision,),
        terminal_reason=None,
    )


def test_three_stages_stream_sequentially_on_one_client() -> None:
    client = FakeStreamingClient()
    events = list(
        run_devils_advocate_stream(
            client, model="gemma4:e4b-it-q4_K_M", workflow=verified_workflow()
        )
    )
    assert [event.stage for event in events if event.kind is EventKind.STARTED] == list(
        AdvocateStage
    )
    assert [event.text for event in events if event.kind is EventKind.COMPLETED] == [
        "wages_s1 stage 1",
        "wages_s1 stage 2",
        "wages_s1 stage 3",
    ]
    assert len(client.calls) == 3
    assert all(call["model"] == "gemma4:e4b-it-q4_K_M" for call in client.calls)
    assert all(call["keep_alive"] == "10m" and call["think"] is False for call in client.calls)
    assert "unverified model analysis" in str(client.calls[1]["prompt"])


def test_confirmation_and_verified_answer_are_hard_gates() -> None:
    client = FakeStreamingClient()
    unconfirmed = confirmed_facts().model_copy(update={"confirmed": False, "confirmed_at": None})
    with pytest.raises(DevilsAdvocateError, match="confirmed"):
        list(
            run_devils_advocate_stream(
                client, model="model", workflow=verified_workflow(facts=unconfirmed)
            )
        )
    unverified = verified_workflow()
    unverified = WorkflowSnapshot(
        stage=WorkflowStage.EVIDENCE_READY,
        facts=unverified.facts,
        evidence=unverified.evidence,
        draft=None,
        verifications=(),
        terminal_reason=None,
    )
    with pytest.raises(DevilsAdvocateError, match="verified answer"):
        list(run_devils_advocate_stream(client, model="model", workflow=unverified))
    assert not client.calls


def test_empty_model_output_fails_closed() -> None:
    class EmptyClient(FakeStreamingClient):
        def generate_stream(self, **kwargs: object):
            self.calls.append(kwargs)
            yield OllamaStreamChunk("", "model", True, {})

    with pytest.raises(DevilsAdvocateError, match="no visible text"):
        list(run_devils_advocate_stream(EmptyClient(), model="model", workflow=verified_workflow()))


def test_uncited_output_and_non_official_evidence_fail_closed() -> None:
    class UncitedClient(FakeStreamingClient):
        def generate_stream(self, **kwargs: object):
            yield OllamaStreamChunk("Section 999 creates a right.", "model", True, {})

    # Section 999 is not in the verified evidence, so the stage fails closed. A stage
    # that names a real, verified provision without repeating the raw source_id is
    # accepted: opposing counsel writes "section 17", not the corpus identifier.
    with pytest.raises(DevilsAdvocateError, match="not in the verified evidence"):
        list(
            run_devils_advocate_stream(UncitedClient(), model="model", workflow=verified_workflow())
        )

    workflow = verified_workflow()
    unsafe = workflow.evidence[0].model_copy(update={"official_url": "https://example.com/source"})
    workflow = WorkflowSnapshot(
        stage=workflow.stage,
        facts=workflow.facts,
        evidence=(unsafe,),
        draft=workflow.draft,
        verifications=workflow.verifications,
        terminal_reason=None,
    )
    with pytest.raises(DevilsAdvocateError, match="official"):
        list(run_devils_advocate_stream(FakeStreamingClient(), model="model", workflow=workflow))


def test_utf8_prompt_budget_fails_before_stage_start_or_generation() -> None:
    client = FakeStreamingClient()
    large_hindi = confirmed_facts().model_copy(update={"incident_summary": "क" * 1_600})
    with pytest.raises(DevilsAdvocateError, match="without truncation"):
        list(
            run_devils_advocate_stream(
                client,
                model="model",
                workflow=verified_workflow(facts=large_hindi),
                context_tokens=2048,
                max_output_tokens=96,
            )
        )
    assert not client.calls


def test_a_verified_provision_may_be_argued_without_quoting_the_source_id() -> None:
    """Opposing counsel writes "section 1", not "wages_s1"; that must not fail closed.

    The guard previously demanded the raw corpus identifier appear verbatim in the
    prose before any section number was permitted, so every stage that argued about
    the law at all was rejected and the stress test could never complete.
    """

    class GroundedClient(FakeStreamingClient):
        def generate_stream(self, **kwargs: object):
            yield OllamaStreamChunk(
                "Section 1 is the provision relied on, and it is not decisive here.",
                "model",
                True,
                {},
            )

    events = list(
        run_devils_advocate_stream(GroundedClient(), model="model", workflow=verified_workflow())
    )
    completed = [event for event in events if event.kind is EventKind.COMPLETED]
    assert len(completed) == 3

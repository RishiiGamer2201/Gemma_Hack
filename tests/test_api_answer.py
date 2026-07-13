"""The /api/answer endpoint must never publish anything the pipeline withheld."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.agents.ollama import OllamaError, OllamaResponse
from src.api.app import create_app
from src.api.state import ApiState
from src.config import Settings

WAGE_EXCERPT = "All wages shall be paid within the prescribed wage period by the employer."

CONFIRMED = {
    "incident_summary": "My employer has not paid my wages for two months.",
    "incident_date": "2026-05-01",
    "jurisdiction": "Delhi",
    "domain": "labour",
    "confirmed": True,
    "confirmed_at": "2026-07-13T09:00:00+00:00",
}


def chunk() -> dict[str, Any]:
    return {
        "chunk_id": "code_on_wages_2019_en:section-17",
        "source_id": "code_on_wages_2019_en",
        "section_id": "17",
        "heading": "Time limit for payment of wages",
        "text": WAGE_EXCERPT,
        "page_start": 12,
        "page_end": 12,
        "metadata": {
            "act": "The Code on Wages, 2019",
            "jurisdiction": "India",
            "language": "en",
            "document_type": "act",
            "status": "in_force",
            "priority": 3,
            "effective_from": "2019-08-08",
            "effective_to": None,
            "official_url": "https://www.indiacode.nic.in/example.pdf",
            "retrieved_at": "2026-07-12T10:00:00+00:00",
            "sha256": "a" * 64,
            "ocr_used": False,
        },
    }


class FakeClient:
    def __init__(self, responses: list[str] | Exception) -> None:
        self._responses = responses
        self.calls = 0

    def generate(self, **kwargs: Any) -> OllamaResponse:
        if isinstance(self._responses, Exception):
            raise self._responses
        self.calls += 1
        return OllamaResponse(
            text=self._responses.pop(0), model=kwargs["model"], done=True, raw={}
        )


def draft(claim: str) -> str:
    return json.dumps(
        {
            "situation": "Wages unpaid.",
            "applicable_law": ["The Code on Wages, 2019"],
            "rights": ["Wages must be paid within the wage period."],
            "options": ["Write to the employer."],
            "evidence_to_preserve": ["Payslips"],
            "deadlines": ["See the cited provision."],
            "consequences_of_inaction": ["The dispute may remain unresolved."],
            "next_steps": ["Contact a legal-services authority."],
            "limitations": ["Legal information, not legal advice."],
            "claims": [
                {
                    "claim_id": "c1",
                    "text": claim,
                    "cited_source_ids": ["code_on_wages_2019_en:section-17"],
                }
            ],
        }
    )


def verdict(status: str, ids: list[str]) -> str:
    return json.dumps({"verdict": status, "reason": "checked", "evidence_source_ids": ids})


@pytest.fixture
def client_factory(tmp_path: Path):
    sections = tmp_path / "sections"
    sections.mkdir()
    (sections / "code_on_wages_2019_en.jsonl").write_text(
        json.dumps(chunk()) + "\n", encoding="utf-8"
    )

    def build(responses: list[str] | Exception) -> tuple[TestClient, FakeClient]:
        fake = FakeClient(responses)
        state = ApiState(
            settings=Settings.from_env(),
            corpus_dir=sections,
            contacts_path=tmp_path / "contacts.json",
            checklists_path=Path("config/evidence_checklists.json"),
            tessdata_dir=tmp_path / "tessdata",
            tesseract_path=tmp_path / "tesseract.exe",
            use_embeddings=False,
        )
        state.load_corpus()
        state._client = fake  # type: ignore[assignment]
        return TestClient(create_app(state)), fake

    return build


def test_unconfirmed_facts_cannot_reach_the_model(client_factory) -> None:
    client, fake = client_factory([])
    response = client.post(
        "/api/answer", json={"facts": {**CONFIRMED, "confirmed": False, "confirmed_at": None}}
    )

    assert response.status_code == 409
    assert response.json()["code"] == "facts_not_confirmed"
    assert fake.calls == 0


def test_a_verified_answer_is_published_with_its_verdicts(client_factory) -> None:
    client, _ = client_factory(
        [
            draft("Wages must be paid within the wage period."),
            verdict("supported", ["code_on_wages_2019_en:section-17"]),
        ]
    )
    body = client.post("/api/answer", json={"facts": CONFIRMED, "limit": 1}).json()

    assert body["published"] is True
    assert body["stage"] == "published"
    assert body["answer"] is not None
    assert body["claims"][0]["verdict"] == "supported"
    assert body["claims"][0]["cited_source_ids"] == ["code_on_wages_2019_en:section-17"]
    assert body["evidence"][0]["section"] == "17"


def test_an_unsupported_claim_is_not_sent_to_the_client_at_all(client_factory) -> None:
    """A withheld answer must not travel over the wire, where it could still render."""

    client, _ = client_factory(
        [draft("You are owed three months' compensation."), verdict("insufficient", [])]
    )
    body = client.post("/api/answer", json={"facts": CONFIRMED, "limit": 1}).json()

    assert body["published"] is False
    assert body["stage"] == "abstained"
    assert body["answer"] is None
    assert body["claims"] == []
    # The retrieved sources remain available; only the unverified prose is withheld.
    assert len(body["evidence"]) == 1
    assert any("not supported" in warning for warning in body["warnings"])


def test_confirmed_urgency_never_calls_the_model(client_factory) -> None:
    client, fake = client_factory([])
    body = client.post(
        "/api/answer",
        json={"facts": CONFIRMED, "confirmed_urgencies": ["violence"], "limit": 1},
    ).json()

    assert body["stage"] == "safety_routed"
    assert body["published"] is False
    assert body["answer"] is None
    assert body["route"]["human_help_required"] is True
    assert fake.calls == 0


def test_an_unreachable_runtime_abstains_and_still_returns_the_sources(
    client_factory,
) -> None:
    """A dead model must not lose the citations that were already retrieved."""

    client, _ = client_factory(OllamaError("connection_error", "runtime down"))
    response = client.post("/api/answer", json={"facts": CONFIRMED, "limit": 1})
    body = response.json()

    assert response.status_code == 200
    assert body["published"] is False
    assert body["stage"] == "abstained"
    assert body["answer"] is None
    assert len(body["evidence"]) == 1
    assert any("could not be drafted" in warning for warning in body["warnings"])


@pytest.mark.parametrize(
    "request_text",
    [
        "What are my chances of winning?",
        "What is my chance of winning this case?",
        "What are the odds of success here?",
        "Will I win?",
        "Do you think we will win?",
        "How likely is my case to succeed?",
        "Predict how many years in jail I will get.",
        "Guarantee that I will win.",
    ],
)
def test_every_ordinary_phrasing_of_an_outcome_question_is_refused(
    client_factory, request_text: str
) -> None:
    """The commonest phrasing must be refused, not just the textbook one.

    An earlier revision matched "what is ... chance of winning" but not the plural
    "what are ... chances of winning", so the way a citizen actually asks the one
    question this product must never answer reached the model.
    """

    client, fake = client_factory([])
    body = client.post(
        "/api/answer", json={"facts": CONFIRMED, "requested_output": request_text}
    ).json()

    assert body["route"]["priority"] == "hard_abstain", request_text
    assert body["published"] is False
    assert fake.calls == 0

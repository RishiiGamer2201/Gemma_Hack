"""The community brief must carry only verified content and drop identifiers."""

from __future__ import annotations

from datetime import UTC, datetime

from src.models.schemas import LegalClaim, SourceEvidence, StructuredLegalAnswer
from src.tools.community import build_community_explanation


def evidence(effective: str | None = "2019-08-08") -> SourceEvidence:
    return SourceEvidence(
        source_id="code_on_wages_2019_en:section-17",
        jurisdiction="India",
        act="The Code on Wages, 2019",
        section="17",
        excerpt="All wages shall be paid within the prescribed wage period.",
        status="in_force",
        priority=3,
        official_url="https://www.indiacode.nic.in/example.pdf",
        retrieved_at=datetime(2026, 7, 12, tzinfo=UTC),
        sha256="a" * 64,
        effective_from=effective,
    )


def answer() -> StructuredLegalAnswer:
    return StructuredLegalAnswer(
        situation="Wages have not been paid for two months.",
        applicable_law=("The Code on Wages, 2019",),
        rights=("Wages must be paid on time (code_on_wages_2019_en:section-17).",),
        options=("Write to the employer.",),
        evidence_to_preserve=("Payslips.",),
        deadlines=(),
        consequences_of_inaction=("The dispute may remain unresolved.",),
        next_steps=("Contact a District Legal Services Authority.",),
        limitations=("Legal information, not legal advice.",),
        claims=(
            LegalClaim(
                claim_id="c1",
                text="Wages must be paid on time.",
                cited_source_ids=("code_on_wages_2019_en:section-17",),
            ),
        ),
    )


def test_brief_is_third_person_and_carries_verified_rights() -> None:
    brief = build_community_explanation(answer(), [evidence()])

    assert "trust" in brief.what_help_is_needed
    assert brief.rights == ("Wages must be paid on time.",)  # source_id stripped
    assert brief.next_steps == ("Contact a District Legal Services Authority.",)
    assert any("Code on Wages" in citation for citation in brief.citations)
    assert any("not legal advice" in caveat for caveat in brief.caveats)
    assert any("cannot override" in caveat for caveat in brief.caveats)


def test_identifiers_are_omitted_by_default() -> None:
    default = build_community_explanation(answer(), [evidence()])
    assert "A person you know" in default.situation

    explicit = build_community_explanation(answer(), [evidence()], include_sensitive=True)
    assert "A person you know" not in explicit.situation


def test_unverified_commencement_is_carried_into_the_brief() -> None:
    brief = build_community_explanation(
        answer(),
        [evidence(effective=None)],
        warnings=("The commencement date of The Code on Wages, 2019 is not proven.",),
    )
    assert any("commencement not verified" in citation for citation in brief.citations)
    assert any("not proven" in caveat for caveat in brief.caveats)


def test_the_brief_never_adds_a_source_id_a_citizen_wrote() -> None:
    # A colon token that is not a real source_id (e.g. a time or ratio) must survive.
    custom = answer().model_copy(
        update={
            "next_steps": ("Reach the office by 9:30 in the morning.",),
        }
    )
    brief = build_community_explanation(custom, [evidence()])
    assert "9:30" in brief.next_steps[0]

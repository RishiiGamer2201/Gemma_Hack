import json
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.applicability import (
    DRC_PROFILE_ID,
    ApplicabilityDecision,
    DelhiRentApplicabilityFacts,
    evaluate_delhi_rent_applicability,
)
from src.retrieval import HybridRetriever, RetrievalDocument, SearchFilters


def complete_facts(**updates: object) -> DelhiRentApplicabilityFacts:
    payload: dict[str, object] = {
        "incident_date": date(2026, 7, 13),
        "within_statutory_or_notified_area": True,
        "government_owned": False,
        "government_grant_tenancy": False,
        "monthly_rent": Decimal("3500"),
        "construction_completed_on": date(2000, 1, 1),
    }
    payload.update(updates)
    return DelhiRentApplicabilityFacts.model_validate(payload)


def test_complete_non_excluded_facts_approve_only_the_drc_profile() -> None:
    result = evaluate_delhi_rent_applicability(complete_facts())

    assert result.decision is ApplicabilityDecision.APPLICABLE
    assert result.approved_profiles == (DRC_PROFILE_ID,)
    assert result.missing_fields == ()
    assert result.source_id == "delhi_rent_control_act_1958_en"
    assert result.official_url.startswith("https://www.indiacode.nic.in/")


@pytest.mark.parametrize(
    ("updates", "section"),
    [
        ({"within_statutory_or_notified_area": False}, "1(2)"),
        ({"government_grant_tenancy": True}, "3(b)"),
        (
            {"government_owned": True, "government_authorized_private_letting": False},
            "3(a)",
        ),
        ({"monthly_rent": Decimal("3500.01")}, "3(c)"),
        (
            {
                "incident_date": date(2025, 1, 1),
                "construction_completed_on": date(2020, 1, 1),
            },
            "3(d)",
        ),
    ],
)
def test_each_express_exclusion_blocks_profile_approval(
    updates: dict[str, object], section: str
) -> None:
    result = evaluate_delhi_rent_applicability(complete_facts(**updates))

    assert result.decision is ApplicabilityDecision.NOT_APPLICABLE
    assert result.approved_profiles == ()
    assert result.cited_sections == (section,)


def test_unknown_material_facts_are_returned_for_confirmation() -> None:
    facts = DelhiRentApplicabilityFacts(incident_date=date(2026, 7, 13))
    result = evaluate_delhi_rent_applicability(facts)

    assert result.decision is ApplicabilityDecision.NEEDS_FACTS
    assert set(result.missing_fields) == {
        "within_statutory_or_notified_area",
        "government_grant_tenancy",
        "government_owned",
        "monthly_rent",
        "construction_completed_on",
    }
    assert result.approved_profiles == ()


def test_government_private_letting_proviso_requires_explicit_confirmation() -> None:
    result = evaluate_delhi_rent_applicability(
        complete_facts(government_owned=True, government_authorized_private_letting=None)
    )
    assert result.decision is ApplicabilityDecision.NEEDS_FACTS
    assert result.missing_fields == ("government_authorized_private_letting",)


def test_ten_year_exclusion_ends_on_anniversary_including_leap_day() -> None:
    before = evaluate_delhi_rent_applicability(
        complete_facts(
            incident_date=date(2028, 2, 27),
            construction_completed_on=date(2018, 2, 28),
        )
    )
    on_anniversary = evaluate_delhi_rent_applicability(
        complete_facts(
            incident_date=date(2028, 2, 28),
            construction_completed_on=date(2018, 2, 28),
        )
    )
    assert before.decision is ApplicabilityDecision.NOT_APPLICABLE
    assert on_anniversary.decision is ApplicabilityDecision.APPLICABLE


def test_commencement_boundary_is_enforced() -> None:
    before = evaluate_delhi_rent_applicability(
        complete_facts(
            incident_date=date(1959, 2, 8),
            construction_completed_on=date(1950, 1, 1),
        )
    )
    on_commencement = evaluate_delhi_rent_applicability(
        complete_facts(
            incident_date=date(1959, 2, 9),
            construction_completed_on=date(1950, 1, 1),
        )
    )
    assert before.decision is ApplicabilityDecision.NOT_APPLICABLE
    assert before.cited_sections == ("1(3)",)
    assert on_commencement.decision is ApplicabilityDecision.APPLICABLE


def test_pre_1988_incident_does_not_apply_later_rent_or_construction_exclusions() -> None:
    facts = DelhiRentApplicabilityFacts(
        incident_date=date(1980, 1, 1),
        within_statutory_or_notified_area=True,
        government_owned=False,
        government_grant_tenancy=False,
        monthly_rent=Decimal("4000"),
        construction_completed_on=date(1970, 1, 1),
    )
    result = evaluate_delhi_rent_applicability(facts)
    assert result.decision is ApplicabilityDecision.APPLICABLE
    assert "3(c)" not in result.cited_sections
    assert "3(d)" not in result.cited_sections

    minimal = DelhiRentApplicabilityFacts(
        incident_date=date(1980, 1, 1),
        within_statutory_or_notified_area=True,
        government_owned=False,
        government_grant_tenancy=False,
    )
    assert evaluate_delhi_rent_applicability(minimal).decision is ApplicabilityDecision.APPLICABLE


def test_strict_facts_reject_coerced_booleans_and_negative_rent() -> None:
    with pytest.raises(ValidationError):
        complete_facts(government_owned="false")
    with pytest.raises(ValidationError):
        complete_facts(monthly_rent=Decimal("-1"))
    with pytest.raises(ValidationError):
        complete_facts(
            government_owned=False,
            government_authorized_private_letting=True,
        )
    with pytest.raises(ValidationError):
        complete_facts(construction_completed_on=date(2027, 1, 1))
    with pytest.raises(ValidationError):
        complete_facts(
            government_owned=True,
            government_authorized_private_letting=True,
            government_grant_tenancy=True,
        )


def test_retrieval_excludes_profiled_law_until_profile_is_approved() -> None:
    restricted = RetrievalDocument(
        source_id="drc:3",
        text="Act not to apply to certain premises",
        metadata={"applicability_profile_id": DRC_PROFILE_ID},
    )
    unrestricted = RetrievalDocument(
        source_id="general:1",
        text="general premises information",
    )
    retriever = HybridRetriever([restricted, unrestricted])

    assert [result.source_id for result in retriever.search("premises")] == ["general:1"]
    approved = SearchFilters(applicability_profiles=frozenset({DRC_PROFILE_ID}))
    assert {result.source_id for result in retriever.search("premises", filters=approved)} == {
        "drc:3",
        "general:1",
    }


def test_profile_filter_contract_is_immutable_and_strict() -> None:
    with pytest.raises(TypeError):
        SearchFilters(applicability_profiles={DRC_PROFILE_ID})  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        SearchFilters(applicability_profiles=frozenset({""}))
    with pytest.raises(ValueError):
        SearchFilters(applicability_profiles=frozenset({"DRC"}))


def test_approved_profile_debug_trace_is_json_serializable_and_stable() -> None:
    retriever = HybridRetriever(
        [RetrievalDocument(source_id="drc:1", text="premises", metadata={})]
    )
    filters = SearchFilters(applicability_profiles=frozenset({DRC_PROFILE_ID}))
    trace = retriever.search_with_debug("premises", filters=filters).trace
    payload = json.dumps(dict(trace.active_filters), sort_keys=True)
    assert payload == (
        '{"applicability_profiles": ["delhi_rent_control_act_1958"]}'
    )


def test_malformed_document_profile_fails_closed_without_crashing() -> None:
    document = RetrievalDocument(
        source_id="malformed:1",
        text="premises",
        metadata={"applicability_profile_id": [DRC_PROFILE_ID]},
    )
    filters = SearchFilters(applicability_profiles=frozenset({DRC_PROFILE_ID}))
    assert filters.matches(document) is False

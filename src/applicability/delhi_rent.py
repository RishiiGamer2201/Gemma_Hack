"""Conservative Delhi Rent Control Act applicability gate.

The evaluator implements only the express extent and exclusions in sections 1(2)
and 3 of the official Act. It does not infer whether an address is in a notified
area and therefore requires that fact to be confirmed upstream.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StrictBool, model_validator

from src.models.schemas import StrictModel

DRC_PROFILE_ID = "delhi_rent_control_act_1958"
DRC_SOURCE_ID = "delhi_rent_control_act_1958_en"
DRC_OFFICIAL_URL = (
    "https://www.indiacode.nic.in/bitstream/123456789/19223/1/a1958-59.pdf"
)
DRC_COMMENCEMENT = date(1959, 2, 9)
AMENDMENT_1988_COMMENCEMENT = date(1988, 12, 1)
RENT_EXCLUSION_THRESHOLD = Decimal("3500")


class ApplicabilityDecision(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    NEEDS_FACTS = "needs_facts"


class DelhiRentApplicabilityFacts(StrictModel):
    """Confirmed premises facts; unknown values remain explicit ``None``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    incident_date: date
    within_statutory_or_notified_area: StrictBool | None = None
    government_owned: StrictBool | None = None
    government_grant_tenancy: StrictBool | None = None
    government_authorized_private_letting: StrictBool | None = None
    monthly_rent: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)] | None = None
    construction_completed_on: date | None = None

    @model_validator(mode="after")
    def facts_are_temporally_and_logically_consistent(self) -> DelhiRentApplicabilityFacts:
        if (
            self.government_owned is not True
            and self.government_authorized_private_letting is not None
        ):
            raise ValueError(
                "government_authorized_private_letting requires government_owned=true"
            )
        if (
            self.construction_completed_on is not None
            and self.construction_completed_on > self.incident_date
        ):
            raise ValueError("construction_completed_on cannot be after incident_date")
        if (
            self.government_grant_tenancy is True
            and self.government_owned is True
            and self.government_authorized_private_letting is True
        ):
            raise ValueError(
                "government grant and Government-owned private letting cannot both be asserted"
            )
        return self


class DelhiRentApplicabilityResult(StrictModel):
    decision: ApplicabilityDecision
    profile_id: Literal["delhi_rent_control_act_1958"] = DRC_PROFILE_ID
    source_id: Literal["delhi_rent_control_act_1958_en"] = DRC_SOURCE_ID
    official_url: Literal[
        "https://www.indiacode.nic.in/bitstream/123456789/19223/1/a1958-59.pdf"
    ] = DRC_OFFICIAL_URL
    approved_profiles: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    reasons: tuple[str, ...]
    cited_sections: tuple[str, ...]

    @model_validator(mode="after")
    def decision_controls_profile_approval(self) -> DelhiRentApplicabilityResult:
        if self.decision is ApplicabilityDecision.APPLICABLE:
            if self.approved_profiles != (DRC_PROFILE_ID,) or self.missing_fields:
                raise ValueError("applicable requires the DRC profile and no missing fields")
        elif self.approved_profiles:
            raise ValueError("only an applicable result may approve retrieval profiles")
        if self.decision is ApplicabilityDecision.NEEDS_FACTS and not self.missing_fields:
            raise ValueError("needs_facts requires at least one missing field")
        return self


def evaluate_delhi_rent_applicability(
    facts: DelhiRentApplicabilityFacts,
) -> DelhiRentApplicabilityResult:
    """Gate DRC retrieval using only confirmed facts and express statutory limits."""

    if not isinstance(facts, DelhiRentApplicabilityFacts):
        raise TypeError("facts must be DelhiRentApplicabilityFacts")
    if facts.incident_date < DRC_COMMENCEMENT:
        return _not_applicable(
            "The incident predates commencement of the Act on 9 February 1959.",
            "1(3)",
        )
    if facts.within_statutory_or_notified_area is False:
        return _not_applicable(
            "The premises are confirmed outside the Act's statutory/notified territorial extent.",
            "1(2)",
        )
    if facts.government_grant_tenancy is True:
        return _not_applicable(
            "The tenancy is confirmed as a Government grant covered by the statutory exclusion.",
            "3(b)",
        )
    if facts.government_owned is True and facts.government_authorized_private_letting is False:
        return _not_applicable(
            "The premises are Government-owned and the statutory private-letting "
            "proviso is not met.",
            "3(a)",
        )
    current_exclusions_apply = facts.incident_date >= AMENDMENT_1988_COMMENCEMENT
    if current_exclusions_apply:
        if facts.monthly_rent is not None and facts.monthly_rent > RENT_EXCLUSION_THRESHOLD:
            return _not_applicable(
                "The confirmed monthly rent exceeds ₹3,500.",
                "3(c)",
            )
        if (
            facts.construction_completed_on is not None
            and facts.construction_completed_on >= AMENDMENT_1988_COMMENCEMENT
            and facts.incident_date < _ten_year_anniversary(facts.construction_completed_on)
        ):
            return _not_applicable(
                "The incident falls within ten years after completion of qualifying "
                "post-1988 premises.",
                "3(d)",
            )

    missing: list[str] = []
    if facts.within_statutory_or_notified_area is None:
        missing.append("within_statutory_or_notified_area")
    if facts.government_grant_tenancy is None:
        missing.append("government_grant_tenancy")
    if facts.government_owned is None:
        missing.append("government_owned")
    elif facts.government_owned and facts.government_authorized_private_letting is None:
        missing.append("government_authorized_private_letting")
    if current_exclusions_apply:
        if facts.monthly_rent is None:
            missing.append("monthly_rent")
        if facts.construction_completed_on is None:
            missing.append("construction_completed_on")
    cited_sections = ["1(2)", "1(3)", "3(a)", "3(b)"]
    if current_exclusions_apply:
        cited_sections.extend(("3(c)", "3(d)"))
    if missing:
        return DelhiRentApplicabilityResult(
            decision=ApplicabilityDecision.NEEDS_FACTS,
            missing_fields=tuple(missing),
            reasons=(
                "Applicability cannot be asserted until the listed premises facts are confirmed.",
            ),
            cited_sections=tuple(cited_sections),
        )
    return DelhiRentApplicabilityResult(
        decision=ApplicabilityDecision.APPLICABLE,
        approved_profiles=(DRC_PROFILE_ID,),
        reasons=(
            "No express section 1(2) or section 3 exclusion is triggered by the confirmed facts.",
        ),
        cited_sections=tuple(cited_sections),
    )


def _not_applicable(reason: str, section: str) -> DelhiRentApplicabilityResult:
    return DelhiRentApplicabilityResult(
        decision=ApplicabilityDecision.NOT_APPLICABLE,
        reasons=(reason,),
        cited_sections=(section,),
    )


def _ten_year_anniversary(completed_on: date) -> date:
    try:
        return completed_on.replace(year=completed_on.year + 10)
    except ValueError:
        return completed_on.replace(year=completed_on.year + 10, day=28)

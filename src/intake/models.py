"""Strict contracts for local text intake before user confirmation."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from src.models import ConfirmedFacts, LegalDomain

ShortText = Annotated[str, Field(min_length=1, max_length=500)]
NarrativeText = Annotated[str, Field(min_length=1, max_length=20_000)]


class IntakeModel(BaseModel):
    """Reject unknown fields and avoid silently changing supplied strings."""

    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)


class DetectedLanguage(StrEnum):
    ENGLISH = "en"
    HINDI = "hi"
    HINGLISH = "hi-Latn-mixed"
    UNDETERMINED = "und"


class UrgencyCategory(StrEnum):
    ARREST_OR_DETENTION = "arrest_or_detention"
    VIOLENCE = "violence"
    IMMEDIATE_EVICTION = "immediate_eviction"
    EXPIRING_DEADLINE = "expiring_deadline"
    CHILD_SAFETY = "child_safety"
    SELF_HARM = "self_harm"
    MEDICAL_EMERGENCY = "medical_emergency"


class LanguageAssessment(IntakeModel):
    language: DetectedLanguage
    devanagari_letters: Annotated[int, Field(ge=0)]
    latin_letters: Annotated[int, Field(ge=0)]
    romanized_hindi_markers: Annotated[int, Field(ge=0)] = 0
    method: Literal["unicode_script_heuristic"] = "unicode_script_heuristic"


class UrgencySignal(IntakeModel):
    category: UrgencyCategory
    matched_phrase: ShortText
    requires_user_confirmation: Literal[True] = True


class IntakeFacts(IntakeModel):
    """User-supplied structured fields; no field is treated as confirmed."""

    incident_summary: NarrativeText
    incident_date: date | None = None
    jurisdiction: ShortText | None = None
    location: ShortText | None = None
    domain: LegalDomain = LegalDomain.OTHER
    parties: tuple[ShortText, ...] = ()
    material_facts: tuple[NarrativeText, ...] = ()
    documents: tuple[ShortText, ...] = ()
    missing_material_facts: tuple[ShortText, ...] = ()

    @model_validator(mode="after")
    def repeated_values_are_unique(self) -> IntakeFacts:
        scalar_values = (self.incident_summary, self.jurisdiction, self.location)
        if any(value is not None and not value.strip() for value in scalar_values):
            raise ValueError("structured text fields must not be blank")
        for field_name in ("parties", "material_facts", "documents", "missing_material_facts"):
            values = getattr(self, field_name)
            if any(not value.strip() for value in values):
                raise ValueError(f"{field_name} must not contain blank values")
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicate values")
        return self


class TextIntakeResult(IntakeModel):
    normalized_text: NarrativeText
    language: LanguageAssessment
    facts: IntakeFacts
    urgency_signals: tuple[UrgencySignal, ...] = ()
    restatement: NarrativeText
    requires_confirmation: Literal[True] = True
    confirmed: Annotated[StrictBool, Field(default=False)] = False

    @model_validator(mode="after")
    def result_cannot_arrive_confirmed(self) -> TextIntakeResult:
        if self.confirmed:
            raise ValueError("text intake must be confirmed explicitly by the user")
        return self

    def to_unconfirmed_facts(self) -> ConfirmedFacts:
        """Convert to the existing workflow contract without opening its gate."""

        return ConfirmedFacts(
            incident_summary=self.facts.incident_summary,
            incident_date=self.facts.incident_date,
            jurisdiction=self.facts.jurisdiction,
            location=self.facts.location,
            domain=self.facts.domain,
            parties=self.facts.parties,
            material_facts=self.facts.material_facts,
            missing_material_facts=self.facts.missing_material_facts,
            input_language=self.language.language.value,
            confirmed=False,
            confirmed_at=None,
        )

"""Strict output contracts for deterministic safety and power routing."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from src.intake import UrgencyCategory
from src.models import LegalDomain


ShortText = Annotated[str, Field(min_length=1, max_length=500)]


class SafetyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class RoutePriority(StrEnum):
    IMMEDIATE_HUMAN_HELP = "immediate_human_help"
    HARD_ABSTAIN = "hard_abstain"
    NEEDS_INFORMATION = "needs_information"
    STANDARD = "standard"


class PowerRelationship(StrEnum):
    POLICE_CITIZEN = "police_citizen"
    EMPLOYER_WORKER = "employer_worker"
    LANDLORD_TENANT = "landlord_tenant"
    ABUSER_SURVIVOR = "abuser_survivor"


class RoleSignal(SafetyModel):
    relationship: PowerRelationship
    matched_role_terms: Annotated[tuple[ShortText, ...], Field(min_length=2, max_length=6)]
    label: Literal["possible_role_pattern"] = "possible_role_pattern"


class MissingFactQuestion(SafetyModel):
    fact_key: Annotated[str, Field(pattern=r"^[a-z_]+$", max_length=80)]
    question: ShortText
    reason: ShortText


class DocumentSafetyWarning(SafetyModel):
    warning_code: Literal["embedded_instruction_pattern"] = "embedded_instruction_pattern"
    pattern_name: ShortText
    instruction_ignored: Literal[True] = True


class SafetyRouteDecision(SafetyModel):
    facts_fingerprint: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    priority: RoutePriority
    domain: LegalDomain
    jurisdiction: ShortText | None = None
    incident_date: date | None = None
    confirmed_urgencies: tuple[UrgencyCategory, ...] = ()
    role_signals: tuple[RoleSignal, ...] = ()
    protective_prompts: tuple[ShortText, ...] = ()
    missing_questions: tuple[MissingFactQuestion, ...] = ()
    document_warnings: tuple[DocumentSafetyWarning, ...] = ()
    general_explanation_allowed: StrictBool
    human_help_required: StrictBool
    terminal_reason: ShortText | None = None

    @model_validator(mode="after")
    def priority_flags_are_consistent(self) -> "SafetyRouteDecision":
        if len(self.confirmed_urgencies) != len(set(self.confirmed_urgencies)):
            raise ValueError("confirmed_urgencies must be unique")
        if self.priority is RoutePriority.IMMEDIATE_HUMAN_HELP:
            if (
                not self.confirmed_urgencies
                or not self.human_help_required
                or self.general_explanation_allowed
                or self.missing_questions
                or self.terminal_reason is None
            ):
                raise ValueError("immediate routes must require human help before explanation")
        elif self.priority is RoutePriority.STANDARD:
            if (
                self.confirmed_urgencies
                or self.human_help_required
                or not self.general_explanation_allowed
                or self.missing_questions
                or self.terminal_reason is not None
            ):
                raise ValueError("standard routes must permit general explanation")
        elif self.priority is RoutePriority.NEEDS_INFORMATION:
            if (
                self.confirmed_urgencies
                or self.human_help_required
                or self.general_explanation_allowed
                or not self.missing_questions
                or self.terminal_reason is not None
            ):
                raise ValueError("needs-information routes require only material questions")
        elif (
            self.confirmed_urgencies
            or self.human_help_required
            or self.general_explanation_allowed
            or self.missing_questions
            or self.terminal_reason is None
        ):
            raise ValueError("hard abstention requires a reason and cannot advance")
        return self

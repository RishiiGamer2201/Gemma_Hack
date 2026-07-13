"""Pydantic contracts passed between deterministic workflow components.

The models deliberately keep confirmed user facts separate from generated legal
claims.  This prevents model output from silently becoming an input fact and makes
the confirmation and citation-verification gates auditable.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    model_validator,
)

NonEmptyText = Annotated[str, Field(min_length=1, max_length=20_000)]
ShortText = Annotated[str, Field(min_length=1, max_length=500)]


class StrictModel(BaseModel):
    """Base contract that rejects unexpected fields and normalizes strings."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        use_enum_values=False,
    )


class LegalDomain(StrEnum):
    """Top-level routing labels supported by the first implementation."""

    CRIMINAL = "criminal"
    LABOUR = "labour"
    CONSUMER = "consumer"
    TENANCY_PROPERTY = "tenancy_property"
    CONSTITUTIONAL = "constitutional"
    OTHER = "other"


class WorkflowStage(StrEnum):
    """Deterministic stages of a single, in-memory legal-information request."""

    INTAKE = "intake"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    SAFETY_ROUTED = "safety_routed"
    RETRIEVAL_READY = "retrieval_ready"
    RETRIEVING = "retrieving"
    EVIDENCE_READY = "evidence_ready"
    DRAFTING = "drafting"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    PUBLISHED = "published"
    ABSTAINED = "abstained"


class ConfirmedFacts(StrictModel):
    """User-controlled facts extracted from an intake message or document.

    ``confirmed`` must be explicitly set after the user has seen and corrected the
    restatement.  Merely constructing this model does not authorize retrieval.
    """

    incident_summary: NonEmptyText
    incident_date: date | None = None
    jurisdiction: ShortText | None = None
    location: ShortText | None = None
    domain: LegalDomain = LegalDomain.OTHER
    parties: tuple[ShortText, ...] = ()
    material_facts: tuple[NonEmptyText, ...] = ()
    missing_material_facts: tuple[ShortText, ...] = ()
    input_language: Annotated[str, Field(min_length=2, max_length=35)] = "en"
    confirmed: StrictBool = False
    confirmed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def confirmation_is_explicit_and_consistent(self) -> ConfirmedFacts:
        if self.confirmed != (self.confirmed_at is not None):
            raise ValueError(
                "confirmed and confirmed_at must be set together after explicit user confirmation"
            )
        return self


class SourceEvidence(StrictModel):
    """A retrieved excerpt with enough provenance for claim-level verification."""

    source_id: Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.:-]+$")]
    jurisdiction: ShortText
    act: ShortText
    section: ShortText | None = None
    heading: ShortText | None = None
    language: Annotated[str, Field(min_length=2, max_length=35)] = "en"
    excerpt: NonEmptyText
    effective_from: date | None = None
    effective_to: date | None = None
    status: Annotated[str, Field(min_length=1, max_length=50)] = "in_force"
    priority: Annotated[int, Field(ge=1, le=10)] = 3
    official_url: HttpUrl
    page: Annotated[int, Field(ge=1)] | None = None
    retrieved_at: datetime
    sha256: Annotated[str, Field(pattern=r"^[a-fA-F0-9]{64}$")]
    ocr_used: bool = False

    @model_validator(mode="after")
    def effective_range_is_ordered(self) -> SourceEvidence:
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValueError("effective_to cannot be earlier than effective_from")
        return self


class ClaimVerdict(StrEnum):
    """Allowed verifier outcomes for a generated legal claim."""

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT = "insufficient"


class LegalClaim(StrictModel):
    """A separately verifiable assertion in a generated answer."""

    claim_id: Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")]
    text: NonEmptyText
    cited_source_ids: Annotated[tuple[str, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def citation_ids_are_unique(self) -> LegalClaim:
        if len(self.cited_source_ids) != len(set(self.cited_source_ids)):
            raise ValueError("cited_source_ids must be unique within a claim")
        return self


class ClaimVerification(StrictModel):
    """Verifier decision and the exact evidence used for one legal claim."""

    claim_id: Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")]
    verdict: ClaimVerdict
    evidence_source_ids: tuple[str, ...] = ()
    reason: NonEmptyText

    @model_validator(mode="after")
    def supported_claim_has_evidence(self) -> ClaimVerification:
        if self.verdict is ClaimVerdict.SUPPORTED and not self.evidence_source_ids:
            raise ValueError("a supported claim must reference at least one evidence source")
        return self


class StructuredLegalAnswer(StrictModel):
    """Complete answer draft; it is not publishable until externally verified."""

    situation: NonEmptyText
    applicable_law: tuple[NonEmptyText, ...]
    rights: tuple[NonEmptyText, ...]
    options: tuple[NonEmptyText, ...]
    evidence_to_preserve: tuple[NonEmptyText, ...]
    deadlines: tuple[NonEmptyText, ...]
    consequences_of_inaction: tuple[NonEmptyText, ...]
    next_steps: tuple[NonEmptyText, ...]
    limitations: tuple[NonEmptyText, ...]
    claims: Annotated[tuple[LegalClaim, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def claim_ids_are_unique(self) -> StructuredLegalAnswer:
        ids = [claim.claim_id for claim in self.claims]
        if len(ids) != len(set(ids)):
            raise ValueError("claim_id values must be unique within an answer")
        return self

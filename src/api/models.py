"""Request and response contracts for the loopback API.

The DTOs wrap the existing reviewed models rather than restating them. No DTO
introduces a legal field, a deadline, or a citation that a reviewed module did not
already produce.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.actions.checklists import ChecklistTemplate
from src.agents.researcher import MAX_EVIDENCE
from src.applicability.delhi_rent import DelhiRentApplicabilityFacts
from src.intake import LanguageAssessment, UrgencyCategory, UrgencySignal
from src.intake.models import IntakeFacts
from src.legal_time.mapping import MappingLookupResult
from src.models.schemas import (
    ClaimVerdict,
    ConfirmedFacts,
    LegalDomain,
    SourceEvidence,
    StructuredLegalAnswer,
)
from src.safety.models import SafetyRouteDecision

ShortText = Annotated[str, Field(min_length=1, max_length=500)]
NarrativeText = Annotated[str, Field(min_length=1, max_length=20_000)]


class ApiModel(BaseModel):
    """Reject unknown request fields; a typo must not be silently ignored."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False)


# --------------------------------------------------------------------------- errors


class ErrorResponse(ApiModel):
    """The single error envelope returned for every 4xx/5xx response."""

    code: str
    message: str
    field: str | None = None


# --------------------------------------------------------------------------- health


class HealthResponse(ApiModel):
    corpus_loaded: bool
    chunk_count: int
    corpus_sha256: str | None = None
    corpus_error: str | None = None
    ollama_reachable: bool
    model: str


# --------------------------------------------------------------------------- intake


class IntakeRequest(ApiModel):
    """Free text plus any structured fields the user typed themselves."""

    text: NarrativeText
    incident_date: date | None = None
    jurisdiction: ShortText | None = None
    location: ShortText | None = None
    domain: LegalDomain = LegalDomain.OTHER
    parties: tuple[ShortText, ...] = ()
    material_facts: tuple[NarrativeText, ...] = ()
    documents: tuple[ShortText, ...] = ()
    missing_material_facts: tuple[ShortText, ...] = ()
    # Turn the free-form account into typed fields with the local model. Anything the
    # user typed themselves always wins. Best-effort: a missing model degrades to the
    # deterministic path rather than failing.
    extract: bool = True


class IntakeResponse(ApiModel):
    """An unconfirmed restatement. It never authorizes retrieval by itself."""

    normalized_text: str
    language: LanguageAssessment
    urgency_signals: tuple[UrgencySignal, ...]
    restatement: str
    facts: IntakeFacts
    unconfirmed_facts: ConfirmedFacts
    extracted: bool = False
    extraction_failed: bool = False
    requires_confirmation: Literal[True] = True
    confirmed: Literal[False] = False


# --------------------------------------------------------------------------- routing


class RouteRequest(ApiModel):
    facts: ConfirmedFacts
    confirmed_urgencies: tuple[UrgencyCategory, ...] = ()
    requested_output: NarrativeText | None = None
    untrusted_document_texts: tuple[NarrativeText, ...] = ()


# --------------------------------------------------------------------------- evidence


class EvidenceRequest(ApiModel):
    facts: ConfirmedFacts
    approved_profiles: tuple[Annotated[str, Field(pattern=r"^[a-z0-9_]+$")], ...] = ()
    limit: Annotated[int, Field(ge=1, le=MAX_EVIDENCE)] = 6
    include_undated_sources: bool = True


class RetrievalTraceSummary(ApiModel):
    """Enough of the retrieval trace to explain a result without leaking internals."""

    original_terms: tuple[str, ...]
    expanded_terms: tuple[str, ...]
    active_filters: dict[str, Any]
    corpus_sha256: str
    candidate_count: int
    excluded_count: int
    deduplicated_count: int
    retriever_config: dict[str, Any]


class EvidenceResponse(ApiModel):
    query: str
    evidence: tuple[SourceEvidence, ...]
    # Verbatim module warnings, including "commencement not verified" notices.
    # The client must display every entry.
    warnings: tuple[str, ...]
    undated_source_ids: tuple[str, ...]
    trace: RetrievalTraceSummary


# --------------------------------------------------------------------------- answer


class AnswerRequest(ApiModel):
    facts: ConfirmedFacts
    approved_profiles: tuple[Annotated[str, Field(pattern=r"^[a-z0-9_]+$")], ...] = ()
    confirmed_urgencies: tuple[UrgencyCategory, ...] = ()
    untrusted_document_texts: tuple[str, ...] = ()
    requested_output: str | None = None
    limit: Annotated[int, Field(ge=1, le=MAX_EVIDENCE)] = 6
    # The explanation is written in this language. The official excerpts are never
    # translated: a translated statute is no longer the statute.
    output_language: Literal["en", "hi"] = "en"
    # Changes how much is said, never what may be said: both levels draw on the
    # same excerpts and both are verified claim by claim.
    detail_level: Literal["simple", "detailed"] = "simple"


class ClaimView(ApiModel):
    """A claim paired with the verdict an independent verifier gave it."""

    claim_id: str
    text: str
    cited_source_ids: tuple[str, ...]
    verdict: ClaimVerdict
    verdict_reason: str
    evidence_source_ids: tuple[str, ...]


class AnswerResponse(ApiModel):
    """The result of the full journey.

    ``published`` is the only field that authorises showing legal content. When it
    is false the answer was withheld on purpose -- because the case needs a human,
    because the request was refused, or because a claim could not be supported --
    and the client must render the route and warnings instead.
    """

    stage: str
    published: bool
    route: SafetyRouteDecision
    answer: StructuredLegalAnswer | None = None
    claims: tuple[ClaimView, ...] = ()
    evidence: tuple[SourceEvidence, ...] = ()
    warnings: tuple[str, ...] = ()
    query: str | None = None


class DevilsAdvocateRequest(ApiModel):
    """Stress-test a case. The pipeline must publish a verified answer first."""

    facts: ConfirmedFacts
    approved_profiles: tuple[Annotated[str, Field(pattern=r"^[a-z0-9_]+$")], ...] = ()
    limit: Annotated[int, Field(ge=1, le=MAX_EVIDENCE)] = 4


class RightsCardRequest(ApiModel):
    """Render a shareable card from a case that produced a verified answer."""

    facts: ConfirmedFacts
    approved_profiles: tuple[Annotated[str, Field(pattern=r"^[a-z0-9_]+$")], ...] = ()
    legal_aid_district: str | None = None
    legal_aid_state: str | None = None
    limit: Annotated[int, Field(ge=1, le=MAX_EVIDENCE)] = 4


class CommunityRequest(ApiModel):
    """Build a third-person intermediary brief from a published answer."""

    facts: ConfirmedFacts
    approved_profiles: tuple[Annotated[str, Field(pattern=r"^[a-z0-9_]+$")], ...] = ()
    include_sensitive: bool = False
    limit: Annotated[int, Field(ge=1, le=MAX_EVIDENCE)] = 4


class OcrApiResponse(ApiModel):
    """OCR text plus the injection scan. Wraps the reviewed OCRResult.

    OCRResult is a reviewed module contract and forbids extra fields, so the safety
    scan is attached here rather than by mutating it.
    """

    text: str
    width: int
    height: int
    image_format: str
    language: str
    mean_confidence_percent: float | None = None
    engine: str = "tesseract"
    tesseract_version: str
    processing_seconds: float
    # An uploaded document is untrusted data. Instruction-like text inside it is
    # reported and ignored; it can never steer the assistant.
    injection_warnings: tuple[str, ...] = ()


class ConsequenceRequest(ApiModel):
    """What happens if I do nothing. Confirmed facts only."""

    facts: ConfirmedFacts
    approved_profiles: tuple[Annotated[str, Field(pattern=r"^[a-z0-9_]+$")], ...] = ()
    limit: Annotated[int, Field(ge=1, le=MAX_EVIDENCE)] = 4


class ConsequenceView(ApiModel):
    deadline_id: str
    title: str
    runs_from: str
    period: str
    due_on: date | None = None
    days_remaining: int | None = None
    expired: bool
    consequence: str
    # "statutory" is what the law says. "practical" is a risk that depends on facts.
    # They must never be blended into one confident sentence.
    consequence_kind: str
    depends_on: tuple[str, ...] = ()
    citation: str
    source_id: str
    official_url: str | None = None
    quote: str
    unverified_commencement: bool
    review_status: str


class ConsequenceResponse(ApiModel):
    consequences: tuple[ConsequenceView, ...] = ()
    questions: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    sources_are_silent: bool


class RightView(ApiModel):
    right_id: str
    statement: str
    what_you_can_do: str | None = None
    citation: str
    source_id: str
    official_url: str | None = None
    quote: str
    review_status: str


class RightsResponse(ApiModel):
    domain: LegalDomain
    rights: tuple[RightView, ...] = ()
    notes: tuple[str, ...] = ()


class PdfResponse(ApiModel):
    """Text lifted from an uploaded PDF. A DRAFT for the user to correct."""

    text: str
    page_count: int
    pages_with_text: int
    scanned_pages: tuple[int, ...]
    truncated: bool
    # Pages read by OCR from an embedded scan rather than a text layer. OCR misreads
    # dates and section numbers, and those change the legal answer, so the user must
    # be told which pages were guessed at.
    ocr_pages: tuple[int, ...] = ()
    # An uploaded document is untrusted data. Instruction-like text inside it is
    # reported and ignored; it can never steer the assistant.
    injection_warnings: tuple[str, ...] = ()


class CommunityResponse(ApiModel):
    heading: str
    what_help_is_needed: str
    situation: str
    rights: tuple[str, ...]
    next_steps: tuple[str, ...]
    citations: tuple[str, ...]
    caveats: tuple[str, ...]
    text: str


# -------------------------------------------------------------------------- legal aid


class LegalAidRequest(ApiModel):
    district_or_city: ShortText
    state: ShortText | None = None


# ------------------------------------------------------------------------- checklists


class ChecklistSummary(ApiModel):
    template_id: str
    title: str
    scenario: str
    domain: str


class ChecklistListResponse(ApiModel):
    templates: tuple[ChecklistSummary, ...]

    @classmethod
    def from_templates(cls, templates: tuple[ChecklistTemplate, ...]) -> ChecklistListResponse:
        return cls(
            templates=tuple(
                ChecklistSummary(
                    template_id=template.template_id,
                    title=template.title,
                    scenario=template.scenario,
                    domain=template.domain,
                )
                for template in templates
            )
        )


# ---------------------------------------------------------------------------- mapping


class MappingRequest(ApiModel):
    query: ShortText
    incident_date: date | None = None


class MappingResponse(ApiModel):
    """A date-routed IPC/BNS lookup over APPROVED mappings only."""

    result: MappingLookupResult
    # Which code governs, once the incident date is known: "IPC", "BNS", or null.
    governing_code: str | None = None
    # Approved BNS sections whose text this build actually holds.
    grounded_bns_sections: tuple[str, ...] = ()
    questions: tuple[str, ...] = ()
    warnings: tuple[str, ...]
    curated_mapping_count: int


# ---------------------------------------------------------------------- applicability


class DelhiRentRequest(ApiModel):
    facts: DelhiRentApplicabilityFacts

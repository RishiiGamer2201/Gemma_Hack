"""Loopback-only FastAPI application over the reviewed offline modules.

Design rules enforced here:

* The confirmation gate is never bypassed. ``/api/intake`` returns an unconfirmed
  restatement; every legal endpoint refuses facts that are not explicitly confirmed.
* Nothing from a request is written to disk. Uploads are held in memory only.
* Warnings produced by the reviewed modules are propagated verbatim.
* Errors become a structured ``{code, message, field}`` envelope, never a traceback.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import ValidationError
from starlette.formparsers import MultiPartParser

from src.actions.checklists import ChecklistError, ChecklistTemplate
from src.agents.devils_advocate import DevilsAdvocateError, run_devils_advocate_stream
from src.agents.ollama import OllamaError
from src.agents.researcher import ResearchError, retrieve_evidence
from src.applicability.delhi_rent import (
    DelhiRentApplicabilityResult,
    evaluate_delhi_rent_applicability,
)
from src.audio.asr import transcribe_audio
from src.audio.models import (
    MAX_AUDIO_BYTES,
    ASRConfig,
    ASRError,
    ASRErrorCode,
    LanguageHint,
    TranscriptionResult,
)
from src.intake import process_text_intake
from src.legal_aid.finder import LegalAidFinderError, LegalAidSearchResult
from src.legal_time.mapping import MappingLookupResult
from src.models.schemas import ConfirmedFacts
from src.ocr import MAX_IMAGE_BYTES, OCRError, OCRErrorCode, OCRResult, extract_image_bytes
from src.pipeline import PipelineError, run_confirmed_request
from src.retrieval import CorpusLoadError
from src.retrieval.collections import CollectionError
from src.safety import SafetyRouteDecision, route_confirmed_case
from src.tools.community import build_community_explanation
from src.tools.rights_card import RightsCardContent, RightsCardError, render_rights_card
from src.workflow import WorkflowError

from .models import (
    AnswerRequest,
    AnswerResponse,
    ChecklistListResponse,
    ClaimView,
    CommunityRequest,
    CommunityResponse,
    DelhiRentRequest,
    DevilsAdvocateRequest,
    ErrorResponse,
    EvidenceRequest,
    EvidenceResponse,
    HealthResponse,
    IntakeRequest,
    IntakeResponse,
    LegalAidRequest,
    MappingRequest,
    MappingResponse,
    RetrievalTraceSummary,
    RightsCardRequest,
    RouteRequest,
)
from .state import NO_REVIEWED_MAPPING_WARNING, ApiState, StateError, build_state

# The React client runs from a local dev server. Loopback origins only: a wildcard
# would let any page in the browser reach a service holding the user's case facts.
ALLOWED_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]

# Multipart parts must stay in RAM. Starlette spools a part larger than
# ``spool_max_size`` to a temporary file on disk, which would persist an uploaded
# document. Raising the spool bound above the OCR image limit keeps every upload
# in memory for its whole lifetime.
MAX_UPLOAD_BYTES = MAX_IMAGE_BYTES
MultiPartParser.spool_max_size = MAX_UPLOAD_BYTES + 1
MultiPartParser.max_part_size = MAX_UPLOAD_BYTES + 1

_OCR_STATUS: dict[OCRErrorCode, int] = {
    OCRErrorCode.INVALID_REQUEST: 400,
    OCRErrorCode.IMAGE_NOT_FOUND: 400,
    OCRErrorCode.UNSUPPORTED_FORMAT: 415,
    OCRErrorCode.INVALID_IMAGE: 400,
    OCRErrorCode.IMAGE_LIMIT_EXCEEDED: 413,
    OCRErrorCode.OUTPUT_LIMIT_EXCEEDED: 413,
    OCRErrorCode.PILLOW_UNAVAILABLE: 503,
    OCRErrorCode.TESSERACT_UNAVAILABLE: 503,
    OCRErrorCode.TESSERACT_VERSION_MISMATCH: 503,
    OCRErrorCode.TESSERACT_INTEGRITY_FAILED: 503,
    OCRErrorCode.TESSDATA_INTEGRITY_FAILED: 503,
    OCRErrorCode.OCR_TIMEOUT: 504,
    OCRErrorCode.OCR_FAILED: 500,
    OCRErrorCode.INTERNAL_ERROR: 500,
}

_ASR_STATUS: dict[ASRErrorCode, int] = {
    ASRErrorCode.INVALID_REQUEST: 400,
    ASRErrorCode.AUDIO_NOT_FOUND: 400,
    ASRErrorCode.UNSUPPORTED_FORMAT: 415,
    ASRErrorCode.AUDIO_LIMIT_EXCEEDED: 413,
    ASRErrorCode.INVALID_AUDIO: 400,
    ASRErrorCode.MODEL_NOT_FOUND: 503,
    ASRErrorCode.MODEL_INTEGRITY_FAILED: 503,
    ASRErrorCode.BACKEND_UNAVAILABLE: 503,
    ASRErrorCode.INFERENCE_FAILED: 500,
    ASRErrorCode.OUTPUT_LIMIT_EXCEEDED: 413,
    ASRErrorCode.INTERNAL_ERROR: 500,
}

_STATE_STATUS: dict[str, int] = {
    "corpus_unavailable": 503,
    "domain_not_routed": 422,
    "directory_unreadable": 503,
    "checklists_unavailable": 503,
}

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


class ApiError(Exception):
    """A deliberate, user-safe API failure with an explicit status."""

    def __init__(self, status: int, code: str, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.field = field


def _error(status: int, code: str, message: str, field: str | None = None) -> JSONResponse:
    payload = ErrorResponse(code=code, message=message, field=field)
    return JSONResponse(status_code=status, content=payload.model_dump(mode="json"))


def _require_confirmed(facts: ConfirmedFacts) -> None:
    """The hard gate: no personalized legal output before explicit confirmation."""

    if not facts.confirmed or facts.confirmed_at is None:
        raise ApiError(
            409,
            "facts_not_confirmed",
            "The user must review and explicitly confirm the restated facts before any "
            "legal retrieval or routing. Send facts with confirmed=true and confirmed_at "
            "set to the confirmation timestamp.",
            field="facts.confirmed",
        )


def _first_field(exc: ValidationError) -> str | None:
    errors = exc.errors()
    if not errors:
        return None
    location = [str(part) for part in errors[0].get("loc", ())]
    return ".".join(location) or None


def create_app(state: ApiState | None = None) -> FastAPI:
    """Build the local application. Corpus loading happens once, at startup."""

    app_state = state if state is not None else build_state()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # A missing corpus must degrade the service, not prevent it from starting.
        app_state.load_corpus()
        yield

    app = FastAPI(
        title="Nyaya Navigator local API",
        version="0.1.0",
        summary="Offline legal-navigation API. Loopback only; no request content is stored.",
        lifespan=lifespan,
    )
    app.state.api = app_state

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
        max_age=600,
    )

    _register_error_handlers(app)
    _register_routes(app, app_state)
    return app


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status, exc.code, exc.message, exc.field)

    @app.exception_handler(OCRError)
    async def _handle_ocr_error(_: Request, exc: OCRError) -> JSONResponse:
        detail = exc.detail
        status = _OCR_STATUS.get(detail.code, 500)
        return _error(status, detail.code.value, detail.message, detail.field)

    @app.exception_handler(StateError)
    async def _handle_state_error(_: Request, exc: StateError) -> JSONResponse:
        return _error(_STATE_STATUS.get(exc.code, 500), exc.code, str(exc))

    @app.exception_handler(LegalAidFinderError)
    async def _handle_legal_aid_error(_: Request, exc: LegalAidFinderError) -> JSONResponse:
        status = 400 if exc.code == "invalid_query" else 503
        return _error(status, exc.code, str(exc))

    @app.exception_handler(ChecklistError)
    async def _handle_checklist_error(_: Request, exc: ChecklistError) -> JSONResponse:
        message = str(exc)
        status = 404 if message.startswith("unknown checklist template_id") else 503
        return _error(status, "checklist_error", message)

    @app.exception_handler(WorkflowError)
    async def _handle_workflow_error(_: Request, exc: WorkflowError) -> JSONResponse:
        return _error(409, "workflow_error", str(exc))

    @app.exception_handler(ResearchError)
    async def _handle_research_error(_: Request, exc: ResearchError) -> JSONResponse:
        return _error(422, "research_error", str(exc))

    @app.exception_handler(CollectionError)
    async def _handle_collection_error(_: Request, exc: CollectionError) -> JSONResponse:
        return _error(422, "domain_not_routed", str(exc))

    @app.exception_handler(CorpusLoadError)
    async def _handle_corpus_error(_: Request, exc: CorpusLoadError) -> JSONResponse:
        return _error(503, "corpus_unavailable", str(exc))

    @app.exception_handler(ValidationError)
    async def _handle_validation_error(_: Request, exc: ValidationError) -> JSONResponse:
        return _error(422, "validation_error", "the request payload is invalid", _first_field(exc))

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        field = ".".join(str(part) for part in errors[0].get("loc", ())) if errors else None
        message = errors[0].get("msg", "invalid request") if errors else "invalid request"
        return _error(422, "validation_error", str(message), field or None)

    @app.exception_handler(ValueError)
    async def _handle_value_error(_: Request, exc: ValueError) -> JSONResponse:
        return _error(400, "invalid_request", str(exc))


def _card_title(facts: ConfirmedFacts) -> str:
    """A short, factual card title taken from the user's own words.

    The title is drawn from the confirmed incident summary, never from generated
    text, so the card header cannot assert something the answer did not.
    """

    summary = facts.incident_summary.strip().splitlines()[0]
    return summary[:80] + ("…" if len(summary) > 80 else "")


def _register_routes(app: FastAPI, state: ApiState) -> None:
    @app.get("/api/health", response_model=HealthResponse, tags=["status"])
    async def health() -> HealthResponse:
        return HealthResponse(
            corpus_loaded=state.corpus_loaded,
            chunk_count=state.chunk_count,
            corpus_sha256=state.corpus_sha256,
            corpus_error=state.corpus_error,
            ollama_reachable=state.ollama_reachable(),
            model=state.settings.ollama_model,
        )

    @app.post(
        "/api/intake",
        response_model=IntakeResponse,
        responses=_ERROR_RESPONSES,
        tags=["intake"],
    )
    async def intake(payload: IntakeRequest) -> IntakeResponse:
        """Return an UNCONFIRMED restatement. This does not open the retrieval gate."""

        result = process_text_intake(
            payload.text,
            incident_date=payload.incident_date,
            jurisdiction=payload.jurisdiction,
            location=payload.location,
            domain=payload.domain,
            parties=payload.parties,
            material_facts=payload.material_facts,
            documents=payload.documents,
            missing_material_facts=payload.missing_material_facts,
        )
        return IntakeResponse(
            normalized_text=result.normalized_text,
            language=result.language,
            urgency_signals=result.urgency_signals,
            restatement=result.restatement,
            facts=result.facts,
            unconfirmed_facts=result.to_unconfirmed_facts(),
        )

    @app.post(
        "/api/route",
        response_model=SafetyRouteDecision,
        responses=_ERROR_RESPONSES,
        tags=["safety"],
    )
    async def route(payload: RouteRequest) -> SafetyRouteDecision:
        _require_confirmed(payload.facts)
        return route_confirmed_case(
            payload.facts,
            confirmed_urgencies=payload.confirmed_urgencies,
            untrusted_document_texts=payload.untrusted_document_texts,
            requested_output=payload.requested_output,
        )

    @app.post(
        "/api/evidence",
        response_model=EvidenceResponse,
        responses=_ERROR_RESPONSES,
        tags=["evidence"],
    )
    async def evidence(payload: EvidenceRequest) -> EvidenceResponse:
        _require_confirmed(payload.facts)
        documents = state.documents_for_domain(payload.facts.domain)
        bundle = retrieve_evidence(
            payload.facts,
            documents,
            approved_profiles=frozenset(payload.approved_profiles),
            limit=payload.limit,
            include_undated_sources=payload.include_undated_sources,
            embedding_callback=state.embedding_callback(),
        )
        trace = bundle.trace
        return EvidenceResponse(
            query=bundle.query,
            evidence=bundle.evidence,
            # Verbatim: these carry the "commencement not verified" notice.
            warnings=bundle.warnings,
            undated_source_ids=tuple(item.source_id for item in bundle.undated_evidence),
            trace=RetrievalTraceSummary(
                original_terms=trace.original_terms,
                expanded_terms=trace.expanded_terms,
                active_filters=dict(trace.active_filters),
                corpus_sha256=trace.corpus_sha256,
                candidate_count=len(trace.channel_candidates),
                excluded_count=len(trace.exclusions),
                deduplicated_count=len(trace.deduplications),
                retriever_config=dict(trace.retriever_config),
            ),
        )

    @app.post(
        "/api/answer",
        response_model=AnswerResponse,
        responses=_ERROR_RESPONSES,
        tags=["answer"],
    )
    async def answer(payload: AnswerRequest) -> AnswerResponse:
        """Run the full journey. Every gate lives in the pipeline, not here.

        This endpoint deliberately contains no safety logic of its own. It adapts a
        PipelineResult to JSON; the confirmation gate, urgency routing, refusal,
        abstention, and claim verification are all enforced upstream, so there is no
        path through this handler that can publish an unverified answer.
        """

        _require_confirmed(payload.facts)
        documents = state.documents_for_domain(payload.facts.domain)
        try:
            result = run_confirmed_request(
                payload.facts,
                documents,
                client=state.model_client(),
                model=state.settings.ollama_model,
                confirmed_urgencies=payload.confirmed_urgencies,
                untrusted_document_texts=payload.untrusted_document_texts,
                requested_output=payload.requested_output,
                approved_profiles=frozenset(payload.approved_profiles),
                evidence_limit=payload.limit,
            )
        except PipelineError as exc:
            raise ApiError(422, "pipeline_error", str(exc)) from exc
        except OllamaError as exc:
            raise ApiError(
                503,
                "model_unavailable",
                "The local model runtime could not be reached, so no grounded answer "
                "can be generated. Retrieved sources are still available.",
            ) from exc

        verdicts = {item.claim_id: item for item in result.verifications}
        claims = (
            tuple(
                ClaimView(
                    claim_id=claim.claim_id,
                    text=claim.text,
                    cited_source_ids=claim.cited_source_ids,
                    verdict=verdicts[claim.claim_id].verdict,
                    verdict_reason=verdicts[claim.claim_id].reason,
                    evidence_source_ids=verdicts[claim.claim_id].evidence_source_ids,
                )
                for claim in result.answer.claims
                if claim.claim_id in verdicts
            )
            if result.answer is not None
            else ()
        )
        bundle = result.evidence_bundle
        return AnswerResponse(
            stage=result.stage.value,
            published=result.published,
            route=result.route,
            # An unpublished answer is withheld on purpose and must not be sent to
            # the client, where it could still be rendered.
            answer=result.answer if result.published else None,
            claims=claims if result.published else (),
            evidence=bundle.evidence if bundle else (),
            warnings=result.warnings,
            query=bundle.query if bundle else None,
        )

    @app.post("/api/devils-advocate", responses=_ERROR_RESPONSES, tags=["answer"])
    async def devils_advocate(payload: DevilsAdvocateRequest) -> StreamingResponse:
        """Stream advocate, opponent, and rebuttal over a verified answer.

        The stress test runs only on an answer that already published: the underlying
        module refuses anything less, so a case that was routed to a human, refused,
        or abstained cannot be argued about. Stages stream as server-sent events so
        the three sequential local generations do not look frozen.
        """

        _require_confirmed(payload.facts)
        documents = state.documents_for_domain(payload.facts.domain)

        def send(payload_dict: dict[str, Any]) -> bytes:
            return f"data: {json.dumps(payload_dict, ensure_ascii=False)}\n\n".encode()

        def events() -> Iterator[bytes]:
            # Re-running the answer to obtain a verified snapshot takes ~20s. Open the
            # stream and announce that first, so the client shows progress instead of a
            # silent connection that looks frozen.
            yield send({"kind": "preparing"})
            try:
                result = run_confirmed_request(
                    payload.facts,
                    documents,
                    client=state.model_client(),
                    model=state.settings.ollama_model,
                    approved_profiles=frozenset(payload.approved_profiles),
                    evidence_limit=payload.limit,
                )
            except (PipelineError, OllamaError) as exc:
                yield send({"kind": "error", "message": str(exc)})
                return
            if not result.published:
                yield send(
                    {
                        "kind": "error",
                        "message": (
                            "A stress test needs a verified answer. This case did not "
                            f"produce one (stage: {result.stage.value})."
                        ),
                    }
                )
                return

            try:
                for event in run_devils_advocate_stream(
                    state.model_client(),
                    model=state.settings.ollama_model,
                    workflow=result.snapshot,
                ):
                    yield send(
                        {
                            "stage": event.stage.value,
                            "kind": event.kind.value,
                            "text": event.text,
                        }
                    )
            except DevilsAdvocateError as exc:
                # The stress test is optional. A failure here must not be able to
                # retract or contradict the verified answer already shown.
                yield send({"kind": "error", "message": str(exc)})

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.post(
        "/api/transcribe",
        response_model=TranscriptionResult,
        responses=_ERROR_RESPONSES,
        tags=["intake"],
    )
    async def transcribe(
        file: UploadFile = File(...),
        language: str = Form("auto"),
    ) -> TranscriptionResult:
        """Transcribe a short local WAV/FLAC clip. The transcript is a DRAFT.

        The result is never treated as confirmed fact: it feeds the same intake and
        confirmation gate as typed text. The upload is held in memory, written only to
        a securely created temporary file the ASR backend must read from, and that
        file is deleted before the response returns.
        """

        try:
            hint = LanguageHint(language)
        except ValueError as exc:
            raise ApiError(
                400, "invalid_request", "language must be one of: auto, hi, en", field="language"
            ) from exc

        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".wav", ".flac"}:
            raise ApiError(
                415, "unsupported_format", "only .wav and .flac audio is accepted", field="file"
            )
        data = await file.read(MAX_AUDIO_BYTES + 1)
        if len(data) > MAX_AUDIO_BYTES:
            raise ApiError(413, "audio_limit_exceeded", "audio exceeds the size limit", field="file")

        descriptor, temp_name = tempfile.mkstemp(suffix=suffix)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
            config = ASRConfig(
                model_path=state.asr_model_dir,
                model_revision=state.asr_model_revision,
                device="cpu",
                compute_type="int8",
            )
            return transcribe_audio(temp_path, config, language=hint)
        except ASRError as exc:
            status = _ASR_STATUS.get(exc.detail.code, 500)
            raise ApiError(status, exc.detail.code.value, exc.detail.message, field=exc.detail.field)
        finally:
            # The clip must not outlive the request. Delete it whether or not the
            # backend succeeded.
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

    @app.post(
        "/api/community",
        response_model=CommunityResponse,
        responses=_ERROR_RESPONSES,
        tags=["answer"],
    )
    async def community(payload: CommunityRequest) -> CommunityResponse:
        """Reformat a verified answer as a brief for a trusted intermediary.

        Built deterministically from a published answer: every legal sentence was
        already verified, so reformatting cannot introduce a new claim. Personal
        identifiers are dropped by default.
        """

        _require_confirmed(payload.facts)
        documents = state.documents_for_domain(payload.facts.domain)
        result = run_confirmed_request(
            payload.facts,
            documents,
            client=state.model_client(),
            model=state.settings.ollama_model,
            approved_profiles=frozenset(payload.approved_profiles),
            evidence_limit=payload.limit,
        )
        if not result.published or result.answer is None or result.evidence_bundle is None:
            raise ApiError(
                409,
                "not_verified",
                "A community explanation summarises a verified answer. This case did not "
                f"produce one (stage: {result.stage.value}).",
            )
        brief = build_community_explanation(
            result.answer,
            result.evidence_bundle.evidence,
            include_sensitive=payload.include_sensitive,
            warnings=result.warnings,
        )
        return CommunityResponse(
            heading=brief.heading,
            what_help_is_needed=brief.what_help_is_needed,
            situation=brief.situation,
            rights=brief.rights,
            next_steps=brief.next_steps,
            citations=brief.citations,
            caveats=brief.caveats,
            text=brief.as_text(),
        )

    @app.post("/api/rights-card", responses=_ERROR_RESPONSES, tags=["answer"])
    async def rights_card(payload: RightsCardRequest) -> Response:
        """Render a phone-sized PNG from a published answer.

        The card is a summary of an answer that already passed verification. Its
        rights are the answer's rights, its citations are the retrieved evidence, its
        helplines come from the reviewed directory, and its QR points only at an
        official government URL. Nothing on it is produced without verification.
        """

        _require_confirmed(payload.facts)
        documents = state.documents_for_domain(payload.facts.domain)
        result = run_confirmed_request(
            payload.facts,
            documents,
            client=state.model_client(),
            model=state.settings.ollama_model,
            approved_profiles=frozenset(payload.approved_profiles),
            evidence_limit=payload.limit,
        )
        if not result.published or result.answer is None or result.evidence_bundle is None:
            raise ApiError(
                409,
                "not_verified",
                "A Rights Card summarises a verified answer. This case did not produce "
                f"one (stage: {result.stage.value}), so there is nothing to put on a card.",
            )

        fallbacks: tuple = ()
        district = payload.legal_aid_district or payload.facts.location
        if district:
            try:
                found = state.legal_aid_finder().find(
                    district, state=payload.legal_aid_state or payload.facts.jurisdiction
                )
                fallbacks = found.fallbacks
            except (LegalAidFinderError, StateError):
                fallbacks = ()

        try:
            png = render_rights_card(
                RightsCardContent(
                    title=_card_title(payload.facts),
                    rights=result.answer.rights,
                    evidence=result.evidence_bundle.evidence,
                    fallbacks=fallbacks,
                    language=payload.facts.input_language,
                    warnings=result.warnings,
                )
            )
        except RightsCardError as exc:
            raise ApiError(422, "rights_card_error", str(exc)) from exc

        return Response(
            content=png,
            media_type="image/png",
            headers={"Cache-Control": "no-store"},
        )

    @app.post(
        "/api/legal-aid",
        response_model=LegalAidSearchResult,
        responses=_ERROR_RESPONSES,
        tags=["legal-aid"],
    )
    async def legal_aid(payload: LegalAidRequest) -> LegalAidSearchResult:
        finder = state.legal_aid_finder()
        return finder.find(payload.district_or_city, state=payload.state)

    @app.get(
        "/api/checklists",
        response_model=ChecklistListResponse,
        responses=_ERROR_RESPONSES,
        tags=["actions"],
    )
    async def checklists() -> ChecklistListResponse:
        return ChecklistListResponse.from_templates(state.checklist_catalog().templates)

    @app.get(
        "/api/checklists/{template_id}",
        response_model=ChecklistTemplate,
        responses={404: {"model": ErrorResponse}, **_ERROR_RESPONSES},
        tags=["actions"],
    )
    async def checklist(template_id: str) -> ChecklistTemplate:
        return state.checklist_catalog().get(template_id)

    @app.post(
        "/api/mapping",
        response_model=MappingResponse,
        responses=_ERROR_RESPONSES,
        tags=["mapping"],
    )
    async def mapping(payload: MappingRequest) -> MappingResponse:
        """Look up the CURATED catalogue only.

        The curated catalogue is empty in this build. Only ``pending_human_review``
        candidates exist on disk, and serving one as a mapping would present an
        unreviewed IPC/BNS equivalence as reviewed law. Every lookup therefore
        returns ``not_found`` with an explicit warning.
        """

        catalog = state.mapping_catalog
        result: MappingLookupResult = catalog.lookup(
            payload.query, incident_date=payload.incident_date
        )
        return MappingResponse(
            result=result,
            warnings=(result.warning, NO_REVIEWED_MAPPING_WARNING),
            curated_mapping_count=len(catalog.mappings),
        )

    @app.post(
        "/api/ocr",
        response_model=OCRResult,
        responses=_ERROR_RESPONSES,
        tags=["ocr"],
        openapi_extra={
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["file"],
                            "properties": {
                                "file": {"type": "string", "format": "binary"},
                            },
                        }
                    }
                },
            }
        },
    )
    async def ocr(request: Request) -> OCRResult:
        """Run local OCR on an uploaded PNG/JPEG. The image never touches disk."""

        form = await request.form(
            max_files=1, max_fields=0, max_part_size=MAX_UPLOAD_BYTES + 1
        )
        try:
            upload = form.get("file")
            filename = getattr(upload, "filename", None)
            reader = getattr(upload, "read", None)
            if filename is None or reader is None:
                raise ApiError(
                    400, "invalid_request", "a single image part named 'file' is required", "file"
                )
            data = await reader(MAX_UPLOAD_BYTES + 1)
            if len(data) > MAX_UPLOAD_BYTES:
                raise ApiError(
                    413,
                    "image_limit_exceeded",
                    f"image exceeds the {MAX_UPLOAD_BYTES}-byte limit",
                    "file",
                )
            safe_name = Path(str(filename)).name
            return extract_image_bytes(bytes(data), safe_name, state.ocr_config())
        finally:
            await form.close()

    @app.post(
        "/api/applicability/delhi-rent",
        response_model=DelhiRentApplicabilityResult,
        responses=_ERROR_RESPONSES,
        tags=["applicability"],
    )
    async def delhi_rent(payload: DelhiRentRequest) -> DelhiRentApplicabilityResult:
        return evaluate_delhi_rent_applicability(payload.facts)

"""Local API contract, confirmation gate, warning propagation, and privacy tests."""

from __future__ import annotations

import json
import struct
import tempfile
import zlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.app import ALLOWED_ORIGINS, create_app
from src.api.state import ROOT, ApiState
from src.config import Settings
from src.ocr import ImageFormat, OCRError, OCRErrorCode, OCRLanguage, OCRResult

RETRIEVED_AT = "2026-07-12T10:00:00+00:00"
SHA = "b" * 64

CONFIRMED_FACTS = {
    "incident_summary": "My employer did not pay my wages for two months.",
    "incident_date": "2024-01-15",
    "jurisdiction": "Delhi",
    "location": "New Delhi",
    "domain": "labour",
    "parties": ["employer", "worker"],
    "material_facts": ["wages unpaid", "no payslip issued"],
    "input_language": "en",
    "confirmed": True,
    "confirmed_at": "2026-07-13T09:00:00+00:00",
}

UNCONFIRMED_FACTS = {**CONFIRMED_FACTS, "confirmed": False, "confirmed_at": None}


def _chunk(
    chunk_id: str,
    source_id: str,
    text: str,
    *,
    act: str,
    section: str,
    effective_from: str | None,
) -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
        "source_id": source_id,
        "section_id": section,
        "heading": f"{section}. Payment of wages",
        "text": text,
        "page_start": 3,
        "page_end": 3,
        "metadata": {
            "act": act,
            "jurisdiction": "India",
            "language": "en",
            "document_type": "act",
            "status": "in_force",
            "priority": 3,
            "effective_from": effective_from,
            "effective_to": None,
            "official_url": "https://www.indiacode.nic.in/example.pdf",
            "retrieved_at": RETRIEVED_AT,
            "sha256": SHA,
            "ocr_used": False,
        },
    }


def _write_corpus(sections: Path) -> None:
    sections.mkdir(parents=True, exist_ok=True)
    records = {
        "code_on_wages_2019_en": [
            _chunk(
                "code_on_wages_2019_en:17",
                "code_on_wages_2019_en",
                "Wages shall be paid to the employee before the expiry of the seventh day.",
                act="The Code on Wages, 2019",
                section="17",
                effective_from="2019-08-08",
            )
        ],
        # A source whose commencement is left to a Government notification: the
        # reviewed text proves no effective date, so retrieval must warn about it.
        "labour_codes_misc_en": [
            _chunk(
                "labour_codes_misc_en:5",
                "labour_codes_misc_en",
                "Unpaid wages of an employee may be claimed by an application to the authority.",
                act="The Industrial Relations Code, 2020",
                section="5",
                effective_from=None,
            )
        ],
    }
    for source_id, items in records.items():
        (sections / f"{source_id}.jsonl").write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n",
            encoding="utf-8",
        )


def _state(corpus_dir: Path, *, tessdata: Path | None = None) -> ApiState:
    return ApiState(
        settings=Settings(
            ollama_url="http://127.0.0.1:11434",
            ollama_model="gemma4:e4b-it-q4_K_M",
            max_context_tokens=8192,
            max_output_tokens=1200,
            corpus_path=corpus_dir,
            index_path=corpus_dir,
        ),
        corpus_dir=corpus_dir,
        contacts_path=ROOT / "data" / "processed" / "contacts" / "delhi_dlsa.json",
        checklists_path=ROOT / "config" / "evidence_checklists.json",
        tessdata_dir=tessdata if tessdata is not None else ROOT / "models" / "ocr" / "tessdata",
        tesseract_path=Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
        ollama_probe_timeout=0.2,
    )


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    sections = tmp_path_factory.mktemp("corpus") / "sections"
    _write_corpus(sections)
    with TestClient(create_app(_state(sections))) as test_client:
        yield test_client


@pytest.fixture()
def empty_client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(_state(tmp_path / "missing"))) as test_client:
        yield test_client


def _png_bytes(width: int = 8, height: int = 8) -> bytes:
    """Build a valid PNG without Pillow so the OCR route can be exercised."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"".join(b"\x00" + b"\xff" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


# --------------------------------------------------------------------------- health


def test_health_reports_a_missing_corpus_without_crashing(empty_client: TestClient) -> None:
    response = empty_client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["corpus_loaded"] is False
    assert body["chunk_count"] == 0
    assert body["corpus_sha256"] is None
    assert body["corpus_error"]
    assert isinstance(body["ollama_reachable"], bool)
    assert body["model"] == "gemma4:e4b-it-q4_K_M"


def test_health_reports_a_loaded_corpus(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["corpus_loaded"] is True
    assert body["chunk_count"] == 2
    assert len(body["corpus_sha256"]) == 64
    assert body["corpus_error"] is None


# --------------------------------------------------------------------------- intake


def test_intake_returns_an_unconfirmed_restatement(client: TestClient) -> None:
    response = client.post(
        "/api/intake",
        json={"text": "My landlord said he will evict me today.", "domain": "tenancy_property"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requires_confirmation"] is True
    assert body["confirmed"] is False
    assert body["unconfirmed_facts"]["confirmed"] is False
    assert body["unconfirmed_facts"]["confirmed_at"] is None
    assert body["restatement"].startswith("Here is what I understood:")
    assert body["language"]["language"] == "en"
    assert [signal["category"] for signal in body["urgency_signals"]] == ["immediate_eviction"]


def test_intake_rejects_blank_text(client: TestClient) -> None:
    response = client.post("/api/intake", json={"text": "   "})
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_request"


# ------------------------------------------------------------------ confirmation gate


def test_route_rejects_unconfirmed_facts(client: TestClient) -> None:
    response = client.post("/api/route", json={"facts": UNCONFIRMED_FACTS})
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "facts_not_confirmed"
    assert body["field"] == "facts.confirmed"
    assert "traceback" not in response.text.casefold()


def test_evidence_rejects_unconfirmed_facts(client: TestClient) -> None:
    response = client.post("/api/evidence", json={"facts": UNCONFIRMED_FACTS, "limit": 3})
    assert response.status_code == 409
    assert response.json()["code"] == "facts_not_confirmed"


def test_facts_claiming_confirmation_without_a_timestamp_are_rejected(
    client: TestClient,
) -> None:
    facts = {**CONFIRMED_FACTS, "confirmed_at": None}
    response = client.post("/api/route", json={"facts": facts})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_route_returns_a_standard_decision_for_confirmed_facts(client: TestClient) -> None:
    response = client.post("/api/route", json={"facts": CONFIRMED_FACTS})
    assert response.status_code == 200
    body = response.json()
    assert body["priority"] == "standard"
    assert body["general_explanation_allowed"] is True
    assert len(body["facts_fingerprint"]) == 64


def test_route_escalates_confirmed_urgency_to_human_help(client: TestClient) -> None:
    response = client.post(
        "/api/route",
        json={"facts": CONFIRMED_FACTS, "confirmed_urgencies": ["violence"]},
    )
    body = response.json()
    assert body["priority"] == "immediate_human_help"
    assert body["human_help_required"] is True
    assert body["general_explanation_allowed"] is False


# -------------------------------------------------------------------------- evidence


def test_evidence_propagates_undated_source_warnings_verbatim(client: TestClient) -> None:
    response = client.post("/api/evidence", json={"facts": CONFIRMED_FACTS, "limit": 4})
    assert response.status_code == 200
    body = response.json()
    assert body["evidence"], "the reviewed corpus should match a wages query"
    assert body["query"].startswith("My employer did not pay my wages")
    warning = " ".join(body["warnings"])
    assert "commencement date" in warning
    assert "The Industrial Relations Code, 2020" in warning
    assert "labour_codes_misc_en:5" in body["undated_source_ids"]
    assert body["trace"]["corpus_sha256"]
    assert body["trace"]["active_filters"]["effective_on"] == "2024-01-15"


def test_evidence_without_a_corpus_returns_503(empty_client: TestClient) -> None:
    response = empty_client.post("/api/evidence", json={"facts": CONFIRMED_FACTS})
    assert response.status_code == 503
    assert response.json()["code"] == "corpus_unavailable"


# ------------------------------------------------------------------------- legal aid


def test_legal_aid_returns_a_matched_district(client: TestClient) -> None:
    response = client.post(
        "/api/legal-aid", json={"district_or_city": "South Delhi", "state": "Delhi"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["match_status"] == "matched"
    assert body["contacts"]
    assert body["fallbacks"]


def test_legal_aid_outside_delhi_routes_to_the_state_authority(client: TestClient) -> None:
    """A citizen outside Delhi is given their own State Legal Services Authority.

    This test's fixture directory may carry no state tier, in which case the older
    fallback-only behaviour still holds; both are correct, and neither may show a
    Delhi district contact to someone in Maharashtra.
    """

    body = client.post(
        "/api/legal-aid", json={"district_or_city": "Pune", "state": "Maharashtra"}
    ).json()
    assert body["match_status"] == "outside_delhi"
    assert body["warnings"]
    for contact in body["contacts"]:
        assert "Maharashtra" in contact["authority"]


# ------------------------------------------------------------------------ checklists


def test_checklists_list_and_fetch(client: TestClient) -> None:
    listing = client.get("/api/checklists")
    assert listing.status_code == 200
    templates = listing.json()["templates"]
    assert templates
    template_id = templates[0]["template_id"]

    detail = client.get(f"/api/checklists/{template_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["template_id"] == template_id
    assert body["items"]
    assert "guidance" in body["guidance_label"].casefold()


def test_unknown_checklist_returns_404(client: TestClient) -> None:
    response = client.get("/api/checklists/not_a_template")
    assert response.status_code == 404
    assert response.json()["code"] == "checklist_error"


# --------------------------------------------------------------------------- mapping


def test_mapping_never_serves_unreviewed_candidates(client: TestClient) -> None:
    response = client.post("/api/mapping", json={"query": "IPC 420", "incident_date": "2023-05-01"})
    assert response.status_code == 200
    body = response.json()
    assert body["curated_mapping_count"] == 0
    assert body["result"]["status"] == "not_found"
    assert body["result"]["candidates"] == []
    assert body["result"]["applicable_provisions"] == []
    warnings = " ".join(body["warnings"]).casefold()
    assert "no human-approved ipc/bns mapping" in warnings
    assert "pending human review" in warnings


# ------------------------------------------------------------------------------- ocr


def test_ocr_returns_a_clean_503_when_the_local_engine_is_unavailable(
    tmp_path: Path,
) -> None:
    app = create_app(_state(tmp_path / "missing", tessdata=tmp_path / "no_tessdata"))
    with TestClient(app) as local_client:
        response = local_client.post(
            "/api/ocr", files={"file": ("scan.png", _png_bytes(), "image/png")}
        )
    assert response.status_code == 503
    body = response.json()
    assert body["code"] in {
        OCRErrorCode.PILLOW_UNAVAILABLE.value,
        OCRErrorCode.TESSERACT_UNAVAILABLE.value,
        OCRErrorCode.TESSERACT_VERSION_MISMATCH.value,
        OCRErrorCode.TESSERACT_INTEGRITY_FAILED.value,
        OCRErrorCode.TESSDATA_INTEGRITY_FAILED.value,
    }
    assert body["message"]
    assert "Traceback" not in response.text


def test_ocr_holds_the_upload_in_memory_and_writes_no_file(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: dict[str, object] = {}

    def fake_extract(image_bytes: bytes, filename: str, config: object) -> OCRResult:
        seen["bytes"] = len(image_bytes)
        seen["filename"] = filename
        return OCRResult(
            text="wage slip",
            width=8,
            height=8,
            image_format=ImageFormat.PNG,
            language=OCRLanguage.ENGLISH_HINDI,
            mean_confidence_percent=91.5,
            tesseract_version="5.4.0",
            processing_seconds=0.01,
        )

    def forbidden_rollover(self: object) -> None:  # pragma: no cover - must never run
        raise AssertionError("an upload was spooled to disk")

    monkeypatch.setattr("src.api.app.extract_image_bytes", fake_extract)
    monkeypatch.setattr(tempfile.SpooledTemporaryFile, "rollover", forbidden_rollover)

    temp_root = Path(tempfile.gettempdir())
    before = set(temp_root.iterdir())
    payload = _png_bytes(64, 64) + b"\x00" * (2 * 1024 * 1024)

    response = client.post("/api/ocr", files={"file": ("wage slip.png", payload, "image/png")})

    assert response.status_code == 200
    assert response.json()["text"] == "wage slip"
    assert seen["bytes"] == len(payload)
    assert seen["filename"] == "wage slip.png"
    assert set(temp_root.iterdir()) - before == set()
    assert not list(tmp_path.iterdir())


def test_ocr_rejects_a_non_image_upload(client: TestClient) -> None:
    response = client.post("/api/ocr", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 415
    assert response.json()["code"] == OCRErrorCode.UNSUPPORTED_FORMAT.value


def test_ocr_error_maps_to_a_structured_envelope(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def raise_timeout(*_: object, **__: object) -> OCRResult:
        raise OCRError(OCRErrorCode.OCR_TIMEOUT, "local OCR exceeded its time limit")

    monkeypatch.setattr("src.api.app.extract_image_bytes", raise_timeout)
    response = client.post("/api/ocr", files={"file": ("scan.png", _png_bytes(), "image/png")})
    assert response.status_code == 504
    assert response.json() == {
        "code": "ocr_timeout",
        "message": "local OCR exceeded its time limit",
        "field": None,
    }


# --------------------------------------------------------------------- applicability


def test_delhi_rent_applicability_needs_facts(client: TestClient) -> None:
    response = client.post(
        "/api/applicability/delhi-rent",
        json={"facts": {"incident_date": "2024-03-01"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "needs_facts"
    assert body["approved_profiles"] == []
    assert "monthly_rent" in body["missing_fields"]


def test_delhi_rent_applicability_excludes_high_rent(client: TestClient) -> None:
    body = client.post(
        "/api/applicability/delhi-rent",
        json={
            "facts": {
                "incident_date": "2024-03-01",
                "within_statutory_or_notified_area": True,
                "government_owned": False,
                "government_grant_tenancy": False,
                "monthly_rent": "45000.00",
                "construction_completed_on": "2001-01-01",
            }
        },
    ).json()
    assert body["decision"] == "not_applicable"
    assert body["cited_sections"] == ["3(c)"]


# ------------------------------------------------------------------------------ cors


def test_cors_allows_only_the_loopback_dev_origins(client: TestClient) -> None:
    assert "*" not in ALLOWED_ORIGINS
    assert set(ALLOWED_ORIGINS) == {"http://127.0.0.1:5173", "http://localhost:5173"}

    allowed = client.options(
        "/api/route",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"

    blocked = client.options(
        "/api/route",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in blocked.headers

    simple = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in simple.headers


# --------------------------------------------------------------- no request persistence


def test_no_endpoint_persists_case_text(client: TestClient, tmp_path: Path) -> None:
    before = set(tempfile.gettempdir() and Path(tempfile.gettempdir()).iterdir())
    confirmed = {**CONFIRMED_FACTS, "confirmed_at": datetime.now(UTC).isoformat()}
    client.post("/api/intake", json={"text": "Sensitive private narrative for the record."})
    client.post("/api/route", json={"facts": confirmed})
    client.post("/api/evidence", json={"facts": confirmed, "limit": 2})
    assert set(Path(tempfile.gettempdir()).iterdir()) - before == set()
    assert not list(tmp_path.iterdir())

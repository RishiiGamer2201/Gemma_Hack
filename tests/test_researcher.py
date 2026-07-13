"""Corpus loading, domain scoping, and confirmed-facts evidence retrieval."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from src.agents.researcher import ResearchError, retrieve_evidence
from src.models.schemas import ConfirmedFacts, LegalDomain
from src.retrieval import (
    CorpusLoadError,
    RetrievalDocument,
    SearchFilters,
    load_processed_corpus,
    to_source_evidence,
)
from src.retrieval.collections import CollectionError, collection_for_domain
from src.retrieval.corpus import MAX_EXCERPT_CHARACTERS
from src.retrieval.hybrid import HybridRetriever

RETRIEVED_AT = "2026-07-12T10:00:00+00:00"
SHA = "a" * 64


def chunk(
    chunk_id: str,
    source_id: str,
    text: str,
    *,
    act: str = "The Code on Wages, 2019",
    section: str | None = "17",
    effective_from: str | None = "2019-08-08",
    **metadata: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
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
        "audit_status": "pending_human_review",
    }
    payload.update(metadata)
    return {
        "chunk_id": chunk_id,
        "source_id": source_id,
        "section_id": section,
        "heading": f"{section}. Heading" if section else "Preamble",
        "text": text,
        "page_start": 3,
        "page_end": 3,
        "metadata": payload,
    }


def write_corpus(root: Path, records: dict[str, list[dict[str, object]]]) -> Path:
    sections = root / "sections"
    sections.mkdir(parents=True)
    for source_id, items in records.items():
        (sections / f"{source_id}.jsonl").write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items),
            encoding="utf-8",
        )
    return sections


def confirmed(**updates: object) -> ConfirmedFacts:
    payload: dict[str, object] = {
        "incident_summary": "My employer has not paid my wages.",
        "incident_date": date(2026, 5, 1),
        "domain": LegalDomain.LABOUR,
        "confirmed": True,
        "confirmed_at": datetime(2026, 7, 13, tzinfo=UTC),
    }
    payload.update(updates)
    return ConfirmedFacts.model_validate(payload)


def test_loader_promotes_section_and_pages_into_filterable_metadata(tmp_path: Path) -> None:
    sections = write_corpus(
        tmp_path,
        {"code_on_wages_2019_en": [chunk("code_on_wages_2019_en:section-17", "code_on_wages_2019_en", "wages payable")]},
    )
    documents = load_processed_corpus(sections)

    assert len(documents) == 1
    metadata = documents[0].metadata
    # SearchFilters and overlap deduplication read these from metadata, but the
    # build pipeline stores them at the top level of the record.
    assert metadata["section"] == "17"
    assert metadata["page_start"] == 3
    assert metadata["corpus_source_id"] == "code_on_wages_2019_en"
    # Act and section must be searchable, not only the body text.
    assert "Code on Wages" in documents[0].text


def test_loader_skips_empty_chunks_and_rejects_duplicate_ids(tmp_path: Path) -> None:
    sections = write_corpus(
        tmp_path,
        {
            "code_on_wages_2019_en": [
                chunk("a:1", "code_on_wages_2019_en", "real text"),
                chunk("a:2", "code_on_wages_2019_en", "   "),
            ]
        },
    )
    assert len(load_processed_corpus(sections)) == 1

    duplicated = write_corpus(
        tmp_path / "dup",
        {
            "code_on_wages_2019_en": [
                chunk("a:1", "code_on_wages_2019_en", "one"),
                chunk("a:1", "code_on_wages_2019_en", "two"),
            ]
        },
    )
    with pytest.raises(CorpusLoadError):
        load_processed_corpus(duplicated)


def test_evidence_conversion_flags_truncated_excerpt() -> None:
    body = "x " * MAX_EXCERPT_CHARACTERS
    document = RetrievalDocument(
        source_id="code_on_wages_2019_en:section-17",
        text="wages",
        metadata=chunk("id", "src", body)["metadata"] | {"source_text": body, "section": "17"},
    )
    result = HybridRetriever([document]).search("wages")[0]
    evidence = to_source_evidence(result)

    assert evidence.excerpt_truncated is True
    assert len(evidence.excerpt) <= MAX_EXCERPT_CHARACTERS


def test_evidence_conversion_refuses_a_chunk_without_provenance() -> None:
    metadata = chunk("id", "src", "text")["metadata"]
    assert isinstance(metadata, dict)
    del metadata["official_url"]
    document = RetrievalDocument(
        source_id="x:1", text="wages", metadata=metadata | {"source_text": "wages"}
    )
    result = HybridRetriever([document]).search("wages")[0]

    with pytest.raises(CorpusLoadError):
        to_source_evidence(result)


def test_domain_scoping_excludes_other_domains_but_keeps_universal_sources() -> None:
    documents = (
        RetrievalDocument(
            source_id="w:1", text="wages", metadata={"corpus_source_id": "code_on_wages_2019_en"}
        ),
        RetrievalDocument(
            source_id="c:1", text="theft", metadata={"corpus_source_id": "bns_2023_en"}
        ),
        RetrievalDocument(
            source_id="k:1", text="rights", metadata={"corpus_source_id": "constitution_2026_en"}
        ),
    )
    labour = {item.source_id for item in collection_for_domain(documents, LegalDomain.LABOUR)}

    assert labour == {"w:1", "k:1"}
    # An unclassified dispute must not be silently guessed into a collection.
    assert len(collection_for_domain(documents, LegalDomain.OTHER)) == 3
    with pytest.raises(CollectionError):
        collection_for_domain(documents[:1], LegalDomain.CRIMINAL)


def test_undated_source_is_excluded_by_default_and_warned_about_when_admitted() -> None:
    undated = RetrievalDocument(
        source_id="code_on_wages_2019_en:section-17",
        text="wages payable to employee",
        metadata=chunk("id", "code_on_wages_2019_en", "wages payable", effective_from=None)[
            "metadata"
        ]
        | {"source_text": "wages payable", "section": "17", "corpus_source_id": "code_on_wages_2019_en"},
    )
    retriever = HybridRetriever([undated])

    strict = retriever.search("wages", filters=SearchFilters(effective_on=date(2026, 5, 1)))
    assert strict == []

    admitted = retriever.search(
        "wages",
        filters=SearchFilters(effective_on=date(2026, 5, 1), include_undated_sources=True),
    )
    assert len(admitted) == 1

    bundle = retrieve_evidence(confirmed(), [undated], limit=1)
    assert len(bundle.undated_evidence) == 1
    assert any("not proven" in warning for warning in bundle.warnings)
    assert any("Code on Wages" in warning for warning in bundle.warnings)


def test_retrieval_is_refused_before_explicit_confirmation() -> None:
    document = RetrievalDocument(
        source_id="w:1", text="wages", metadata={"corpus_source_id": "code_on_wages_2019_en"}
    )
    unconfirmed = ConfirmedFacts(
        incident_summary="My employer has not paid my wages.",
        domain=LegalDomain.LABOUR,
    )
    with pytest.raises(ResearchError):
        retrieve_evidence(unconfirmed, [document])

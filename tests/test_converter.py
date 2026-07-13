"""IPC/BNS conversion: routed by date, never inferred from a section number."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.legal_time.converter import convert
from src.legal_time.mapping import (
    LegalMapping,
    MappingCatalog,
    load_reviewed_mappings,
)
from src.retrieval import RetrievalDocument


def empty_catalog() -> MappingCatalog:
    return MappingCatalog(())


def bns_chunk(section: str = "318") -> RetrievalDocument:
    return RetrievalDocument(
        source_id=f"bns_2023_en:section-{section}",
        text=f"{section}. Cheating.",
        metadata={
            "corpus_source_id": "bns_2023_en",
            "section": section,
            "source_text": f"{section}. Cheating.",
        },
    )


def approved_mapping() -> LegalMapping:
    return LegalMapping.model_validate(
        {
            "mapping_id": "ipc-420-bns-318",
            "source_provisions": [{"code": "IPC", "section": "420"}],
            "target_provisions": [{"code": "BNS", "section": "318"}],
            "mapping_type": "partial",
            "offence_names": ["Cheating"],
            "plain_language_description": "Cheating and dishonestly inducing delivery.",
            "change_notes": "The scope and structure changed; not a one-to-one carry-over.",
            "official_source_url": "https://cytrain.ncrb.gov.in/example.html",
            "official_source_id": "ncrb_sankalan_ipc_bns",
            "reviewed_by": "Reviewer",
            "reviewed_at": "2026-07-13",
        }
    )


def test_without_the_incident_date_it_asks_instead_of_choosing_a_code() -> None:
    result = convert("IPC 420", incident_date=None, catalog=empty_catalog())

    assert result.governing_code is None
    assert any("before or after 1 July 2024" in q for q in result.questions)


def test_a_pre_bns_incident_is_governed_by_the_ipc_which_is_not_in_the_corpus() -> None:
    """The IPC is not in this build. Saying so is the honest answer."""

    result = convert("IPC 420", incident_date=date(2023, 5, 10), catalog=empty_catalog())

    assert result.governing_code == "IPC"
    warning = " ".join(result.warnings)
    assert "before 1 July 2024" in warning
    assert "NOT included in this build" in warning
    # It must not quietly offer the BNS as a substitute for the code that governs.
    assert "does not apply to you" in warning


def test_a_post_bns_incident_is_governed_by_the_bns() -> None:
    result = convert("IPC 420", incident_date=date(2026, 5, 10), catalog=empty_catalog())
    assert result.governing_code == "BNS"


def test_an_unmapped_section_is_never_inferred_from_its_number() -> None:
    result = convert("IPC 420", incident_date=date(2026, 5, 10), catalog=empty_catalog())

    assert result.has_approved_mapping is False
    warning = " ".join(result.warnings)
    assert "no human-approved IPC/BNS mapping" in warning
    # The reason matters: a matching number is not a matching offence.
    assert "split, merged, reworded, and dropped" in warning


def test_an_approved_mapping_is_grounded_against_the_corpus() -> None:
    catalog = MappingCatalog((approved_mapping(),))

    grounded = convert(
        "IPC 420",
        incident_date=date(2026, 5, 10),
        catalog=catalog,
        documents=[bns_chunk("318")],
    )
    assert grounded.has_approved_mapping is True
    assert grounded.grounded_bns_sections == ("318",)

    # If the mapped BNS section's text is not in the corpus, say so: the app cannot
    # cite a provision it has no text for.
    ungrounded = convert(
        "IPC 420",
        incident_date=date(2026, 5, 10),
        catalog=catalog,
        documents=[bns_chunk("999")],
    )
    assert ungrounded.grounded_bns_sections == ()
    assert any("not in this build's corpus" in w for w in ungrounded.warnings)


def test_only_reviewed_records_are_ever_loaded(tmp_path: Path) -> None:
    path = tmp_path / "mappings.json"
    path.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "mapping_id": "pending",
                        "mapping_type": "REVIEWER_MUST_SET",
                        "review_status": "pending_human_review",
                    },
                    {**json.loads(approved_mapping().model_dump_json()), "review_status": "reviewed"},
                ]
            }
        )
    )
    loaded = load_reviewed_mappings(path)

    # The pending candidate is skipped; only the signed-off record is served.
    assert [item.mapping_id for item in loaded] == ["ipc-420-bns-318"]


def test_a_record_marked_reviewed_but_unfilled_is_a_hard_error(tmp_path: Path) -> None:
    path = tmp_path / "mappings.json"
    path.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "mapping_id": "half-done",
                        "mapping_type": "REVIEWER_MUST_SET",
                        "review_status": "reviewed",
                    }
                ]
            }
        )
    )
    with pytest.raises(ValueError, match="REVIEWER_MUST_SET"):
        load_reviewed_mappings(path)


def test_the_shipped_worksheet_serves_nothing_yet() -> None:
    shipped = Path("config/ipc_bns_mappings.json")
    if not shipped.is_file():
        pytest.skip("the worksheet has not been generated")
    # Candidates are not mappings. Until a person signs one off, none are served.
    assert load_reviewed_mappings(shipped) == ()

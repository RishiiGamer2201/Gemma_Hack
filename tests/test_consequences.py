"""Deadlines exist only if the law says so, and are computed, never guessed."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.legal_time.deadlines import DeadlineError, DeadlineRecord, load_deadlines
from src.models.schemas import LegalDomain
from src.retrieval import RetrievalDocument
from src.tools.consequences import build_consequences

QUOTE = "shall not admit a complaint unless it is filed within two years"
BODY = (
    "69. (1) The District Commission shall not admit a complaint unless it is filed "
    "within two years from the date on which the cause of action has arisen."
)


def chunk() -> RetrievalDocument:
    return RetrievalDocument(
        source_id="consumer_protection_act_2019_en:section-69",
        text=BODY,
        metadata={
            "source_text": BODY,
            "act": "The Consumer Protection Act, 2019",
            "section": "69",
            "official_url": "https://www.indiacode.nic.in/example.pdf",
            "effective_from": None,
        },
    )


def record(**updates: object) -> dict[str, object]:
    base: dict[str, object] = {
        "deadline_id": "consumer_two_years",
        "domain": "consumer",
        "title": "Time limit to file a consumer complaint",
        "runs_from": "the date on which the cause of action has arisen",
        "period": {"count": 2, "unit": "year"},
        "consequence": "The commission shall not admit the complaint.",
        "consequence_kind": "statutory",
        "source_id": "consumer_protection_act_2019_en:section-69",
        "quote": QUOTE,
    }
    base.update(updates)
    return base


def write(tmp_path: Path, *records: dict[str, object]) -> Path:
    path = tmp_path / "deadlines.json"
    path.write_text(json.dumps({"schema_version": 1, "deadlines": list(records)}))
    return path


def test_a_deadline_whose_quote_is_not_in_the_law_does_not_load(tmp_path: Path) -> None:
    """The whole safety property. A fabricated period must be impossible to load."""

    fabricated = record(
        quote="a claim must be filed within thirty days or it is barred forever",
        period={"count": 30, "unit": "day"},
    )
    with pytest.raises(DeadlineError, match="does not appear"):
        load_deadlines(write(tmp_path, fabricated), [chunk()])


def test_a_deadline_citing_a_chunk_outside_the_corpus_does_not_load(
    tmp_path: Path,
) -> None:
    orphan = record(source_id="invented_act_en:section-1")
    with pytest.raises(DeadlineError, match="not in the corpus"):
        load_deadlines(write(tmp_path, orphan), [chunk()])


def test_a_quoted_deadline_loads_and_the_due_date_is_computed(tmp_path: Path) -> None:
    records = load_deadlines(write(tmp_path, record()), [chunk()])
    assert len(records) == 1

    report = build_consequences(
        records,
        LegalDomain.CONSUMER,
        [],
        start_date=date(2023, 1, 5),
        today=date(2026, 7, 13),
        documents=[chunk()],
    )
    item = report.consequences[0]
    assert item.due_on == date(2025, 1, 5)
    assert item.expired is True
    assert item.consequence_kind == "statutory"
    # The citation resolves from the corpus even though retrieval returned nothing.
    assert item.citation == "The Consumer Protection Act, 2019, Section 69"
    assert item.quote == QUOTE
    assert any("appears to have passed" in note for note in report.notes)


def test_without_a_start_date_no_deadline_is_invented(tmp_path: Path) -> None:
    records = load_deadlines(write(tmp_path, record()), [chunk()])
    report = build_consequences(
        records, LegalDomain.CONSUMER, [], start_date=None, documents=[chunk()]
    )

    # No clock without a start date. Ask, never assume today.
    assert report.consequences[0].due_on is None
    assert report.consequences[0].days_remaining is None
    assert any("When did this happen" in question for question in report.questions)


def test_no_record_means_the_sources_are_silent_not_that_there_is_no_deadline(
    tmp_path: Path,
) -> None:
    records = load_deadlines(write(tmp_path, record()), [chunk()])
    report = build_consequences(
        records, LegalDomain.CRIMINAL, [], start_date=date(2026, 1, 1)
    )

    assert report.sources_are_silent is True
    assert report.consequences == ()
    assert any("will not guess one" in note for note in report.notes)


def test_a_practical_risk_must_declare_what_it_depends_on() -> None:
    """"The commission shall not admit it" and "evidence gets harder to find" are
    not the same kind of statement and must not be blended."""

    with pytest.raises(ValueError, match="depends on"):
        DeadlineRecord.model_validate(
            record(consequence_kind="practical", depends_on=())
        )
    DeadlineRecord.model_validate(
        record(consequence_kind="practical", depends_on=("whether witnesses remain",))
    )


def test_month_arithmetic_does_not_produce_an_invalid_date(tmp_path: Path) -> None:
    monthly = record(period={"count": 1, "unit": "month"})
    records = load_deadlines(write(tmp_path, monthly), [chunk()])
    report = build_consequences(
        records,
        LegalDomain.CONSUMER,
        [],
        start_date=date(2026, 1, 31),
        today=date(2026, 1, 1),
        documents=[chunk()],
    )
    # 31 January + 1 month is the end of February, not the 31st of it.
    assert report.consequences[0].due_on == date(2026, 2, 28)


def test_the_shipped_records_all_quote_the_real_corpus() -> None:
    """The records that ship must load against the real corpus, or they are wrong."""

    sections = Path("data/processed/sections")
    if not sections.is_dir():
        pytest.skip("the processed corpus is not present")
    from src.retrieval import load_processed_corpus

    documents = load_processed_corpus(sections)
    records = load_deadlines(Path("config/deadlines.json"), documents)
    assert records
    # None of them may claim to be reviewed until a person says so.
    assert all(item.review_status == "pending_human_review" for item in records)

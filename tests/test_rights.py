"""A right is a legal claim. It may only say what the official text says."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.actions.rights import RightsError, load_rights, rights_for
from src.models.schemas import LegalDomain
from src.retrieval import RetrievalDocument

BODY = (
    "47. Person arrested to be informed of grounds of arrest and of right to bail.—(1) "
    "Every police officer arresting any person without warrant shall forthwith "
    "communicate to him full particulars of the offence for which he is arrested."
)
QUOTE = "shall forthwith communicate to him full particulars of the offence"


def chunk() -> RetrievalDocument:
    return RetrievalDocument(
        source_id="bnss_2023_en:section-47",
        text=BODY,
        metadata={
            "source_text": BODY,
            "act": "The Bharatiya Nagarik Suraksha Sanhita, 2023",
            "section": "47",
        },
    )


def entry(**updates: object) -> dict[str, object]:
    base: dict[str, object] = {
        "right_id": "arrest_grounds",
        "domain": "criminal",
        "statement": "If you are arrested, the police must tell you what for.",
        "source_id": "bnss_2023_en:section-47",
        "quote": QUOTE,
    }
    base.update(updates)
    return base


def write(tmp_path: Path, *entries: dict[str, object]) -> Path:
    path = tmp_path / "rights.json"
    path.write_text(json.dumps({"schema_version": 1, "rights": list(entries)}))
    return path


def test_an_invented_right_does_not_load(tmp_path: Path) -> None:
    """The whole point. "You have a right to compensation" is not in s.47."""

    invented = entry(
        statement="You are entitled to compensation for a wrongful arrest.",
        quote="every person wrongfully arrested shall be paid compensation",
    )
    with pytest.raises(RightsError, match="does not appear"):
        load_rights(write(tmp_path, invented), [chunk()])


def test_a_right_citing_a_chunk_outside_the_corpus_does_not_load(tmp_path: Path) -> None:
    with pytest.raises(RightsError, match="not in the corpus"):
        load_rights(write(tmp_path, entry(source_id="made_up_act:section-1")), [chunk()])


def test_a_quoted_right_loads(tmp_path: Path) -> None:
    entries = load_rights(write(tmp_path, entry()), [chunk()])
    assert len(entries) == 1
    assert entries[0].review_status == "pending_human_review"


def test_legal_aid_entitlement_travels_with_every_domain(tmp_path: Path) -> None:
    """Free legal aid is not a criminal right or a labour right. It is everyone's."""

    aid_body = "12. Every person shall be entitled to legal services under this Act if"
    aid_chunk = RetrievalDocument(
        source_id="legal_services_authorities_act_en:section-12",
        text=aid_body,
        metadata={"source_text": aid_body, "act": "LSA Act", "section": "12"},
    )
    aid = entry(
        right_id="free_legal_aid",
        domain="constitutional",
        statement="Free legal services are an entitlement.",
        source_id="legal_services_authorities_act_en:section-12",
        quote="shall be entitled to legal services under this Act",
    )
    entries = load_rights(write(tmp_path, entry(), aid), [chunk(), aid_chunk])

    for domain in (LegalDomain.CRIMINAL, LegalDomain.LABOUR, LegalDomain.CONSUMER):
        selected = {item.right_id for item in rights_for(entries, domain)}
        assert "free_legal_aid" in selected, domain


def test_the_shipped_rights_all_quote_the_real_corpus() -> None:
    sections = Path("data/processed/sections")
    if not sections.is_dir():
        pytest.skip("the processed corpus is not present")
    from src.retrieval import load_processed_corpus

    entries = load_rights(
        Path("config/rights_checklists.json"), load_processed_corpus(sections)
    )
    assert entries
    # None may claim to be reviewed until a person says so.
    assert all(item.review_status == "pending_human_review" for item in entries)

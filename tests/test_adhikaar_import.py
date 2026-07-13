"""Importing a teammate's mappings must corroborate, never trust."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.import_adhikaar_mappings import (
    PROVENANCE,
    _cross_check,
    _ncrb_index,
    _section_key,
    build_candidates,
    run,
)


def test_section_key_drops_subsection_but_keeps_letter_suffix() -> None:
    assert _section_key("3(5)") == "3"
    assert _section_key("318") == "318"
    assert _section_key("376AB") == "376ab"
    assert _section_key("") == ""
    assert _section_key("N/A") == ""


def test_cross_check_reports_agreement_conflict_and_absence() -> None:
    index = {"420": {"318"}, "351": {"130"}}
    assert _cross_check("420", "318", index) == "agrees_with_ncrb"
    assert _cross_check("351", "131", index) == "conflicts_with_ncrb"
    assert _cross_check("999", "1", index) == "ipc_not_in_ncrb_snapshot"
    assert _cross_check("N/A", "117", index) == "no_ipc_ancestor"


def test_ncrb_index_pairs_every_ipc_reference_with_its_bns(tmp_path: Path) -> None:
    path = tmp_path / "ncrb.jsonl"
    path.write_text(
        json.dumps({"bns_reference": "318", "ipc_references": ["415", "420"]}) + "\n",
        encoding="utf-8",
    )
    index = _ncrb_index(path)
    assert index["415"] == {"318"} and index["420"] == {"318"}


def test_imported_candidates_are_pending_review_and_carry_provenance() -> None:
    mappings = [
        {
            "ipc_section": "420",
            "bns_section": "318",
            "offence": "Cheating",
            "ipc_title": "Cheating",
            "bns_title": "Cheating",
            "description": "d",
            "punishment": "p",
            "key_changes": "k",
            "category": "Property",
        }
    ]
    candidates = build_candidates(mappings, {"420": {"318"}}, digest="a" * 64)

    assert len(candidates) == 1
    c = candidates[0]
    # A teammate contribution is a candidate, never a served mapping.
    assert c["audit_status"] == "pending_human_review"
    assert c["provenance"] == PROVENANCE
    assert c["ncrb_cross_check"] == "agrees_with_ncrb"
    # The rich plain-language content is preserved for the reviewer.
    assert c["plain_language_description"] == "d"
    assert c["source_sha256"] == "a" * 64


def test_end_to_end_import_writes_candidates_without_serving_them(tmp_path: Path) -> None:
    source = tmp_path / "adhikaar.json"
    source.write_text(
        json.dumps(
            [
                {"ipc_section": "351", "bns_section": "131", "offence": "Assault",
                 "ipc_title": "", "bns_title": "", "description": "", "punishment": "",
                 "key_changes": "", "category": ""},
                {"ipc_section": "N/A", "bns_section": "117", "offence": "New",
                 "ipc_title": "", "bns_title": "", "description": "", "punishment": "",
                 "key_changes": "", "category": "New Provisions"},
            ]
        ),
        encoding="utf-8",
    )
    ncrb = tmp_path / "ncrb.jsonl"
    ncrb.write_text(
        json.dumps({"bns_reference": "130", "ipc_references": ["351"]}) + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.jsonl"

    assert run(["--source", str(source), "--ncrb-candidates", str(ncrb), "--output", str(out)]) == 0
    written = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]

    assert [c["ncrb_cross_check"] for c in written] == ["conflicts_with_ncrb", "no_ipc_ancestor"]
    assert all(c["audit_status"] == "pending_human_review" for c in written)

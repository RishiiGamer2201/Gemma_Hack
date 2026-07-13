"""Importing a teammate's legal-aid data must cross-check, never serve."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.import_adhikaar_legal_aid import (
    PROVENANCE,
    _slsa_cross_check,
    _split_numbers,
    build_district_candidates,
    run,
)


def test_multiple_numbers_are_split_so_any_match_counts() -> None:
    assert _split_numbers("022-22691395, 22691358") == ("02222691395", "22691358")
    verified = {"maharashtra": ("02222691395", "22691358")}
    # His single number matches the second listed number -> agreement, not conflict.
    assert _slsa_cross_check("Maharashtra", "02222691358", verified) == "agrees_with_verified"
    assert _slsa_cross_check("Maharashtra", "02299999999", verified) == "conflicts_with_verified"
    assert _slsa_cross_check("Goa", "0832111111", verified) == "state_not_in_verified_directory"
    assert _slsa_cross_check("Maharashtra", "", verified) == "no_phone_to_compare"


def test_district_candidates_are_pending_review_with_provenance() -> None:
    data = {
        "states": [
            {
                "name": "Bihar",
                "districts": [
                    {"name": "Patna", "name_hi": "पटना", "dlsa_address": "Patna Court",
                     "phone": "0612-2200000"}
                ],
            }
        ]
    }
    candidates = build_district_candidates(data, digest="b" * 64)

    assert len(candidates) == 1
    c = candidates[0]
    assert c["tier"] == "district"
    assert c["audit_status"] == "pending_human_review"
    assert c["provenance"] == PROVENANCE
    assert c["state"] == "Bihar" and c["district"] == "Patna"
    assert c["source_sha256"] == "b" * 64


def test_end_to_end_writes_candidates_and_reports_slsa_conflict(tmp_path: Path) -> None:
    source = tmp_path / "aid.json"
    source.write_text(
        json.dumps(
            {
                "helplines": [],
                "states": [
                    {
                        "name": "Maharashtra",
                        "slsa": {"phone": "022-22617612"},
                        "districts": [{"name": "Mumbai", "dlsa_address": "x", "phone": "1"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    verified = tmp_path / "verified.json"
    verified.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contacts": [],
                "fallbacks": [],
                "state_contacts": [{"state": "Maharashtra", "phone": "022-22691395, 22691358"}],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out.jsonl"

    assert run(
        ["--source", str(source), "--verified-directory", str(verified), "--output", str(out)]
    ) == 0
    written = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]

    # The one district was imported as a candidate...
    assert len(written) == 1 and written[0]["district"] == "Mumbai"
    # ...and his SLSA number genuinely differs from ours, which the cross-check catches
    # (a real disagreement, not a formatting artifact).
    from scripts.import_adhikaar_legal_aid import _verified_slsa_phones, slsa_report

    report = slsa_report(json.loads(source.read_text(encoding="utf-8")), _verified_slsa_phones(verified))
    assert report[0]["cross_check"] == "conflicts_with_verified"

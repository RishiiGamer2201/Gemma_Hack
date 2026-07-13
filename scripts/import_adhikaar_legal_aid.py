"""Import a teammate's legal-aid directory as review-pending contact candidates.

The AdhiKaar build ships 9 helplines, 20 State Legal Services Authorities, and 98
district contacts. This project already holds 34 SLSA contacts built from a verified
NALSA snapshot with provenance, so the teammate's SLSA rows add nothing there and are
used only to cross-check. What is genuinely new is the 98 district (DLSA) contacts:
this project's served directory covers Delhi districts only.

As with the mappings, nothing here is served. District contacts are written as
`pending_human_review` candidates with provenance, and each teammate SLSA is
cross-checked (by phone) against our verified state contact so a reviewer can see
whether the teammate's data agrees with a source we already trust.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

PROVENANCE = "adhikaar_teammate_contribution"
UNVERIFIED_NOTE = (
    "Contributed by the AdhiKaar teammate build. Not source-verified. A contact is "
    "time-sensitive; confirm the number and address against the official SLSA/DLSA "
    "site before it is shown to a user."
)


def _digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def _norm(value: str) -> str:
    return " ".join((value or "").casefold().split())


def _verified_slsa_phones(directory_path: Path) -> dict[str, tuple[str, ...]]:
    """Map each state to the subscriber numbers in our verified state_contacts.

    An SLSA row often lists several numbers ("022-22691395, 22691358"), so each is
    kept separately rather than concatenated -- concatenation would make a match
    against any one of them read as a conflict.
    """

    if not directory_path.is_file():
        return {}
    payload = json.loads(directory_path.read_text(encoding="utf-8"))
    phones: dict[str, tuple[str, ...]] = {}
    for contact in payload.get("state_contacts", []):
        state = _norm(str(contact.get("state", "")))
        if state:
            phones[state] = _split_numbers(str(contact.get("phone", "")))
    return phones


def _split_numbers(value: str) -> tuple[str, ...]:
    """Return each individual phone number's digits from a possibly multi-number field."""

    parts = re.split(r"[,/;]|\band\b", value or "")
    return tuple(digits for part in parts if (digits := _digits(part)))


def _slsa_cross_check(state: str, phone: str, verified: dict[str, tuple[str, ...]]) -> str:
    known = verified.get(_norm(state))
    if known is None:
        return "state_not_in_verified_directory"
    if not phone or not known:
        return "no_phone_to_compare"
    # A number can be written many ways; compare on the last 6 subscriber digits, and
    # accept a match against any of the several numbers a state office may list.
    return (
        "agrees_with_verified"
        if any(phone[-6:] == number[-6:] for number in known)
        else "conflicts_with_verified"
    )


def build_district_candidates(data: dict, digest: str) -> list[dict]:
    now = datetime.now(UTC).isoformat()
    candidates: list[dict] = []
    for state in data.get("states", []):
        state_name = str(state.get("name", "")).strip()
        for i, district in enumerate(state.get("districts", [])):
            name = str(district.get("name", "")).strip()
            candidates.append(
                {
                    "candidate_id": f"adhikaar-dlsa-{_slug(state_name)}-{i:02d}",
                    "audit_status": "pending_human_review",
                    "provenance": PROVENANCE,
                    "source_sha256": digest,
                    "imported_at": now,
                    "review_note": UNVERIFIED_NOTE,
                    "tier": "district",
                    "state": state_name,
                    "district": name,
                    "district_hi": district.get("name_hi", ""),
                    "address": district.get("dlsa_address", ""),
                    "phone": str(district.get("phone", "")).strip(),
                }
            )
    return candidates


def slsa_report(data: dict, verified: dict[str, str]) -> list[dict]:
    rows: list[dict] = []
    for state in data.get("states", []):
        slsa = state.get("slsa", {})
        state_name = str(state.get("name", "")).strip()
        phone = _digits(str(slsa.get("phone", "")))
        rows.append(
            {
                "state": state_name,
                "teammate_phone": slsa.get("phone", ""),
                "cross_check": _slsa_cross_check(state_name, phone, verified),
            }
        )
    return rows


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "state"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="import_adhikaar_legal_aid",
        description="Import AdhiKaar district legal-aid contacts as review-pending candidates.",
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--verified-directory",
        type=Path,
        default=Path("data/processed/contacts/delhi_dlsa.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/contacts/adhikaar_dlsa_candidates.jsonl"),
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        body = args.source.read_bytes()
    except OSError as exc:
        print(f"could not read source: {exc}", file=sys.stderr)
        return 1
    digest = hashlib.sha256(body).hexdigest()
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        print(f"source is not valid JSON: {exc}", file=sys.stderr)
        return 1
    if not isinstance(data, dict) or "states" not in data:
        print("source must be the AdhiKaar legal-aid directory object", file=sys.stderr)
        return 1

    verified = _verified_slsa_phones(args.verified_directory)
    candidates = build_district_candidates(data, digest)
    slsa = slsa_report(data, verified)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n" for c in candidates),
        encoding="utf-8",
    )

    print(f"imported {len(candidates)} district candidates (source sha256 {digest[:16]})")
    print(f"  -> {args.output}")
    stats = Counter(row["cross_check"] for row in slsa)
    print(f"\nSLSA cross-check against our {len(verified)} verified state contacts:")
    for verdict in (
        "agrees_with_verified",
        "conflicts_with_verified",
        "state_not_in_verified_directory",
        "no_phone_to_compare",
    ):
        print(f"  {verdict:32} {stats.get(verdict, 0)}")
    conflicts = [row["state"] for row in slsa if row["cross_check"] == "conflicts_with_verified"]
    if conflicts:
        print("  conflicting states:", ", ".join(conflicts))
    print(
        "\nDistrict candidates are pending_human_review and are NOT served. Our "
        "verified SLSA state contacts already cover routing; a reviewer confirms these "
        "district numbers before any is shown."
    )
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()

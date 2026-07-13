"""Import a teammate's IPC/BNS mappings as review-pending candidates.

The AdhiKaar project (a parallel build by a teammate) ships 95 plain-language
IPC/BNS mappings. They are richer than anything we hold, but they carry no official
source and were not verified against the gazetted codes, so this project must not
serve them as fact -- that is precisely the failure the verifier exists to prevent.

This script imports them the safe way: as `pending_human_review` candidates, each
cross-checked against our own NCRB Sankalan snapshot. The cross-check is the point.
Where the teammate's BNS section agrees with the official Sankalan row for the same
IPC section, a reviewer has corroboration; where it conflicts or is absent, the
reviewer is warned. Nothing here approves a mapping or enters the served catalogue;
it produces the worklist a human curates from.
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
    "Contributed by the AdhiKaar teammate build. Not officially sourced and not "
    "verified against the gazetted BNS. Pending human review; must not be served "
    "as a mapping until a reviewer approves it against an official source."
)


def _section_key(reference: str) -> str:
    """Reduce a BNS/IPC reference to a comparable section key.

    "3(5)" -> "3", "318" -> "318", "376AB" -> "376ab". Subsection and clause parts
    are dropped for the agreement check because the Sankalan table and the teammate
    cite provisions at different granularity; the exact reference is preserved
    separately so a reviewer sees both.
    """

    match = re.match(r"\s*(\d+[A-Za-z]*)", reference or "")
    return match.group(1).casefold() if match else ""


def _ncrb_index(candidates_path: Path) -> dict[str, set[str]]:
    """Map each IPC section key to the set of BNS section keys the Sankalan pairs it with."""

    index: dict[str, set[str]] = {}
    if not candidates_path.is_file():
        return index
    for line in candidates_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        bns_key = _section_key(str(row.get("bns_reference", "")))
        for ipc in row.get("ipc_references", []):
            index.setdefault(_section_key(str(ipc)), set()).add(bns_key)
    return index


def _cross_check(ipc_section: str, bns_section: str, index: dict[str, set[str]]) -> str:
    ipc_key = _section_key(ipc_section)
    if ipc_key in {"", "n/a"}:
        # A "New Provision" has no IPC ancestor to corroborate against.
        return "no_ipc_ancestor"
    ncrb_bns = index.get(ipc_key)
    if not ncrb_bns:
        return "ipc_not_in_ncrb_snapshot"
    return "agrees_with_ncrb" if _section_key(bns_section) in ncrb_bns else "conflicts_with_ncrb"


def build_candidates(mappings: list[dict], index: dict[str, set[str]], digest: str) -> list[dict]:
    now = datetime.now(UTC).isoformat()
    candidates: list[dict] = []
    for i, entry in enumerate(mappings):
        ipc = str(entry.get("ipc_section", "")).strip()
        bns = str(entry.get("bns_section", "")).strip()
        candidates.append(
            {
                "candidate_id": f"adhikaar-{i:03d}",
                "audit_status": "pending_human_review",
                "provenance": PROVENANCE,
                "source_sha256": digest,
                "imported_at": now,
                "review_note": UNVERIFIED_NOTE,
                "ipc_section": ipc,
                "bns_section": bns,
                "offence": entry.get("offence", ""),
                "ipc_title": entry.get("ipc_title", ""),
                "bns_title": entry.get("bns_title", ""),
                "plain_language_description": entry.get("description", ""),
                "punishment": entry.get("punishment", ""),
                "key_changes": entry.get("key_changes", ""),
                "category": entry.get("category", ""),
                # The independent corroboration signal from our own snapshot.
                "ncrb_cross_check": _cross_check(ipc, bns, index),
            }
        )
    return candidates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="import_adhikaar_mappings",
        description="Import AdhiKaar IPC/BNS mappings as review-pending candidates.",
    )
    parser.add_argument("--source", type=Path, required=True, help="AdhiKaar ipc_bns_mapping.json")
    parser.add_argument(
        "--ncrb-candidates",
        type=Path,
        default=Path("data/processed/mappings/ipc_bns_candidates.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/mappings/adhikaar_candidates.jsonl"),
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
        mappings = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        print(f"source is not valid JSON: {exc}", file=sys.stderr)
        return 1
    if not isinstance(mappings, list) or not mappings:
        print("source must be a non-empty JSON list of mappings", file=sys.stderr)
        return 1

    index = _ncrb_index(args.ncrb_candidates)
    candidates = build_candidates(mappings, index, digest)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(
            json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n" for c in candidates
        ),
        encoding="utf-8",
    )

    stats = Counter(c["ncrb_cross_check"] for c in candidates)
    print(f"imported {len(candidates)} candidates (source sha256 {digest[:16]})")
    print(f"  -> {args.output}")
    for verdict in (
        "agrees_with_ncrb",
        "conflicts_with_ncrb",
        "ipc_not_in_ncrb_snapshot",
        "no_ipc_ancestor",
    ):
        print(f"  {verdict:26} {stats.get(verdict, 0)}")
    print(
        "\nAll candidates are pending_human_review and are NOT served. "
        "A reviewer must approve each against an official source before it becomes a "
        "mapping. Start with the conflicts_with_ncrb rows."
    )
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()

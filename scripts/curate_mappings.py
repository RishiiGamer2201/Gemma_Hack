"""Turn NCRB Sankalan candidates into a mapping worksheet a reviewer can approve.

A mapping is a legal judgement. Sections were split, merged, reworded, and dropped
when the IPC became the BNS, so no script can decide that IPC 420 corresponds to
BNS 318 — a person has to. This produces the worksheet for that person: the
candidate pairs, the BNS text we actually hold, and a ready-to-fill record.

It approves nothing. Every row is emitted as `pending_human_review`, and
`src/api/state.py` serves only mappings a human has marked reviewed.

The default selection targets the plan's brief: theft, cheating, breach of trust,
assault, harassment, intimidation, public-order offences, and document offences.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from src.retrieval import CorpusLoadError, load_processed_corpus

# The offence families the plan asks for first. Matched against the Sankalan row's
# own BNS heading text, not guessed.
PRIORITY_TERMS = (
    "theft",
    "extortion",
    "robbery",
    "dacoity",
    "cheating",
    "criminal breach of trust",
    "misappropriation",
    "assault",
    "criminal force",
    "hurt",
    "grievous hurt",
    "wrongful restraint",
    "wrongful confinement",
    "criminal intimidation",
    "harassment",
    "stalking",
    "outraging",
    "defamation",
    "forgery",
    "false document",
    "counterfeit",
    "public tranquillity",
    "unlawful assembly",
    "rioting",
    "affray",
    "mischief",
    "trespass",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="curate_mappings",
        description="Emit an IPC/BNS mapping worksheet for a human legal reviewer.",
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("data/processed/mappings/ipc_bns_candidates.jsonl"),
    )
    parser.add_argument("--sections-dir", type=Path, default=Path("data/processed/sections"))
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--output", type=Path, default=Path("docs/ipc_bns_worksheet.md"))
    parser.add_argument(
        "--records",
        type=Path,
        default=Path("config/ipc_bns_mappings.json"),
        help="Ready-to-fill records the reviewer edits and marks reviewed.",
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        lines = args.candidates.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"could not read candidates: {exc}", file=sys.stderr)
        return 1
    try:
        documents = load_processed_corpus(args.sections_dir)
    except CorpusLoadError as exc:
        print(f"corpus unavailable: {exc}", file=sys.stderr)
        return 1

    bns_text = {
        str(document.metadata.get("section")): str(document.metadata.get("source_text", ""))
        for document in documents
        if str(document.metadata.get("corpus_source_id", "")).startswith("bns_2023")
    }

    candidates = [json.loads(line) for line in lines if line.strip()]
    # Only rows that actually pair an IPC section with a BNS one are worth a
    # reviewer's time; "new in BNS" and "deleted" rows carry no mapping to approve.
    pairs = [
        item
        for item in candidates
        if item.get("ipc_references") and item.get("relationship_hint") != "new_in_bns"
    ]

    def priority(item: dict) -> int:
        text = f"{item.get('bns_text', '')} {item.get('ipc_text', '')}".casefold()
        return sum(term in text for term in PRIORITY_TERMS)

    ranked = sorted(pairs, key=lambda item: (-priority(item), item["row_id"]))
    selected = [item for item in ranked if priority(item) > 0][: args.limit]
    if len(selected) < args.limit:
        # Top up with the remaining pairs so the reviewer still gets a full sheet.
        rest = [item for item in ranked if item not in selected]
        selected += rest[: args.limit - len(selected)]

    lines_out: list[str] = [
        "# IPC to BNS mapping worksheet",
        "",
        f"{len(selected)} candidate pairs drawn from the verified NCRB Sankalan snapshot "
        f"({len(pairs)} pairs available of {len(candidates)} rows).",
        "",
        "**This is a legal judgement, not a lookup.** When the IPC became the BNS, "
        "provisions were split, merged, reworded, and dropped. A matching number is not "
        "a matching offence. Nothing here is approved by running this script: every "
        "record ships as `pending_human_review`, and the app serves only mappings a "
        "reviewer has marked `reviewed`.",
        "",
        "For each row, decide the relationship and record it:",
        "",
        "- `exact` — one IPC provision, one BNS provision, same offence",
        "- `partial` — overlaps but the scope changed",
        "- `split` — one IPC provision became several BNS provisions",
        "- `merged` — several IPC provisions became one",
        "- `omitted` — dropped from the BNS",
        "- `no_direct_equivalent`",
        "",
        "Then edit `config/ipc_bns_mappings.json`, fill `change_notes` and `reviewed_by`, "
        "and set `review_status` to `reviewed`.",
        "",
        "---",
        "",
    ]

    records: list[dict] = []
    for number, item in enumerate(selected, start=1):
        bns_section = str(item["bns_reference"]).split("(")[0]
        held = bns_text.get(bns_section, "")
        lines_out += [
            f"## {number}. IPC {', '.join(item['ipc_references'])} → BNS {item['bns_reference']}",
            "",
            f"- **Sankalan hint:** `{item['relationship_hint']}`",
            f"- **Sankalan BNS text:** {item['bns_text'][:220]}",
            f"- **Sankalan IPC text:** {item['ipc_text'][:220]}",
            f"- **Source:** {item['official_url']} (retrieved {item['retrieved_at']})",
            "",
            "BNS text we actually hold for that section:",
            "",
            "```text",
            (held[:700] + ("…" if len(held) > 700 else ""))
            if held
            else "NOT IN CORPUS — this section's text is not in the build, so the app "
            "could not quote it even if the mapping were approved.",
            "```",
            "",
            "Reviewer: relationship = ____________  [ ] approved  [ ] rejected",
            "",
            "Notes on what changed: ",
            "",
            "---",
            "",
        ]
        records.append(
            {
                "mapping_id": f"ipc-{'-'.join(item['ipc_references'])}-bns-{bns_section}",
                "source_provisions": [
                    {"code": "IPC", "section": reference}
                    for reference in item["ipc_references"]
                ],
                "target_provisions": [{"code": "BNS", "section": bns_section}],
                "mapping_type": "REVIEWER_MUST_SET",
                "offence_names": ["REVIEWER_MUST_SET"],
                "plain_language_description": "REVIEWER_MUST_SET",
                "change_notes": "REVIEWER_MUST_SET",
                "official_source_url": item["official_url"],
                "official_source_id": "ncrb_sankalan_ipc_bns",
                "reviewed_by": "REVIEWER_MUST_SET",
                "reviewed_at": "REVIEWER_MUST_SET",
                "review_status": "pending_human_review",
                "_sankalan_hint": item["relationship_hint"],
                "_bns_text_in_corpus": bool(held),
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines_out), encoding="utf-8")
    args.records.parent.mkdir(parents=True, exist_ok=True)
    args.records.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "review_status": "pending_human_review",
                "note": "Nothing here is served until review_status on a record is "
                "'reviewed' and the REVIEWER_MUST_SET fields are filled.",
                "mappings": records,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    missing = sum(1 for record in records if not record["_bns_text_in_corpus"])
    print(f"wrote {args.output} and {args.records} ({len(records)} candidates)")
    if missing:
        print(f"{missing} candidate(s) point at a BNS section whose text is NOT in the corpus.")
    print("Nothing is approved. A human reviewer must sign off each mapping.")
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()

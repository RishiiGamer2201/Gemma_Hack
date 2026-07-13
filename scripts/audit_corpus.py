"""Emit a chunk-audit worksheet for a human source reviewer.

The corpus exit gate requires a person to check sampled chunks against the original
PDFs. That check is theirs to make -- no script can do it, and this one does not
pretend to. What it does is remove the tedium: it draws a deterministic random
sample, and for each chunk prints the act, section, page, official URL, and the
exact text that was extracted, so the reviewer can open the PDF at that page and
compare.

The reviewer marks each row pass/fail in the emitted file. Nothing here approves a
chunk; the `pending_human_review` status on every chunk stays until a person says
otherwise.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections.abc import Sequence
from pathlib import Path

from src.retrieval import CorpusLoadError, load_processed_corpus

CHECKS = (
    "act name matches the source",
    "section number matches the source",
    "text starts and ends at the right boundary (no bleed from the next section)",
    "provisos, explanations, and illustrations that belong to it are attached",
    "page number is right",
    "official URL opens the right document",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit_corpus",
        description="Sample corpus chunks into a worksheet for a human source reviewer.",
    )
    parser.add_argument("--sections-dir", type=Path, default=Path("data/processed/sections"))
    parser.add_argument("--sample", type=int, default=20)
    parser.add_argument(
        "--seed",
        type=int,
        default=20260715,
        help="Fixed so the same sample can be re-drawn and a second reviewer can "
        "check the same chunks.",
    )
    parser.add_argument("--source-id", action="append", help="Restrict to these corpus sources.")
    parser.add_argument("--output", type=Path, default=Path("docs/corpus_audit_worksheet.md"))
    parser.add_argument("--excerpt-chars", type=int, default=1200)
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        documents = load_processed_corpus(args.sections_dir)
    except CorpusLoadError as exc:
        print(f"corpus unavailable: {exc}", file=sys.stderr)
        return 1

    pool = [
        document
        for document in documents
        if not args.source_id
        or str(document.metadata.get("corpus_source_id")) in set(args.source_id)
    ]
    if not pool:
        print("no chunks matched the requested sources", file=sys.stderr)
        return 1
    if args.sample > len(pool):
        print(f"only {len(pool)} chunks available; sampling all of them")

    sample = random.Random(args.seed).sample(pool, min(args.sample, len(pool)))
    sample.sort(key=lambda document: document.source_id)

    lines: list[str] = [
        "# Corpus audit worksheet",
        "",
        f"Sample of {len(sample)} chunks from {len(pool)} (seed `{args.seed}`, so a second "
        "reviewer can draw the identical sample).",
        "",
        "**This is a human check.** Open each official URL at the given page and compare it "
        "with the extracted text below. Nothing in the corpus is approved by running this "
        "script; every chunk stays `pending_human_review` until a person signs it off.",
        "",
        "The exit gate in `IMPLEMENTATION_PLAN.md` is: at least 95% of the sample has the "
        "correct act, section, text boundaries, page, and source URL.",
        "",
        "For each chunk, mark every check:",
        "",
    ]
    lines += [f"- {check}" for check in CHECKS]
    lines += ["", "---", ""]

    for number, document in enumerate(sample, start=1):
        metadata = document.metadata
        text = str(metadata.get("source_text", ""))
        excerpt = text[: args.excerpt_chars]
        truncated = len(text) > args.excerpt_chars
        effective = metadata.get("effective_from")
        lines += [
            f"## {number}. `{document.source_id}`",
            "",
            f"- **Act:** {metadata.get('act')}",
            f"- **Section:** {metadata.get('section')}",
            f"- **Heading:** {metadata.get('heading')}",
            f"- **Page:** {metadata.get('page_start')}"
            + (
                f"–{metadata.get('page_end')}"
                if metadata.get("page_end") != metadata.get("page_start")
                else ""
            ),
            f"- **Effective from:** {effective if effective else '**not proven** — see the '
            'commencement warning'}",
            f"- **Status:** {metadata.get('status')} | **Priority:** {metadata.get('priority')}",
            f"- **OCR used:** {metadata.get('ocr_used')} | "
            f"**Scan review flagged:** {metadata.get('chunk_scan_review_required')}",
            f"- **Official URL:** {metadata.get('official_url')}",
            f"- **SHA-256:** `{metadata.get('sha256')}`",
            "",
            "Extracted text:",
            "",
            "```text",
            excerpt + ("\n… [truncated for the worksheet]" if truncated else ""),
            "```",
            "",
            "Reviewer: [ ] pass  [ ] fail — notes: ",
            "",
            "---",
            "",
        ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.output} ({len(sample)} chunks, seed {args.seed})")
    print("This is a worksheet, not an approval. A person must sign off each chunk.")

    summary = {
        "seed": args.seed,
        "sampled": len(sample),
        "pool": len(pool),
        "chunk_ids": [document.source_id for document in sample],
    }
    print(json.dumps(summary["chunk_ids"][:3], indent=None), "...")
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()

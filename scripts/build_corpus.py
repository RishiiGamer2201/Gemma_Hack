"""Build deterministic corpus chunks from verified local official-source files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Support ``python scripts/build_corpus.py`` from the repository root without an
# editable installation.  Importing the pipeline performs no network calls.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.corpus.pipeline import CorpusBuildError, build_corpus  # noqa: E402


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build review-pending JSONL chunks from verified local downloads."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("config/official_sources.json"),
        help="reviewed official-source manifest",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw/official_law"),
        help="directory containing downloaded files and receipt sidecars",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/sections"),
        help="directory for per-source JSONL and build_report.json",
    )
    parser.add_argument(
        "--source-id",
        action="append",
        dest="source_ids",
        help="build only this manifest source ID; may be repeated",
    )
    parser.add_argument(
        "--allow-empty-pages",
        action="store_true",
        help="allow PDFs with blank extracted pages; the count remains in the report",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        report = build_corpus(
            args.manifest,
            args.raw_dir,
            args.output_dir,
            source_ids=args.source_ids,
            allow_empty_pages=args.allow_empty_pages,
        )
    except (CorpusBuildError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for result in report.successes:
        print(
            f"BUILT {result.source_id}: pages={result.page_count} "
            f"chunks={result.chunk_count} empty_pages={result.empty_page_count} "
            f"parser={result.parser} sha256={result.sha256}"
        )
    for failure in report.failures:
        requirement = "required" if failure.required else "optional"
        print(
            f"FAILED {failure.source_id} ({requirement}): {failure.error}",
            file=sys.stderr,
        )
    print(f"REPORT {args.output_dir / 'build_report.json'}")
    return 1 if report.required_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

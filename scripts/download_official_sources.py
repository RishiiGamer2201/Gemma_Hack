"""Download manifest-approved official sources with restrictive network controls."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.corpus.downloader import DownloadError, download_source  # noqa: E402
from src.corpus.manifest import load_manifest  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "config" / "official_sources.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "official_law",
    )
    parser.add_argument("--source-id", action="append", dest="source_ids")
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--max-bytes", type=int, default=50 * 1024 * 1024)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--list",
        action="store_true",
        help="Validate the manifest and list source IDs without network access",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = load_manifest(args.manifest)
    selected = set(args.source_ids or [])
    known = {source.source_id for source in manifest.sources}
    unknown = selected - known
    if unknown:
        print(f"Unknown source_id values: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    if args.list:
        for source in manifest.sources:
            if not selected or source.source_id in selected:
                print(f"{source.source_id}\t{source.title}\t{source.url}")
        return 0

    failures = 0
    for source in manifest.sources:
        if selected and source.source_id not in selected:
            continue
        try:
            receipt = download_source(
                source,
                args.output_dir,
                timeout=args.timeout,
                max_bytes=args.max_bytes,
                overwrite=args.overwrite,
            )
        except (DownloadError, FileExistsError, ValueError) as exc:
            failures += 1
            print(f"FAILED {source.source_id}: {exc}", file=sys.stderr)
            continue
        print(f"VERIFIED {receipt.source_id}: {receipt.filename} sha256={receipt.sha256}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

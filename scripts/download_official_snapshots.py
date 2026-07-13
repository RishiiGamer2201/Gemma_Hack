"""Download reviewed official web pages for offline mapping and directories."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.corpus.snapshots import (  # noqa: E402
    SnapshotError,
    download_snapshot,
    load_snapshot_manifest,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("config/official_web_sources.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/official_web"))
    parser.add_argument("--source-id", action="append", dest="source_ids")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = load_snapshot_manifest(args.manifest)
        requested = set(args.source_ids or [])
        known = {source.source_id for source in manifest.sources}
        unknown = sorted(requested - known)
        if unknown:
            raise ValueError("unknown source_id value(s): " + ", ".join(unknown))
        selected = [source for source in manifest.sources if not requested or source.source_id in requested]
        if args.list:
            for source in selected:
                print(f"{source.source_id}\t{source.title}\t{source.url}")
            return 0
        failures = 0
        for source in selected:
            try:
                receipt = download_snapshot(source, args.output_dir, overwrite=args.overwrite)
            except (SnapshotError, FileExistsError, OSError) as exc:
                failures += 1
                print(f"FAILED {source.source_id}: {exc}", file=sys.stderr)
            else:
                print(f"VERIFIED {source.source_id}: sha256={receipt.sha256}")
        return 1 if failures else 0
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

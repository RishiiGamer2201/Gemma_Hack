"""Build review-pending IPC/BNS candidates from a verified NCRB snapshot."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.legal_time.sankalan import SankalanError, parse_verified_sankalan, write_candidates  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path("data/raw/official_web/ncrb_sankalan_ipc_bns.html"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/mappings/ipc_bns_candidates.jsonl"),
    )
    args = parser.parse_args(argv)
    try:
        candidates = parse_verified_sankalan(args.snapshot)
        write_candidates(candidates, args.output)
    except (SankalanError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"BUILT {len(candidates)} review-pending mapping candidates -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Query the verified local legal-aid directory and emit JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.legal_aid.finder import LegalAidFinder, LegalAidFinderError  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory",
        type=Path,
        default=ROOT / "data" / "processed" / "contacts" / "delhi_dlsa.json",
    )
    parser.add_argument("--district", required=True, help="District or city to match")
    parser.add_argument("--state", help="Optional state or union territory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = LegalAidFinder(args.directory).find(args.district, state=args.state)
    except LegalAidFinderError as exc:
        error = {"error": {"code": exc.code, "message": str(exc)[:500]}}
        print(json.dumps(error, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    print(
        json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

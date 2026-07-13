"""Print one validated offline evidence checklist as JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.actions.checklists import ChecklistCatalog, ChecklistError  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalogue", type=Path, default=ROOT / "config" / "evidence_checklists.json"
    )
    parser.add_argument(
        "--template",
        required=True,
        help="Exact template ID; hyphens are normalized to underscores",
    )
    args = parser.parse_args(argv)
    try:
        template = ChecklistCatalog(args.catalogue).get(args.template)
    except ChecklistError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(template.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Run deterministic text intake locally and emit confirmation-ready JSON."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.intake import process_text_intake  # noqa: E402
from src.models import LegalDomain  # noqa: E402


def emit_json(payload: object) -> None:
    """Write UTF-8 even when the Windows console defaults to a legacy code page."""

    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        sys.stdout.write(rendered)
    else:
        buffer.write(rendered.encode("utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline, non-persistent legal text intake")
    parser.add_argument("--text", required=True)
    parser.add_argument("--summary")
    parser.add_argument("--incident-date", type=date.fromisoformat)
    parser.add_argument("--jurisdiction")
    parser.add_argument("--location")
    parser.add_argument("--domain", choices=[item.value for item in LegalDomain], default="other")
    parser.add_argument("--party", action="append", default=[])
    parser.add_argument("--material-fact", action="append", default=[])
    parser.add_argument("--document", action="append", default=[])
    parser.add_argument("--missing-fact", action="append", default=[])
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = process_text_intake(
            args.text,
            incident_summary=args.summary,
            incident_date=args.incident_date,
            jurisdiction=args.jurisdiction,
            location=args.location,
            domain=LegalDomain(args.domain),
            parties=tuple(args.party),
            material_facts=tuple(args.material_fact),
            documents=tuple(args.document),
            missing_material_facts=tuple(args.missing_fact),
        )
    except (TypeError, ValueError) as exc:
        emit_json({"error": str(exc)})
        return 2
    emit_json(result.model_dump(mode="json"))
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()

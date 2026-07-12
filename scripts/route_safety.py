"""Route confirmed facts through the deterministic offline safety boundary."""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import ValidationError  # noqa: E402

from src.intake import UrgencyCategory  # noqa: E402
from src.models import ConfirmedFacts, LegalDomain  # noqa: E402
from src.safety import route_confirmed_case  # noqa: E402


def emit_json(payload: object) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        sys.stdout.write(rendered)
    else:
        buffer.write(rendered.encode("utf-8"))


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline safety routing for confirmed facts")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--facts-json", help="Inline ConfirmedFacts JSON object")
    source.add_argument("--summary", help="Confirmed incident summary")
    parser.add_argument("--incident-date", type=date.fromisoformat)
    parser.add_argument("--jurisdiction")
    parser.add_argument("--location")
    parser.add_argument("--domain", choices=[item.value for item in LegalDomain], default="other")
    parser.add_argument("--party", action="append", default=[])
    parser.add_argument("--material-fact", action="append", default=[])
    parser.add_argument("--missing-fact", action="append", default=[])
    parser.add_argument(
        "--confirmed-at",
        type=datetime.fromisoformat,
        help="Timezone-aware ISO timestamp recording explicit user confirmation",
    )
    parser.add_argument(
        "--urgency",
        action="append",
        choices=[item.value for item in UrgencyCategory],
    )
    parser.add_argument("--document-text", action="append", default=[])
    parser.add_argument("--requested-output")
    args = parser.parse_args(argv)
    try:
        if args.facts_json is not None:
            payload = json.loads(args.facts_json)
            if not isinstance(payload, dict):
                raise ValueError("facts JSON must be an object")
            facts = ConfirmedFacts.model_validate(payload)
        else:
            facts = ConfirmedFacts(
                incident_summary=args.summary,
                incident_date=args.incident_date,
                jurisdiction=args.jurisdiction,
                location=args.location,
                domain=LegalDomain(args.domain),
                parties=tuple(args.party),
                material_facts=tuple(args.material_fact),
                missing_material_facts=tuple(args.missing_fact),
                confirmed=args.confirmed_at is not None,
                confirmed_at=args.confirmed_at,
            )
        decision = route_confirmed_case(
            facts,
            confirmed_urgencies=tuple(UrgencyCategory(value) for value in args.urgency or ()),
            untrusted_document_texts=tuple(args.document_text),
            requested_output=args.requested_output,
        )
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
        emit_json({"error": str(exc)})
        return 2
    emit_json(decision.model_dump(mode="json"))
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()

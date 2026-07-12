"""Build the offline Delhi DLSA contact directory from a verified snapshot."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.legal_aid.directory import (  # noqa: E402
    DirectoryError,
    build_delhi_contacts,
    build_tele_law_fallback,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path("data/raw/official_web/dslsa_directory.html"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/contacts/delhi_dlsa.json"),
    )
    parser.add_argument(
        "--tele-law-snapshot",
        type=Path,
        default=Path("data/raw/official_web/tele_law_pib_2026.html"),
    )
    args = parser.parse_args(argv)
    try:
        contacts = build_delhi_contacts(args.snapshot)
        fallback = build_tele_law_fallback(args.tele_law_snapshot)
        payload = {
            "schema_version": 1,
            "contacts": [contact.model_dump(mode="json") for contact in contacts],
            "fallbacks": [fallback.model_dump(mode="json")],
        }
        data = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{args.output.name}.", dir=args.output.parent)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, args.output)
    except (DirectoryError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"BUILT {len(contacts)} verified Delhi DLSA contacts -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

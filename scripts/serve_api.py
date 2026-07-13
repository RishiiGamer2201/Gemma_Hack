"""Run the local API on the loopback interface only.

The host is not configurable from the command line on purpose: binding to 0.0.0.0
would expose a service that holds confirmed case facts to the local network.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOOPBACK_HOST = "127.0.0.1"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--log-level",
        default="warning",
        choices=("critical", "error", "warning", "info"),
        help="Request logs can contain case text; the default keeps them quiet.",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")

    try:
        import uvicorn
    except ImportError:
        print("uvicorn is not installed; install the project's 'api' extra", file=sys.stderr)
        return 2

    from src.api import create_app

    uvicorn.run(
        create_app(),
        host=LOOPBACK_HOST,
        port=args.port,
        log_level=args.log_level,
        access_log=False,
        server_header=False,
        date_header=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

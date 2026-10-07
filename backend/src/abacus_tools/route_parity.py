"""`make route-parity ROUTE=direct|bedrock` (SPEC-010 AC-5): run the parity check with real
credentials, write `docs/operations/route-parity/<route>-<date>.json`, and print the SHA-256 to
record in `route_parity` (TASK-025 D2). Exits non-zero when the route fails parity."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path
from typing import cast

from abacus.ai_gateway.routes.parity import check_route
from abacus.kernel.config import Route

REPORTS = Path(__file__).resolve().parents[3] / "docs" / "operations" / "route-parity"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="route-parity")
    parser.add_argument("--route", choices=("direct", "bedrock"), required=True)
    args = parser.parse_args(argv)
    route = cast(Route, args.route)
    report = asyncio.run(check_route(route))
    body = report.to_json() + "\n"
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"{route}-{report.checked_on}.json"
    path.write_text(body, encoding="utf-8")
    digest = hashlib.sha256(body.encode()).hexdigest()
    print(f"{path}\nreport_sha256={digest}\npassed={report.passed}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())

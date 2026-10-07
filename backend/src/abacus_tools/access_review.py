"""`make access-review QUARTER=2026Q4` (SPEC-012 AC-10, Q5): every break-glass session in the
quarter across firms, for the SOC 2 access review. Reads only through `support_sessions_review`,
which the owner role alone may execute (TASK-027 D4), so it runs with the migrations
credentials. Reasons appear as SHA-256 fingerprints; their text stays in each firm's
trail. Writes `docs/operations/access-reviews/<quarter>.json`; the founder signs it off in the
commit."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import asyncpg

from abacus.kernel.config import settings

REPORTS = Path(__file__).resolve().parents[3] / "docs" / "operations" / "access-reviews"
_QUARTER = re.compile(r"^(\d{4})Q([1-4])$")


def quarter_bounds(quarter: str) -> tuple[datetime, datetime]:
    match = _QUARTER.fullmatch(quarter)
    if match is None:
        raise ValueError("QUARTER looks like 2026Q4")
    year, q = int(match.group(1)), int(match.group(2))
    start = datetime(year, 3 * q - 2, 1, tzinfo=UTC)
    end = (
        datetime(year + 1, 1, 1, tzinfo=UTC)
        if q == 4
        else datetime(year, 3 * q + 1, 1, tzinfo=UTC)
    )
    return start, end


def _plain(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, (bool, int)):
        return value
    return str(value)


async def review(url: str, quarter: str) -> dict[str, object]:
    start, end = quarter_bounds(quarter)
    conn = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        rows = await conn.fetch("SELECT * FROM support_sessions_review($1, $2)", start, end)
    finally:
        await conn.close()
    sessions = [{k: _plain(v) for k, v in dict(r).items()} for r in rows]
    return {
        "quarter": quarter,
        "generated_at": datetime.now(UTC).isoformat(),
        "sessions": sessions,
        "totals": {
            "sessions": len(sessions),
            "emergency": sum(1 for s in sessions if s["emergency"]),
            "requests": sum(int(str(s["requests"] or 0)) for s in sessions),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="access-review")
    parser.add_argument("--quarter", required=True)
    args = parser.parse_args(argv)
    url = settings().migrations_database_url
    if url is None:
        print(
            "migrations_database_url is not set (the owner role runs the review)", file=sys.stderr
        )
        return 2
    try:
        report = asyncio.run(review(url.get_secret_value(), args.quarter))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / f"{args.quarter}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{path}: {report['totals']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

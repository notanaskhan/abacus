"""Set one firm's daily OCR page cap (P-11-T33; P-11 §cost, R9; RB-68).

Run: python -m abacus_tools.ocr_daily_cap <tenant-id> <pages> --raised-by NAME [--second-by NAME]
     --reason TEXT
     python -m abacus_tools.ocr_daily_cap <tenant-id> --show

Writes a new `ocr_daily_caps` row as a platform session (`system`); the latest row is the firm's
cap, the default is 5,000 pages. A cap above the default needs a second, different operator (R9:
"cap raised by both founders"); the table's CHECK refuses it otherwise, and this tool says so
before it tries. On staging or production it runs as an ECS one-off task, never from a laptop
against a shared database.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.evidence.api import DAILY_PAGE_CAP, daily_page_cap, set_daily_page_cap

ACTOR = "platform:ocr_daily_cap"


def problem(pages: int, raised_by: str, second_by: str | None, reason: str) -> str | None:
    """What the table would refuse, said before the write (the CHECKs stay the rule)."""
    if not 1 <= pages <= 100_000:
        return "pages must be between 1 and 100,000"
    if len(reason.strip()) < 10:
        return "the reason needs at least 10 characters"
    if pages > DAILY_PAGE_CAP and (
        second_by is None or second_by.strip().lower() == raised_by.strip().lower()
    ):
        return f"a cap above {DAILY_PAGE_CAP:,} needs a second, different operator (R9)"
    return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.ocr_daily_cap")
    parser.add_argument("tenant_id", type=UUID)
    parser.add_argument("pages", type=int, nargs="?")
    parser.add_argument("--raised-by")
    parser.add_argument("--second-by")
    parser.add_argument("--reason", default="")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args(argv)
    tenant = TenantContext(args.tenant_id, "system", ACTOR)
    if args.show:
        print(f"cap {asyncio.run(daily_page_cap(tenant)):,} pages a day")
        return 0
    if args.pages is None or not args.raised_by:
        parser.error("pages and --raised-by are required unless --show")
    refused = problem(args.pages, args.raised_by, args.second_by, args.reason)
    if refused:
        print(refused, file=sys.stderr)
        return 2
    cap_id = asyncio.run(
        set_daily_page_cap(
            tenant,
            pages=args.pages,
            raised_by=args.raised_by,
            second_by=args.second_by,
            reason=args.reason,
        )
    )
    print(f"set {args.pages:,} pages a day ({cap_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

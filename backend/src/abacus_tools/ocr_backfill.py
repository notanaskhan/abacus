"""OCR a firm's `not_scannable` pages after its flag turns on (P-11-T25; P-11 AC7.4).

Run: python -m abacus_tools.ocr_backfill <tenant-id>

Starts (or joins) the tenant's `ocr_backfill:<tenant>` workflow on the background queue. It runs
the idempotent activities new uploads run, behind the same gate, and never changes evidence. On
staging or production it runs as an ECS one-off task, never from a laptop against a shared
database.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import UUID

from abacus.modules.evidence.api import start_ocr_backfill


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.ocr_backfill")
    parser.add_argument("tenant_id", type=UUID)
    args = parser.parse_args(argv)
    print(f"started {asyncio.run(start_ocr_backfill(args.tenant_id))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

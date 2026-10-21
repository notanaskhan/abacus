"""Read a firm's earlier PDF uploads again with the current extractor (TASK-344).

Run: python -m abacus_tools.reextract <tenant-id> [--dry-run] [--limit N]

Extraction v3 (TASK-334) keeps where each line was printed, so values can point back to it;
uploads read by v1 or v2 don't have that. This runs the ordinary upload processing step on each
PDF upload and inbox file without a v3 reading. It is idempotent (one extraction per version per
upload), audited like any extraction, and never changes the evidence: the earlier reading stays,
and readers take the newest (TASK-333). Checks aren't re-run; their results don't depend on
positions.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from uuid import UUID

from abacus.modules.evidence.api import process_upload, stale_pdfs


async def _run(tenant_id: UUID, *, dry_run: bool, limit: int) -> Counter[str]:
    todo = await stale_pdfs(tenant_id, limit)
    outcome: Counter[str] = Counter()
    if dry_run:
        outcome["to_read"] = len(todo)
        return outcome
    for given in todo:
        try:
            outcome[await process_upload(given)] += 1
        except Exception:  # one unreadable or missing file mustn't stop the rest
            outcome["failed"] += 1
    return outcome


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.reextract")
    parser.add_argument("tenant_id", type=UUID)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args(argv)
    outcome = asyncio.run(_run(args.tenant_id, dry_run=args.dry_run, limit=args.limit))
    print(", ".join(f"{k} {v}" for k, v in sorted(outcome.items())) or "nothing to read")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

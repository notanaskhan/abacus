"""Re-project a firm's Home client activity from its published events (I-01-T12; DEC-900).

Run: python -m abacus_tools.reproject_home_activity <tenant-id>

`home_activity_items` is a rebuildable projection, never the record of anything. This runs
`practice.api.rebuild_home_activity` for one firm: the firm's published allowlisted outbox events
of the last 90 days (read through the relay role, that firm only), projected again inside the
firm's own row-level security as the system. It is idempotent: rows already there are untouched,
so a second run inserts nothing. On staging it runs as an ECS one-off task, never from a laptop
against the staging database (the working agreement: no local build against a hosted database).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import UUID


async def _run(tenant_id: UUID) -> int:
    from abacus.modules.practice.api import rebuild_home_activity

    return await rebuild_home_activity(tenant_id)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.reproject_home_activity")
    parser.add_argument("tenant_id", type=UUID)
    args = parser.parse_args(argv)
    print(f"rows inserted {asyncio.run(_run(args.tenant_id))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

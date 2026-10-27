"""Re-project a firm's human gates from the owners' records (I-01-T04; C13; DEC-320).

Run: python -m abacus_tools.reproject_human_gates <tenant-id>

`human_gates` is a rebuildable projection, never the record of anything. This runs
`review.api.rebuild_human_gates` for one firm: every registered gate source over every
engagement, inside the firm's own row-level security as the system, so it reaches no other
firm's rows. It is idempotent: a second run writes nothing, and rows already right are never
touched (their `updated_at` stays). Run it after a release that adds a projected column (0223's
`office_id`, `blocked`, `sort_hint`) or changes a source, and after an office change, which emits
no C13 event yet. On staging it runs as an ECS one-off task, never from a laptop against the
staging database (the working agreement: no local build against a hosted database).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from importlib import import_module
from uuid import UUID

from abacus.modules import MODULES


async def _run(tenant_id: UUID) -> int:
    # Every owner registers its gate sources when its api is imported (as the worker does).
    for name in MODULES:
        import_module(f"abacus.modules.{name}.api")
    from abacus.modules.review.api import rebuild_human_gates

    return await rebuild_human_gates(tenant_id)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.reproject_human_gates")
    parser.add_argument("tenant_id", type=UUID)
    args = parser.parse_args(argv)
    print(f"rows written {asyncio.run(_run(args.tenant_id))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

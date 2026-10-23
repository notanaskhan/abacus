"""Give a firm's earlier PDF uploads a word layer (P-03-T05; P-03 §4.5).

Run: python -m abacus_tools.trust_layer_backfill <tenant-id>

Starts (or joins) the tenant's `trust_layer_backfill:<tenant>` workflow on the background queue.
It runs the same idempotent `upload.words` activity new uploads run, and never changes evidence.
On staging it runs as an ECS one-off task, never from a laptop against the staging database (the
working agreement: no local build against a hosted database).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import UUID

from abacus.modules.evidence.api import start_trust_layer_backfill


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.trust_layer_backfill")
    parser.add_argument("tenant_id", type=UUID)
    args = parser.parse_args(argv)
    print(f"started {asyncio.run(start_trust_layer_backfill(args.tenant_id))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

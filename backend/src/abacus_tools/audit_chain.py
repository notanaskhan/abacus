"""Seal and verify a firm's audit hash chain (Q-02-T21; AC-26). Operators and CI only.

    make audit-chain-verify TENANT=<uuid>       # exits 1 and names the bad checkpoints
    python -m abacus_tools.audit_chain seal --tenant <uuid>

The checkpoint job and the nightly verifier call the same `kernel.uow.chain` functions; until
their Temporal Schedules exist this is how the chain is sealed and checked.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import UUID

from abacus.kernel.db import dispose_engine
from abacus.kernel.uow.chain import seal_checkpoint, verify_chain


async def _run(command: str, tenant: UUID) -> int:
    try:  # the engine comes from settings (ABACUS_DATABASE_URL)
        if command == "seal":
            sealed = await seal_checkpoint(tenant)
            print(
                "nothing to seal"
                if sealed is None
                else f"sealed checkpoint {sealed.checkpoint_no}"
            )
            return 0
        bad = await verify_chain(tenant)
        if bad:
            print(f"audit chain mismatch at checkpoint(s): {', '.join(map(str, bad))}")
            return 1
        print("audit chain verified")
        return 0
    finally:
        await dispose_engine()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="abacus_tools.audit_chain")
    parser.add_argument("command", choices=("seal", "verify"))
    parser.add_argument("--tenant", required=True, type=UUID)
    args = parser.parse_args(argv)
    return asyncio.run(_run(args.command, args.tenant))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

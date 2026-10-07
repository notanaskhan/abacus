"""`python -m abacus_tools.evals.publish SUMMARY.json --database-url URL`: load a run's summary
into an evaluation store (TASK-020 D3), as the owner role. The deploy pipeline publishes runs
into its environment so the gateway's eligibility check sees them (TASK-014)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import cast

import asyncpg

from abacus_tools.evals.runner import store_finish


async def publish(summary: dict[str, object], database_url: str) -> None:
    conn = await asyncpg.connect(database_url)
    try:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO eval_runs (id, agent_id, suite_version, prompt_version, model, "
                "tier, subset, fake) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
                uuid.UUID(str(summary["id"])),
                summary["agent"],
                summary["suite_version"],
                summary["prompt_version"],
                summary["model"],
                summary["tier"],
                summary["subset"],
                summary["fake"],
            )
            await store_finish(conn, summary)
    finally:
        await conn.close()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.evals.publish")
    parser.add_argument("summary", type=Path)
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args(argv)
    summary = cast(dict[str, object], json.loads(cast(Path, args.summary).read_text()))
    asyncio.run(publish(summary, cast(str, args.database_url)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

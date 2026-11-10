"""`python -m abacus_tools.agent_run_backfill` (P-10-T14): the deploy pipeline starts the legacy
agent run backfill once per firm, after 8 pm CT, before Dec 24, 2027 (SPEC-647 §4.7).

Each firm gets `AgentRunBackfill` with the id `agent_run_backfill:<tenant>` on the background
queue. A workflow already running under that id is left alone (it is resuming); a finished one is
started again, which picks up only rows still without a state, so re-running is harmless. Before
8 pm Central the tool refuses unless `--now` is given (a rehearsal on staging).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, time
from zoneinfo import ZoneInfo

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel.clock import system_now
from abacus.kernel.dispatch import queue_for
from abacus.kernel.temporal import temporal_client
from abacus.modules.agents.api import BACKFILL_ID_PREFIX, AgentRunBackfillWorkflow, BackfillInput
from abacus.modules.identity.api import firm_tenant_ids

CENTRAL = ZoneInfo("America/Chicago")
WINDOW_OPENS = time(20, 0)


def window_open(now: datetime) -> bool:
    """After 8 pm Central (the live specialists are quiet), until midnight."""
    return now.astimezone(CENTRAL).time() >= WINDOW_OPENS


async def start_all(batch_size: int, pause_seconds: float) -> tuple[int, int]:
    client = await temporal_client()
    started = running = 0
    for tenant_id in await firm_tenant_ids():
        try:
            await client.start_workflow(
                AgentRunBackfillWorkflow.run,
                BackfillInput(str(tenant_id), batch_size, pause_seconds),
                id=f"{BACKFILL_ID_PREFIX}{tenant_id}",
                task_queue=queue_for("background"),
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
                id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
            )
            started += 1
        except WorkflowAlreadyStartedError:
            running += 1
    return started, running


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-run-backfill")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--pause-seconds", type=float, default=2.0)
    parser.add_argument("--now", action="store_true", help="ignore the 8 pm CT window")
    args = parser.parse_args(argv)
    if not args.now and not window_open(system_now()):
        print("agent run backfill: the window opens at 8 pm CT; pass --now to rehearse")
        return 2
    started, running = asyncio.run(start_all(args.batch_size, args.pause_seconds))
    print(f"agent run backfill: started={started} already_running={running}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

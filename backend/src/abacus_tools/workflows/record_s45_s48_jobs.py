"""Record the replay histories of three single-activity jobs that landed without one (Q-03-T195;
ADR-090). See `histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_s45_s48_jobs <output-directory>

Records the real workflows against throwaway containers with their activities replaced by stubs
(replay never runs activities):
- `confirmation-follow-up-v1-swept.json`: A-08's daily second-request sweep;
- `integration-health-v1-probed.json`: the integrations health sweep, every 15 minutes;
- `consolidation-pull-all-v1-attached.json`: A-09's pull of every component TB.
Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.assurance.confirmations_follow_up import ConfirmationFollowUpWorkflow
from abacus.modules.assurance.group_pull import ConsolidationPullAll, PullAllInput
from abacus.modules.integrations.health_workflow import IntegrationHealthWorkflow
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_PULL = PullAllInput(
    "00000000-0000-4000-8000-0000000000e1",
    "00000000-0000-4000-8000-0000000000e2",
    "00000000-0000-4000-8000-0000000000e3",
)
FOLLOW_UP = "confirmation-follow-up-v1-swept.json"
HEALTH = "integration-health-v1-probed.json"
PULL_ALL = "consolidation-pull-all-v1-attached.json"
FOLLOW_UP_ID = "confirmation_follow_up:platform"
HEALTH_ID = "integration_health:platform"
PULL_ALL_ID = f"consolidation_pull_all:{_PULL.consolidation_id}"
_FILES = (FOLLOW_UP, HEALTH, PULL_ALL)


@activity.defn(name="assurance.confirmations.follow_up_sweep")
async def _follow_up() -> int:
    return 1


@activity.defn(name="integrations.health_sweep")
async def _health() -> int:
    return 3


@activity.defn(name="assurance.consolidation.pull_all")
async def _pull_all(p: PullAllInput) -> int:
    return 2


async def _record(out: Path, stack: Stack) -> None:
    client: Client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[ConfirmationFollowUpWorkflow, IntegrationHealthWorkflow, ConsolidationPullAll],
        activities=[_follow_up, _health, _pull_all],
    ):
        follow_up = await client.start_workflow(
            ConfirmationFollowUpWorkflow.run, id=FOLLOW_UP_ID, task_queue=_TASK_QUEUE
        )
        health = await client.start_workflow(
            IntegrationHealthWorkflow.run, id=HEALTH_ID, task_queue=_TASK_QUEUE
        )
        pull_all = await client.start_workflow(
            ConsolidationPullAll.run, _PULL, id=PULL_ALL_ID, task_queue=_TASK_QUEUE
        )
        for name, handle in ((FOLLOW_UP, follow_up), (HEALTH, health), (PULL_ALL, pull_all)):
            await handle.result()
            history = await handle.fetch_history()
            scrubbed = await decoded_and_scrubbed(history, payload_codec())
            path = out / name
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if refuse_overwrite(out, list(_FILES)):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

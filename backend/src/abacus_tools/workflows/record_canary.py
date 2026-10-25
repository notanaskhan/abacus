"""Record the canary's replay histories (Q-01-T30; ADR-090). See `histories.py` for the fixture
rules.

Run: python -m abacus_tools.workflows.record_canary <output-directory>

Records the real `CanaryWorkflow` against throwaway containers with its activities replaced by
stubs (replay never runs activities):
- `canary-v1-passed.json`: every step passes and the report beats;
- `canary-v1-failed.json`: the outbox step fails (`outbox_lag`) and the report records it.
Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.platform.api import (
    CanaryInput,
    CanaryOutcome,
    CanaryPlan,
    CanaryResult,
    CanaryWorkflow,
    canary_workflow_id,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-0000000000c1"
_PLAN = CanaryPlan(
    _TENANT, "00000000-0000-4000-8000-0000000000c2", "00000000-0000-4000-8000-0000000000c3"
)
_FILES = ("canary-v1-passed.json", "canary-v1-failed.json")
_failing = {"on": False}


@activity.defn(name="canary.prepare")
async def _prepare(given: CanaryInput) -> CanaryPlan:
    return _PLAN


@activity.defn(name="canary.create_item")
async def _create_item(plan: CanaryPlan) -> str:
    return "00000000-0000-4000-8000-0000000000c4"


@activity.defn(name="canary.upload")
async def _upload(plan: CanaryPlan, item_id: str) -> str:
    return "00000000-0000-4000-8000-0000000000c5"


@activity.defn(name="canary.wait_processing")
async def _wait(plan: CanaryPlan, item_id: str, version_id: str) -> None:
    return None


@activity.defn(name="canary.screen")
async def _screen(plan: CanaryPlan, item_id: str, version_id: str) -> str:
    return "fake"


@activity.defn(name="canary.observe_outbox")
async def _observe(plan: CanaryPlan, version_id: str) -> None:
    if _failing["on"]:
        raise ApplicationError("outbox_lag", type="CanaryStepFailed", non_retryable=True)


@activity.defn(name="canary.send_simulator")
async def _send(plan: CanaryPlan) -> None:
    return None


@activity.defn(name="canary.report")
async def _report(outcome: CanaryOutcome) -> CanaryResult:
    return CanaryResult(
        outcome.tenant_id,
        outcome.passed,
        outcome.failed_step,
        outcome.code,
        outcome.route,
        False,
    )


async def _run(client: Client, suffix: str) -> WorkflowHistory:
    handle = await client.start_workflow(
        CanaryWorkflow.run,
        CanaryInput(_TENANT),
        id=f"{canary_workflow_id(_TENANT)}-{suffix}",
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[CanaryWorkflow],
        activities=[
            _prepare,
            _create_item,
            _upload,
            _wait,
            _screen,
            _observe,
            _send,
            _report,
        ],
    ):
        for failing, name in ((False, _FILES[0]), (True, _FILES[1])):
            _failing["on"] = failing
            history = await _run(client, "failed" if failing else "passed")
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

"""Record screening replay histories (AC-19, ADR-090). See `histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_screening <output-directory> [version] [slots]

Retrieves one synthetic trial balance, then records three runs of the real screening workflow
against throwaway containers, with the fake model:
- `screening-<version>-completed.json`: the fake screener answers;
- `screening-<version>-skipped.json`: no `requested_by`, so no run is created;
- `screening-<version>-provider-unavailable.json`: no fake answer, so the model call fails until
  retries run out and `screening.fail_run` ends the run.

With `slots`, records the work-slot scenarios instead (SPEC-003, TASK-018 018b), on the
time-sensitive class queue with the firm held at its cap by a blocker slot:
`screening-<version>-queued-then-completed.json` (at least two asks and timers, then the blocker
goes), `screening-<version>-capacity-timeout.json` and
`screening-<version>-cancelled-while-queued.json`.

Refuses to overwrite an existing file: a changed workflow records `v<N+1>`.
"""

from __future__ import annotations

import contextlib
import os
import sys
import uuid
from pathlib import Path

from temporalio.client import Client, WorkflowFailureError, WorkflowHandle, WorkflowHistory
from temporalio.worker import Worker

from abacus.ai_gateway import FakeModel, configure_provider
from abacus.kernel.dispatch import queue_for
from abacus.kernel.temporal import payload_codec
from abacus.modules.agents import api as agents
from abacus.modules.connections import api as connections
from abacus_tools.synthetic.connector_fixtures import write_trial_balance
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import (
    Stack,
    block_firm,
    connect,
    period_of,
    refuse_overwrite,
    run_with_stack,
    seed,
    slot_limits,
    trial_balance,
    unblock,
    wait_for_history,
)

_TASK_QUEUE = "abacus-recorder"
_NAMES = ("completed", "skipped", "provider-unavailable")


async def _screen(
    client: Client, name: str, input: agents.ScreeningInput, model: FakeModel
) -> WorkflowHistory:
    configure_provider(model)
    try:
        handle = await client.start_workflow(
            "screening", input, id=f"recorder-screening-{name}", task_queue=_TASK_QUEUE
        )
        await handle.result()
        return await handle.fetch_history()
    finally:
        configure_provider(None)


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    world = await seed(stack.superuser)
    tb = trial_balance()
    period = period_of(tb)
    write_trial_balance(
        Path(os.environ["ABACUS_FAKE_CONNECTOR_DIR"]),
        world.connection,
        tb,
        period_start=period.start,
        entity_name="Example",
    )
    codec = payload_codec()
    worker = Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[*connections.WORKFLOWS, *agents.WORKFLOWS],
        activities=[*connections.ACTIVITIES, *agents.ACTIVITIES],
    )
    async with worker:
        started = await connections.start_retrieval(
            world.context(),
            engagement_id=world.engagement,
            request_item_id=world.items[0],
            period=period,
        )
        retrieval = await client.start_workflow(
            "retrieval",
            connections.RetrievalInput(str(world.tenant), str(started.run_id)),
            id=connections.workflow_id(started.run_id),
            task_queue=_TASK_QUEUE,
            result_type=connections.RetrievalOutcome,
        )
        outcome = await retrieval.result()
        version_id = str(outcome.evidence_version_id)
        cases = (
            ("completed", str(world.user), agents.install_fake_responses(FakeModel())),
            ("skipped", None, FakeModel()),
            ("provider-unavailable", str(world.user), FakeModel()),
        )
        for name, requested_by, model in cases:
            input = agents.ScreeningInput(
                str(world.tenant), version_id, str(uuid.uuid4()), requested_by
            )
            history = await _screen(client, name, input, model)
            scrubbed = await decoded_and_scrubbed(history, codec)
            path = out / f"screening-{version}-{name}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


_SLOT_NAMES = ("queued-then-completed", "capacity-timeout", "cancelled-while-queued")


async def _record_slots(out: Path, version: str, stack: Stack) -> None:
    slot_limits("time_sensitive", firm_cap=1, max_wait_seconds=120)
    client = await connect(stack)
    world = await seed(stack.superuser)
    tb = trial_balance()
    period = period_of(tb)
    write_trial_balance(
        Path(os.environ["ABACUS_FAKE_CONNECTOR_DIR"]),
        world.connection,
        tb,
        period_start=period.start,
        entity_name="Example",
    )
    codec = payload_codec()
    queue = queue_for("time_sensitive")
    worker = Worker(
        client,
        task_queue=queue,
        workflows=[*connections.WORKFLOWS, *agents.WORKFLOWS],
        activities=[*connections.ACTIVITIES, *agents.ACTIVITIES],
    )
    asks = "screening.acquire_slot"

    async def start(version_id: str) -> WorkflowHandle[object, object]:
        given = agents.ScreeningInput(
            str(world.tenant), version_id, str(uuid.uuid4()), str(world.user)
        )
        return await client.start_workflow(
            "screening", given, id=f"recorder-screening-{uuid.uuid4()}", task_queue=queue
        )

    async def save(name: str, handle: WorkflowHandle[object, object]) -> None:
        history = await decoded_and_scrubbed(await handle.fetch_history(), codec)
        path = out / f"screening-{version}-{name}.json"
        path.write_text(history.to_json())
        print(f"recorded {path}")

    async with worker:
        started = await connections.start_retrieval(
            world.context(),
            engagement_id=world.engagement,
            request_item_id=world.items[0],
            period=period,
        )
        retrieval = await client.start_workflow(
            "retrieval",
            connections.RetrievalInput(str(world.tenant), str(started.run_id)),
            id=connections.workflow_id(started.run_id),
            task_queue=queue,
            result_type=connections.RetrievalOutcome,
        )
        version_id = str((await retrieval.result()).evidence_version_id)
        configure_provider(agents.install_fake_responses(FakeModel()))
        try:
            await block_firm(stack.superuser, world.tenant, "time_sensitive")
            handle = await start(version_id)
            await wait_for_history(handle, asks=asks, count=2, timers=1)
            await unblock(stack.superuser)
            await handle.result()
            await save("queued-then-completed", handle)
            slot_limits("time_sensitive", firm_cap=1, max_wait_seconds=2)
            await block_firm(stack.superuser, world.tenant, "time_sensitive")
            handle = await start(version_id)
            await handle.result()
            await save("capacity-timeout", handle)
            slot_limits("time_sensitive", firm_cap=1, max_wait_seconds=120)
            await block_firm(stack.superuser, world.tenant, "time_sensitive")
            handle = await start(version_id)
            await wait_for_history(handle, asks=asks, count=2, timers=1)
            await handle.cancel()
            with contextlib.suppress(WorkflowFailureError):
                await handle.result()
            await save("cancelled-while-queued", handle)
        finally:
            configure_provider(None)


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    version = argv[1] if len(argv) > 1 else "v1"
    slots = len(argv) > 2 and argv[2] == "slots"
    if refuse_overwrite(
        out, [f"screening-{version}-{name}.json" for name in (_SLOT_NAMES if slots else _NAMES)]
    ):
        return 1
    out.mkdir(parents=True, exist_ok=True)
    record = _record_slots if slots else _record
    run_with_stack(lambda stack: record(out, version, stack))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

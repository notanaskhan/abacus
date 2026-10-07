"""Record retrieval replay histories (AC-19). See `histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_retrieval <output-directory> [version] [slots]

Records two runs of the real workflow against throwaway containers, with synthetic data:
`retrieval-<version>-succeeded.json` and `retrieval-<version>-failed-validation.json`. Refuses to
overwrite an existing file.

With `slots`, records the work-slot scenarios instead (SPEC-003, TASK-018 018b), on the
interactive class queue with the firm held at its cap by a blocker slot:
`retrieval-<version>-queued-then-succeeded.json` (at least two asks and timers, then the blocker
goes and the run succeeds), `retrieval-<version>-capacity-timeout.json` and
`retrieval-<version>-cancelled-while-queued.json`.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import uuid
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import asyncpg
from temporalio.api.enums.v1 import EventType
from temporalio.client import WorkflowFailureError, WorkflowHandle
from temporalio.worker import Worker

from abacus.kernel.config import settings
from abacus.kernel.dispatch import queue_for
from abacus.kernel.temporal import payload_codec
from abacus.modules.connections.api import (
    ACTIVITIES,
    WORKFLOWS,
    RetrievalInput,
    start_retrieval,
    workflow_id,
)
from abacus_tools.stack import (
    Stack,
    connect,
    period_of,
    run_with_stack,
    seed,
    trial_balance,
)
from abacus_tools.synthetic.connector_fixtures import write_trial_balance
from abacus_tools.workflows.histories import decoded_and_scrubbed

if TYPE_CHECKING:
    pass

_TASK_QUEUE = "abacus-recorder"


# The throwaway gateway's credentials, the same as the compose stack's local defaults.
async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    fixtures = Path(os.environ["ABACUS_FAKE_CONNECTOR_DIR"])
    world = await seed(stack.superuser)
    tenant, engagement, items, connection = (
        world.tenant,
        world.engagement,
        world.items,
        world.connection,
    )
    tb = trial_balance()
    period = period_of(tb)
    ctx = world.context()
    codec = payload_codec()
    worker = Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=list(WORKFLOWS),
        activities=list(ACTIVITIES),
    )
    unbalanced = replace(
        tb,
        lines=(*tb.lines[:-1], replace(tb.lines[-1], debit=tb.lines[-1].debit + Decimal(1))),
    )
    async with worker:
        for name, item, data in (
            ("succeeded", items[0], tb),
            ("failed-validation", items[1], unbalanced),
        ):
            write_trial_balance(
                fixtures, connection, data, period_start=period.start, entity_name="Example"
            )
            started = await start_retrieval(
                ctx, engagement_id=engagement, request_item_id=item, period=period
            )
            handle = await client.start_workflow(
                "retrieval",
                RetrievalInput(str(tenant), str(started.run_id)),
                id=workflow_id(started.run_id),
                task_queue=_TASK_QUEUE,
            )
            await handle.result()
            history = await decoded_and_scrubbed(await handle.fetch_history(), codec)
            path = out / f"retrieval-{version}-{name}.json"
            path.write_text(history.to_json())
            print(f"recorded {path}")


_SLOT_CLASSES = ("interactive", "time_sensitive", "background", "batch")


def slot_limits(work_class: str, **overrides: int) -> None:
    """Set one class's caps for the recording (the others keep generous defaults)."""
    full = {
        name: {
            "max_activities": 10,
            "max_workflow_tasks": 10,
            "firm_cap": 20,
            "engagement_cap": 10,
            "class_capacity": 50,
            "max_wait_seconds": 120,
            "admission_reserve_pct": 0,
        }
        for name in _SLOT_CLASSES
    }
    full[work_class].update(overrides)
    os.environ["ABACUS_WORK_CLASSES"] = json.dumps(full)
    settings.cache_clear()


async def block_firm(superuser: str, tenant: uuid.UUID, work_class: str) -> None:
    """A live slot held by the firm's other work, so a run of the firm waits at `firm_cap`."""
    conn = await asyncpg.connect(superuser)
    try:
        await conn.execute("DELETE FROM work_slots")
        await conn.execute("DELETE FROM work_waiters")
        await conn.execute(
            "INSERT INTO work_slots (tenant_id, holder, work_class, acquired_at, lease_until) "
            "VALUES ($1, 'recorder-blocker', $2, now(), now() + interval '1 hour')",
            tenant,
            work_class,
        )
    finally:
        await conn.close()


async def unblock(superuser: str) -> None:
    conn = await asyncpg.connect(superuser)
    try:
        await conn.execute("DELETE FROM work_slots WHERE holder = 'recorder-blocker'")
    finally:
        await conn.close()


async def wait_for_history(
    handle: WorkflowHandle[object, object], *, asks: str, count: int, timers: int = 0
) -> None:
    """Until the workflow has scheduled `asks` at least `count` times and started `timers`."""
    for _ in range(120):
        history = await handle.fetch_history()
        names = [
            e.activity_task_scheduled_event_attributes.activity_type.name
            for e in history.events
            if e.HasField("activity_task_scheduled_event_attributes")
        ]
        started = [e for e in history.events if e.event_type == EventType.EVENT_TYPE_TIMER_STARTED]
        if names.count(asks) >= count and len(started) >= timers:
            return
        await asyncio.sleep(0.5)
    raise RuntimeError(f"{handle.id} did not reach {count} asks and {timers} timers")


async def _record_slots(out: Path, version: str, stack: Stack) -> None:
    slot_limits("interactive", firm_cap=1, max_wait_seconds=120)
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
    queue = queue_for("interactive")
    worker = Worker(
        client, task_queue=queue, workflows=list(WORKFLOWS), activities=list(ACTIVITIES)
    )
    asks = "retrieval.acquire_slot"

    async def start(item: uuid.UUID) -> WorkflowHandle[object, object]:
        started = await start_retrieval(
            world.context(), engagement_id=world.engagement, request_item_id=item, period=period
        )
        return await client.start_workflow(
            "retrieval",
            RetrievalInput(str(world.tenant), str(started.run_id)),
            id=workflow_id(started.run_id),
            task_queue=queue,
        )

    async def save(name: str, handle: WorkflowHandle[object, object]) -> None:
        history = await decoded_and_scrubbed(await handle.fetch_history(), codec)
        path = out / f"retrieval-{version}-{name}.json"
        path.write_text(history.to_json())
        print(f"recorded {path}")

    async with worker:
        # Queued, then the slot frees and the run succeeds: several asks and timers.
        await block_firm(stack.superuser, world.tenant, "interactive")
        handle = await start(world.items[0])
        await wait_for_history(handle, asks=asks, count=2, timers=1)
        await unblock(stack.superuser)
        await handle.result()
        await save("queued-then-succeeded", handle)
        # Queued past the maximum wait: capacity_timeout through fail_run.
        slot_limits("interactive", firm_cap=1, max_wait_seconds=2)
        await block_firm(stack.superuser, world.tenant, "interactive")
        handle = await start(world.items[1])
        await handle.result()
        await save("capacity-timeout", handle)
        # Cancelled while queued.
        slot_limits("interactive", firm_cap=1, max_wait_seconds=120)
        await block_firm(stack.superuser, world.tenant, "interactive")
        handle = await start(world.items[1])
        await wait_for_history(handle, asks=asks, count=2, timers=1)
        await handle.cancel()
        with contextlib.suppress(WorkflowFailureError):
            await handle.result()
        await save("cancelled-while-queued", handle)


def refuse_overwrite(out: Path, names: list[str]) -> bool:
    """True (and a message) if any history file already exists: record a new version instead."""
    for name in names:
        if (out / name).exists():
            print(f"refusing to overwrite {name}; record a new version")
            return True
    return False


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    version = argv[1] if len(argv) > 1 else "v1"
    slots = len(argv) > 2 and argv[2] == "slots"
    scenarios = ("queued-then-succeeded", "capacity-timeout", "cancelled-while-queued")
    names = [
        f"retrieval-{version}-{n}.json"
        for n in (scenarios if slots else ("succeeded", "failed-validation"))
    ]
    if refuse_overwrite(out, names):
        return 1
    out.mkdir(parents=True, exist_ok=True)
    record = _record_slots if slots else _record
    run_with_stack(lambda stack: record(out, version, stack))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

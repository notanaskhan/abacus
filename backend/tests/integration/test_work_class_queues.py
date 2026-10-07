"""AC-1, AC-2, AC-5: work classes against a real Temporal server (TASK-018 interface contract,
"Worker" and "AC-5"; SPEC-003; ADR-071).

The worker is the real one (`build_workers`), with its boot checks stubbed (no database or
storage is needed) and its modules replaced by two small workflows of this file: a long-running
`background` one and an `interactive` probe. Workflows start through `dispatch`. Pool sizes come
from settings. Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncGenerator, Callable, Iterator
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace

import pytest
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.worker import Worker

from abacus.kernel.config import settings
from abacus.kernel.dispatch import WORK_CLASSES, dispatch, queue_for, register_work_classes
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.worker import __main__ as worker_main

BASE = f"ac5-{uuid.uuid4().hex[:10]}"
# TASK-018b: the slot caps and maximum wait are required fields of each class.
SLOT_FIELDS = {"firm_cap": 20, "engagement_cap": 10, "class_capacity": 50, "max_wait_seconds": 120}
LIMITS = {
    "interactive": {"max_activities": 4, "max_workflow_tasks": 4, **SLOT_FIELDS},
    "time_sensitive": {"max_activities": 4, "max_workflow_tasks": 4, **SLOT_FIELDS},
    "background": {"max_activities": 1, "max_workflow_tasks": 4, **SLOT_FIELDS},
    "batch": {"max_activities": 1, "max_workflow_tasks": 4, **SLOT_FIELDS},
}
TARGET_SECONDS = 2.0


class State:
    """What the activities saw, in this process (the worker runs in it)."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.release = asyncio.Event()
        self.started: list[str] = []
        self.queues: dict[str, str] = {}
        self.waited: dict[str, float] = {}


STATE = State()


@activity.defn(name="queues.hold")
async def hold(label: str) -> None:
    STATE.started.append(label)
    STATE.queues[label] = activity.info().task_queue
    await asyncio.wait_for(STATE.release.wait(), timeout=120)


@activity.defn(name="queues.probe")
async def probe(label: str) -> None:
    info = activity.info()
    STATE.queues[label] = info.task_queue
    STATE.waited[label] = (info.started_time - info.scheduled_time).total_seconds()
    STATE.started.append(label)


@workflow.defn(name="queues-hold", sandboxed=False)
class HoldWorkflow:
    @workflow.run
    async def run(self, label: str) -> None:
        await workflow.execute_activity(
            "queues.hold", label, start_to_close_timeout=timedelta(seconds=150)
        )


@workflow.defn(name="queues-probe", sandboxed=False)
class ProbeWorkflow:
    @workflow.run
    async def run(self, label: str) -> None:
        await workflow.execute_activity(
            "queues.probe", label, start_to_close_timeout=timedelta(seconds=30)
        )


@workflow.defn(name="queues-batch", sandboxed=False)
class BatchWorkflow:
    @workflow.run
    async def run(self, label: str) -> None:
        await workflow.execute_activity(
            "queues.probe", label, start_to_close_timeout=timedelta(seconds=30)
        )


register_work_classes(
    {HoldWorkflow: "background", ProbeWorkflow: "interactive", BatchWorkflow: "batch"}
)


@pytest.fixture(autouse=True)
def pools(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", BASE)
    monkeypatch.setenv("ABACUS_WORK_CLASSES", json.dumps(LIMITS))
    settings.cache_clear()

    async def nothing() -> None:
        return None

    monkeypatch.setattr(worker_main, "ping", nothing)
    monkeypatch.setattr(worker_main, "ping_relay", nothing)
    monkeypatch.setattr(worker_main, "check_ready", nothing)
    monkeypatch.setattr(worker_main, "key_service", lambda: None)
    monkeypatch.setattr(
        worker_main,
        "MODULES",
        (
            SimpleNamespace(
                WORKFLOWS={
                    HoldWorkflow: "background",
                    ProbeWorkflow: "interactive",
                    BatchWorkflow: "batch",
                },
                ACTIVITIES=[hold, probe],
                SUBSCRIPTIONS={},
            ),
        ),
    )
    STATE.reset()
    yield
    settings.cache_clear()


@pytest.fixture
async def temporal(temporal_target: str) -> AsyncGenerator[Client]:
    client = await Client.connect(temporal_target, data_converter=data_converter())
    configure_temporal_client(client)
    yield client
    configure_temporal_client(None)


@asynccontextmanager
async def _serving() -> AsyncGenerator[list[Worker]]:
    async with AsyncExitStack() as running:
        built = await worker_main.build_workers()
        for pool in built:
            await running.enter_async_context(pool)
        try:
            yield built
        finally:
            STATE.release.set()  # never leave a hold running: the pools drain on exit


async def _until(condition: Callable[[], bool], seconds: float) -> None:
    async with asyncio.timeout(seconds):
        while not condition():
            await asyncio.sleep(0.02)


async def _start(workflow_type: type, label: str) -> str:
    workflow_id = f"queues-{label}-{uuid.uuid4()}"
    await dispatch(
        workflow_type,
        label,
        id=workflow_id,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
    )
    return workflow_id


# --- AC-1, AC-2 ----------------------------------------------------------------------------------


async def test_ac2_a_dispatched_workflow_and_its_activity_run_on_its_class_queue(
    temporal: Client,
) -> None:
    async with _serving():
        probe_id = await _start(ProbeWorkflow, "probe")
        batch_id = await _start(BatchWorkflow, "batch-probe")
        for workflow_id in (probe_id, batch_id):
            await asyncio.wait_for(temporal.get_workflow_handle(workflow_id).result(), 30)
        assert (await temporal.get_workflow_handle(probe_id).describe()).task_queue == queue_for(
            "interactive"
        )
        assert (await temporal.get_workflow_handle(batch_id).describe()).task_queue == queue_for(
            "batch"
        )
    assert STATE.queues["probe"] == queue_for("interactive")
    assert STATE.queues["batch-probe"] == queue_for("batch")


async def test_ac1_a_process_serving_some_classes_runs_only_their_work(temporal: Client) -> None:
    async with AsyncExitStack() as running:
        built = await worker_main.build_workers(("batch",))
        assert [w.task_queue for w in built] == [queue_for("batch")]  # no legacy: not interactive
        for pool in built:
            await running.enter_async_context(pool)
        batch_id = await _start(BatchWorkflow, "only-batch")
        interactive_id = await _start(ProbeWorkflow, "not-served")
        await asyncio.wait_for(temporal.get_workflow_handle(batch_id).result(), 30)
        await asyncio.sleep(1.0)
        assert "only-batch" in STATE.started
        assert "not-served" not in STATE.started  # nobody polls the interactive queue
        description = await temporal.get_workflow_handle(interactive_id).describe()
        assert description.status is not None
        assert description.close_time is None  # still waiting for a worker
        await temporal.get_workflow_handle(interactive_id).terminate()


# --- AC-5 ----------------------------------------------------------------------------------------


async def test_ac5_an_interactive_workflow_starts_within_the_target_while_background_is_saturated(
    temporal: Client,
) -> None:
    assert settings().work_classes["background"].max_activities == 1
    async with _serving():
        held = [await _start(HoldWorkflow, "hold-1"), await _start(HoldWorkflow, "hold-2")]
        await _until(lambda: len(STATE.started) >= 1, 30)
        await asyncio.sleep(0.5)
        # the background pool (one slot) is full, with more work waiting behind it
        assert len(STATE.started) == 1
        assert STATE.queues[STATE.started[0]] == queue_for("background")

        began = time.monotonic()
        probe_id = await _start(ProbeWorkflow, "interactive-probe")
        await _until(lambda: "interactive-probe" in STATE.started, TARGET_SECONDS)
        assert time.monotonic() - began < TARGET_SECONDS
        assert STATE.waited["interactive-probe"] < TARGET_SECONDS  # schedule to start
        assert STATE.queues["interactive-probe"] == queue_for("interactive")
        await asyncio.wait_for(temporal.get_workflow_handle(probe_id).result(), 10)
        assert len(STATE.started) == 2  # the saturated pool still holds only its one hold

        STATE.release.set()
        for workflow_id in held:
            await asyncio.wait_for(temporal.get_workflow_handle(workflow_id).result(), 60)
    assert sorted(label for label in STATE.started if label.startswith("hold")) == [
        "hold-1",
        "hold-2",
    ]


def test_ac5_the_test_pools_are_sized_from_settings() -> None:
    assert [LIMITS[c]["max_activities"] for c in WORK_CLASSES] == [4, 4, 1, 1]

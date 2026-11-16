"""C-01-T19 (C-01 §4.5): `RequestPublishWorkflow` on Temporal's time-skipping server, activities
stubbed: it sleeps to BD1 09:00, publishes once, re-asks on `recompute`, and ends on -1."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from abacus.modules.closes.request_publish_types import (
    PUBLISH,
    RECOMPUTE,
    SECONDS_UNTIL,
    PublishInput,
    PublishResult,
)
from abacus.modules.closes.request_publish_workflow import RequestPublishWorkflow

QUEUE = "request-publish"
GIVEN = PublishInput("00000000-0000-4000-8000-0000000000b1", "00000000-0000-4000-8000-0000000019a1")
asked: list[int] = []
published: list[str] = []
waits: list[int] = []


@activity.defn(name=SECONDS_UNTIL)
async def _until(given: PublishInput) -> int:
    asked.append(1)
    return waits.pop(0) if waits else 0


@activity.defn(name=PUBLISH)
async def _publish(given: PublishInput) -> PublishResult:
    published.append(given.close_id)
    return PublishResult(8, 3)


@pytest.fixture
async def env() -> AsyncGenerator[WorkflowEnvironment]:
    asked.clear()
    published.clear()
    waits.clear()
    environment = await WorkflowEnvironment.start_time_skipping()
    try:
        async with Worker(
            environment.client, task_queue=QUEUE, workflows=[RequestPublishWorkflow],
            activities=[_until, _publish],
        ):  # fmt: skip
            yield environment
    finally:
        await environment.shutdown()


@pytest.mark.asyncio
async def test_ac_sleeps_to_bd1_then_publishes_once(env: WorkflowEnvironment) -> None:
    waits.extend([24 * 3600])
    result = await env.client.execute_workflow(
        RequestPublishWorkflow.run, GIVEN, id="close_requests:t:c", task_queue=QUEUE
    )
    assert (result.created, published) == (8, [GIVEN.close_id])


@pytest.mark.asyncio
async def test_a_recompute_asks_again(env: WorkflowEnvironment) -> None:
    waits.extend([24 * 3600, 3600])
    handle = await env.client.start_workflow(
        RequestPublishWorkflow.run, GIVEN, id="close_requests:t:r", task_queue=QUEUE
    )
    await handle.signal(RECOMPUTE)
    await handle.result()
    assert len(asked) == 2 and published == [GIVEN.close_id]


@pytest.mark.asyncio
async def test_nothing_to_do_ends(env: WorkflowEnvironment) -> None:
    waits.extend([-1])
    result = await env.client.execute_workflow(
        RequestPublishWorkflow.run, GIVEN, id="close_requests:t:n", task_queue=QUEUE
    )
    assert (result.created, published) == (0, [])

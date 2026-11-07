"""N-04-T23 (TASK-6009; ADR-078): the notice response's alerts and follow-up, on Temporal's
time-skipping test server.

The row's last open property: "time-skipping tests for alerts and the 60-day follow-up". The
workflow runs for real with stub activities that record what they were asked; days pass on the
test server's clock, never the machine's. A CP2000 alerts at 7 and 2 days left (across
continue-as-new), a CP3219A at 30, 14, 7 and 2; a response sent first cancels every alert still
due, and the follow-up fires on its day and waits for the agency's reply.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import date, timedelta

import pytest
from temporalio import activity
from temporalio.client import WorkflowHandle
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from abacus.modules.notices.response_workflow import NoticeResponseWorkflow
from abacus.modules.notices.response_workflow_types import (
    AlertInput,
    FollowUpInput,
    NoticeResponseInput,
)

QUEUE = "notice-timers"
TENANT = "00000000-0000-4000-8000-000000000001"
alerts: list[int] = []
follow_ups: list[str] = []


@activity.defn(name="notice_response.alert")
async def _alert(given: AlertInput) -> None:
    alerts.append(given.days_left)


@activity.defn(name="notice_response.follow_up")
async def _follow_up(given: FollowUpInput) -> None:
    follow_ups.append(given.follow_up_on)


@pytest.fixture
async def env() -> AsyncGenerator[WorkflowEnvironment]:
    alerts.clear()
    follow_ups.clear()
    environment = await WorkflowEnvironment.start_time_skipping()
    try:
        async with Worker(
            environment.client,
            task_queue=QUEUE,
            workflows=[NoticeResponseWorkflow],
            activities=[_alert, _follow_up],
        ):
            yield environment
    finally:
        await environment.shutdown()


async def _today(env: WorkflowEnvironment) -> date:
    return (await env.get_current_time()).date()


async def _start(
    env: WorkflowEnvironment, respond_by: date, kind: str = "cp2000"
) -> WorkflowHandle[NoticeResponseWorkflow, str]:
    work_item = str(uuid.uuid4())
    return await env.client.start_workflow(
        NoticeResponseWorkflow.run,
        NoticeResponseInput(TENANT, work_item, respond_by.isoformat(), kind),
        id=f"notice_response:{work_item}",
        task_queue=QUEUE,
    )


def _latest(
    env: WorkflowEnvironment, handle: WorkflowHandle[NoticeResponseWorkflow, str]
) -> WorkflowHandle[NoticeResponseWorkflow, str]:
    """The run after continue-as-new: a handle by id only signals the current run."""
    return env.client.get_workflow_handle_for(NoticeResponseWorkflow.run, handle.id)


async def test_a_cp2000_alerts_at_seven_then_two_days_left(env: WorkflowEnvironment) -> None:
    handle = await _start(env, await _today(env) + timedelta(days=10))
    await env.sleep(timedelta(days=4))
    assert alerts == [7]
    await env.sleep(timedelta(days=5))
    assert alerts == [7, 2]
    await _latest(env, handle).signal(NoticeResponseWorkflow.agency_reply)
    assert await _latest(env, handle).result() == "replied"


async def test_a_cp3219a_alerts_at_thirty_fourteen_seven_and_two(env: WorkflowEnvironment) -> None:
    handle = await _start(env, await _today(env) + timedelta(days=40), "cp3219a")
    await env.sleep(timedelta(days=39))
    assert alerts == [30, 14, 7, 2]
    await _latest(env, handle).signal(NoticeResponseWorkflow.agency_reply)
    assert await _latest(env, handle).result() == "replied"


async def test_a_response_sent_cancels_every_alert_still_due(env: WorkflowEnvironment) -> None:
    respond_by = await _today(env) + timedelta(days=10)
    handle = await _start(env, respond_by)
    await env.sleep(timedelta(days=4))
    assert alerts == [7]
    follow_up_on = respond_by + timedelta(days=60)
    await _latest(env, handle).signal(NoticeResponseWorkflow.sent, follow_up_on.isoformat())
    await env.sleep(timedelta(days=20))
    assert alerts == [7]  # the 2-day alert never fires once the response is sent


async def test_the_follow_up_fires_on_its_day_and_waits_for_the_reply(
    env: WorkflowEnvironment,
) -> None:
    respond_by = await _today(env) + timedelta(days=10)
    handle = await _start(env, respond_by)
    follow_up_on = respond_by + timedelta(days=60)
    await _latest(env, handle).signal(NoticeResponseWorkflow.sent, follow_up_on.isoformat())
    await env.sleep(timedelta(days=60))
    assert follow_ups == []
    await env.sleep(timedelta(days=11))
    assert follow_ups == [follow_up_on.isoformat()]
    await _latest(env, handle).signal(NoticeResponseWorkflow.agency_reply)
    assert await _latest(env, handle).result() == "replied"
    assert alerts == []


async def test_a_changed_respond_by_moves_the_alerts(env: WorkflowEnvironment) -> None:
    today = await _today(env)
    handle = await _start(env, today + timedelta(days=10))
    await env.sleep(timedelta(days=1))
    await _latest(env, handle).signal(
        NoticeResponseWorkflow.respond_by_changed, (today + timedelta(days=30)).isoformat()
    )
    await env.sleep(timedelta(days=10))
    assert alerts == []  # the old day-3 alert was replaced: -7 now falls on day 23
    await env.sleep(timedelta(days=13))
    assert alerts == [7]

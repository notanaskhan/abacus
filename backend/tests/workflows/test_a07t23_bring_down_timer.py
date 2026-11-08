"""A-07-T23 (TASK-6207; A-07 F2, I-CLOCKS; DEC-2807): BringDown on Temporal's time-skipping server.

Row acceptance: "Run #4240 fires at 9:00 AM CDT on Oct 9, 2026 in the time-skipping test, re-arms
when the report date moves, and never records a going-concern conclusion." The workflow runs for
real with a stub activity that records when it was asked; time passes on the test server's clock.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from abacus.modules.assurance.bring_down import (
    BringDownInput,
    BringDownResult,
    BringDownWorkflow,
    ReportDateMoved,
    fire_at,
)

QUEUE = "bring-down"
TENANT = "00000000-0000-4000-8000-000000000001"
WORK_ITEM = "00000000-0000-4000-8000-0000000004a1"
ENGAGEMENT = "00000000-0000-4000-8000-0000000004e1"
fired: list[tuple[str, datetime]] = []


@activity.defn(name="assurance.bring_down")
async def _bring_down(
    tenant_id: str, work_item_id: str, engagement_id: str, report_date: str
) -> BringDownResult:
    fired.append((report_date, activity.info().current_attempt_scheduled_time))
    return BringDownResult(report_date, 4, 4, 5)


@pytest.fixture
async def env() -> AsyncGenerator[WorkflowEnvironment]:
    fired.clear()
    environment = await WorkflowEnvironment.start_time_skipping()
    try:
        async with Worker(
            environment.client,
            task_queue=QUEUE,
            workflows=[BringDownWorkflow],
            activities=[_bring_down],
        ):
            yield environment
    finally:
        await environment.shutdown()


def test_nine_am_central_on_oct_9_2026_is_14_utc() -> None:
    assert fire_at(date(2026, 10, 9), "America/Chicago") == datetime(2026, 10, 9, 14, tzinfo=UTC)
    # After the fall change, 9:00 CST is 15:00 UTC.
    assert fire_at(date(2026, 11, 9), "America/Chicago") == datetime(2026, 11, 9, 15, tzinfo=UTC)


@pytest.mark.asyncio
async def test_ac_it_fires_at_9_am_cdt_on_the_report_date(env: WorkflowEnvironment) -> None:
    when = fire_at(date(2026, 10, 9), "America/Chicago")
    handle = await env.client.start_workflow(
        BringDownWorkflow.run,
        BringDownInput(TENANT, WORK_ITEM, ENGAGEMENT, "2026-10-09", when.isoformat()),
        id=f"bring_down:{WORK_ITEM}",
        task_queue=QUEUE,
    )
    result = await handle.result()
    assert result.reconfirmations_requested == 5
    assert [d for d, _ in fired] == ["2026-10-09"]
    assert fired[0][1] >= when


@pytest.mark.asyncio
async def test_ac_it_re_arms_when_the_report_date_moves(env: WorkflowEnvironment) -> None:
    first = fire_at(date(2026, 10, 9), "America/Chicago")
    moved = fire_at(date(2026, 10, 16), "America/Chicago")
    handle = await env.client.start_workflow(
        BringDownWorkflow.run,
        BringDownInput(TENANT, WORK_ITEM, ENGAGEMENT, "2026-10-09", first.isoformat()),
        id=f"bring_down:{WORK_ITEM}:moved",
        task_queue=QUEUE,
    )
    await handle.signal(
        BringDownWorkflow.report_date_changed, ReportDateMoved("2026-10-16", moved.isoformat())
    )
    await handle.result()
    assert [d for d, _ in fired] == ["2026-10-16"]
    assert fired[0][1] >= moved


def test_ac_the_activity_records_no_conclusion() -> None:
    import inspect

    from abacus.modules.assurance import bring_down

    source = inspect.getsource(bring_down.bring_down)
    for word in ("going_concern", "decide", "conclusion", "subsequent_events ("):
        assert word not in source

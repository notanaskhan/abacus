"""Q-01-T26 (Q-01 §4.5; DISPATCH-001): the platform jobs' Schedules on a real Temporal dev server.
`abacus_tools.schedules ensure` creates one Schedule per declared job and converges it when run
again (an operator's pause survives); each Schedule starts its workflow on the background queue,
skips while a run is open and catches up at most an hour; a triggered run does the job once,
however many interactive workers are up (the workers no longer run the loops)."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

import pytest
from temporalio import activity
from temporalio.client import Client
from temporalio.service import RPCError
from temporalio.worker import Worker

from abacus.kernel import dispatch
from abacus.kernel.dispatch import queue_for
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.modules.notifications import api as notifications
from abacus.modules.platform import api as platform
from abacus_tools import schedules

IDS = ("notification_purge:platform", "spend_anomaly:platform")
_passes: list[str] = []


@activity.defn(name="platform.flag_spend_anomalies")
async def _flag() -> int:
    _passes.append("anomaly")
    return 0


@activity.defn(name="notifications.purge_expired")
async def _purge() -> int:
    _passes.append("purge")
    return 0


@pytest.fixture
async def temporal(temporal_target: str) -> AsyncIterator[Client]:
    client = await Client.connect(temporal_target, data_converter=data_converter())
    configure_temporal_client(client)
    _passes.clear()
    yield client
    for schedule_id in IDS:
        # Already deleted by the test, or never created.
        with contextlib.suppress(RPCError):
            await dispatch.delete(schedule_id)
    configure_temporal_client(None)


async def test_ensure_creates_one_schedule_per_job_and_converges_on_a_rerun(
    temporal: Client,
) -> None:
    assert await schedules.ensure() == dict.fromkeys(IDS, "created")
    assert await schedules.ensure() == dict.fromkeys(IDS, "updated")
    listed = [s.id async for s in await temporal.list_schedules()]
    assert sorted(i for i in listed if i in IDS) == sorted(IDS)
    facts = {f["id"]: f for f in await schedules.show()}
    assert facts["spend_anomaly:platform"]["workflow_type"] == "SpendAnomaly"
    assert facts["spend_anomaly:platform"]["every_seconds"] == (3600,)
    assert facts["notification_purge:platform"]["workflow_type"] == "NotificationPurge"
    assert facts["notification_purge:platform"]["every_seconds"] == (86400,)
    for fact in facts.values():
        assert fact["task_queue"] == queue_for("background")
        assert fact["overlap"] == "SKIP"
        assert fact["catchup_window_seconds"] == 3600
        assert fact["paused"] is False


async def test_an_operators_pause_survives_ensure(temporal: Client) -> None:
    await schedules.ensure()
    await dispatch.pause("spend_anomaly:platform", note="operator:ops: RB-07")
    await schedules.ensure()
    paused = await dispatch.describe_schedule("spend_anomaly:platform")
    assert paused.paused is True
    assert paused.note == "operator:ops: RB-07"
    await dispatch.unpause("spend_anomaly:platform", note="operator:ops: resolved")
    assert (await dispatch.describe_schedule("spend_anomaly:platform")).paused is False


async def test_a_triggered_run_does_each_job_once_on_the_background_queue(
    temporal: Client, temporal_target: str
) -> None:
    await schedules.ensure()
    # A second connection, as a second deployment's worker would have.
    other = await Client.connect(temporal_target, data_converter=data_converter())
    workflows = [platform.SpendAnomalyWorkflow, notifications.NotificationPurgeWorkflow]
    # Two background pools polling the same queue, as two deployments would: one run, one pass.
    async with (
        Worker(
            temporal,
            task_queue=queue_for("background"),
            workflows=workflows,
            activities=[_flag, _purge],
        ),
        Worker(
            other,
            task_queue=queue_for("background"),
            workflows=workflows,
            activities=[_flag, _purge],
        ),
    ):
        for schedule_id in IDS:
            await temporal.get_schedule_handle(schedule_id).trigger()
        for _ in range(200):
            if sorted(_passes) == ["anomaly", "purge"]:
                break
            await asyncio.sleep(0.1)
        await asyncio.sleep(1)  # nothing else arrives
    assert sorted(_passes) == ["anomaly", "purge"]
    for schedule_id in IDS:
        described = await temporal.get_schedule_handle(schedule_id).describe()
        assert len(described.info.recent_actions) == 1


async def test_delete_removes_the_schedule_and_ensure_brings_it_back(temporal: Client) -> None:
    await schedules.ensure()
    await dispatch.delete("notification_purge:platform")
    listed = [s.id async for s in await temporal.list_schedules()]
    assert "notification_purge:platform" not in listed
    assert (await schedules.ensure())["notification_purge:platform"] == "created"

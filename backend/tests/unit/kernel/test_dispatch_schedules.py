"""Q-01-T26 (Q-01 §4.5; DISPATCH-001): platform jobs on Temporal Schedules through
`kernel.dispatch`. A Schedule starts its workflow on the workflow's class queue, skips a run
while the last is open, catches up at most an hour, and converging an existing Schedule keeps an
operator's pause. Driven with a fake Temporal client; the real server is
`tests/integration/test_platform_schedules.py`."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from temporalio import workflow
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleOverlapPolicy,
    ScheduleState,
    ScheduleUpdate,
)

from abacus.kernel import dispatch
from abacus.kernel.dispatch import PlatformSchedule, queue_for, register_work_classes
from abacus.kernel.temporal import configure_temporal_client
from abacus.modules.communications import api as communications
from abacus.modules.notifications import api as notifications
from abacus.modules.platform import api as platform


class _Handle:
    def __init__(self, owner: _Client, schedule_id: str) -> None:
        self.owner = owner
        self.id = schedule_id

    async def update(self, updater: Callable[[object], ScheduleUpdate]) -> None:
        current = self.owner.schedules[self.id]
        given = SimpleNamespace(description=SimpleNamespace(schedule=current))
        self.owner.schedules[self.id] = updater(given).schedule
        self.owner.log.append(("update", self.id))

    async def pause(self, *, note: str | None = None) -> None:
        self.owner.schedules[self.id].state = ScheduleState(note=note, paused=True)
        self.owner.log.append(("pause", self.id))

    async def unpause(self, *, note: str | None = None) -> None:
        self.owner.schedules[self.id].state = ScheduleState(note=note, paused=False)
        self.owner.log.append(("unpause", self.id))

    async def delete(self) -> None:
        del self.owner.schedules[self.id]
        self.owner.log.append(("delete", self.id))


class _Client:
    """Stands in for the Temporal client's Schedule calls."""

    def __init__(self) -> None:
        self.schedules: dict[str, Schedule] = {}
        self.log: list[tuple[str, str]] = []

    async def create_schedule(self, schedule_id: str, schedule: Schedule) -> None:
        if schedule_id in self.schedules:
            raise ScheduleAlreadyRunningError()
        self.schedules[schedule_id] = schedule
        self.log.append(("create", schedule_id))

    def get_schedule_handle(self, schedule_id: str) -> _Handle:
        return _Handle(self, schedule_id)


@pytest.fixture
def client() -> Iterator[_Client]:
    fake = _Client()
    configure_temporal_client(cast(Client, fake))
    yield fake
    configure_temporal_client(None)


@workflow.defn(name="ScheduledBackground", sandboxed=False)
class _Background:
    @workflow.run
    async def run(self) -> int:
        return 0


@workflow.defn(name="ScheduledUnclassified", sandboxed=False)
class _Unclassified:
    @workflow.run
    async def run(self) -> int:
        return 0


register_work_classes({_Background: "background"})


def _job(
    name: str, every: timedelta = timedelta(hours=1), workflow_type: type = _Background
) -> PlatformSchedule:
    return PlatformSchedule(id=f"{name}:platform", workflow=workflow_type, every=every, note="n")


async def test_a_schedule_starts_its_workflow_on_its_class_queue(client: _Client) -> None:
    flow = "ScheduledBackground"
    assert await dispatch.schedule(_job(flow)) == "created"
    made = client.schedules["ScheduledBackground:platform"]
    action = made.action
    assert isinstance(action, ScheduleActionStartWorkflow)
    assert action.task_queue == queue_for("background") == "abacus-background"
    assert action.id == "ScheduledBackground:platform"
    assert [i.every for i in made.spec.intervals] == [timedelta(hours=1)]


async def test_overlap_is_skip_and_catch_up_is_one_hour(client: _Client) -> None:
    flow = "ScheduledPolicy"
    await dispatch.schedule(_job(flow))
    policy = client.schedules["ScheduledPolicy:platform"].policy
    assert policy.overlap == ScheduleOverlapPolicy.SKIP
    assert policy.catchup_window == timedelta(hours=1)


async def test_ensuring_twice_keeps_one_schedule_and_converges_it(client: _Client) -> None:
    flow = "ScheduledTwice"
    assert await dispatch.schedule(_job(flow)) == "created"
    assert await dispatch.schedule(_job(flow, timedelta(minutes=30))) == "updated"
    assert list(client.schedules) == ["ScheduledTwice:platform"]
    assert [i.every for i in client.schedules["ScheduledTwice:platform"].spec.intervals] == [
        timedelta(minutes=30)
    ]


async def test_converging_keeps_an_operators_pause(client: _Client) -> None:
    flow = "ScheduledPaused"
    await dispatch.schedule(_job(flow))
    await dispatch.pause("ScheduledPaused:platform", note="operator:ops: RB-07")
    await dispatch.schedule(_job(flow))
    state = client.schedules["ScheduledPaused:platform"].state
    assert state.paused is True
    assert state.note == "operator:ops: RB-07"


async def test_pause_unpause_and_delete_act_on_the_named_schedule(client: _Client) -> None:
    flow = "ScheduledLevers"
    await dispatch.schedule(_job(flow))
    await dispatch.pause("ScheduledLevers:platform", note="a")
    await dispatch.unpause("ScheduledLevers:platform", note="b")
    assert client.schedules["ScheduledLevers:platform"].state.paused is False
    await dispatch.delete("ScheduledLevers:platform")
    assert client.schedules == {}
    assert [verb for verb, _ in client.log] == ["create", "pause", "unpause", "delete"]


async def test_a_workflow_without_a_class_cannot_be_scheduled(client: _Client) -> None:
    with pytest.raises(LookupError):
        await dispatch.schedule(_job("Unclassified", workflow_type=_Unclassified))
    assert client.schedules == {}


def test_the_ses_drain_runs_every_minute_on_the_time_sensitive_queue() -> None:
    """Q-01-T46's drain had no starter until these Schedules (Q-01 §4.5: every minute)."""
    [job] = communications.SCHEDULES
    assert (job.id, job.every) == ("ses_events:platform", timedelta(minutes=1))
    assert job.workflow is communications.DrainSesEventsWorkflow
    assert communications.WORKFLOWS[communications.DrainSesEventsWorkflow] == "time_sensitive"


def test_the_two_moved_jobs_are_declared_as_background_schedules() -> None:
    declared = {job.id: job for job in (*platform.SCHEDULES, *notifications.SCHEDULES)}
    assert set(declared) == {
        "spend_anomaly:platform",
        "notification_purge:platform",
        "incident_reminders:platform",  # G-02-T18: the FTC clock reminders
        "pilot_metrics:platform",  # Q-04-T008: last week's pilot metrics (a batch job)
    }
    assert declared["spend_anomaly:platform"].every == timedelta(hours=1)
    assert declared["spend_anomaly:platform"].workflow is platform.SpendAnomalyWorkflow
    assert declared["notification_purge:platform"].every == timedelta(days=1)
    assert (
        declared["notification_purge:platform"].workflow is notifications.NotificationPurgeWorkflow
    )
    assert declared["pilot_metrics:platform"].every == timedelta(days=7)
    assert declared["pilot_metrics:platform"].workflow.__name__ == "PilotMetricsWorkflow"
    assert platform.WORKFLOWS[platform.SpendAnomalyWorkflow] == "background"
    assert notifications.WORKFLOWS[notifications.NotificationPurgeWorkflow] == "background"


async def test_g02t19_a_firm_schedule_runs_on_the_firms_calendar(client: _Client) -> None:
    """G-02-T19 (DEC-623): the 1st at 02:00 in the firm's zone, paused as its record says, and
    converged (not duplicated) on a second call."""
    job = dispatch.FirmSchedule(
        id="firm_export_schedule:00000000-0000-4000-8000-000000000001",
        workflow=_Background,
        arg="00000000-0000-4000-8000-000000000001",
        day_of_month=1,
        hour=2,
        minute=0,
        time_zone="America/Chicago",
        note="n",
    )
    assert await dispatch.firm_schedule(job, paused=True) == "created"
    made = client.schedules[job.id]
    assert made.spec.time_zone_name == "America/Chicago"
    [calendar] = made.spec.calendars
    assert [r.start for r in calendar.day_of_month] == [1]
    assert [r.start for r in calendar.hour] == [2]
    assert made.state.paused is True
    assert made.policy.overlap == ScheduleOverlapPolicy.SKIP
    assert await dispatch.firm_schedule(job, paused=False) == "updated"
    assert list(client.schedules) == [job.id]
    assert client.schedules[job.id].state.paused is False

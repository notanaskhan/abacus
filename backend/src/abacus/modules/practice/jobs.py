"""Practice's worker parts (I-01-T12): the client-activity projector and its daily prune."""

from __future__ import annotations

from datetime import timedelta

from temporalio import activity

from abacus.kernel.dispatch import PlatformSchedule, WorkClass, register_work_classes
from abacus.kernel.uow import Handler
from abacus.modules.practice.activity import SOURCES, on_event, prune_once
from abacus.modules.practice.agent_monitoring import agent_monitoring_activity
from abacus.modules.practice.overrides import SOURCE_KINDS as OVERRIDE_SOURCES
from abacus.modules.practice.overrides import record_outcome
from abacus.modules.practice.workflows import (
    AGENT_MONITORING_ID,
    HOME_ACTIVITY_PRUNE_ID,
    AgentMonitoringWorkflow,
    HomeActivityPruneWorkflow,
)


@activity.defn(name="practice.prune_home_activity")
async def prune_home_activity_activity() -> int:
    return await prune_once()


# The `HomeActivityProjector`: every allowlisted event type (I-01 §4.4).
SUBSCRIPTIONS: dict[str, Handler] = {
    **dict.fromkeys(SOURCES, on_event),
    # Q-05-T07 (DEC-5710): the override-rate projection (idempotent by event id).
    **dict.fromkeys(OVERRIDE_SOURCES, record_outcome),
}
WORKFLOWS: dict[type, WorkClass] = {
    HomeActivityPruneWorkflow: "background",
    AgentMonitoringWorkflow: "batch",  # Q-05-T08: nightly QM monitoring (dark)
}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (prune_home_activity_activity, agent_monitoring_activity)
SCHEDULES: tuple[PlatformSchedule, ...] = (
    PlatformSchedule(
        id=HOME_ACTIVITY_PRUNE_ID,
        workflow=HomeActivityPruneWorkflow,
        every=timedelta(days=1),
        note="I-01-T12: delete Home client-activity rows older than 90 days",
    ),
    PlatformSchedule(
        id=AGENT_MONITORING_ID,
        workflow=AgentMonitoringWorkflow,
        every=timedelta(days=1),
        note="Q-05-T08: QM findings for agents above tolerance; due and evaluation notices",
    ),
)

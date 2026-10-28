"""Practice's worker parts (I-01-T12): the client-activity projector and its daily prune."""

from __future__ import annotations

from datetime import timedelta

from temporalio import activity

from abacus.kernel.dispatch import PlatformSchedule, WorkClass, register_work_classes
from abacus.kernel.uow import Handler
from abacus.modules.practice.activity import SOURCES, project, prune_once
from abacus.modules.practice.workflows import HOME_ACTIVITY_PRUNE_ID, HomeActivityPruneWorkflow


@activity.defn(name="practice.prune_home_activity")
async def prune_home_activity_activity() -> int:
    return await prune_once()


# The `HomeActivityProjector`: every allowlisted event type (I-01 §4.4).
SUBSCRIPTIONS: dict[str, Handler] = dict.fromkeys(SOURCES, project)
WORKFLOWS: dict[type, WorkClass] = {HomeActivityPruneWorkflow: "background"}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (prune_home_activity_activity,)
SCHEDULES: tuple[PlatformSchedule, ...] = (
    PlatformSchedule(
        id=HOME_ACTIVITY_PRUNE_ID,
        workflow=HomeActivityPruneWorkflow,
        every=timedelta(days=1),
        note="I-01-T12: delete Home client-activity rows older than 90 days",
    ),
)

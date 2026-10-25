"""The daily notification purge as a platform job (Q-01-T26; SPEC-013 AC-10).

`NotificationPurgeWorkflow` runs one `purge_once()` pass a day on the Schedule
`notification_purge:platform` (overlap SKIP, one hour catch-up; `kernel.dispatch`). It replaced
the loop the interactive worker ran, which ran once per worker process.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import activity

from abacus.kernel.dispatch import PlatformSchedule, WorkClass, register_work_classes
from abacus.modules.notifications.service import purge_once
from abacus.modules.notifications.workflows import NOTIFICATION_PURGE_ID, NotificationPurgeWorkflow


@activity.defn(name="notifications.purge_expired")
async def purge_expired_activity() -> int:
    return await purge_once()


WORKFLOWS: dict[type, WorkClass] = {NotificationPurgeWorkflow: "background"}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (purge_expired_activity,)
SCHEDULES: tuple[PlatformSchedule, ...] = (
    PlatformSchedule(
        id=NOTIFICATION_PURGE_ID,
        workflow=NotificationPurgeWorkflow,
        every=timedelta(days=1),
        note="SPEC-013 AC-10: the daily notification purge (Q-01-T26)",
    ),
)

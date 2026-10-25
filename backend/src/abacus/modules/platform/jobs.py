"""Platform jobs on Temporal Schedules (Q-01-T26; Q-01 §4.5; DISPATCH-001).

`SpendAnomalyWorkflow` runs `ai_gateway.budgets.flag_anomalies` once an hour on the Schedule
`spend_anomaly:platform` (overlap SKIP, one hour catch-up). It replaced the loop the interactive
worker ran, which ran once per worker process: two interactive workers flagged twice.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import activity

from abacus.ai_gateway.budgets import ANOMALY_INTERVAL_SECONDS, flag_anomalies
from abacus.kernel.dispatch import PlatformSchedule, WorkClass, register_work_classes
from abacus.modules.platform.workflows import SPEND_ANOMALY_ID, SpendAnomalyWorkflow


@activity.defn(name="platform.flag_spend_anomalies")
async def flag_spend_anomalies_activity() -> int:
    return await flag_anomalies()


WORKFLOWS: dict[type, WorkClass] = {SpendAnomalyWorkflow: "background"}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (flag_spend_anomalies_activity,)
SCHEDULES: tuple[PlatformSchedule, ...] = (
    PlatformSchedule(
        id=SPEND_ANOMALY_ID,
        workflow=SpendAnomalyWorkflow,
        every=timedelta(seconds=ANOMALY_INTERVAL_SECONDS),
        note="SPEC-007 AC-6: the hourly spend-anomaly pass (Q-01-T26)",
    ),
)

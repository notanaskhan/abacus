"""Platform jobs on Temporal Schedules (Q-01-T26; Q-01 §4.5; DISPATCH-001).

`SpendAnomalyWorkflow` runs `ai_gateway.budgets.flag_anomalies` once an hour on the Schedule
`spend_anomaly:platform` (overlap SKIP, one hour catch-up). It replaced the loop the interactive
worker ran, which ran once per worker process: two interactive workers flagged twice.
"""

from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

from temporalio import activity

from abacus.ai_gateway.budgets import ANOMALY_INTERVAL_SECONDS, flag_anomalies
from abacus.kernel.clock import system_now
from abacus.kernel.dispatch import PlatformSchedule, WorkClass, register_work_classes
from abacus.modules.identity.api import firm_tenant_ids
from abacus.modules.platform.incident_register import incident_reminders_activity
from abacus.modules.platform.pilot_metrics import compute_week, last_week
from abacus.modules.platform.safeguards import ACTIVITIES as WISP_ACTIVITIES
from abacus.modules.platform.workflows import (
    INCIDENT_REMINDERS_ID,
    PILOT_METRICS_ID,
    SPEND_ANOMALY_ID,
    IncidentClockRemindersWorkflow,
    PilotMetricsWorkflow,
    SpendAnomalyWorkflow,
    WispPackWorkflow,
)

CENTRAL = ZoneInfo("America/Chicago")


@activity.defn(name="platform.flag_spend_anomalies")
async def flag_spend_anomalies_activity() -> int:
    return await flag_anomalies()


@activity.defn(name="platform.pilot_metrics")
async def pilot_metrics_activity() -> int:
    """Q-04-T008: last week's snapshots for every firm (each firm's own tenant context)."""
    week = last_week(system_now().astimezone(CENTRAL).date())
    written = 0
    for tenant_id in await firm_tenant_ids():
        written += await compute_week(tenant_id, week)
    return written


WORKFLOWS: dict[type, WorkClass] = {
    SpendAnomalyWorkflow: "background",
    IncidentClockRemindersWorkflow: "background",  # G-02-T18: days 20, 25 and 29
    WispPackWorkflow: "batch",  # G-02-T20: Export WISP pack
    PilotMetricsWorkflow: "batch",  # Q-04-T008: Mondays 06:00 Central
}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (
    flag_spend_anomalies_activity,
    incident_reminders_activity,  # G-02-T18
    *WISP_ACTIVITIES,  # G-02-T20
    pilot_metrics_activity,  # Q-04-T008
)
SCHEDULES: tuple[PlatformSchedule, ...] = (
    PlatformSchedule(
        id=SPEND_ANOMALY_ID,
        workflow=SpendAnomalyWorkflow,
        every=timedelta(seconds=ANOMALY_INTERVAL_SECONDS),
        note="SPEC-007 AC-6: the hourly spend-anomaly pass (Q-01-T26)",
    ),
    PlatformSchedule(
        id=INCIDENT_REMINDERS_ID,
        workflow=IncidentClockRemindersWorkflow,
        every=timedelta(hours=6),
        note="G-02-T18: FTC clock reminders on days 20, 25 and 29, once each (DEC-625)",
    ),
    PlatformSchedule(
        id=PILOT_METRICS_ID,
        workflow=PilotMetricsWorkflow,
        every=timedelta(days=7),
        weekly=(1, 6, 0, "America/Chicago"),
        note="Q-04-T008: last week's pilot metrics, Mondays 06:00 Central (AC-8.1)",
    ),
)

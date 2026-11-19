"""Practice workflows (ADR-090): orchestration only, activities by name.

`HomeActivityPrune` (I-01-T12; DEC-900): the daily 90-day prune of `home_activity_items`, started
only by its Schedule `home_activity_prune:platform` (overlap SKIP). v1, recorded in
`home-activity-prune-v1-pruned.json`; a change to what it schedules goes behind
`workflow.patched`.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

HOME_ACTIVITY_PRUNE_ID = "home_activity_prune:platform"
_PRUNE_TIMEOUT = timedelta(minutes=10)
_PRUNE_RETRY = RetryPolicy(maximum_attempts=3)  # a failed day is retried by the next run


@workflow.defn(name="HomeActivityPrune")
class HomeActivityPruneWorkflow:
    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "practice.prune_home_activity",
            result_type=int,
            start_to_close_timeout=_PRUNE_TIMEOUT,
            retry_policy=_PRUNE_RETRY,
        )


AGENT_MONITORING_ID = "agent_monitoring:platform"
_MONITOR_TIMEOUT = timedelta(minutes=20)
_MONITOR_HEARTBEAT = timedelta(minutes=5)


@workflow.defn(name="AgentMonitoringWorkflow")
class AgentMonitoringWorkflow:
    """Q-05-T08 (S51 partials; DEC-5727): the nightly QM monitoring run, started only by its
    Schedule `agent_monitoring:platform` (overlap SKIP). v1, recorded in
    `agent-monitoring-v1-swept.json`; a change goes behind `workflow.patched`."""

    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "practice.agent_monitoring_sweep",
            result_type=int,
            start_to_close_timeout=_MONITOR_TIMEOUT,
            heartbeat_timeout=_MONITOR_HEARTBEAT,
            retry_policy=_PRUNE_RETRY,
        )

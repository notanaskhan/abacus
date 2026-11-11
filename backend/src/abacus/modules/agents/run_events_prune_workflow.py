"""`RunEventsPruneWorkflow` (P-10-T44; P-10 §4.4; DEC-4302): one `agents.run_events.prune` pass
a day on the Schedule `run_events_prune:platform` (overlap SKIP). Orchestration only; the activity
is `trace_records.prune_run_events_activity`. No branching, so one history pins it
(`run-events-prune-v1.json`)."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from temporalio import workflow
from temporalio.common import RetryPolicy

PRUNE_ID: Final = "run_events_prune:platform"


@workflow.defn(name="RunEventsPrune")
class RunEventsPruneWorkflow:
    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "agents.run_events.prune",
            result_type=int,
            start_to_close_timeout=timedelta(hours=1),
            retry_policy=RetryPolicy(maximum_attempts=3, initial_interval=timedelta(minutes=1)),
        )

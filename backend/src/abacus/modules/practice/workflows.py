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

"""`StandardsRunWorkflow` (T-08-T14; ADR-090; S52 end pass): its own module with no service
imports, so the workflow sandbox can load it. Code only: no model is called (OQ-3). A change lands
behind `workflow.patched(...)` so the v1 history replays."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Final, cast

from temporalio import workflow
from temporalio.common import RetryPolicy

ITEMS_ACTIVITY: Final = "standards_run_items"
ITEM_ACTIVITY: Final = "standards_run_item"
FINISH_ACTIVITY: Final = "standards_run_finish"
_RETRY: Final = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=5,
    non_retryable_error_types=["NotFound"],
)


@workflow.defn(name="StandardsRunWorkflow")
class StandardsRunWorkflow:
    """`standards_run:<tenant>:<run>`: list the items, run each return's checks in parallel, then
    complete the run. Code only: no model is called (OQ-3)."""

    @workflow.run
    async def run(self, given: list[str]) -> str:
        items = cast(
            list[str],
            await workflow.execute_activity(
                ITEMS_ACTIVITY,
                given,
                result_type=list[str],
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=_RETRY,
            ),
        )
        await asyncio.gather(
            *(
                workflow.execute_activity(
                    ITEM_ACTIVITY,
                    [*given, item],
                    result_type=str,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=_RETRY,
                )
                for item in items
            )
        )
        return cast(
            str,
            await workflow.execute_activity(
                FINISH_ACTIVITY,
                given,
                result_type=str,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=_RETRY,
            ),
        )

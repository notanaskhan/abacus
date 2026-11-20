"""`DestructionExecuteWorkflow` (Q-05-T15; ADR-090; S52 end pass): its own module with no
service imports, so the workflow sandbox can load it. A change lands behind `workflow.patched(...)`
so the v1 history replays."""

from __future__ import annotations

from datetime import timedelta
from typing import Final, cast

from temporalio import workflow
from temporalio.common import RetryPolicy

EXECUTE: Final = "evidence.execute_destruction"


@workflow.defn(name="DestructionExecuteWorkflow")
class DestructionExecuteWorkflow:
    """`destruction:<tenant>:<batch>`, batch class: one activity that resumes where it stopped."""

    @workflow.run
    async def run(self, given: list[str]) -> str:
        return cast(
            str,
            await workflow.execute_activity(
                EXECUTE, given, result_type=str,
                start_to_close_timeout=timedelta(hours=2),
                heartbeat_timeout=None,
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=30), maximum_attempts=10,
                    non_retryable_error_types=["NotFound", "DomainConflict"],
                ),
            ),
        )  # fmt: skip

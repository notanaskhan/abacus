"""`DestructionAssembleWorkflow` (Q-05-T11; S51 partials, TASK-8731; ADR-090): the daily run of
the quarterly destruction assembly (`destruction_jobs.py` holds its activity and Schedule)."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from temporalio import workflow
from temporalio.common import RetryPolicy

ACTIVITY: Final = "evidence.destruction.assemble_sweep"
_TIMEOUT = timedelta(minutes=30)
_HEARTBEAT = timedelta(minutes=5)
_RETRY = RetryPolicy(maximum_attempts=3)  # a failed day is retried; assembly is idempotent


@workflow.defn(name="DestructionAssembleWorkflow")
class DestructionAssembleWorkflow:
    """v1: one activity per run, started only by its Schedule (overlap SKIP). A change to what it
    schedules goes behind `workflow.patched`, so its recorded history keeps replaying."""

    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            ACTIVITY,
            result_type=int,
            start_to_close_timeout=_TIMEOUT,
            heartbeat_timeout=_HEARTBEAT,
            retry_policy=_RETRY,
        )

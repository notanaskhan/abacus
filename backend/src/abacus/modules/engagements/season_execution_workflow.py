"""`SeasonSetupExecutionWorkflow` (T-08-T12; S51 partials, TASK-8739; ADR-090): one approved
cohort's execution, `season_exec:<tenant>:<cohort>`. One activity runs the cohort's rows step by
step (idempotent on row and step, so a retried activity or a replayed history creates nothing
twice); the activity consumes the approval's single-use grant first."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from temporalio import workflow
from temporalio.common import RetryPolicy

ACTIVITY: Final = "engagements.season_execute_cohort"
_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=5,
    non_retryable_error_types=["ApprovalGrantMismatch", "NotFound"],
)


@dataclass(frozen=True)
class SeasonExecInput:
    tenant_id: str
    cohort_id: str


@workflow.defn(name="SeasonSetupExecutionWorkflow")
class SeasonSetupExecutionWorkflow:
    @workflow.run
    async def run(self, given: SeasonExecInput) -> str:
        return await workflow.execute_activity(
            ACTIVITY,
            given,
            result_type=str,
            start_to_close_timeout=timedelta(minutes=30),
            heartbeat_timeout=timedelta(minutes=5),
            retry_policy=_RETRY,
        )

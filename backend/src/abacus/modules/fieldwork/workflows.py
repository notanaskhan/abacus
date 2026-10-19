"""Fieldwork workflows (SPEC-037; TASK-077 D3). Orchestration only (ADR-017)."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from abacus.modules.fieldwork.workflow_types import ProcedureSelectInput

_TIMEOUT = timedelta(minutes=10)
_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=3,
)


@workflow.defn(name="procedure_select")
class ProcedureSelectWorkflow:
    """One selection for a procedure: build and tie the population, select, record. A failure
    after the retries marks the procedure `failed` so it can be run again."""

    @workflow.run
    async def run(self, input: ProcedureSelectInput) -> str:
        try:
            return await workflow.execute_activity(
                "procedure.select",
                input,
                result_type=str,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        except ActivityError:
            await workflow.execute_activity(
                "procedure.fail",
                input,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=0),
            )
            return "failed"

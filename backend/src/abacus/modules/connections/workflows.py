"""The retrieval workflow (ADR-017, ADR-038, ADR-090). PROTECTED. TASK-010 design §6.

Orchestration only: activities by name, identifiers in, identifiers out. No I/O, clocks or
randomness here (the sandbox enforces it; WF-001 limits imports). Any change to the steps below
must be guarded with `workflow.patched(...)`, and the replay test (AC-19) must still pass against
`tests/workflows/histories/retrieval-v1.json`.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from abacus.modules.connections.workflow_types import (
        FailInput,
        RetrievalInput,
        RetrievalOutcome,
    )

STAGES = (
    "retrieval.pull_raw",
    "retrieval.normalise_raw",
    "retrieval.validate_run",
    "retrieval.snapshot",
)
RENDER = "retrieval.render"
FAIL = "retrieval.fail_run"
_TIMEOUT = timedelta(minutes=5)
_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=6,
)


@workflow.defn(name="retrieval")
class RetrievalWorkflow:
    @workflow.run
    async def run(self, input: RetrievalInput) -> RetrievalOutcome:
        try:
            for stage in STAGES:
                await workflow.execute_activity(
                    stage, input, start_to_close_timeout=_TIMEOUT, retry_policy=_RETRY
                )
            version_id = await workflow.execute_activity(
                RENDER,
                input,
                result_type=str,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        except ActivityError as err:
            status, code = _failure(err)
            return await workflow.execute_activity(
                FAIL,
                FailInput(input.tenant_id, input.run_id, status, code),
                result_type=RetrievalOutcome,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        return RetrievalOutcome("succeeded", None, version_id)


def _failure(err: ActivityError) -> tuple[str, str]:
    cause = err.cause
    if isinstance(cause, ApplicationError):
        if cause.type == "RunFailed" and len(cause.details) >= 2:
            return str(cause.details[0]), str(cause.details[1])
        if cause.type == "Unavailable":
            return "failed", "provider_unavailable"
    return "failed", "internal_error"

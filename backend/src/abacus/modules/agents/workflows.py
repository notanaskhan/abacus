"""The screening workflow (ADR-017, ADR-090). PROTECTED. TASK-011 design §7.

Started by the relay for each `evidence_version.created` (`screening:<evidence_version_id>`).
Orchestration only: activities by name, identifiers in and out, no I/O (WF-001). Steps:
create the agent run (none: `skipped`), then screen it as one activity. Any failure,
cancellation included, ends in `screening.fail_run`, which retries until it succeeds, so a run
never stays `running` because of the workflow. Changes are guarded with `workflow.patched(...)`.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError, is_cancelled_exception

with workflow.unsafe.imports_passed_through():
    from abacus.modules.agents.workflow_types import (
        CANCELLED,
        INTERNAL_ERROR,
        PROVIDER_UNAVAILABLE,
        FailInput,
        RunInput,
        ScreeningInput,
        ScreeningOutcome,
    )

_TIMEOUT = timedelta(minutes=2)
_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=4,
)
_FAIL_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=0,
)
_UNAVAILABLE = frozenset({"ProviderError"})


@workflow.defn(name="screening")
class ScreeningWorkflow:
    @workflow.run
    async def run(self, input: ScreeningInput) -> ScreeningOutcome:
        run_id = await workflow.execute_activity(
            "screening.create_run",
            input,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        if not run_id:
            return ScreeningOutcome("skipped")
        run = RunInput(input.tenant_id, run_id)
        try:
            return await workflow.execute_activity(
                "screening.screen",
                run,
                result_type=ScreeningOutcome,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        except ActivityError as err:
            if is_cancelled_exception(err):
                await _fail(run, CANCELLED)
                raise asyncio.CancelledError from err
            return await _fail(run, _code(err))
        except asyncio.CancelledError:
            await _fail(run, CANCELLED)
            raise


async def _fail(run: RunInput, code: str) -> ScreeningOutcome:
    return await workflow.execute_activity(
        "screening.fail_run",
        FailInput(run.tenant_id, run.run_id, code),
        result_type=ScreeningOutcome,
        start_to_close_timeout=_TIMEOUT,
        retry_policy=_FAIL_RETRY,
    )


def _code(err: ActivityError) -> str:
    cause = err.cause
    if isinstance(cause, ApplicationError) and cause.type in _UNAVAILABLE:
        return PROVIDER_UNAVAILABLE
    return INTERNAL_ERROR

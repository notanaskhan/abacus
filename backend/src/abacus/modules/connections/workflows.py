"""The retrieval workflow (ADR-017, ADR-038, ADR-090). PROTECTED. TASK-010 design §6, rev. 1.

Orchestration only: activities by name, identifiers in, identifiers out. No I/O, clocks or
randomness here (the sandbox enforces it; WF-001 limits imports). The steps are written out one
by one: any change must be guarded with `workflow.patched(...)`, and every history in
`tests/workflows/histories/` must still replay (AC-19). Histories are never re-recorded over;
a changed workflow adds `retrieval-vN+1-*.json`.

A run never stays `running` because of the workflow: any failure, cancellation included, ends in
`retrieval.fail_run`, which retries until the database accepts it.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError, is_cancelled_exception

with workflow.unsafe.imports_passed_through():
    from abacus.modules.connections.workflow_types import (
        CANCELLED,
        CAPACITY_TIMEOUT,
        FORBIDDEN,
        FORBIDDEN_ERROR,
        INTERNAL_ERROR,
        PROVIDER_UNAVAILABLE,
        RUN_FAILED,
        UNAVAILABLE,
        FailInput,
        RetrievalInput,
        RetrievalOutcome,
        SlotGrant,
    )

_TIMEOUT = timedelta(minutes=5)
_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=6,
)
# Ending a run must not give up: unlimited attempts, at most a minute apart.
_FAIL_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=0,
)


@workflow.defn(name="retrieval")
class RetrievalWorkflow:
    @workflow.run
    async def run(self, input: RetrievalInput) -> RetrievalOutcome:
        # SPEC-003: hold a work slot of the run's class for the whole run (TASK-018 design §4).
        slotted = workflow.patched("work-slots")
        try:
            if slotted and not await wait_for_slot("retrieval.acquire_slot", input):
                return await _fail(input, "failed", CAPACITY_TIMEOUT)
            await workflow.execute_activity(
                "retrieval.pull_raw", input, start_to_close_timeout=_TIMEOUT, retry_policy=_RETRY
            )
            await workflow.execute_activity(
                "retrieval.normalise_raw",
                input,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
            await workflow.execute_activity(
                "retrieval.validate_run",
                input,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
            await workflow.execute_activity(
                "retrieval.snapshot", input, start_to_close_timeout=_TIMEOUT, retry_policy=_RETRY
            )
            version_id = await workflow.execute_activity(
                "retrieval.render",
                input,
                result_type=str,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        except ActivityError as err:
            if is_cancelled_exception(err):
                # The workflow was cancelled while an activity ran: end the run, then end the
                # workflow as cancelled too.
                await _fail(input, "failed", CANCELLED)
                raise asyncio.CancelledError from err
            status, code = _failure(err)
            return await _fail(input, status, code)
        except asyncio.CancelledError:
            await _fail(input, "failed", CANCELLED)
            raise
        finally:
            if slotted:
                await workflow.execute_activity(
                    "retrieval.release_slot",
                    input,
                    start_to_close_timeout=_TIMEOUT,
                    retry_policy=_FAIL_RETRY,
                )
        return RetrievalOutcome("succeeded", None, version_id)


async def _fail(input: RetrievalInput, status: str, code: str) -> RetrievalOutcome:
    return await workflow.execute_activity(
        "retrieval.fail_run",
        FailInput(input.tenant_id, input.run_id, status, code),
        result_type=RetrievalOutcome,
        start_to_close_timeout=_TIMEOUT,
        retry_policy=_FAIL_RETRY,
    )


def _failure(err: ActivityError) -> tuple[str, str]:
    cause = err.cause
    if isinstance(cause, ApplicationError):
        if cause.type == RUN_FAILED and len(cause.details) >= 2:
            return str(cause.details[0]), str(cause.details[1])
        if cause.type == UNAVAILABLE:
            return "failed", PROVIDER_UNAVAILABLE
        # A denial (a wall on the person the run acts for) ends the run `forbidden` (SPEC-002 §12).
        if cause.type == FORBIDDEN_ERROR and workflow.patched("retrieval-forbidden-code"):
            return "failed", FORBIDDEN
    return "failed", INTERNAL_ERROR


async def wait_for_slot(activity: str, arg: object) -> bool:
    """SPEC-003 (TASK-018 design §4, D2): ask `activity` for the run's work slot until granted
    (True), or until the class's maximum wait has passed (False). Between asks the workflow
    sleeps on a durable timer with jittered backoff, so waiting holds no worker slot and survives
    deploys; the backoff grows with the maximum wait, so a day-long wait stays a few hundred
    activities in the history. The same loop is in the other module's workflows (ADR-017 keeps
    workflows from sharing code outside their module)."""
    started = workflow.now()
    delay = 1.0
    while True:
        grant = await workflow.execute_activity(
            activity,
            arg,
            result_type=SlotGrant,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        if grant.granted:
            return True
        if (workflow.now() - started).total_seconds() >= grant.max_wait_seconds:
            return False
        await workflow.sleep(timedelta(seconds=delay * (0.5 + workflow.random().random())))
        delay = min(delay * 2, max(10.0, grant.max_wait_seconds / 300))

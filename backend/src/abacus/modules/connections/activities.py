"""Retrieval activities: one per pipeline stage (ADR-017, ADR-038). PROTECTED.
TASK-010 design §6.

Each activity first proves its system context from the run row (`load_system_context`), then
runs its stage. Decided outcomes (failed run, invalid data, missing or forbidden resource) are
raised as non-retryable `ApplicationError`s whose type is the exception's class name; provider
outages and infrastructure errors propagate and are retried. A retry that finds the run already
succeeded returns quietly. Activity names are fixed: renaming one breaks replay (ADR-090).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.modules.connections.pipeline import (
    RunFailed,
    fail_run,
    is_retryable,
    normalise_raw,
    pull_raw,
    render,
    snapshot,
    validate_run,
)
from abacus.modules.connections.service import RunNotRunning, load_system_context
from abacus.modules.connections.workflow_types import FailInput, RetrievalInput, RetrievalOutcome
from abacus.modules.identity.api import SystemContext


def _non_retryable(exc: BaseException) -> ApplicationError:
    if isinstance(exc, RunFailed):
        return ApplicationError(
            exc.code, exc.status, exc.code, type="RunFailed", non_retryable=True
        )
    return ApplicationError(type(exc).__name__, type=type(exc).__name__, non_retryable=True)


async def _system(input: RetrievalInput) -> SystemContext | None:
    """None if the run already succeeded (a retry after the work committed)."""
    try:
        return await load_system_context(UUID(input.tenant_id), UUID(input.run_id))
    except RunNotRunning as exc:
        if str(exc) == "succeeded":
            return None
        raise ApplicationError(
            str(exc), str(exc), str(exc), type="RunFailed", non_retryable=True
        ) from None


async def _stage[T](
    input: RetrievalInput, stage: Callable[[SystemContext], Awaitable[T]]
) -> T | None:
    system = await _system(input)
    if system is None:
        return None
    try:
        return await stage(system)
    except Exception as exc:
        if is_retryable(exc):
            raise
        raise _non_retryable(exc) from None


@activity.defn(name="retrieval.pull_raw")
async def pull_raw_activity(input: RetrievalInput) -> None:
    await _stage(input, pull_raw)


@activity.defn(name="retrieval.normalise_raw")
async def normalise_raw_activity(input: RetrievalInput) -> None:
    await _stage(input, normalise_raw)


@activity.defn(name="retrieval.validate_run")
async def validate_run_activity(input: RetrievalInput) -> None:
    await _stage(input, validate_run)


@activity.defn(name="retrieval.snapshot")
async def snapshot_activity(input: RetrievalInput) -> None:
    await _stage(input, snapshot)


@activity.defn(name="retrieval.render")
async def render_activity(input: RetrievalInput) -> str | None:
    version_id = await _stage(input, render)
    return str(version_id) if version_id is not None else None


@activity.defn(name="retrieval.fail_run")
async def fail_run_activity(input: FailInput) -> RetrievalOutcome:
    """After retries are exhausted or a stage failed for good: end the run (if still running)
    and report its final state."""
    try:
        system = await load_system_context(UUID(input.tenant_id), UUID(input.run_id))
    except RunNotRunning as exc:
        return RetrievalOutcome(str(exc), input.code)
    failed = await fail_run(system, input.status, input.code)
    return RetrievalOutcome(failed.status, failed.code)


ACTIVITIES = (
    pull_raw_activity,
    normalise_raw_activity,
    validate_run_activity,
    snapshot_activity,
    render_activity,
    fail_run_activity,
)

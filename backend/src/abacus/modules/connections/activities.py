"""Retrieval activities: one per pipeline stage (ADR-017, ADR-038). PROTECTED.
TASK-010 design §6.

Each activity first proves its system context from the run row (`load_system_context`), then
runs its stage. Every error leaves as an `ApplicationError` carrying only the exception's class
name (never its message): decided outcomes (failed run, invalid data, missing or forbidden
resource) are non-retryable, provider outages and infrastructure errors are retryable. A retry
that finds the run already succeeded returns its recorded result. Activity names are fixed:
renaming one breaks replay (ADR-090).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.kernel import slots
from abacus.kernel.config import settings
from abacus.kernel.errors import NotFound
from abacus.modules.connections.pipeline import (
    RunFailed,
    fail_run,
    is_retryable,
    mark_queued,
    normalise_raw,
    pull_raw,
    render,
    snapshot,
    validate_run,
)
from abacus.modules.connections.service import (
    RunNotRunning,
    load_system_context,
    succeeded_version,
)
from abacus.modules.connections.workflow_types import (
    FAIL_CODES,
    FAIL_STATUSES,
    INTERNAL_ERROR,
    RUN_FAILED,
    FailInput,
    RetrievalInput,
    RetrievalOutcome,
    SlotGrant,
)
from abacus.modules.identity.api import SystemContext


def _as_application_error(exc: BaseException, *, retryable: bool) -> ApplicationError:
    """Only the exception's class name crosses to Temporal, never its message: messages can
    carry provider text or database values (security S3). `RunFailed` adds its status and
    failure code as details, which the codec encrypts."""
    if isinstance(exc, RunFailed):
        return ApplicationError(
            RUN_FAILED, exc.status, exc.code, type=RUN_FAILED, non_retryable=True
        )
    name = type(exc).__name__
    return ApplicationError(name, type=name, non_retryable=not retryable)


async def _system(input: RetrievalInput) -> SystemContext | None:
    """None if the run already succeeded (a retry after the work committed). A finished run
    reports its own status and code; a missing run is a decided outcome too."""
    try:
        return await load_system_context(UUID(input.tenant_id), UUID(input.run_id))
    except RunNotRunning as exc:
        if exc.status == "succeeded":
            return None
        raise _as_application_error(
            RunFailed(exc.status, exc.failure_code or "unknown"), retryable=False
        ) from None
    except NotFound as exc:
        raise _as_application_error(exc, retryable=False) from None


async def _stage[T](
    input: RetrievalInput, stage: Callable[[SystemContext], Awaitable[T]]
) -> T | None:
    system = await _system(input)
    if system is None:
        return None
    try:
        work_class = slots.current_class()
        if work_class is not None:
            await slots.keep(system.tenant, system.engagement_id, work_class)
        return await stage(system)
    except Exception as exc:
        raise _as_application_error(exc, retryable=is_retryable(exc)) from None


@activity.defn(name="retrieval.acquire_slot")
async def acquire_slot_activity(input: RetrievalInput) -> SlotGrant:
    """Ask for the run's work slot (SPEC-003): granted, or the run is marked queued with its
    reason and estimate. A run already finished, or on the legacy queue, needs none."""
    try:
        system = await _system(input)
    except ApplicationError as ended:
        if ended.type == RUN_FAILED:  # the run already ended: nothing to hold a slot for
            return SlotGrant(True, 0)
        raise
    work_class = slots.current_class()
    if system is None or work_class is None:
        return SlotGrant(True, 0)
    try:
        decision = await slots.acquire(
            system.tenant, slots.current_holder(), system.engagement_id, work_class
        )
        await mark_queued(
            system,
            None if decision.granted else decision.reason,
            None if decision.granted else decision.estimated_start_at,
        )
    except Exception as exc:
        raise _as_application_error(exc, retryable=True) from None
    return SlotGrant(decision.granted, settings().work_classes[work_class].max_wait_seconds)


@activity.defn(name="retrieval.release_slot")
async def release_slot_activity(input: RetrievalInput) -> None:
    """Free the run's slot (idempotent; also when the run has ended)."""
    if slots.current_class() is None:
        return
    try:
        await slots.release(UUID(input.tenant_id), slots.current_holder())
    except Exception as exc:
        raise _as_application_error(exc, retryable=True) from None


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
    if version_id is None:  # retried after success: report what the run recorded
        version_id = await succeeded_version(UUID(input.tenant_id), UUID(input.run_id))
    return str(version_id) if version_id is not None else None


@activity.defn(name="retrieval.fail_run")
async def fail_run_activity(input: FailInput) -> RetrievalOutcome:
    """After retries are exhausted or a stage failed for good: end the run (if still running)
    and report its final state."""
    try:
        system = await load_system_context(UUID(input.tenant_id), UUID(input.run_id))
    except RunNotRunning as exc:
        version = await succeeded_version(UUID(input.tenant_id), UUID(input.run_id))
        return RetrievalOutcome(
            exc.status, exc.failure_code, str(version) if version is not None else None
        )
    except NotFound as exc:
        raise _as_application_error(exc, retryable=False) from None
    # The workflow decides only these; the stage failures are already recorded by the stages.
    status = input.status if input.status in FAIL_STATUSES else "failed"
    code = input.code if input.code in FAIL_CODES else INTERNAL_ERROR
    failed = await fail_run(system, status, code)
    return RetrievalOutcome(failed.status, failed.code)


ACTIVITIES = (
    acquire_slot_activity,
    release_slot_activity,
    pull_raw_activity,
    normalise_raw_activity,
    validate_run_activity,
    snapshot_activity,
    render_activity,
    fail_run_activity,
)

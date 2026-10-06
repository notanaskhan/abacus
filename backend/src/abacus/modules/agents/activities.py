"""Screening activities (ADR-017, ADR-025). PROTECTED. TASK-011 design §7.

`screening.screen` proves the agent's context from its run row first (`load_agent_context`),
then screens as one activity: a retry after a failed final write calls the model again, and the
spend counts against the run's budget. It heartbeats, so a timed-out attempt is cancelled. Every
error, database errors included, crosses to Temporal as an `ApplicationError` carrying only the
exception's class name, never its message. Terminal errors are non-retryable (`screen` has
already failed the run); provider outages and infrastructure errors are retried. A retry that
finds the run already ended reports what it recorded. Activity names are fixed (ADR-090).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.kernel.errors import NotFound
from abacus.modules.agents.service import (
    TERMINAL,
    AgentRunNotRunning,
    create_screening_run,
    fail_run,
    load_agent_context,
    run_outcome,
    screen,
)
from abacus.modules.agents.workflow_types import (
    FAIL_CODES,
    INTERNAL_ERROR,
    FailInput,
    RunInput,
    ScreeningInput,
    ScreeningOutcome,
)
from abacus.modules.identity.api import NoActiveTenant

INITIATOR_INACTIVE = "initiator_inactive"


def _as_application_error(exc: BaseException, *, retryable: bool) -> ApplicationError:
    name = type(exc).__name__
    return ApplicationError(name, type=name, non_retryable=not retryable)


async def _recorded(tenant_id: UUID, run_id: UUID) -> ScreeningOutcome:
    found = await run_outcome(tenant_id, run_id)
    return ScreeningOutcome(
        found.status,
        str(run_id),
        found.failure_code,
        str(found.screening_result_id) if found.screening_result_id else None,
    )


HEARTBEAT_EVERY = 10.0


@asynccontextmanager
async def _heartbeating() -> AsyncGenerator[None]:
    """Heartbeat while the body runs, so Temporal can cancel a timed-out attempt (the
    cancellation arrives as `CancelledError` at the next await)."""

    async def beat() -> None:
        while True:
            activity.heartbeat()
            await asyncio.sleep(HEARTBEAT_EVERY)

    task = asyncio.create_task(beat())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


@activity.defn(name="screening.create_run")
async def create_run_activity(input: ScreeningInput) -> str | None:
    try:
        run_id = await create_screening_run(
            UUID(input.tenant_id),
            UUID(input.evidence_version_id),
            UUID(input.event_id),
            UUID(input.requested_by) if input.requested_by else None,
        )
    except NotFound as exc:
        raise _as_application_error(exc, retryable=False) from None
    except Exception as exc:
        raise _as_application_error(exc, retryable=True) from None
    return str(run_id) if run_id is not None else None


async def _screen(tenant_id: UUID, run_id: UUID) -> ScreeningOutcome:
    try:
        agent = await load_agent_context(tenant_id, run_id)
    except AgentRunNotRunning:
        return await _recorded(tenant_id, run_id)
    except NoActiveTenant:
        # The person the agent acts for is gone: the run ends, nobody is acted for.
        await fail_run(tenant_id, run_id, INITIATOR_INACTIVE)
        return await _recorded(tenant_id, run_id)
    try:
        outcome = await screen(agent)
    except AgentRunNotRunning:
        return await _recorded(tenant_id, run_id)
    return ScreeningOutcome(
        outcome.status,
        str(run_id),
        None,
        str(outcome.screening_result_id) if outcome.screening_result_id else None,
    )


@activity.defn(name="screening.screen")
async def screen_activity(input: RunInput) -> ScreeningOutcome:
    try:
        async with _heartbeating():
            return await _screen(UUID(input.tenant_id), UUID(input.run_id))
    except (NotFound, *TERMINAL) as exc:
        raise _as_application_error(exc, retryable=False) from None
    except Exception as exc:  # anything else, database errors included: class name only
        raise _as_application_error(exc, retryable=True) from None


@activity.defn(name="screening.fail_run")
async def fail_run_activity(input: FailInput) -> ScreeningOutcome:
    """End the run if it is still running, then report its final state."""
    tenant_id, run_id = UUID(input.tenant_id), UUID(input.run_id)
    code = input.code if input.code in FAIL_CODES else INTERNAL_ERROR
    try:
        await fail_run(tenant_id, run_id, code)
        return await _recorded(tenant_id, run_id)
    except NotFound as exc:
        raise _as_application_error(exc, retryable=False) from None
    except Exception as exc:
        raise _as_application_error(exc, retryable=True) from None


ACTIVITIES = (create_run_activity, screen_activity, fail_run_activity)

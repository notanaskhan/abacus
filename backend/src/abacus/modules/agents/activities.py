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
from datetime import UTC, datetime, timedelta
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.ai_gateway import NotAdmitted
from abacus.kernel import slots
from abacus.kernel.config import settings
from abacus.kernel.errors import NotFound
from abacus.modules.agents.engagement_agent import handle as engagement_agent_handle
from abacus.modules.agents.knowledge import embed_next_batch, fail_document
from abacus.modules.agents.service import (
    TERMINAL,
    AgentRunNotRunning,
    create_screening_run,
    fail_run,
    load_agent_context,
    mark_queued,
    run_outcome,
    running_engagement,
    screen,
)
from abacus.modules.agents.workflow_types import (
    FAIL_CODES,
    INTERNAL_ERROR,
    NOT_ADMITTED,
    BatchOutcome,
    FailInput,
    FailKnowledgeInput,
    KnowledgeInput,
    RunInput,
    ScreeningInput,
    ScreeningOutcome,
    SlotGrant,
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
    work_class = slots.current_class()
    if work_class is not None:
        await slots.keep(agent.tenant, agent.engagement_id, work_class)
    try:
        outcome = await screen(agent)
        # Admitted and done: no longer waiting for the provider. Only here, so a repeated refusal
        # with the same reason writes nothing (no queued/resumed flapping in the audit trail).
        await mark_queued(tenant_id, run_id, None, None)
    except NotAdmitted as refused:
        # SPEC-003 AC-11/13: the run waits for the provider, visibly; the workflow asks again.
        estimate = datetime.now(UTC) + timedelta(seconds=refused.retry_after)
        await mark_queued(tenant_id, run_id, refused.reason, estimate)
        max_wait = settings().work_classes[work_class].max_wait_seconds if work_class else 600
        raise ApplicationError(
            NOT_ADMITTED,
            refused.reason,
            refused.retry_after,
            max_wait,
            type=NOT_ADMITTED,
            non_retryable=True,
        ) from None
    except AgentRunNotRunning:
        return await _recorded(tenant_id, run_id)
    return ScreeningOutcome(
        outcome.status,
        str(run_id),
        None,
        str(outcome.screening_result_id) if outcome.screening_result_id else None,
    )


@activity.defn(name="screening.acquire_slot")
async def acquire_slot_activity(input: RunInput) -> SlotGrant:
    """Ask for the run's work slot (SPEC-003): granted, or the run is marked queued with its
    reason and estimate. A run already ended, or on the legacy queue, needs none."""
    tenant_id, run_id = UUID(input.tenant_id), UUID(input.run_id)
    work_class = slots.current_class()
    try:
        engagement_id = await running_engagement(tenant_id, run_id)
        if engagement_id is None or work_class is None:
            return SlotGrant(True, 0)
        decision = await slots.acquire(
            slots.system_tenant(tenant_id), slots.current_holder(), engagement_id, work_class
        )
        await mark_queued(
            tenant_id,
            run_id,
            None if decision.granted else decision.reason,
            None if decision.granted else decision.estimated_start_at,
        )
    except NotFound as exc:
        raise _as_application_error(exc, retryable=False) from None
    except Exception as exc:
        raise _as_application_error(exc, retryable=True) from None
    return SlotGrant(decision.granted, settings().work_classes[work_class].max_wait_seconds)


@activity.defn(name="screening.release_slot")
async def release_slot_activity(input: RunInput) -> None:
    """Free the run's slot (idempotent; also when the run has ended)."""
    if slots.current_class() is None:
        return
    try:
        await slots.release(UUID(input.tenant_id), slots.current_holder())
    except Exception as exc:
        raise _as_application_error(exc, retryable=True) from None


@activity.defn(name="screening.screen")
async def screen_activity(input: RunInput) -> ScreeningOutcome:
    try:
        async with _heartbeating():
            return await _screen(UUID(input.tenant_id), UUID(input.run_id))
    except ApplicationError as exc:
        if exc.type == NOT_ADMITTED:
            raise  # a reason and two numbers: safe to cross as they are
        raise _as_application_error(exc, retryable=True) from None
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


# --- Knowledge embedding (SPEC-009; TASK-024 design §7) ----------------------------------------


@activity.defn(name="knowledge.embed_batch")
async def embed_batch_activity(input: KnowledgeInput) -> BatchOutcome:
    return await embed_next_batch(UUID(input.tenant_id), UUID(input.document_id))


@activity.defn(name="knowledge.fail")
async def fail_knowledge_activity(input: FailKnowledgeInput) -> None:
    await fail_document(UUID(input.tenant_id), UUID(input.document_id), input.code)


ACTIVITIES = (
    create_run_activity,
    acquire_slot_activity,
    release_slot_activity,
    screen_activity,
    fail_run_activity,
    embed_batch_activity,
    fail_knowledge_activity,
    engagement_agent_handle,  # SPEC-027 (TASK-050)
)

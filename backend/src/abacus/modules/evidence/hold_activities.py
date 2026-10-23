"""The legal-hold workflows' activities (Q-02-T29). Identifiers in, a count or a status out.

Each re-reads the hold from the database under the firm's system context (the input is never
proof), is repeat-safe, and crosses errors as their class name only. A hold that isn't in the
tenant is `NotFound` (not retried); anything else (storage or database down) is retried.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.kernel.errors import NotFound
from abacus.modules.evidence import holds
from abacus.modules.evidence.workflow_types import HOLD_NOT_FOUND, LegalHoldInput


async def _run[T](given: LegalHoldInput, step: Callable[[UUID, UUID], Awaitable[T]]) -> T:
    try:
        return await step(UUID(given.tenant_id), UUID(given.hold_id))
    except NotFound:
        raise ApplicationError(HOLD_NOT_FOUND, type=HOLD_NOT_FOUND, non_retryable=True) from None
    except Exception as exc:
        name = type(exc).__name__
        raise ApplicationError(name, type=name) from None


@activity.defn(name="legal_hold.apply_batch")
async def apply_batch_activity(given: LegalHoldInput) -> int:
    return await _run(given, holds.apply_batch)


@activity.defn(name="legal_hold.activate")
async def activate_activity(given: LegalHoldInput) -> str:
    return await _run(given, holds.activate)


@activity.defn(name="legal_hold.release_batch")
async def release_batch_activity(given: LegalHoldInput) -> int:
    return await _run(given, holds.release_batch)


@activity.defn(name="legal_hold.finish_release")
async def finish_release_activity(given: LegalHoldInput) -> str:
    return await _run(given, holds.finish_release)


ACTIVITIES = (
    apply_batch_activity,
    activate_activity,
    release_batch_activity,
    finish_release_activity,
)

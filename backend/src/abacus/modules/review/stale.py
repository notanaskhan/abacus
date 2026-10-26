"""The `StaleSignOffDetector` (P-04-T19; ADR-160 clause 3; DEC-84).

An outbox consumer of the owners' change events. For the changed target it reads the owner's
current hash and the computed staleness query, and announces `sign_off.went_stale` for each
newest-per-level sign-off that no longer matches, so the signer is told (notification
`sign_off_stale`). Nothing about a sign-off row changes: staleness stays `content_hash <> the
target's hash`, and a re-sign is a new row.

Idempotent: each announcement's event id is derived from the sign-off and the hash it went stale
against, written in its own unit of work, so a replayed change event finds it already written
and skips it.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Mapping
from typing import Final
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.review.events import SignOffWentStale
from abacus.modules.review.service import stale_of
from abacus.modules.review.slots import UnregisteredKind, reviewable_facts

_log = get_logger(__name__)
_NAMESPACE: Final = uuid.UUID("5b0f3c2e-6a43-4d6e-9a51-7f2c1f0e9d14")

# The change events an owner announces, and which payload key names the changed target.
STALE_SOURCES: Final[dict[str, tuple[str, str]]] = {
    "trial_balance.version_created": ("trial_balance", "trial_balance_id"),
    "workpaper.content_changed": ("workpaper", "workpaper_id"),
}


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "review.stale_sign_offs")


def went_stale_id(sign_off_id: UUID, current_hash: str) -> UUID:
    return uuid.uuid5(_NAMESPACE, f"{sign_off_id}:{current_hash}")


async def detect_stale(event: OutboxEvent) -> int:
    """Announce the sign-offs this change left stale; returns how many were new."""
    source = STALE_SOURCES.get(event.event_type)
    raw = event.payload.get(source[1]) if source else None
    if source is None or raw is None:
        return 0
    target_type, target_id = source[0], UUID(str(raw))
    tenant = _system(event.tenant_id)
    try:
        facts = await reviewable_facts(tenant, target_type, target_id)
    except (NotFound, UnregisteredKind):
        return 0
    announced = 0
    for found in await stale_of(tenant, target_type, {target_id: facts.content_hash}):
        if found.sign_off_id is None:
            continue
        went = SignOffWentStale(
            event_id=went_stale_id(found.sign_off_id, found.current_hash),
            sign_off_id=found.sign_off_id,
            engagement_id=facts.engagement_id,
            target_type=target_type,
            target_id=target_id,
            level=found.level,
            signed_by=found.signed_by,
        )
        try:
            async with uow(tenant) as tx:
                tx.emit(went)
        except IntegrityError:
            continue  # already announced against this hash (a replay)
        announced += 1
    _log.info("sign_offs.went_stale", announced=announced, target_type=target_type)
    return announced


async def _consume(event: OutboxEvent) -> None:
    await detect_stale(event)


SUBSCRIPTIONS: Mapping[str, Callable[[OutboxEvent], Awaitable[None]]] = {
    event: _consume for event in sorted(STALE_SOURCES)
}

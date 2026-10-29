"""`tax.api.apply_transition` and `tax.api.record_sync_state` (T-02-T07; SPEC-502 AC-8).

A move is checked against `status.TRANSITIONS` before anything is written; it writes the new
status with the row version the caller saw, an insert-only status event with the actor, and an
audit event, in one unit of work. `record_sync_state` is T-01's only way to write the sync chip
(T-01 §4.1: T-01 adds no column to `tax_returns`).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from abacus.kernel._statuses import ReturnStatus, ReturnSyncChipStatus
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import Forbidden
from abacus.modules.tax import repository
from abacus.modules.tax.status import StaleReturn, actor_may, next_status


async def apply_transition(
    tenant: TenantContext,
    work_item_id: UUID,
    event: str,
    *,
    seen_version: int,
    reason: str | None = None,
    on_behalf_of: UUID | None = None,
) -> ReturnStatus:
    """Move a return on `event`. 404 for an unknown return; 409 `transition_refused` for a move
    the table does not hold; 409 `stale_version` when the row moved since `seen_version`; 403
    for the agent or support, and for the system on a person's decision (`final_approved`)."""
    if not actor_may(event, tenant.actor_kind):
        raise Forbidden(f"tax_return.{event}", "role")
    keys = {"tenant_id": tenant.tenant_id, "work_item_id": work_item_id}
    async with uow(tenant) as tx:
        found = await repository.status_of(tx.session, keys)
        if found is None:
            raise NotFound("tax_return")
        current = ReturnStatus(found[0])
        to = next_status(current, event)
        moved = await repository.move_status(
            tx.session, {**keys, "to_status": to.value, "seen": seen_version}
        )
        if not moved:
            raise StaleReturn(facts={"work_item_id": str(work_item_id)})
        await repository.insert_status_event(
            tx.session,
            {
                **keys,
                "from_status": current.value,
                "to_status": to.value,
                "event": event,
                "actor_kind": tenant.actor_kind,
                "actor_id": tenant.actor_id,
                "on_behalf_of": on_behalf_of,
                "reason": reason,
            },
        )
        tx.record(
            "tax_return.status_changed",
            target=Target("tax_return", work_item_id),
            after=Ref(version=seen_version + 1),
        )
    return to


async def record_sync_state(
    tenant: TenantContext, work_item_id: UUID, state: ReturnSyncChipStatus, at: datetime
) -> None:
    """T-01 only (the engine bridge): the chip state and when it was reached."""
    async with uow(tenant) as tx:
        await repository.set_sync_state(
            tx.session,
            {
                "tenant_id": tenant.tenant_id,
                "work_item_id": work_item_id,
                "sync_status": state.value,
                "at": at,
            },
        )
        tx.record("tax_return.sync_recorded", target=Target("tax_return", work_item_id))

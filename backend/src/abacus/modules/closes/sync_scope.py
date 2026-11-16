"""The closes' ledger sync scope (C-01-T17; C-01 §4.5 `entities_due`).

Registered into `connections.api.register_sync_scope`, so connections never imports closes. An
entity is in scope while it has an unlocked close for a month that has ended (by the firm's
business clock); the sync keeps the latest two such months fresh (the close month and the one
before it, which flux compares against). A Locked close is never re-synced: its snapshot is the
close's record.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.connections.api import SyncScope

MONTHS_KEPT: Final = 2

_OPEN = text(
    "SELECT client_entity_id, engagement_id, period FROM closes "
    "WHERE client_entity_id IS NOT NULL AND status <> 'locked' AND locked_at IS NULL "
    "AND period < :month ORDER BY client_entity_id, period DESC"
)


async def sync_scope(tenant: TenantContext) -> list[SyncScope]:
    """Every entity with an unlocked, ended close month (LIST_EXEMPT: a system read of the
    tenant's own closes for its sync; nothing is shown to a person)."""
    month = (await today(tenant)).strftime("%Y-%m")
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_OPEN, {"month": month})).all()
    periods: dict[UUID, list[str]] = defaultdict(list)
    engagements: dict[UUID, UUID] = {}
    for entity, engagement, period in rows:
        engagements.setdefault(entity, engagement)
        if len(periods[entity]) < MONTHS_KEPT:
            periods[entity].append(period)
    return [
        SyncScope(entity, engagements[entity], tuple(sorted(found)))
        for entity, found in periods.items()
    ]

"""Synthetic-only connection seeding (A-02-T27; the scenario loader's `connections` slice).

`seed_synthetic_connection` writes a client entity's connection at a given state for a synthetic
firm, without an OAuth round trip: the provider must be a tooling fake (`fake_*`, which reaches
no host) and the environment local, test or evaluation, or it refuses. The row is recorded as the
system's, on behalf of the client person who connected it, with `connection.created`.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import insert

from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.connections.models import Connection
from abacus.modules.connections.repository import set_connection
from abacus.modules.connections.service import FAKE_PREFIX


class SyntheticSeedRefused(RuntimeError):
    """Seeding is for fake providers in synthetic environments only."""


async def seed_synthetic_connection(
    tenant_id: UUID,
    *,
    client_entity_id: UUID,
    provider: str,
    category: str,
    display_label: str,
    status: str,
    reason: str | None,
    connected_by_user_id: UUID,
    connected_at: datetime,
    last_sync_at: datetime | None,
) -> UUID:
    if settings().environment not in SYNTHETIC_ENVIRONMENTS or not provider.startswith(
        FAKE_PREFIX
    ):
        raise SyntheticSeedRefused(provider)
    system = TenantContext(tenant_id, "system", "connections:scenario", connected_by_user_id)
    connection_id = uuid4()
    async with uow(system) as tx:
        await tx.session.execute(
            insert(Connection).values(
                id=connection_id,
                tenant_id=tenant_id,
                client_entity_id=client_entity_id,
                provider=provider,
                scopes=[],
                created_by=str(connected_by_user_id),
                category=category,
                display_label=display_label,
                connected_by_user_id=connected_by_user_id,
                connected_at=connected_at,
            )
        )
        await set_connection(
            tx.session,
            connection_id,
            status=status,
            status_reason_code=reason,
            last_sync_at=last_sync_at,
        )
        tx.record(
            "connection.created",
            target=Target("connection", connection_id),
            after=Ref(client_entity_id=client_entity_id),
        )
    return connection_id

"""Connection entity coverage (A-09-T11, T13; SPEC-658; ADR-045 as A-09 relaxes it): which
entities a connection covers. A OneWorld ledger connection covers every subsidiary a group
consolidation names; at most one live ledger covers an entity (the database's partial unique
index), so covering an entity another live ledger covers is `EntityAlreadyCovered` (409).
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow


class EntityAlreadyCovered(DomainConflict):
    code = "entity_already_covered"


async def covers(tenant: TenantContext, connection_id: UUID, client_entity_id: UUID) -> bool:
    """The live connection covers the entity (its own, or one a consolidation added)."""
    async with tenant_session(tenant) as session:
        found = await session.execute(
            text(
                "SELECT 1 FROM connection_entity_coverage WHERE connection_id = :c "
                "AND client_entity_id = :e AND live"
            ),
            {"c": connection_id, "e": client_entity_id},
        )
        return found.first() is not None


async def cover_entities(
    tenant: TenantContext, connection_id: UUID, client_entity_ids: Sequence[UUID]
) -> int:
    """Add the entities a covering ledger connection reads; the ones it covers already stay.
    The connection must be live; the count added."""
    async with tenant_session(tenant) as session:
        head = (
            await session.execute(
                text("SELECT category, status FROM connections WHERE id = :c"),
                {"c": connection_id},
            )
        ).first()
    if head is None or head.status == "revoked":
        raise NotFound("connection")
    added = 0
    try:
        async with uow(tenant) as tx:
            for entity in client_entity_ids:
                done = await tx.session.execute(
                    text(
                        "INSERT INTO connection_entity_coverage (tenant_id, connection_id, "
                        "client_entity_id, category, live) VALUES (:t, :c, :e, :k, true) "
                        "ON CONFLICT (tenant_id, connection_id, client_entity_id) DO NOTHING "
                        "RETURNING id"
                    ),
                    {"t": tenant.tenant_id, "c": connection_id, "e": entity, "k": head.category},
                )
                added += 1 if done.first() is not None else 0
            tx.record(
                "connection.coverage_extended",
                target=Target("connection", connection_id),
                after=Ref(entities=added),
            )
    except IntegrityError:
        raise EntityAlreadyCovered from None
    return added

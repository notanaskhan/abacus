"""The `client` search projection (P-02-T07; C15 v1; ADR-241; DEC-4613).

A client is found by its name, its practice-management reference and its entities' names (a 401(k)
plan's sponsor finds the plan's client). The context line is its descriptor and primary office
("C corp · Denver"). Scoped to the client (walls bite on `client_id`); target CLI-02.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.platform.api import (
    RelatedParty,
    SearchIndexDocument,
    SearchProjection,
    register_search_projection,
)

_CLIENT = text(
    "SELECT c.id, c.name, c.descriptor, c.practice_mgmt_ref, c.status, c.created_at, "
    "o.name AS office FROM clients c LEFT JOIN offices o ON o.id = c.primary_office_id "
    "WHERE c.id = :id"
)
_ENTITIES = text(
    "SELECT name FROM client_entities WHERE client_id = :id AND name <> :client "
    "ORDER BY name LIMIT 19"
)
_IDS = text(
    "SELECT id FROM clients WHERE (CAST(:after AS uuid) IS NULL OR id > CAST(:after AS uuid)) "
    "ORDER BY id LIMIT :limit"
)


async def build_client(tenant: TenantContext, client_id: UUID) -> SearchIndexDocument | None:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_CLIENT, {"id": client_id})).mappings().first()
        if row is None:
            return None
        entities = (
            (await session.execute(_ENTITIES, {"id": client_id, "client": row["name"]}))
            .scalars()
            .all()
        )
    context = " · ".join(str(p) for p in (row["descriptor"], row["office"]) if p)
    created: datetime = row["created_at"]
    return SearchIndexDocument(
        object_id=client_id,
        title=str(row["name"]),
        context=context or None,
        client_id=client_id,
        identifiers=tuple(str(r) for r in (row["practice_mgmt_ref"],) if r),
        related=tuple(RelatedParty(name=str(n), label="entity") for n in entities),
        source_updated_at=created,
        target_params={"clientId": str(client_id)},
    )


async def client_ids(tenant: TenantContext, after: UUID | None, limit: int) -> list[UUID]:
    async with tenant_session(tenant) as session:
        rows = await session.execute(_IDS, {"after": after, "limit": limit})
        return [UUID(str(r)) for r in rows.scalars()]


def _client_of(payload: Mapping[str, object]) -> list[UUID]:
    raw = payload.get("client_id")
    return [] if raw is None else [UUID(str(raw))]


CLIENT_PROJECTION = SearchProjection(
    object_type="client",
    group="clients",
    read_action="client.read",
    scope_kind="client",
    build=build_client,
    target="CLI-02",
    triggers={"client.updated": _client_of},
    list_ids=client_ids,
)
register_search_projection(CLIENT_PROJECTION)

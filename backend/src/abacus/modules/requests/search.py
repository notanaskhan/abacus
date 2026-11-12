"""The `binder` search projection (P-02-T07; C15 v1; ADR-241; DEC-4613).

A binder (a published request list) is found by its name, with its open-request count as the
context ("13 requests open"); counts are code, never text a client wrote. It opens BND-02, scoped
to its engagement.
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.api import engagement_hold_facts
from abacus.modules.platform.api import (
    SearchIndexDocument,
    SearchProjection,
    register_search_projection,
)

_OPEN = ("requested", "uploaded", "returned")  # not yet received (C2 `request`)
_LIST = text(
    "SELECT id, engagement_id, name, status, created_at FROM request_lists "
    "WHERE id = :id AND unpublished_at IS NULL AND closed_at IS NULL"
)
_OPEN_COUNT = text(
    "SELECT count(*) FROM request_items WHERE request_list_id = :id "
    "AND status = ANY(CAST(:open AS text[]))"
)
_IDS = text(
    "SELECT id FROM request_lists "
    "WHERE (CAST(:after AS uuid) IS NULL OR id > CAST(:after AS uuid)) ORDER BY id LIMIT :limit"
)
_LIST_OF_ITEM = text("SELECT request_list_id FROM request_items WHERE id = :id")


async def build_binder(tenant: TenantContext, list_id: UUID) -> SearchIndexDocument | None:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_LIST, {"id": list_id})).mappings().first()
        if row is None:
            return None
        open_count = int(
            (await session.execute(_OPEN_COUNT, {"id": list_id, "open": list(_OPEN)})).scalar_one()
        )
    engagement_id = UUID(str(row["engagement_id"]))
    facts = await engagement_hold_facts(tenant, engagement_id)
    if facts is None:
        return None
    client_id = facts.client_id
    noun = "request" if open_count == 1 else "requests"
    return SearchIndexDocument(
        object_id=list_id,
        title=str(row["name"]),
        context=f"{open_count} {noun} open",
        engagement_id=engagement_id,
        client_id=client_id,
        status_code=str(row["status"]),
        source_updated_at=row["created_at"],
        target_params={"binderId": str(list_id)},
    )


async def binder_ids(tenant: TenantContext, after: UUID | None, limit: int) -> list[UUID]:
    async with tenant_session(tenant) as session:
        rows = await session.execute(_IDS, {"after": after, "limit": limit})
        return [UUID(str(r)) for r in rows.scalars()]


def _list_of(payload: Mapping[str, object]) -> list[UUID]:
    raw = payload.get("request_list_id")
    return [] if raw is None else [UUID(str(raw))]


BINDER_PROJECTION = SearchProjection(
    object_type="binder",
    group="binders",
    read_action="binder.read",
    scope_kind="engagement",
    build=build_binder,
    target="BND-02",
    triggers={"request_item.status_changed": _list_of, "request_item.created": _list_of},
    list_ids=binder_ids,
)
register_search_projection(BINDER_PROJECTION)

"""The `assurance` search projection (P-02-T07; C15 v1; ADR-241; DEC-4613).

An audit or assurance work item is found by its name and its client's name ("FY2026 Financial
Statement Audit" · Granite Peak), with its phase as the status ("Fieldwork"). It opens AUD-02,
scoped to the work item's engagement. The projection lives here, with `work_items` and
`assurance_work_items`, the tables it reads (the epic placed it in `assurance`, which may not
query them).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast
from uuid import UUID

from sqlalchemy import Column, literal, select, text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.organisations.api import client_name_column
from abacus.modules.platform.api import (
    SearchIndexDocument,
    SearchProjection,
    register_search_projection,
)

_ITEM = text(
    "SELECT w.id, w.engagement_id, w.client_id, w.name, w.created_at, a.phase, a.assurance_type "
    "FROM work_items w JOIN assurance_work_items a ON a.work_item_id = w.id "
    "WHERE w.id = :id AND w.archived_at IS NULL"
)
_IDS = text(
    "SELECT work_item_id FROM assurance_work_items "
    "WHERE (CAST(:after AS uuid) IS NULL OR work_item_id > CAST(:after AS uuid)) "
    "ORDER BY work_item_id LIMIT :limit"
)


async def build_assurance(tenant: TenantContext, work_item_id: UUID) -> SearchIndexDocument | None:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_ITEM, {"id": work_item_id})).mappings().first()
        if row is None:
            return None
        client_id = UUID(str(row["client_id"]))
        name = await session.scalar(
            select(client_name_column(cast(Column[UUID], literal(client_id))))
        )
    return SearchIndexDocument(
        object_id=work_item_id,
        title=str(row["name"]),
        context=None if name is None else str(name),
        engagement_id=UUID(str(row["engagement_id"])),
        work_item_id=work_item_id,
        client_id=client_id,
        identifiers=(str(row["assurance_type"]),),
        status_code=str(row["phase"]),
        source_updated_at=row["created_at"],
        target_params={"auditId": str(work_item_id)},
    )


async def assurance_ids(tenant: TenantContext, after: UUID | None, limit: int) -> list[UUID]:
    async with tenant_session(tenant) as session:
        rows = await session.execute(_IDS, {"after": after, "limit": limit})
        return [UUID(str(r)) for r in rows.scalars()]


def _work_item(payload: Mapping[str, object]) -> list[UUID]:
    """`assurance.phase_changed` names the work item whose phase (its status here) moved."""
    raw = payload.get("work_item_id")
    return [] if raw is None else [UUID(str(raw))]


ASSURANCE_PROJECTION = SearchProjection(
    object_type="assurance",
    group="audits",
    read_action="engagement.read",
    scope_kind="work_item",
    build=build_assurance,
    target="AUD-02",
    triggers={"assurance.phase_changed": _work_item},
    list_ids=assurance_ids,
)
register_search_projection(ASSURANCE_PROJECTION)

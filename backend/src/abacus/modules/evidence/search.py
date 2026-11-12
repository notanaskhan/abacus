"""The `document` search projection (P-02-T07; C15 v1; ADR-241; DEC-4613).

A file in Files (N-01) is found by its name, scrubbed of any TIN or amount (a file named after a
taxpayer's SSN is still found by the rest of its name). It opens FIL-01 on its folder, scoped to
its client. A withdrawn item (P-31) or a destroyed one answers None, so the indexer deletes its
row. No document text is ever indexed.
"""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.platform.api import (
    SearchIndexDocument,
    SearchProjection,
    register_search_projection,
)

_ITEM = text(
    "SELECT i.id, i.title, i.client_id, i.engagement_id, i.work_item_id, i.folder_kind, "
    "i.created_at FROM evidence_items i WHERE i.id = :id AND i.client_id IS NOT NULL "
    "AND EXISTS (SELECT 1 FROM evidence_versions v WHERE v.evidence_item_id = i.id "
    "AND NOT EXISTS (SELECT 1 FROM evidence_withdrawals w WHERE w.evidence_version_id = v.id))"
)
_IDS = text(
    "SELECT id FROM evidence_items WHERE client_id IS NOT NULL "
    "AND (CAST(:after AS uuid) IS NULL OR id > CAST(:after AS uuid)) ORDER BY id LIMIT :limit"
)


async def build_document(tenant: TenantContext, item_id: UUID) -> SearchIndexDocument | None:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_ITEM, {"id": item_id})).mappings().first()
    if row is None:
        return None
    params = {"itemId": str(item_id)}
    if row["work_item_id"] is not None and row["folder_kind"] is not None:
        params["folder"] = f"folder:{row['work_item_id']}:{row['folder_kind']}"
    else:
        params["folder"] = f"permanent:{row['client_id']}"
    return SearchIndexDocument(
        object_id=item_id,
        title=str(row["title"]),
        engagement_id=None if row["engagement_id"] is None else UUID(str(row["engagement_id"])),
        work_item_id=None if row["work_item_id"] is None else UUID(str(row["work_item_id"])),
        client_id=UUID(str(row["client_id"])),
        source_updated_at=row["created_at"],
        target_params=params,
    )


async def document_ids(tenant: TenantContext, after: UUID | None, limit: int) -> list[UUID]:
    async with tenant_session(tenant) as session:
        rows = await session.execute(_IDS, {"after": after, "limit": limit})
        return [UUID(str(r)) for r in rows.scalars()]


def _item_of(payload: Mapping[str, object]) -> list[UUID]:
    raw = payload.get("evidence_item_id")
    return [] if raw is None else [UUID(str(raw))]


DOCUMENT_PROJECTION = SearchProjection(
    object_type="document",
    group="files",
    read_action="evidence.read",
    scope_kind="client",
    build=build_document,
    target="FIL-01",
    triggers={"evidence_version.created": _item_of, "evidence_version.withdrawn": _item_of},
    list_ids=document_ids,
)
register_search_projection(DOCUMENT_PROJECTION)

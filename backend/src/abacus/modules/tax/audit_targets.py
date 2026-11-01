"""Which engagement owns the rows an audit event can point at (SPEC-304; DEC-121), for the tax
module's kinds. A `tax_return` target is its work item (T-02-T07 records status moves on it), as
is a `work_item` target (the pinned due dates); the engagement module answers which engagement
holds the work item, so the explorer shows the event to whoever may see that engagement. A tax
profile's authorization, file and transcript belong to a client entity (0550). Unknown ids are
left out (fail closed)."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.api import work_item_engagement

AUDIT_KINDS = frozenset({"tax_return", "work_item"})
_ENTITIES = {
    "tax_authorization": text(
        "SELECT id, client_entity_id FROM tax_authorizations WHERE id = ANY(:ids)"
    ),
    "tax_profile_file": text(
        "SELECT id, client_entity_id FROM tax_profile_files WHERE id = ANY(:ids)"
    ),
    "transcript": text("SELECT id, client_entity_id FROM transcripts WHERE id = ANY(:ids)"),
}
ENTITY_KINDS = frozenset(_ENTITIES)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `tax_return` and `work_item` rows: their work item id -> its engagement."""
    owned: dict[UUID, UUID] = {}
    for work_item_id in ids:
        engagement = await work_item_engagement(tenant, work_item_id)
        if engagement is not None:
            owned[work_item_id] = engagement
    return owned


async def audit_entities(
    tenant: TenantContext, kind: str, ids: Sequence[UUID]
) -> dict[UUID, UUID]:
    """For a tax profile's rows named by an audit event: their id -> the owning client entity."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(_ENTITIES[kind], {"ids": list(ids)})
        return dict(rows.tuples())

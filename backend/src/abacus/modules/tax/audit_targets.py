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

# T-04-T15: a worksheet is its own row, owned by its engagement. T-04-T36: a K-1 activity and
# its treatments too (audited as `pass_through_*`: audit names hold no digits).
_ROWS = {
    "return_worksheet": text(
        "SELECT id, engagement_id FROM return_worksheets WHERE id = ANY(:ids)"
    ),
    "pass_through_activity": text(
        "SELECT id, engagement_id FROM k1_activities WHERE id = ANY(:ids)"
    ),
    "pass_through_treatment": text(
        "SELECT id, engagement_id FROM k1_treatments WHERE id = ANY(:ids)"
    ),
    # T-05-T22 / T-04-T39 (S38): an entity return's partner (its TIN seal and reveals) and a
    # return's residency determination, each owned by its engagement.
    "partner": text("SELECT id, engagement_id FROM partners WHERE id = ANY(:ids)"),
    "residency_determination": text(
        "SELECT id, engagement_id FROM residency_determinations WHERE id = ANY(:ids)"
    ),
    # T-05-T41 (DEC-4701): an allocation structure version, owned by its engagement.
    # T-05-T42 (DEC-4705): a workbook section (its sign-offs and acknowledged tie-outs).
    "tax_workbook_section": text(
        "SELECT id, engagement_id FROM tax_workbook_sections WHERE id = ANY(:ids)"
    ),
    "allocation_structure": text(
        "SELECT id, engagement_id FROM allocation_structures WHERE id = ANY(:ids)"
    ),
}
# T-05-T35 (DEC-4620): the entity workbook's events (`workbook.step_written`,
# `workbook.cell_edited`) target the return's work item, like `tax_return`.
AUDIT_KINDS = frozenset({"tax_return", "work_item", "tax_workbook"}) | frozenset(_ROWS)
_ENTITIES = {
    "tax_authorization": text(
        "SELECT id, client_entity_id FROM tax_authorizations WHERE id = ANY(:ids)"
    ),
    "tax_profile_file": text(
        "SELECT id, client_entity_id FROM tax_profile_files WHERE id = ANY(:ids)"
    ),
    "transcript": text("SELECT id, client_entity_id FROM transcripts WHERE id = ANY(:ids)"),
    "estimate_schedule": text(
        "SELECT id, client_entity_id FROM estimate_schedules WHERE id = ANY(:ids)"
    ),
}
ENTITY_KINDS = frozenset(_ENTITIES)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `tax_return` and `work_item` rows: their work item id -> its engagement."""
    if kind in _ROWS:
        async with tenant_session(tenant) as session:
            found = await session.execute(_ROWS[kind], {"ids": list(ids)})
            return {row[0]: row[1] for row in found}
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
        return dict(rows.tuples().all())

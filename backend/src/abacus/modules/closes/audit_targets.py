"""Who owns the rows a close's audit events point at (SPEC-304; DEC-121), so the explorer shows
an event only to whoever may see its owner. A `close` is its work item (owned by the engagement);
a close plan and its rows belong to the client entity the plan is for. Unknown ids are left out
(fail closed). The firm's close templates are firm-level (`audit_trail.targets.FIRM_LEVEL`)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import TextClause, text

from abacus.kernel.db import TenantContext, tenant_session

_ENGAGEMENT: Final[dict[str, TextClause]] = {
    "close": text("SELECT work_item_id, engagement_id FROM closes WHERE work_item_id = ANY(:ids)"),
    # C-01-T20: a reconciliation the close run computed, owned by its close's engagement.
    "reconciliation": text(
        "SELECT r.id, c.engagement_id FROM reconciliations r "
        "JOIN closes c ON c.work_item_id = r.close_id WHERE r.id = ANY(:ids)"
    ),
}
_ENTITY: Final[dict[str, TextClause]] = {
    "close_plan": text("SELECT id, client_entity_id FROM close_plans WHERE id = ANY(:ids)"),
    "close_plan_row": text(
        "SELECT r.id, p.client_entity_id FROM close_plan_rows r "
        "JOIN close_plan_versions v ON v.id = r.version_id "
        "JOIN close_plans p ON p.id = v.plan_id WHERE r.id = ANY(:ids)"
    ),
    # C-01-T30: a close plan version (the planner's draft) belongs to its plan's client entity.
    "close_plan_version": text(
        "SELECT v.id, p.client_entity_id FROM close_plan_versions v "
        "JOIN close_plans p ON p.id = v.plan_id WHERE v.id = ANY(:ids)"
    ),
    # C-01-T21: an arrangement belongs to the client entity it schedules.
    "arrangement": text("SELECT id, client_entity_id FROM arrangements WHERE id = ANY(:ids)"),
}
AUDIT_KINDS: Final = frozenset(_ENGAGEMENT)
ENTITY_KINDS: Final = frozenset(_ENTITY)


async def _owners(
    statements: dict[str, TextClause], tenant: TenantContext, kind: str, ids: Sequence[UUID]
) -> dict[UUID, UUID]:
    async with tenant_session(tenant) as session:
        rows = await session.execute(statements[kind], {"ids": list(ids)})
        return {row[0]: row[1] for row in rows}


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For a `close`: its work item id -> its engagement."""
    return await _owners(_ENGAGEMENT, tenant, kind, ids)


async def audit_entities(
    tenant: TenantContext, kind: str, ids: Sequence[UUID]
) -> dict[UUID, UUID]:
    """For a close plan and its rows: their id -> the plan's client entity."""
    return await _owners(_ENTITY, tenant, kind, ids)

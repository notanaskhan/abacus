"""Who owns the rows S48's group-audit and SSARS audit events point at (SPEC-304; DEC-121), so the
explorer shows an event only to whoever may see the engagement. Every row carries its engagement;
unknown ids are left out (fail closed). S48 end pass (A-08-T22, A-09-T27, A-09-T28, A-09-T31)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import TextClause, text

from abacus.kernel.db import TenantContext, tenant_session

_OWNERS: Final[dict[str, TextClause]] = {
    "component_auditor": text(
        "SELECT id, engagement_id FROM component_auditors WHERE id = ANY(:ids)"
    ),
    "component_deliverable": text(
        "SELECT id, engagement_id FROM component_deliverables WHERE id = ANY(:ids)"
    ),
    "component_instructions": text(
        "SELECT id, engagement_id FROM component_instructions WHERE id = ANY(:ids)"
    ),
    "component_send": text(
        "SELECT id, engagement_id FROM component_instruction_sends WHERE id = ANY(:ids)"
    ),
    "ssars_inquiry_program": text(
        "SELECT id, engagement_id FROM ssars_inquiry_programs WHERE id = ANY(:ids)"
    ),
}
GROUP_AUDIT_TARGET_KINDS: Final = frozenset(_OWNERS)


async def group_audit_owners(
    tenant: TenantContext, kind: str, ids: Sequence[UUID]
) -> dict[UUID, UUID]:
    """A row's id -> its engagement."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(_OWNERS[kind], {"ids": list(ids)})
        return {row[0]: row[1] for row in rows}

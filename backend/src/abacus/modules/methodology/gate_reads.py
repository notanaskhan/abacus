"""What HOME-02's methodology approval gate reads (I-01-T23; K-01 AC3.7; DEC-2613).

A version in Needs review waits on a quality partner's approval (`methodology.approve`). Review
registers the gate (it may depend on methodology, never the reverse); these reads are the
owner's: the versions waiting, and the words a row shows. Identifiers, the template's name and
the version's label only.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session


@dataclass(frozen=True)
class VersionInReview:
    version_id: UUID
    template_name: str
    label: str


async def versions_in_review(tenant: TenantContext) -> list[UUID]:
    """The firm's versions in Needs review, oldest first."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(
                "SELECT s.version_id FROM methodology_version_states s "
                "JOIN methodology_versions v ON v.id = s.version_id "
                "WHERE s.status = 'needs_review' ORDER BY v.created_at, s.version_id"
            )
        )
        return [r.version_id for r in rows]


async def versions_named(
    tenant: TenantContext, ids: Sequence[UUID]
) -> dict[UUID, VersionInReview]:
    """Each version's template name and label, for the gate's row."""
    if not ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(
                "SELECT v.id, t.name, v.label FROM methodology_versions v "
                "JOIN methodology_templates t ON t.id = v.template_id WHERE v.id = ANY(:ids)"
            ),
            {"ids": list(ids)},
        )
        return {r.id: VersionInReview(r.id, r.name, r.label) for r in rows}

"""Documents as run-trace samples (P-09-T08; WB-09 a2; `docs/contracts/agent-runs.md`).

The evidence versions and items a run step read, for the reader who opens the step: only those
on engagements the reader may see documents on (`visible(evidence.read_metadata)`, walls apply),
never a withdrawn version (ADR-162 §4), each named by its document's title and opening the source
viewer (`?ov=viewer:<version>`). An item opens at its newest version that is not withdrawn.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select

from abacus.kernel.db import tenant_session
from abacus.modules.engagements.api import TraceSampleRow
from abacus.modules.evidence.models import EvidenceItem, EvidenceVersion, EvidenceWithdrawal
from abacus.modules.identity.api import AuthContext, visible

_NOT_WITHDRAWN = ~(
    select(EvidenceWithdrawal.evidence_version_id)
    .where(EvidenceWithdrawal.evidence_version_id == EvidenceVersion.id)
    .exists()
)


def _route(engagement_id: UUID, version_id: UUID) -> str:
    return f"/engagements/{engagement_id}?ov=viewer:{version_id}"


async def evidence_version_trace_samples(
    ctx: AuthContext, ids: Sequence[UUID]
) -> list[TraceSampleRow]:
    if not ids:
        return []
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            select(EvidenceVersion.id, EvidenceVersion.engagement_id, EvidenceItem.title)
            .join(EvidenceItem, EvidenceItem.id == EvidenceVersion.evidence_item_id)
            .where(
                EvidenceVersion.id.in_(list(ids)),
                visible(ctx, "evidence.read_metadata", EvidenceVersion.engagement_id),
                _NOT_WITHDRAWN,
            )
        )
        return [TraceSampleRow(i, title, _route(e, i)) for i, e, title in rows]


async def evidence_item_trace_samples(
    ctx: AuthContext, ids: Sequence[UUID]
) -> list[TraceSampleRow]:
    if not ids:
        return []
    newest = (
        select(
            EvidenceVersion.evidence_item_id.label("item_id"),
            func.max(EvidenceVersion.version_no).label("version_no"),
        )
        .where(EvidenceVersion.evidence_item_id.in_(list(ids)), _NOT_WITHDRAWN)
        .group_by(EvidenceVersion.evidence_item_id)
        .subquery()
    )
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            select(
                EvidenceItem.id, EvidenceItem.engagement_id, EvidenceItem.title, EvidenceVersion.id
            )
            .join(newest, newest.c.item_id == EvidenceItem.id)
            .join(
                EvidenceVersion,
                (EvidenceVersion.evidence_item_id == EvidenceItem.id)
                & (EvidenceVersion.version_no == newest.c.version_no),
            )
            .where(visible(ctx, "evidence.read_metadata", EvidenceItem.engagement_id))
        )
        return [TraceSampleRow(i, title, _route(e, v)) for i, e, title, v in rows]

"""What other modules may ask evidence about the versions and inbox files their proposals are
about (P-04-T16; C13): agents read no evidence table (DEC-299), so the human-gate sources ask here
whether a person has already decided."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.evidence.models import InboxFile, ReviewAssignment, ReviewDecision


async def decided_among(tenant: TenantContext, version_ids: Sequence[UUID]) -> frozenset[UUID]:
    """The versions whose effective review decision stands (their newest row is not an undo)."""
    ids = list(dict.fromkeys(version_ids))
    if not ids:
        return frozenset()
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(ReviewDecision.evidence_version_id, ReviewDecision.decision)
            .where(ReviewDecision.evidence_version_id.in_(ids))
            .ext(distinct_on(ReviewDecision.evidence_version_id))
            .order_by(ReviewDecision.evidence_version_id, ReviewDecision.decision_seq.desc())
        )
        return frozenset(v for v, decision in rows.all() if decision != "undone")


async def effective_decisions(
    tenant: TenantContext, version_ids: Sequence[UUID]
) -> dict[UUID, str]:
    """P-04-T25: each version's standing review decision (`accept`, `reject` or `send_back`);
    versions with none, or whose newest row is an undo, are left out."""
    ids = list(dict.fromkeys(version_ids))
    if not ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(ReviewDecision.evidence_version_id, ReviewDecision.decision)
            .where(ReviewDecision.evidence_version_id.in_(ids))
            .ext(distinct_on(ReviewDecision.evidence_version_id))
            .order_by(ReviewDecision.evidence_version_id, ReviewDecision.decision_seq.desc())
        )
        return {v: decision for v, decision in rows.all() if decision != "undone"}


async def waiting_among(tenant: TenantContext, inbox_file_ids: Sequence[UUID]) -> frozenset[UUID]:
    """The inbox files still waiting for a person to assign or discard them."""
    ids = list(dict.fromkeys(inbox_file_ids))
    if not ids:
        return frozenset()
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(InboxFile.id).where(InboxFile.id.in_(ids), InboxFile.status == "waiting")
        )
        return frozenset(rows.scalars().all())


async def review_assignees(
    tenant: TenantContext, version_ids: Sequence[UUID]
) -> dict[UUID, UUID | None]:
    """I-01-T08: who took each version for review (SPEC-004 Q3); a version nobody took is
    absent, one released is None."""
    ids = list(dict.fromkeys(version_ids))
    if not ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(ReviewAssignment.evidence_version_id, ReviewAssignment.assignee_user_id).where(
                ReviewAssignment.evidence_version_id.in_(ids)
            )
        )
        return dict(rows.tuples().all())


__all__ = ["decided_among", "effective_decisions", "review_assignees", "waiting_among"]

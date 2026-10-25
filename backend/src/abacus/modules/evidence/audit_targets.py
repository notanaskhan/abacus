"""Which engagement owns the rows an audit event can point at (SPEC-304; DEC-121). The audit
explorer drops events about engagements the reader may not see, so each module says, for the
kinds of target it owns, the engagement of each id. Follow-up: an `engagement_id` on audit events
makes this exact and cheap."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.evidence.models import (
    Citation,
    EvidenceItem,
    EvidenceVersion,
    InboxFile,
    ReviewDecision,
    StatementDataset,
)

_OWNERS: dict[str, tuple[QueryableAttribute[UUID], QueryableAttribute[UUID | None]]] = {
    "evidence_version": (EvidenceVersion.id, EvidenceVersion.engagement_id),
    "evidence_item": (EvidenceItem.id, EvidenceItem.engagement_id),
    "inbox_file": (InboxFile.id, InboxFile.engagement_id),
    "review_decision": (ReviewDecision.id, ReviewDecision.engagement_id),
    "statement_dataset": (StatementDataset.id, StatementDataset.engagement_id),  # SPEC-312
    "citation": (Citation.id, Citation.engagement_id),  # P-03-T06: a recorded citation
}
AUDIT_KINDS = frozenset(_OWNERS)
# SPEC-036 AC-5 (TASK-1210): a shadow run's citation is never shown, so neither are its events.
_SHOWN: dict[str, ColumnElement[bool]] = {"citation": Citation.shadow.is_(False)}


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `kind` rows named by an audit event (the caller has authorised the read of the trail):
    their id -> the owning engagement. Unknown ids are left out."""
    key, owner = _OWNERS[kind]
    stmt = select(key, owner).where(key.in_(list(ids)))
    if kind in _SHOWN:
        stmt = stmt.where(_SHOWN[kind])
    async with tenant_session(tenant) as session:
        rows = await session.execute(stmt)
        return {found: owned for found, owned in rows if owned is not None}

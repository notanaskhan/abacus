"""Which engagement owns the rows an audit event can point at (SPEC-304; DEC-121). The audit
explorer drops events about engagements the reader may not see, so each module says, for the
kinds of target it owns, the engagement of each id. Follow-up: an `engagement_id` on audit events
makes this exact and cheap."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import ColumnElement, select, text
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.evidence.export_models import EngagementExport
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
    "engagement_export": (EngagementExport.id, EngagementExport.engagement_id),  # A-01-T18
}
OCR_RUN = "ocr_run"  # P-11-T22: a run reads a version or an inbox file, whose engagement owns it
_OCR_OWNERS = text(
    "SELECT r.id, coalesce(v.engagement_id, f.engagement_id) FROM ocr_runs r "
    "LEFT JOIN evidence_versions v ON v.id = r.evidence_version_id "
    "LEFT JOIN inbox_files f ON f.id = r.inbox_file_id WHERE r.id = ANY(:ids)"
)
AUDIT_KINDS = frozenset(_OWNERS) | {OCR_RUN}
# SPEC-036 AC-5 (TASK-1210): a shadow run's citation is never shown, so neither are its events.
_SHOWN: dict[str, ColumnElement[bool]] = {"citation": Citation.shadow.is_(False)}


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `kind` rows named by an audit event (the caller has authorised the read of the trail):
    their id -> the owning engagement. Unknown ids are left out."""
    if kind == OCR_RUN:
        async with tenant_session(tenant) as session:
            found = await session.execute(_OCR_OWNERS, {"ids": list(ids)})
            return {row[0]: row[1] for row in found if row[1] is not None}
    key, owner = _OWNERS[kind]
    stmt = select(key, owner).where(key.in_(list(ids)))
    if kind in _SHOWN:
        stmt = stmt.where(_SHOWN[kind])
    async with tenant_session(tenant) as session:
        rows = await session.execute(stmt)
        return {found: owned for found, owned in rows if owned is not None}

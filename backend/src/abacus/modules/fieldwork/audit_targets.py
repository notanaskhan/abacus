"""Which engagement owns the rows an audit event can point at (SPEC-304; DEC-121). The audit
explorer drops events about engagements the reader may not see, so each module says, for the
kinds of target it owns, the engagement of each id. Follow-up: an `engagement_id` on audit events
makes this exact and cheap."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.fieldwork.models import (
    Adjustment,
    Finding,
    Procedure,
    Representation,
    ReviewNote,
    Risk,
    SelectedItem,
    SelectionRow,
)

_OWNERS: dict[str, tuple[QueryableAttribute[UUID], QueryableAttribute[UUID | None]]] = {
    "procedure": (Procedure.id, Procedure.engagement_id),
    "finding": (Finding.id, Finding.engagement_id),
    "risk": (Risk.id, Risk.engagement_id),
    "review_note": (ReviewNote.id, ReviewNote.engagement_id),
    "representation": (Representation.id, Representation.engagement_id),
    "adjustment": (Adjustment.id, Adjustment.engagement_id),
}
AUDIT_KINDS = frozenset({*_OWNERS, "selected_item"})


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `kind` rows named by an audit event (the caller has authorised the read of the trail):
    their id -> the owning engagement. Unknown ids are left out."""
    async with tenant_session(tenant) as session:
        if kind == "selected_item":
            rows = await session.execute(
                select(SelectedItem.id, Procedure.engagement_id)
                .join(SelectionRow, SelectionRow.id == SelectedItem.selection_id)
                .join(Procedure, Procedure.id == SelectionRow.procedure_id)
                .where(SelectedItem.id.in_(list(ids)))
            )
        else:
            key, owner = _OWNERS[kind]
            rows = await session.execute(select(key, owner).where(key.in_(list(ids))))
        return {found: owned for found, owned in rows if owned is not None}

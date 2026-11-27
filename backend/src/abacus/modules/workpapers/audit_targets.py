"""Which engagement owns the rows an audit event can point at (SPEC-304; DEC-121). The audit
explorer drops events about engagements the reader may not see, so each module says, for the
kinds of target it owns, the engagement of each id. Follow-up: an `engagement_id` on audit events
makes this exact and cheap."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import TextClause, select, text
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.workpapers.models import ProgramProcedure
from abacus.modules.workpapers.tie_models import TieOutCheck

_OWNERS: dict[str, tuple[QueryableAttribute[UUID], QueryableAttribute[UUID | None]]] = {
    "tie_out_check": (TieOutCheck.id, TieOutCheck.engagement_id),  # SPEC-310
    "program_procedure": (ProgramProcedure.id, ProgramProcedure.engagement_id),  # A-04-T07
}
# K-03-T20, T22, T23 (S54 end pass): a sheet and its rows belong to their engagement (no ORM
# models: the sheets service reads with text queries).
_ROWS: dict[str, TextClause] = {
    "sheet": text("SELECT id, engagement_id FROM sheets WHERE id = ANY(:ids)"),
    "sheet_row": text("SELECT id, engagement_id FROM sheet_rows WHERE id = ANY(:ids)"),
}
AUDIT_KINDS = frozenset(_OWNERS) | frozenset(_ROWS)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `kind` rows named by an audit event (the caller has authorised the read of the trail):
    their id -> the owning engagement. Unknown ids are left out."""
    if kind in _ROWS:
        async with tenant_session(tenant) as session:
            found = await session.execute(_ROWS[kind], {"ids": list(ids)})
            return {row[0]: row[1] for row in found}
    key, owner = _OWNERS[kind]
    async with tenant_session(tenant) as session:
        rows = await session.execute(select(key, owner).where(key.in_(list(ids))))
        return {found: owned for found, owned in rows if owned is not None}

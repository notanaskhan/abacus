"""Where the trail places A-07's completion targets (S31 end pass; SPEC-304; DEC-121).

The completion projector, subsequent events, legal letters and the representation letter record
audit events on their own rows; each row carries its engagement, so the trail shows the event
only to people who can see that engagement.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import TextClause, text

from abacus.kernel.db import TenantContext, tenant_session

# target type -> the read of its owning engagement (each table has `id` and `engagement_id`).
_OWNERS: Final[dict[str, TextClause]] = {
    "completion_item": text("SELECT id, engagement_id FROM completion_items WHERE id = ANY(:ids)"),
    "subsequent_event_procedure": text(
        "SELECT id, engagement_id FROM subsequent_event_procedures WHERE id = ANY(:ids)"
    ),
    "subsequent_event": text(
        "SELECT id, engagement_id FROM subsequent_events WHERE id = ANY(:ids)"
    ),
    "legal_letter": text("SELECT id, engagement_id FROM legal_letters WHERE id = ANY(:ids)"),
    "representation_letter": text(
        "SELECT id, engagement_id FROM representation_letters WHERE id = ANY(:ids)"
    ),
    # S32 end pass: A-07-T26/T27 and R-02-T12 record on their own rows too.
    "governance_communication": text(
        "SELECT id, engagement_id FROM governance_communications WHERE id = ANY(:ids)"
    ),
    "audit_report": text("SELECT id, engagement_id FROM audit_reports WHERE id = ANY(:ids)"),
}
AUDIT_KINDS: Final = frozenset(_OWNERS)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """id -> the owning engagement, for rows named by an audit event; unknown ids are left out."""
    query = _OWNERS.get(kind)
    if query is None or not ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(query, {"ids": list(ids)})
        return {found: owned for found, owned in rows}

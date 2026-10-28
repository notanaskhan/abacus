"""Which engagement owns the rows an audit event can point at (SPEC-304; DEC-121). The audit
explorer drops events about engagements the reader may not see, so each module says, for the
kinds of target it owns, the engagement of each id. `sign_off.went_stale` names the sign-off
itself (ED-112). Follow-up: an `engagement_id` on audit events makes this exact and cheap."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.review.models import (
    DecisionCard,
    FieldValueVersion,
    HumanGate,
    ReviewableNote,
    SignOff,
)

_OWNERS: dict[str, tuple[QueryableAttribute[UUID], QueryableAttribute[UUID]]] = {
    "sign_off": (SignOff.id, SignOff.engagement_id),  # SPEC-308
    "reviewable_note": (ReviewableNote.id, ReviewableNote.engagement_id),  # P-04-T21, ED-150
    "decision_card": (DecisionCard.id, DecisionCard.engagement_id),  # P-04-T23
    # I-01-T07: a snooze, unsnooze or reassign names its gate; a firm-level gate has none.
    "human_gate": (HumanGate.id, cast(QueryableAttribute[UUID], HumanGate.engagement_id)),
    # P-04-T24 (review low, DEC-609): each field write is audited; a firm-level field has none.
    "field_value_version": (
        FieldValueVersion.id,
        cast(QueryableAttribute[UUID], FieldValueVersion.engagement_id),
    ),
}
AUDIT_KINDS = frozenset(_OWNERS)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `kind` rows named by an audit event (the caller has authorised the read of the trail):
    their id -> the owning engagement. Unknown ids are left out."""
    key, owner = _OWNERS[kind]
    async with tenant_session(tenant) as session:
        rows = await session.execute(select(key, owner).where(key.in_(list(ids))))
        # A firm-level field version has no engagement (the outer join of rows on None).
        return {found: owned for found, owned in rows if cast(UUID | None, owned) is not None}

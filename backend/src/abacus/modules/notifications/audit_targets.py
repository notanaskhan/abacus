"""Which engagement a notification an audit event names is about (SPEC-304; DEC-121). Follow-up:
an `engagement_id` on audit events makes this exact and cheap."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.notifications.repository import notifications

AUDIT_KINDS = frozenset({"notification"})


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """Notification id -> its engagement; a notification about no engagement is left out."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(notifications.c.id, notifications.c.engagement_id).where(
                notifications.c.id.in_(list(ids)), notifications.c.engagement_id.is_not(None)
            )
        )
        return {found: owned for found, owned in rows}

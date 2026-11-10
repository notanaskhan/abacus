"""Which engagement owns the rows collaboration's audit events point at (DEC-121). A firm-scope
to-do has no engagement, so the explorer treats it as firm-level (`targets.OPTIONAL_OWNER`)."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.collaboration.models import CommentThread, Todo

_OWNERS: dict[str, tuple[QueryableAttribute[UUID], QueryableAttribute[UUID | None]]] = {
    "comment_thread": (CommentThread.id, CommentThread.engagement_id),
    "todo": (Todo.id, Todo.engagement_id),
}
AUDIT_KINDS = frozenset(_OWNERS)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `kind` rows named by an audit event: their id -> the owning engagement."""
    key, owner = _OWNERS[kind]
    async with tenant_session(tenant) as session:
        rows = await session.execute(select(key, owner).where(key.in_(list(ids))))
        return {found: owned for found, owned in rows if owned is not None}

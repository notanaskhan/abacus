"""Which engagement owns the rows an audit event can point at (SPEC-304; DEC-121). The audit
explorer drops events about engagements the reader may not see, so each module says, for the
kinds of target it owns, the engagement of each id. Follow-up: an `engagement_id` on audit events
makes this exact and cheap."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.communications.models import Message

_OWNERS: dict[str, tuple[QueryableAttribute[UUID], QueryableAttribute[UUID | None]]] = {
    "message": (Message.id, Message.engagement_id),
}
AUDIT_KINDS = frozenset(_OWNERS)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `kind` rows named by an audit event (the caller has authorised the read of the trail):
    their id -> the owning engagement. Unknown ids are left out."""
    key, owner = _OWNERS[kind]
    async with tenant_session(tenant) as session:
        rows = await session.execute(select(key, owner).where(key.in_(list(ids))))
        return {found: owned for found, owned in rows if owned is not None}


# N-01 intake (0293): a thread, its messages and their attachments belong to the client the
# intake matched them to, before any engagement does; unmatched (no client), they stay hidden
# from the trail's readers until they are (fail closed).
_CLIENTS = {
    "inbox_thread": text("SELECT id, client_id FROM inbox_threads WHERE id = ANY(:ids)"),
    "inbound_message": text(
        "SELECT m.id, t.client_id FROM inbound_messages m "
        "JOIN inbox_threads t ON t.tenant_id = m.tenant_id AND t.id = m.thread_id "
        "WHERE m.id = ANY(:ids)"
    ),
    "inbox_attachment": text(
        "SELECT a.id, coalesce(a.client_id, t.client_id) FROM inbox_attachments a "
        "JOIN inbox_threads t ON t.tenant_id = a.tenant_id AND t.id = a.thread_id "
        "WHERE a.id = ANY(:ids)"
    ),
}
CLIENT_KINDS = frozenset(_CLIENTS)


async def audit_clients(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For intake rows named by an audit event: their id -> the client they were matched to.
    Unknown or unmatched ids are left out."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(_CLIENTS[kind], {"ids": list(ids)})
        return {found: owned for found, owned in rows.tuples() if owned is not None}

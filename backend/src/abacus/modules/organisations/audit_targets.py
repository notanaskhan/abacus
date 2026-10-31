"""Which client owns the organisations rows an audit event can point at (T-01-T10, T-01-T16).

The audit explorer hides events about a client the reader may not see; a consent belongs to its
client (a household or an entity), never to one engagement.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

_CLIENTS: Final = {
    "consent": text("SELECT id, client_id FROM consents WHERE id = ANY(:ids)"),
}
CLIENT_KINDS: Final = frozenset(_CLIENTS)


async def audit_clients(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `kind` rows named by an audit event (the caller has authorised the read of the trail):
    their id -> the owning client. Unknown ids are left out."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(_CLIENTS[kind], {"ids": list(ids)})
        return {row[0]: row[1] for row in rows}

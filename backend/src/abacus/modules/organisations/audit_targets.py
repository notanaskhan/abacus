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
    # T-06-T21 (S50): an external party is kept on its client; a relationship belongs to the
    # client of its entity end (or, with none, of its external party).
    "external_party": text("SELECT id, client_id FROM external_parties WHERE id = ANY(:ids)"),
    "entity_relationship": text(
        "SELECT r.id, COALESCE(ce.client_id, ep.client_id) FROM entity_relationships r "
        "LEFT JOIN client_entities ce ON ce.id = COALESCE(r.from_entity_id, r.to_entity_id) "
        "LEFT JOIN external_parties ep "
        "ON ep.id = COALESCE(r.from_external_party_id, r.to_external_party_id) "
        "WHERE r.id = ANY(:ids)"
    ),
}
CLIENT_KINDS: Final = frozenset(_CLIENTS)


async def audit_clients(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `kind` rows named by an audit event (the caller has authorised the read of the trail):
    their id -> the owning client. Unknown ids are left out."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(_CLIENTS[kind], {"ids": list(ids)})
        return {row[0]: row[1] for row in rows}

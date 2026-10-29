"""Which client owns the rows an audit event can point at (SPEC-304; DEC-121), for the
signatures module's kinds. An envelope always has its client (0292); a staged import file has
one once an envelope consumes it (0294), and until then it stays hidden from the trail's readers
(fail closed). The explorer then shows the event to whoever may see one of the client's
engagements, as it does a client's own events."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

_CLIENTS = {
    "envelope": text("SELECT id, client_id FROM envelopes WHERE id = ANY(:ids)"),
    "envelope_import_file": text(
        "SELECT f.id, e.client_id FROM envelope_import_files f "
        "JOIN envelopes e ON e.tenant_id = f.tenant_id AND e.id = f.consumed_envelope_id "
        "WHERE f.id = ANY(:ids)"
    ),
}
CLIENT_KINDS = frozenset(_CLIENTS)


async def audit_clients(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `kind` rows named by an audit event: their id -> the owning client. Unknown ids, and
    import files no envelope has consumed, are left out."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(_CLIENTS[kind], {"ids": list(ids)})
        return {found: owned for found, owned in rows.tuples() if owned is not None}

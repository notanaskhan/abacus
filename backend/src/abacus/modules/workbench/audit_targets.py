"""Which engagement owns a `workbench_session` an audit event points at (SPEC-304; DEC-121;
P-10-T43). A session names its engagement in `context_refs`; the explorer shows the event to
whoever may see that engagement. A session with no engagement is left out (fail closed)."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

AUDIT_KINDS = frozenset({"workbench_session"})
_SESSIONS = text(
    "SELECT s.id, CAST(r->>'id' AS uuid) AS engagement_id FROM workbench_sessions s "
    "CROSS JOIN LATERAL jsonb_array_elements(s.context_refs) AS r "
    "WHERE s.id = ANY(:ids) AND r->>'kind' = 'engagement'"
)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `workbench_session` rows: their id -> the engagement in their context refs."""
    del kind  # one kind
    async with tenant_session(tenant) as session:
        found = await session.execute(_SESSIONS, {"ids": list(ids)})
        return {row[0]: row[1] for row in found}

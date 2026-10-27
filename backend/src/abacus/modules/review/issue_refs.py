"""Which engagement an issue belongs to (A-02-T17), for owners that link an issue raised through
C3 to a record of theirs (a tie-out check that does not tie, AUD-06 c). Review owns `issues`;
the caller has authorised on its own record's engagement and compares."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session


async def issue_engagement(tenant: TenantContext, issue_id: UUID) -> UUID | None:
    """The issue's engagement in the active tenant, or None (no such issue, or a firm-level
    one). Row-level security keeps other firms' issues out."""
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT engagement_id FROM issues WHERE id = :id"), {"id": issue_id}
        )
    return found if isinstance(found, UUID) else None

"""The engagement's run logs as the archive counts them (A-07-T31; DEC-3108)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

_COUNT = text(
    "SELECT count(*) AS total, count(*) FILTER (WHERE status <> 'running') AS ended "
    "FROM agent_runs WHERE engagement_id = :e"
)


async def run_log_count(tenant: TenantContext, engagement_id: UUID) -> tuple[int, int]:
    """Binder section G and the checklist's "agent run logs packaged": the engagement's runs,
    and how many have ended (a run still `running` has no final log to package)."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_COUNT, {"e": engagement_id})).one()
    return int(row.total), int(row.ended)

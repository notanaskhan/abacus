"""The engagement's run logs as the archive counts them (A-07-T31; DEC-3108)."""

from __future__ import annotations

from datetime import datetime
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


_LAST_COMPLETED = text(
    "SELECT max(finished_at) FROM agent_runs WHERE engagement_id = :e "
    "AND agent_id = :a AND status = 'completed'"
)


async def last_completed_run_at(
    tenant: TenantContext, engagement_id: UUID, agent_id: str
) -> datetime | None:
    """When the engagement's newest completed run of `agent_id` finished (A-07-T32's bring-down
    also-required; DEC-3109), or None."""
    async with tenant_session(tenant) as session:
        found = await session.scalar(_LAST_COMPLETED, {"e": engagement_id, "a": agent_id})
    return found if isinstance(found, datetime) else None


_RECORD_HASHES = text(
    "SELECT run_id, record_sha256 FROM agent_run_records WHERE engagement_id = :e ORDER BY run_id"
)


async def run_record_hashes(tenant: TenantContext, engagement_id: UUID) -> list[tuple[UUID, str]]:
    """A-07-T37: each packaged run record's `record_sha256`, the archive seal's run-record leaves
    (identifiers and hashes only)."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_RECORD_HASHES, {"e": engagement_id})).all()
    return [(r.run_id, r.record_sha256) for r in rows]

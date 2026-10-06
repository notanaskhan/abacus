"""Connections data access: connections and sync runs only (ADR-008, ADR-103)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.connections.models import Connection, SyncRun


async def active_connection_for(
    session: AsyncSession, client_entity_id: UUID
) -> Connection | None:
    """The entity's active connection, newest first (expired ones don't count)."""
    now = datetime.now(UTC)
    return (
        await session.execute(
            select(Connection)
            .where(
                Connection.client_entity_id == client_entity_id,
                Connection.status == "active",
                (Connection.expires_at.is_(None)) | (Connection.expires_at > now),
            )
            .order_by(Connection.created_at.desc(), Connection.id)
            .limit(1)
        )
    ).scalar_one_or_none()


async def get_connection(session: AsyncSession, connection_id: UUID) -> Connection | None:
    return (
        await session.execute(select(Connection).where(Connection.id == connection_id))
    ).scalar_one_or_none()


async def insert_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    connection_id: UUID,
    engagement_id: UUID,
    request_item_id: UUID,
    period_start: date,
    period_end: date,
    started_by: str,
) -> SyncRun:
    return (
        await session.execute(
            insert(SyncRun)
            .values(
                id=uuid4(),
                tenant_id=tenant_id,
                connection_id=connection_id,
                engagement_id=engagement_id,
                request_item_id=request_item_id,
                dataset="trial_balance",
                period_start=period_start,
                period_end=period_end,
                started_by=started_by,
            )
            .returning(SyncRun)
        )
    ).scalar_one()


async def get_run(session: AsyncSession, run_id: UUID) -> SyncRun | None:
    return (
        await session.execute(select(SyncRun).where(SyncRun.id == run_id))
    ).scalar_one_or_none()


async def lock_run(session: AsyncSession, run_id: UUID) -> SyncRun | None:
    """The run, row-locked until commit: stages of one run never interleave."""
    return (
        await session.execute(select(SyncRun).where(SyncRun.id == run_id).with_for_update())
    ).scalar_one_or_none()


async def set_raw(
    session: AsyncSession,
    run_id: UUID,
    *,
    key: str,
    version_id: str,
    fingerprint: str,
    size: int,
    pulled_at: datetime,
) -> None:
    await session.execute(
        update(SyncRun)
        .where(SyncRun.id == run_id)
        .values(
            raw_storage_key=key,
            raw_version_id=version_id,
            raw_fingerprint=fingerprint,
            raw_size_bytes=size,
            raw_pulled_at=pulled_at,
        )
    )


async def set_snapshot(session: AsyncSession, run_id: UUID, snapshot_id: UUID) -> None:
    await session.execute(
        update(SyncRun).where(SyncRun.id == run_id).values(snapshot_id=snapshot_id)
    )


async def finish(
    session: AsyncSession, run_id: UUID, *, status: str, failure_code: str | None = None
) -> None:
    await session.execute(
        update(SyncRun)
        .where(SyncRun.id == run_id, SyncRun.status == "running")
        .values(status=status, failure_code=failure_code, finished_at=datetime.now(UTC))
    )

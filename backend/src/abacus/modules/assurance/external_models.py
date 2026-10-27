"""Record-mode release and archive rows (A-01-T23; migration 0226). Insert-only, human-only.

The readers here serve the interim G8 and G9 providers and the phase service's gate check, in
the caller's session (RLS keeps them to the active tenant).
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import FetchedValue, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.crypto import open_sealed
from abacus.kernel.db import Base, TenantContext


class ExternalRelease(Base):
    __tablename__ = "assurance_external_releases"

    work_item_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    report_released_on: Mapped[date]
    report_kind: Mapped[str]
    recorded_by: Mapped[UUID]
    actor_kind: Mapped[str]
    mfa_at: Mapped[datetime]
    recorded_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ExternalArchive(Base):
    __tablename__ = "assurance_external_archives"

    work_item_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    export_id: Mapped[UUID]
    manifest_sha256: Mapped[str]
    firm_tool_ref_sealed: Mapped[bytes]
    recorded_by: Mapped[UUID]
    actor_kind: Mapped[str]
    mfa_at: Mapped[datetime]
    recorded_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


async def external_release_of(
    session: AsyncSession, engagement_id: UUID
) -> ExternalRelease | None:
    return await session.scalar(
        select(ExternalRelease).where(ExternalRelease.engagement_id == engagement_id).limit(1)
    )


async def external_archive_of(
    session: AsyncSession, engagement_id: UUID
) -> ExternalArchive | None:
    return await session.scalar(
        select(ExternalArchive).where(ExternalArchive.engagement_id == engagement_id).limit(1)
    )


async def external_releases_by_item(
    session: AsyncSession, work_item_ids: list[UUID]
) -> dict[UUID, date]:
    """The recorded release date of each work item that has one (AUD-01 "Released Jul 29")."""
    if not work_item_ids:
        return {}
    rows = await session.execute(
        select(ExternalRelease.work_item_id, ExternalRelease.report_released_on).where(
            ExternalRelease.work_item_id.in_(work_item_ids)
        )
    )
    return {r.work_item_id: r.report_released_on for r in rows}


async def external_archives_by_item(
    session: AsyncSession, work_item_ids: list[UUID]
) -> dict[UUID, bytes]:
    """The sealed firm-tool reference of each archived work item that has one."""
    if not work_item_ids:
        return {}
    rows = await session.execute(
        select(ExternalArchive.work_item_id, ExternalArchive.firm_tool_ref_sealed).where(
            ExternalArchive.work_item_id.in_(work_item_ids)
        )
    )
    return {r.work_item_id: r.firm_tool_ref_sealed for r in rows}


def ref_context(work_item_id: UUID) -> str:
    """What a sealed firm-tool reference is bound to: its own work item's archive record."""
    return hashlib.sha256(f"assurance_external_archive.ref:{work_item_id}".encode()).hexdigest()


async def firm_tool_ref(tenant: TenantContext, work_item_id: UUID, sealed: bytes) -> str:
    """The reference, opened for a caller that may read the work item (AUD-01's tooltip)."""
    return (await open_sealed(tenant.tenant_id, sealed, ref_context(work_item_id))).decode()

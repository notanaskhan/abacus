"""Evidence data access: evidence items and versions only (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.evidence.models import EvidenceItem, EvidenceVersion
from abacus.modules.identity.api import AuthContext, visible

# Serialises version numbering per item for the rest of the transaction. Row locks would need
# UPDATE privilege on the item, which the app deliberately doesn't have. Two-key form: the first
# key namespaces evidence-version locks from any other advisory lock.
_EVIDENCE_LOCK_SPACE = 9_004
_LOCK_ITEM = text("SELECT pg_advisory_xact_lock(:space, hashtext(:item))")


async def insert_item(
    session: AsyncSession,
    *,
    item_id: UUID,
    tenant_id: UUID,
    engagement_id: UUID,
    title: str,
    created_by_kind: str,
    created_by_id: str,
) -> None:
    await session.execute(
        insert(EvidenceItem).values(
            id=item_id,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            title=title,
            created_by_kind=created_by_kind,
            created_by_id=created_by_id,
        )
    )


async def next_version_no(session: AsyncSession, evidence_item_id: UUID) -> int:
    await session.execute(
        _LOCK_ITEM, {"space": _EVIDENCE_LOCK_SPACE, "item": str(evidence_item_id)}
    )
    current = (
        await session.execute(
            select(func.max(EvidenceVersion.version_no)).where(
                EvidenceVersion.evidence_item_id == evidence_item_id
            )
        )
    ).scalar_one_or_none()
    return (current or 0) + 1


async def insert_version(
    session: AsyncSession,
    *,
    version_id: UUID,
    tenant_id: UUID,
    engagement_id: UUID,
    evidence_item_id: UUID,
    version_no: int,
    fingerprint: str,
    storage_key: str,
    storage_version_id: str,
    size_bytes: int,
    media_type: str,
    source: str,
    method: str,
    pulled_at: datetime | None,
    period_start: date | None,
    period_end: date | None,
    client_entity_id: UUID | None,
    snapshot_id: UUID | None,
    idempotency_key: str | None,
) -> EvidenceVersion:
    return (
        await session.execute(
            insert(EvidenceVersion)
            .values(
                id=version_id,
                tenant_id=tenant_id,
                engagement_id=engagement_id,
                evidence_item_id=evidence_item_id,
                version_no=version_no,
                fingerprint=fingerprint,
                storage_key=storage_key,
                storage_version_id=storage_version_id,
                size_bytes=size_bytes,
                media_type=media_type,
                source=source,
                method=method,
                pulled_at=pulled_at,
                period_start=period_start,
                period_end=period_end,
                client_entity_id=client_entity_id,
                snapshot_id=snapshot_id,
                idempotency_key=idempotency_key,
            )
            .returning(EvidenceVersion)
        )
    ).scalar_one()


async def get_version(session: AsyncSession, version_id: UUID) -> EvidenceVersion | None:
    return (
        await session.execute(select(EvidenceVersion).where(EvidenceVersion.id == version_id))
    ).scalar_one_or_none()


async def get_item(session: AsyncSession, item_id: UUID) -> EvidenceItem | None:
    return (
        await session.execute(select(EvidenceItem).where(EvidenceItem.id == item_id))
    ).scalar_one_or_none()


async def version_for_key(session: AsyncSession, idempotency_key: str) -> EvidenceVersion | None:
    return (
        await session.execute(
            select(EvidenceVersion).where(EvidenceVersion.idempotency_key == idempotency_key)
        )
    ).scalar_one_or_none()


async def list_versions(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[EvidenceVersion]:
    """The engagement's evidence versions the caller may read, oldest first."""
    return (
        (
            await session.execute(
                select(EvidenceVersion)
                .where(
                    EvidenceVersion.engagement_id == engagement_id,
                    visible(ctx, "evidence.read", EvidenceVersion.engagement_id),
                )
                .order_by(EvidenceVersion.created_at, EvidenceVersion.id)
            )
        )
        .scalars()
        .all()
    )

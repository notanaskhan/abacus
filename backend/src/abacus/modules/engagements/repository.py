"""Engagements data access: `engagements` and the methodology tables (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute, aliased

from abacus.modules.engagements.models import (
    Engagement,
    MethodologyAccountRule,
    MethodologyArea,
    MethodologyRequestItem,
    MethodologyTemplate,
    MethodologyVersion,
)
from abacus.modules.engagements.workbook import Methodology
from abacus.modules.identity.api import AuthContext, visible


async def insert_engagement(
    session: AsyncSession,
    *,
    engagement_id: UUID,
    tenant_id: UUID,
    client_id: UUID,
    client_entity_id: UUID,
    name: str,
    fiscal_period_start: date,
    fiscal_period_end: date,
    created_by: UUID,
    type: str = "audit",
) -> None:
    await session.execute(
        insert(Engagement).values(
            type=type,
            id=engagement_id,
            tenant_id=tenant_id,
            client_id=client_id,
            client_entity_id=client_entity_id,
            name=name,
            fiscal_period_start=fiscal_period_start,
            fiscal_period_end=fiscal_period_end,
            created_by=created_by,
        )
    )


async def get_engagement(session: AsyncSession, engagement_id: UUID) -> Engagement | None:
    """Row-level security returns None for another firm's engagement, as for a missing one."""
    return (
        await session.execute(select(Engagement).where(Engagement.id == engagement_id))
    ).scalar_one_or_none()


async def lock_engagement(session: AsyncSession, engagement_id: UUID) -> Engagement | None:
    """Inside a unit of work: the row, share-locked until commit, so it can't be archived (or
    otherwise changed) between the permission check and the write."""
    return (
        await session.execute(
            select(Engagement).where(Engagement.id == engagement_id).with_for_update(read=True)
        )
    ).scalar_one_or_none()


async def list_engagements(session: AsyncSession, ctx: AuthContext) -> Sequence[Engagement]:
    return (
        (
            await session.execute(
                select(Engagement)
                .where(visible(ctx, "engagement.read_metadata", Engagement.id))
                .order_by(Engagement.created_at.desc(), Engagement.id)
            )
        )
        .scalars()
        .all()
    )


def client_column(
    engagement_id: ColumnElement[UUID] | QueryableAttribute[UUID],
) -> ColumnElement[UUID]:
    """The engagement's client, as a subquery (for ethical walls in `visible()`). Aliased, so it
    correlates with the outer row even when the outer query lists engagements itself."""
    inner = aliased(Engagement)
    return (
        select(inner.client_id)
        .where(inner.id == engagement_id)
        .correlate_except(inner)  # it may sit inside another subquery (walls' EXISTS)
        .scalar_subquery()
    )


async def template_id_for(session: AsyncSession, name: str) -> UUID | None:
    return (
        await session.execute(
            select(MethodologyTemplate.id).where(MethodologyTemplate.name == name)
        )
    ).scalar_one_or_none()


async def lock_or_insert_template(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    name: str,
    created_by: UUID,
    engagement_types: Sequence[str] = ("audit",),
) -> tuple[UUID, bool]:
    """The template's ID, created if new; locked, so concurrent imports number versions in turn."""
    created = (
        await session.execute(
            pg_insert(MethodologyTemplate)
            .values(
                id=uuid4(),
                tenant_id=tenant_id,
                name=name,
                created_by=created_by,
                engagement_types=list(engagement_types),
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "name"])
            .returning(MethodologyTemplate.id)
        )
    ).scalar_one_or_none()
    if created is not None:
        return created, True
    existing = (
        await session.execute(
            select(MethodologyTemplate.id)
            .where(MethodologyTemplate.name == name)
            .with_for_update()
        )
    ).scalar_one()
    return existing, False


async def insert_version(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    template_id: UUID,
    fingerprint: str,
    imported_by: UUID,
    methodology: Methodology,
) -> tuple[UUID, int]:
    """The next version of the template with its rows (the caller holds the template's lock)."""
    latest = await session.scalar(
        select(func.max(MethodologyVersion.version)).where(
            MethodologyVersion.template_id == template_id
        )
    )
    number = (latest or 0) + 1
    version_id = uuid4()
    await session.execute(
        insert(MethodologyVersion).values(
            id=version_id,
            tenant_id=tenant_id,
            template_id=template_id,
            version=number,
            source_fingerprint=fingerprint,
            imported_by=imported_by,
        )
    )
    base = {"tenant_id": tenant_id, "version_id": version_id}
    await session.execute(
        insert(MethodologyArea),
        [
            {**base, "code": a.code, "name": a.name, "position": i}
            for i, a in enumerate(methodology.areas)
        ],
    )
    if methodology.items:
        await session.execute(
            insert(MethodologyRequestItem),
            [
                {
                    **base,
                    "area_code": t.area_code,
                    "description": t.description,
                    "retrievability_tier": t.tier,
                    "position": i,
                }
                for i, t in enumerate(methodology.items)
            ],
        )
    if methodology.rules:
        await session.execute(
            insert(MethodologyAccountRule),
            [
                {
                    **base,
                    "area_code": r.area_code,
                    "account_from": r.account_from,
                    "account_to": r.account_to,
                    "position": i,
                }
                for i, r in enumerate(methodology.rules)
            ],
        )
    return version_id, number


async def list_templates(
    session: AsyncSession,
) -> Sequence[tuple[MethodologyTemplate, MethodologyVersion]]:
    """Every template of the firm with each of its versions, newest first."""
    rows = await session.execute(
        select(MethodologyTemplate, MethodologyVersion)
        .join(MethodologyVersion, MethodologyVersion.template_id == MethodologyTemplate.id)
        .order_by(MethodologyTemplate.name, MethodologyVersion.version.desc())
    )
    return [(t, v) for t, v in rows.all()]


async def get_version(
    session: AsyncSession, version_id: UUID
) -> tuple[MethodologyTemplate, MethodologyVersion] | None:
    row = (
        await session.execute(
            select(MethodologyTemplate, MethodologyVersion)
            .join(MethodologyVersion, MethodologyVersion.template_id == MethodologyTemplate.id)
            .where(MethodologyVersion.id == version_id)
        )
    ).first()
    return (row[0], row[1]) if row is not None else None


async def version_rows(
    session: AsyncSession, version_id: UUID
) -> tuple[
    Sequence[MethodologyArea], Sequence[MethodologyRequestItem], Sequence[MethodologyAccountRule]
]:
    areas = (
        await session.execute(
            select(MethodologyArea)
            .where(MethodologyArea.version_id == version_id)
            .order_by(MethodologyArea.position)
        )
    ).scalars()
    items = (
        await session.execute(
            select(MethodologyRequestItem)
            .where(MethodologyRequestItem.version_id == version_id)
            .order_by(MethodologyRequestItem.position)
        )
    ).scalars()
    rules = (
        await session.execute(
            select(MethodologyAccountRule)
            .where(MethodologyAccountRule.version_id == version_id)
            .order_by(MethodologyAccountRule.position)
        )
    ).scalars()
    return areas.all(), items.all(), rules.all()


async def set_methodology_version(
    session: AsyncSession, engagement_id: UUID, version_id: UUID
) -> bool:
    """Pin the version, only if none is pinned yet (AC-5). False when one already was."""
    pinned = await session.execute(
        update(Engagement)
        .where(Engagement.id == engagement_id, Engagement.methodology_version_id.is_(None))
        .values(methodology_version_id=version_id)
        .returning(Engagement.id)
    )
    return pinned.scalar_one_or_none() is not None

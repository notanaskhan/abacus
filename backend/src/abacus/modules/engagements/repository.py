"""Engagements data access: `engagements` and the methodology tables (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, exists, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute, aliased

from abacus.modules.engagements.models import (
    Engagement,
    EngagementAcceptance,
    EngagementLetter,
    IndependenceConfirmation,
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
    session: AsyncSession, *, latest: bool = False
) -> Sequence[tuple[MethodologyTemplate, MethodologyVersion]]:
    """Every template of the firm with each of its versions, newest first; with `latest`, only
    each template's newest version (SPEC-025 AC-3; TASK-047 D3)."""
    query = (
        select(MethodologyTemplate, MethodologyVersion)
        .join(MethodologyVersion, MethodologyVersion.template_id == MethodologyTemplate.id)
        .order_by(MethodologyTemplate.name, MethodologyVersion.version.desc())
    )
    if latest:
        newer = aliased(MethodologyVersion)
        query = query.where(
            ~select(newer.id)
            .where(
                newer.template_id == MethodologyVersion.template_id,
                newer.version > MethodologyVersion.version,
            )
            .exists()
        )
    rows = await session.execute(query)
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


async def setup_counts(session: AsyncSession) -> tuple[int, int]:
    """How many methodology templates and engagements the session's firm has (SPEC-024 AC-7)."""
    templates = await session.scalar(select(func.count()).select_from(MethodologyTemplate))
    engagements = await session.scalar(select(func.count()).select_from(Engagement))
    return int(templates or 0), int(engagements or 0)


# --- Acceptance, independence and the letter (SPEC-025; TASK-044) ------------------------------


async def latest_acceptance(
    session: AsyncSession, engagement_id: UUID
) -> EngagementAcceptance | None:
    return (
        await session.execute(
            select(EngagementAcceptance)
            .where(EngagementAcceptance.engagement_id == engagement_id)
            .order_by(EngagementAcceptance.created_at.desc(), EngagementAcceptance.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def insert_acceptance(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(EngagementAcceptance).values(**values))


async def other_engagements_of_client(
    session: AsyncSession, client_id: UUID, engagement_id: UUID
) -> int:
    found = await session.scalar(
        select(func.count())
        .select_from(Engagement)
        .where(Engagement.client_id == client_id, Engagement.id != engagement_id)
    )
    return int(found or 0)


async def request_confirmation(
    session: AsyncSession, tenant_id: UUID, engagement_id: UUID, user_id: UUID
) -> bool:
    """A `requested` row unless one exists (an earlier answer stands). True if created."""
    created = await session.execute(
        pg_insert(IndependenceConfirmation)
        .values(tenant_id=tenant_id, engagement_id=engagement_id, user_id=user_id)
        .on_conflict_do_nothing()
        .returning(IndependenceConfirmation.user_id)
    )
    return created.scalar_one_or_none() is not None


async def answer_confirmation(
    session: AsyncSession,
    engagement_id: UUID,
    user_id: UUID,
    *,
    status: str,
    statement_version: str | None,
    note: str | None,
) -> None:
    await session.execute(
        update(IndependenceConfirmation)
        .where(
            IndependenceConfirmation.engagement_id == engagement_id,
            IndependenceConfirmation.user_id == user_id,
        )
        .values(
            status=status,
            statement_version=statement_version,
            note=note,
            answered_at=func.clock_timestamp(),
        )
    )


def confirmed_column(
    engagement_id: ColumnElement[UUID] | QueryableAttribute[UUID], user_id: UUID
) -> ColumnElement[bool]:
    """Whether the person has confirmed their independence for the row's engagement (SPEC-025,
    TASK-045: identity's `visible()`)."""
    return (
        exists()
        .where(
            IndependenceConfirmation.engagement_id == engagement_id,
            IndependenceConfirmation.user_id == user_id,
            IndependenceConfirmation.status == "confirmed",
        )
        .correlate_except(IndependenceConfirmation)
    )


async def is_confirmed(session: AsyncSession, engagement_id: UUID, user_id: UUID) -> bool:
    found = await session.scalar(
        select(IndependenceConfirmation.status).where(
            IndependenceConfirmation.engagement_id == engagement_id,
            IndependenceConfirmation.user_id == user_id,
        )
    )
    return found == "confirmed"


async def confirmations_of(
    session: AsyncSession, engagement_id: UUID
) -> Sequence[IndependenceConfirmation]:
    """The engagement's confirmations, for a caller that authorised `setup.read` on it
    (LIST_EXEMPT)."""
    return (
        (
            await session.execute(
                select(IndependenceConfirmation)
                .where(IndependenceConfirmation.engagement_id == engagement_id)
                .order_by(IndependenceConfirmation.requested_at, IndependenceConfirmation.user_id)
            )
        )
        .scalars()
        .all()
    )


async def my_open_confirmations(
    session: AsyncSession, user_id: UUID
) -> Sequence[tuple[IndependenceConfirmation, Engagement]]:
    """The person's own unanswered requests in the session's firm (LIST_EXEMPT: own rows)."""
    rows = await session.execute(
        select(IndependenceConfirmation, Engagement)
        .join(Engagement, Engagement.id == IndependenceConfirmation.engagement_id)
        .where(
            IndependenceConfirmation.user_id == user_id,
            IndependenceConfirmation.status != "confirmed",
        )
        .order_by(IndependenceConfirmation.requested_at)
    )
    return list(rows.tuples().all())


async def get_letter(session: AsyncSession, engagement_id: UUID) -> EngagementLetter | None:
    return (
        await session.execute(
            select(EngagementLetter).where(EngagementLetter.engagement_id == engagement_id)
        )
    ).scalar_one_or_none()


async def put_letter(session: AsyncSession, values: dict[str, object]) -> None:
    keep = {k: v for k, v in values.items() if k not in ("tenant_id", "engagement_id")}
    await session.execute(
        pg_insert(EngagementLetter)
        .values(**values)
        .on_conflict_do_update(index_elements=["tenant_id", "engagement_id"], set_=keep)
    )

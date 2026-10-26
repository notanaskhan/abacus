"""Engagements data access: `engagements` and its own tables (ADR-008, ADR-103). The methodology
tables are the methodology module's since K-01-T02."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import ColumnElement, exists, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute, aliased

from abacus.modules.engagements.models import (
    Engagement,
    EngagementAcceptance,
    EngagementLetter,
    IndependenceConfirmation,
)
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
    type: str = "fs_audit",
    prior_engagement_id: UUID | None = None,
    prospect: bool = False,
) -> None:
    """`prospect`: created Prospect, awaiting acceptance (intake, "Start acceptance"; DEC-372).
    The app never inserts a status (the column default is `active`); it moves the new row to
    `prospect` in the same transaction, so no other session ever sees it otherwise."""
    await session.execute(
        insert(Engagement).values(
            type=type,
            prior_engagement_id=prior_engagement_id,
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
    if prospect:
        await session.execute(
            update(Engagement).where(Engagement.id == engagement_id).values(status="prospect")
        )


async def prior_candidates(
    session: AsyncSession, ctx: AuthContext, client_entity_id: UUID, type: str, before: date
) -> Sequence[Engagement]:
    """SPEC-025 AC-2 (TASK-048): the entity's engagements of this type whose period ended before
    `before`, latest first, that the caller may roll forward from (walls excluded)."""
    return (
        (
            await session.execute(
                select(Engagement)
                .where(
                    visible(ctx, "roll_forward.read", Engagement.id),
                    Engagement.client_entity_id == client_entity_id,
                    Engagement.type == type,
                    Engagement.fiscal_period_end < before,
                )
                .order_by(Engagement.fiscal_period_end.desc(), Engagement.created_at.desc())
                .limit(10)
            )
        )
        .scalars()
        .all()
    )


async def open_engagement_ids(session: AsyncSession) -> Sequence[UUID]:
    """SPEC-027 (TASK-050): the session firm's non-archived engagements, for resuming every
    agent in the firm (LIST_EXEMPT: the platform, not a person, reads them)."""
    return (
        (await session.execute(select(Engagement.id).where(Engagement.status != "archived")))
        .scalars()
        .all()
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
    session: AsyncSession, ctx: AuthContext
) -> Sequence[tuple[IndependenceConfirmation, Engagement]]:
    """The person's own unanswered requests in the session's firm, through `visible()`: a wall
    hides the engagement and its client from its own team member (SPEC-002 AC-5)."""
    rows = await session.execute(
        select(IndependenceConfirmation, Engagement)
        .join(Engagement, Engagement.id == IndependenceConfirmation.engagement_id)
        .where(
            IndependenceConfirmation.user_id == ctx.user_id,
            IndependenceConfirmation.status != "confirmed",
            visible(ctx, "engagement.read_metadata", Engagement.id),
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


# --- AI exclusion (SPEC-036; TASK-076) ----------------------------------------------------------


async def set_ai_exclusion(
    session: AsyncSession, engagement_id: UUID, by: UUID | None, reason: str | None
) -> None:
    await session.execute(
        update(Engagement)
        .where(Engagement.id == engagement_id)
        .values(
            ai_excluded_at=func.clock_timestamp() if by is not None else None,
            ai_excluded_by=by,
            ai_excluded_reason=reason,
        )
    )


async def engagement_count(session: AsyncSession) -> int:
    """How many engagements the session's firm has (SPEC-024 AC-7)."""
    return int(await session.scalar(select(func.count()).select_from(Engagement)) or 0)

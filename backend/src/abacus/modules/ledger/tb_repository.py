"""Trial balance of record data access (SPEC-309). Only ledger tables (ADR-008)."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.ledger.models import (
    LedgerSnapshot,
    TrialBalance,
    TrialBalanceAnnotation,
    TrialBalanceVersion,
)


async def snapshots_of_entity(
    session: AsyncSession, client_entity_id: UUID
) -> Sequence[LedgerSnapshot]:
    """Newest first (LIST_EXEMPT: the caller authorised on an engagement for the entity)."""
    return (
        (
            await session.execute(
                select(LedgerSnapshot)
                .where(LedgerSnapshot.client_entity_id == client_entity_id)
                .order_by(LedgerSnapshot.pulled_at.desc(), LedgerSnapshot.created_at.desc())
                .limit(200)
            )
        )
        .scalars()
        .all()
    )


async def trial_balances_of(session: AsyncSession, engagement_id: UUID) -> Sequence[TrialBalance]:
    """By period end then label (LIST_EXEMPT: the caller authorised on the engagement)."""
    return (
        (
            await session.execute(
                select(TrialBalance)
                .where(TrialBalance.engagement_id == engagement_id)
                .order_by(TrialBalance.period_end.desc(), TrialBalance.label)
            )
        )
        .scalars()
        .all()
    )


async def get_trial_balance(session: AsyncSession, tb_id: UUID) -> TrialBalance | None:
    return await session.get(TrialBalance, tb_id)


async def lock_trial_balance(session: AsyncSession, tb_id: UUID) -> TrialBalance | None:
    return (
        await session.execute(
            select(TrialBalance).where(TrialBalance.id == tb_id).with_for_update()
        )
    ).scalar_one_or_none()


async def find_trial_balance(
    session: AsyncSession,
    work_item_id: UUID,
    client_entity_id: UUID,
    label: str,
    period_end: object,
) -> UUID | None:
    return await session.scalar(
        select(TrialBalance.id).where(
            TrialBalance.work_item_id == work_item_id,
            TrialBalance.client_entity_id == client_entity_id,
            TrialBalance.label == label,
            TrialBalance.period_end == period_end,
        )
    )


async def insert_trial_balance(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(insert(TrialBalance).values(**values).returning(TrialBalance.id))
    ).scalar_one()


async def set_current_version(session: AsyncSession, tb_id: UUID, version_no: int) -> None:
    await session.execute(
        update(TrialBalance).where(TrialBalance.id == tb_id).values(current_version_no=version_no)
    )


async def versions_of(session: AsyncSession, tb_id: UUID) -> Sequence[TrialBalanceVersion]:
    """Newest first (LIST_EXEMPT: the caller authorised on the engagement)."""
    return (
        (
            await session.execute(
                select(TrialBalanceVersion)
                .where(TrialBalanceVersion.trial_balance_id == tb_id)
                .order_by(TrialBalanceVersion.version_no.desc())
            )
        )
        .scalars()
        .all()
    )


async def insert_version(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(TrialBalanceVersion).values(**values))


async def newest_annotations(
    session: AsyncSession, tb_id: UUID
) -> Sequence[TrialBalanceAnnotation]:
    """Each account's newest annotation (LIST_EXEMPT: the caller authorised on the engagement)."""
    return (
        (
            await session.execute(
                select(TrialBalanceAnnotation)
                .where(TrialBalanceAnnotation.trial_balance_id == tb_id)
                .distinct(TrialBalanceAnnotation.account_code)
                .order_by(
                    TrialBalanceAnnotation.account_code,
                    TrialBalanceAnnotation.created_at.desc(),
                    TrialBalanceAnnotation.id.desc(),
                )
            )
        )
        .scalars()
        .all()
    )


async def annotation_setters(session: AsyncSession, tb_id: UUID) -> set[UUID]:
    """Everyone who ever annotated the trial balance (P-04-T15: its preparers; LIST_EXEMPT: the
    caller authorised on the engagement)."""
    found = await session.execute(
        select(TrialBalanceAnnotation.set_by)
        .where(TrialBalanceAnnotation.trial_balance_id == tb_id)
        .distinct()
    )
    return set(found.scalars().all())


async def insert_annotations(session: AsyncSession, rows: list[dict[str, object]]) -> None:
    if rows:
        await session.execute(insert(TrialBalanceAnnotation), rows)

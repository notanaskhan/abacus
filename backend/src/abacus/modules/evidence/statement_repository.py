"""Approved statement data access (SPEC-312; TASK-324). Only this module's tables."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.evidence.models import StatementDataset, StatementTransaction


async def dataset_for_version(session: AsyncSession, version_id: UUID) -> StatementDataset | None:
    return await session.scalar(
        select(StatementDataset).where(StatementDataset.evidence_version_id == version_id)
    )


async def transactions_of(
    session: AsyncSession, dataset_id: UUID
) -> Sequence[StatementTransaction]:
    """In order (LIST_EXEMPT: the caller authorised `evidence.read` on the item)."""
    return (
        (
            await session.execute(
                select(StatementTransaction)
                .where(StatementTransaction.dataset_id == dataset_id)
                .order_by(StatementTransaction.position)
            )
        )
        .scalars()
        .all()
    )


async def insert_dataset(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(
            insert(StatementDataset).values(**values).returning(StatementDataset.id)
        )
    ).scalar_one()


async def insert_transactions(session: AsyncSession, rows: list[dict[str, object]]) -> None:
    if rows:
        await session.execute(insert(StatementTransaction), rows)

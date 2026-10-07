"""Ledger data access: snapshots and trial balance lines only (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.ledger.models import LedgerSnapshot, TrialBalanceLineRow
from abacus.modules.ledger.normalise import LedgerLine


async def find_snapshot(
    session: AsyncSession,
    *,
    client_entity_id: UUID,
    period_start: date,
    period_end: date,
    raw_fingerprint: str,
) -> LedgerSnapshot | None:
    return (
        await session.execute(
            select(LedgerSnapshot).where(
                LedgerSnapshot.client_entity_id == client_entity_id,
                LedgerSnapshot.period_start == period_start,
                LedgerSnapshot.period_end == period_end,
                LedgerSnapshot.raw_fingerprint == raw_fingerprint,
            )
        )
    ).scalar_one_or_none()


async def insert_snapshot(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    client_entity_id: UUID,
    period_start: date,
    period_end: date,
    pulled_at: datetime,
    source: str,
    raw_fingerprint: str,
    line_count: int,
    total_debit: Decimal,
    total_credit: Decimal,
) -> UUID | None:
    """The new snapshot's ID, or None if this pull's snapshot already exists."""
    return (
        await session.execute(
            pg_insert(LedgerSnapshot)
            .values(
                id=uuid4(),
                tenant_id=tenant_id,
                client_entity_id=client_entity_id,
                period_start=period_start,
                period_end=period_end,
                pulled_at=pulled_at,
                source=source,
                raw_fingerprint=raw_fingerprint,
                line_count=line_count,
                total_debit=total_debit,
                total_credit=total_credit,
            )
            .on_conflict_do_nothing(constraint="ledger_snapshots_pull")
            .returning(LedgerSnapshot.id)
        )
    ).scalar_one_or_none()


async def insert_lines(
    session: AsyncSession, tenant_id: UUID, snapshot_id: UUID, lines: Sequence[LedgerLine]
) -> None:
    await session.execute(
        insert(TrialBalanceLineRow),
        [
            {
                "id": uuid4(),
                "tenant_id": tenant_id,
                "snapshot_id": snapshot_id,
                "account_code": line.account_code,
                "account_name": line.account_name,
                "debit": line.debit,
                "credit": line.credit,
                "source_ref": line.source_ref,
            }
            for line in lines
        ],
    )


async def get_snapshot(session: AsyncSession, snapshot_id: UUID) -> LedgerSnapshot | None:
    return (
        await session.execute(select(LedgerSnapshot).where(LedgerSnapshot.id == snapshot_id))
    ).scalar_one_or_none()


async def lines_of(session: AsyncSession, snapshot_id: UUID) -> Sequence[TrialBalanceLineRow]:
    """Lines of one snapshot the caller has already resolved under RLS (LIST_EXEMPT)."""
    return (
        (
            await session.execute(
                select(TrialBalanceLineRow)
                .where(TrialBalanceLineRow.snapshot_id == snapshot_id)
                .order_by(TrialBalanceLineRow.account_code)
            )
        )
        .scalars()
        .all()
    )


async def lines_of_snapshots(
    session: AsyncSession, snapshot_ids: Sequence[UUID]
) -> Sequence[TrialBalanceLineRow]:
    """The lines of these snapshots (SPEC-006 scope), for a caller that authorised on them."""
    if not snapshot_ids:
        return []
    return (
        (
            await session.execute(
                select(TrialBalanceLineRow).where(
                    TrialBalanceLineRow.snapshot_id.in_(snapshot_ids)
                )
            )
        )
        .scalars()
        .all()
    )


async def totals_of_snapshots(
    session: AsyncSession, snapshot_ids: Sequence[UUID]
) -> Sequence[tuple[Decimal, Decimal]]:
    if not snapshot_ids:
        return []
    rows = await session.execute(
        select(LedgerSnapshot.total_debit, LedgerSnapshot.total_credit).where(
            LedgerSnapshot.id.in_(snapshot_ids)
        )
    )
    return [(d, c) for d, c in rows.all()]


async def accounts_in_firm(session: AsyncSession) -> Sequence[tuple[str, str]]:
    """Every (account code, account name) in the tenant's snapshots (SPEC-006 scope)."""
    rows = await session.execute(
        select(TrialBalanceLineRow.account_code, TrialBalanceLineRow.account_name).distinct()
    )
    return [(c, n) for c, n in rows.all()]

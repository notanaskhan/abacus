"""Ledger data access: snapshots and trial balance lines only (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.ledger.models import (
    GlAccountBalance,
    GlEntryRow,
    GlSnapshot,
    LedgerSnapshot,
    TrialBalanceLineRow,
)
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


# --- General ledger detail (SPEC-034; TASK-069) -------------------------------------------------


async def insert_gl_snapshot(session: AsyncSession, **values: object) -> UUID | None:
    """The new snapshot's ID, or None when this file's snapshot already exists."""
    return (
        await session.execute(
            pg_insert(GlSnapshot)
            .values(**values)
            .on_conflict_do_nothing(constraint="gl_snapshots_file")
            .returning(GlSnapshot.id)
        )
    ).scalar_one_or_none()


async def find_gl_snapshot(
    session: AsyncSession,
    *,
    client_entity_id: UUID,
    period_start: date,
    period_end: date,
    raw_fingerprint: str,
) -> GlSnapshot | None:
    return (
        await session.execute(
            select(GlSnapshot).where(
                GlSnapshot.client_entity_id == client_entity_id,
                GlSnapshot.period_start == period_start,
                GlSnapshot.period_end == period_end,
                GlSnapshot.raw_fingerprint == raw_fingerprint,
            )
        )
    ).scalar_one_or_none()


async def insert_gl_rows(
    session: AsyncSession,
    table: type[GlAccountBalance] | type[GlEntryRow],
    rows: list[dict[str, object]],
) -> None:
    if rows:
        await session.execute(insert(table), rows)


async def get_gl_snapshot(session: AsyncSession, snapshot_id: UUID) -> GlSnapshot | None:
    return (
        await session.execute(select(GlSnapshot).where(GlSnapshot.id == snapshot_id))
    ).scalar_one_or_none()


async def gl_balances_of(session: AsyncSession, snapshot_id: UUID) -> Sequence[GlAccountBalance]:
    """A GL snapshot's reconciliation, by account (the caller authorised on it; LIST_EXEMPT)."""
    return (
        (
            await session.execute(
                select(GlAccountBalance)
                .where(GlAccountBalance.snapshot_id == snapshot_id)
                .order_by(GlAccountBalance.account_code)
            )
        )
        .scalars()
        .all()
    )


async def gl_entries_of(
    session: AsyncSession, snapshot_id: UUID, *, after: int, limit: int
) -> Sequence[GlEntryRow]:
    """A page of a GL snapshot's entries in line order (the caller authorised; LIST_EXEMPT)."""
    return (
        (
            await session.execute(
                select(GlEntryRow)
                .where(GlEntryRow.snapshot_id == snapshot_id, GlEntryRow.line_no > after)
                .order_by(GlEntryRow.line_no)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def latest_snapshot_for(
    session: AsyncSession, client_entity_id: UUID, period_start: date, period_end: date
) -> LedgerSnapshot | None:
    """The newest trial balance snapshot of an entity for a period (SPEC-034 AC-3)."""
    return (
        await session.execute(
            select(LedgerSnapshot)
            .where(
                LedgerSnapshot.client_entity_id == client_entity_id,
                LedgerSnapshot.period_start == period_start,
                LedgerSnapshot.period_end == period_end,
            )
            .order_by(LedgerSnapshot.pulled_at.desc(), LedgerSnapshot.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

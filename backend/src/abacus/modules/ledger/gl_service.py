"""General ledger snapshots (SPEC-034; TASK-069; ADR-004, ADR-038). PROTECTED.

A GL snapshot exists only for a general ledger that `validate_gl` proved complete against a
trial balance snapshot of the same entity and period: `record_gl_snapshot` checks again inside
the caller's unit of work, then inserts the snapshot, its reconciliation and its entries (in
batches) in that one transaction. The same file gives the same snapshot.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final
from uuid import UUID, uuid4

from abacus.kernel.db import TenantContext, tenant_session, transaction_context
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.ledger.general_ledger import (
    Balance,
    GlEntry,
    GlSummary,
    TbAccount,
    validate_gl,
)
from abacus.modules.ledger.models import GlAccountBalance, GlEntryRow
from abacus.modules.ledger.repository import (
    find_gl_snapshot,
    get_gl_snapshot,
    get_snapshot,
    gl_balances_of,
    gl_entries_of,
    insert_gl_rows,
    insert_gl_snapshot,
    latest_snapshot_for,
    lines_of,
    newest_gl_snapshot,
)
from abacus.modules.ledger.service import Unvalidated

BATCH: Final = 5000


@dataclass(frozen=True)
class TrialBalanceFor:
    snapshot_id: UUID
    accounts: tuple[TbAccount, ...]


async def year_end_trial_balance(
    tenant: TenantContext, client_entity_id: UUID, period_start: date, period_end: date
) -> TrialBalanceFor | None:
    """The newest trial balance snapshot for the entity and period, as accounts; None without
    one (SPEC-034 AC-4: the general ledger waits)."""
    async with tenant_session(tenant) as session:
        snapshot = await latest_snapshot_for(session, client_entity_id, period_start, period_end)
        if snapshot is None:
            return None
        lines = await lines_of(session, snapshot.id)
    return TrialBalanceFor(
        snapshot.id,
        tuple(TbAccount(x.account_code, x.account_name, x.debit - x.credit) for x in lines),
    )


@dataclass(frozen=True)
class GlSnapshotRef:
    id: UUID
    created: bool


def _balance_row(tenant_id: UUID, snapshot_id: UUID, b: Balance) -> dict[str, object]:
    return {
        "tenant_id": tenant_id,
        "snapshot_id": snapshot_id,
        "account_code": b.code,
        "account_name": b.name[:200] or b.code,
        "opening": b.opening,
        "debit": b.debit,
        "credit": b.credit,
        "closing": b.closing,
        "tb_closing": b.tb_closing,
        "opening_derived": b.opening_derived,
    }


def _entry_row(tenant_id: UUID, snapshot_id: UUID, e: GlEntry) -> dict[str, object]:
    return {
        "tenant_id": tenant_id,
        "snapshot_id": snapshot_id,
        "line_no": e.line_no,
        "account_code": e.account_code,
        "posted_on": e.posted_on,
        "reference": e.reference,
        "kind": e.kind,
        "counterparty": e.counterparty,
        "description": e.description,
        "debit": e.debit,
        "credit": e.credit,
        "source_ref": e.source_ref,
    }


async def record_gl_snapshot(
    tx: UnitOfWork,
    *,
    client_entity_id: UUID,
    period_start: date,
    period_end: date,
    summary: GlSummary,
    entries: Iterable[GlEntry],
    tb_snapshot_id: UUID,
    raw_fingerprint: str,
    source: str,
) -> GlSnapshotRef:
    """Inside the caller's unit of work: nothing unproven is ever stored (ADR-038)."""
    tb = await get_snapshot(tx.session, tb_snapshot_id)
    if tb is None or tb.client_entity_id != client_entity_id:
        raise NotFound("ledger_snapshot")
    lines = await lines_of(tx.session, tb_snapshot_id)
    accounts = tuple(TbAccount(x.account_code, x.account_name, x.debit - x.credit) for x in lines)
    check = validate_gl(summary, accounts, period_start=period_start, period_end=period_end)
    if check.failure is not None:
        raise Unvalidated(check.failure)
    tenant = await transaction_context(tx.session)
    snapshot_id = uuid4()
    made = await insert_gl_snapshot(
        tx.session,
        id=snapshot_id,
        tenant_id=tenant.tenant_id,
        client_entity_id=client_entity_id,
        period_start=period_start,
        period_end=period_end,
        source=source,
        raw_fingerprint=raw_fingerprint,
        tb_snapshot_id=tb_snapshot_id,
        line_count=summary.line_count,
        total_debit=summary.total_debit,
        total_credit=summary.total_credit,
    )
    if made is None:
        existing = await find_gl_snapshot(
            tx.session,
            client_entity_id=client_entity_id,
            period_start=period_start,
            period_end=period_end,
            raw_fingerprint=raw_fingerprint,
        )
        if existing is None:
            raise NotFound("gl_snapshot")
        return GlSnapshotRef(existing.id, created=False)
    await insert_gl_rows(
        tx.session,
        GlAccountBalance,
        [_balance_row(tenant.tenant_id, snapshot_id, b) for b in check.balances],
    )
    count, debit, credit = 0, Decimal(0), Decimal(0)
    batch: list[dict[str, object]] = []
    for entry in entries:
        count, debit, credit = count + 1, debit + entry.debit, credit + entry.credit
        batch.append(_entry_row(tenant.tenant_id, snapshot_id, entry))
        if len(batch) >= BATCH:
            await insert_gl_rows(tx.session, GlEntryRow, batch)
            batch = []
    await insert_gl_rows(tx.session, GlEntryRow, batch)
    if (count, debit, credit) != (summary.line_count, summary.total_debit, summary.total_credit):
        raise Unvalidated("entries_differ_from_summary")  # the transaction is rolled back
    tx.record(
        "gl_snapshot.created",
        target=Target("gl_snapshot", snapshot_id),
        after=Ref(
            client_entity_id=client_entity_id,
            raw_fingerprint=raw_fingerprint,
            tb_snapshot_id=tb_snapshot_id,
            lines=count,
        ),
    )
    return GlSnapshotRef(snapshot_id, created=True)


@dataclass(frozen=True)
class GlSnapshotView:
    id: UUID
    client_entity_id: UUID
    period_start: date
    period_end: date
    source: str
    raw_fingerprint: str
    tb_snapshot_id: UUID
    line_count: int
    total_debit: Decimal
    created_at: datetime
    balances: tuple[Balance, ...]


async def gl_snapshot_view(tenant: TenantContext, snapshot_id: UUID) -> GlSnapshotView:
    async with tenant_session(tenant) as session:
        snapshot = await get_gl_snapshot(session, snapshot_id)
        if snapshot is None:
            raise NotFound("gl_snapshot")
        rows = await gl_balances_of(session, snapshot_id)
    return GlSnapshotView(
        snapshot.id,
        snapshot.client_entity_id,
        snapshot.period_start,
        snapshot.period_end,
        snapshot.source,
        snapshot.raw_fingerprint,
        snapshot.tb_snapshot_id,
        snapshot.line_count,
        snapshot.total_debit,
        snapshot.created_at,
        tuple(
            Balance(
                r.account_code,
                r.account_name,
                r.opening,
                r.debit,
                r.credit,
                r.closing,
                r.tb_closing,
                r.opening_derived,
            )
            for r in rows
        ),
    )


async def gl_entries(
    tenant: TenantContext, snapshot_id: UUID, *, after: int = 0, limit: int = BATCH
) -> list[GlEntry]:
    """A page of the snapshot's entries in line order (renderers stream through them)."""
    async with tenant_session(tenant) as session:
        rows = await gl_entries_of(session, snapshot_id, after=after, limit=limit)
    return [
        GlEntry(
            r.line_no,
            r.account_code,
            "",
            r.posted_on,
            r.reference,
            r.kind,
            r.counterparty,
            r.description,
            r.debit,
            r.credit,
            r.source_ref,
        )
        for r in rows
    ]


async def latest_gl_snapshot(
    tenant: TenantContext, client_entity_id: UUID, period_end: date
) -> GlSnapshotView | None:
    """SPEC-037 (TASK-077): the newest reconciled general ledger snapshot for an entity's year,
    for a caller that authorised on the engagement."""
    async with tenant_session(tenant) as session:
        found = await newest_gl_snapshot(session, client_entity_id, period_end)
    return await gl_snapshot_view(tenant, found) if found is not None else None

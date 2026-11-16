"""A close month's ledger as one immutable set (C-01-T17; C-01 §4.5; SPEC-655 F5; ADR-004).

The hourly sync (`connections`' `LedgerSyncWorkflow`) records, inside its unit of work:

- a monthly `ledger_snapshots` row (`period_kind = 'month'`, `period = 'YYYY-MM'`) with the
  month's trial balance lines;
- the chart of accounts as of that snapshot (`ledger_accounts`);
- the month's register as a general-ledger snapshot of kind `month`, tied to the snapshot, its
  rows carrying the offset account, payee, type and Intuit's transaction id.

Change-data-capture tells the sync which datasets changed; a dataset it did not pull again is
carried forward from the month's previous set, copied into the new rows (nothing is updated in
place). Nothing unvalidated is stored: the trial balance passes `normalise.validate` and the
register foots (debits = credits) before any row is written. A set whose content is unchanged is
answered with the existing snapshot (`created=False`), so a repeat records nothing.

Money is `Decimal`; nothing here asks a model for arithmetic (ADR-050). Read only: nothing here
writes to a client system (CONN-001, ADR-040).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import transaction_context
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.ledger.models import GlEntryRow, GlSnapshot, LedgerSnapshot, TrialBalanceLineRow
from abacus.modules.ledger.normalise import LedgerLine, NormalisedTrialBalance, validate
from abacus.modules.ledger.repository import insert_gl_rows, insert_lines
from abacus.modules.ledger.service import Unvalidated

MONTH_SOURCE_MAX: Final = 100
# The natural debit side by classification: a positive asset or expense amount is a debit; a
# positive liability, equity or income amount is a credit (C-01 §7, R1).
_DEBIT_NATURAL: Final = frozenset({"asset", "expense"})
_CLASSIFICATIONS: Final = frozenset({"asset", "liability", "equity", "income", "expense"})


class MonthIncomplete(DomainConflict):
    """The first set of a month needs every dataset: nothing to carry forward from."""

    code = "month_incomplete"


@dataclass(frozen=True)
class MonthAccount:
    """One account of the chart as of the snapshot (Intuit's id is the external id)."""

    external_id: str
    number: str | None
    name: str
    classification: str  # asset | liability | equity | income | expense
    account_type: str
    account_subtype: str | None
    parent_external_id: str | None
    mask: str | None
    is_contra: bool
    active: bool


@dataclass(frozen=True)
class MonthRegisterLine:
    """One register row, signed in its account's natural direction (as Intuit prints it)."""

    source_ref: str
    account_external_id: str
    external_txn_id: str | None
    txn_date: date
    txn_type: str | None
    doc_number: str | None
    payee: str | None
    memo: str | None
    offset_account_ref: str | None
    amount: Decimal


@dataclass(frozen=True)
class MonthSnapshotRef:
    id: UUID
    created: bool  # False when this content's set already existed
    gl_snapshot_id: UUID | None
    period: str


def month_bounds(period: str) -> tuple[date, date]:
    """`2026-08` → (Aug 1, Aug 31)."""
    year, month = int(period[:4]), int(period[5:7])
    start = date(year, month, 1)
    following = date(year + (month == 12), month % 12 + 1, 1)
    return start, date.fromordinal(following.toordinal() - 1)


def _fingerprint(parts: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def content_fingerprint(
    tb: NormalisedTrialBalance, accounts: Sequence[MonthAccount], register: Sequence[MonthRegisterLine]
) -> str:
    """A stable digest of the set's content, so an unchanged pull finds its snapshot again."""
    parts = [f"tb:{x.account_code}|{x.debit}|{x.credit}" for x in tb.lines]
    parts += [
        f"acct:{a.external_id}|{a.number}|{a.name}|{a.classification}|{a.account_type}|"
        f"{a.account_subtype}|{a.parent_external_id}|{a.mask}|{a.is_contra}|{a.active}"
        for a in sorted(accounts, key=lambda a: a.external_id)
    ]
    parts += [
        f"reg:{r.source_ref}|{r.account_external_id}|{r.txn_date}|{r.amount}|{r.offset_account_ref}"
        for r in register
    ]
    return _fingerprint(parts)


def _sides(classification: str, amount: Decimal) -> tuple[Decimal, Decimal]:
    debit_natural = classification in _DEBIT_NATURAL
    if (amount >= 0) == debit_natural:
        return abs(amount), Decimal(0)
    return Decimal(0), abs(amount)


async def latest_month_snapshot(
    session: AsyncSession, client_entity_id: UUID, period: str
) -> LedgerSnapshot | None:
    """The entity's newest set for the month (LIST_EXEMPT: the caller holds the entity)."""
    return (
        await session.execute(
            select(LedgerSnapshot)
            .where(
                LedgerSnapshot.client_entity_id == client_entity_id,
                LedgerSnapshot.period_kind == "month",
                LedgerSnapshot.period == period,
            )
            .order_by(LedgerSnapshot.created_at.desc(), LedgerSnapshot.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


_ACCOUNTS_OF = text(
    "SELECT external_id, number, name, classification, account_type, account_subtype, "
    "parent_external_id, mask, is_contra, active FROM ledger_accounts "
    "WHERE snapshot_id = :s ORDER BY external_id"
)
_INSERT_ACCOUNT = text(
    "INSERT INTO ledger_accounts (tenant_id, client_entity_id, snapshot_id, external_id, number, "
    "name, classification, account_type, account_subtype, parent_external_id, mask, is_contra, "
    "active) VALUES (:tenant_id, :client_entity_id, :snapshot_id, :external_id, :number, :name, "
    ":classification, :account_type, :account_subtype, :parent_external_id, :mask, :is_contra, "
    ":active)"
)


async def accounts_of(session: AsyncSession, snapshot_id: UUID) -> tuple[MonthAccount, ...]:
    rows = (await session.execute(_ACCOUNTS_OF, {"s": snapshot_id})).all()
    return tuple(MonthAccount(*r) for r in rows)  # pyright: ignore[reportArgumentType] -- column order


async def _tb_of(session: AsyncSession, snapshot: LedgerSnapshot) -> NormalisedTrialBalance:
    lines = (
        (
            await session.execute(
                select(TrialBalanceLineRow)
                .where(TrialBalanceLineRow.snapshot_id == snapshot.id)
                .order_by(TrialBalanceLineRow.account_code)
            )
        )
        .scalars()
        .all()
    )
    copied = tuple(
        LedgerLine(x.account_code, x.account_name, x.debit, x.credit, x.source_ref) for x in lines
    )
    return NormalisedTrialBalance(
        snapshot.period_start,
        snapshot.period_end,
        "USD",
        copied,
        snapshot.total_debit,
        snapshot.total_credit,
    )


async def register_of(session: AsyncSession, gl_snapshot_id: UUID) -> tuple[MonthRegisterLine, ...]:
    rows = (
        (
            await session.execute(
                select(GlEntryRow)
                .where(GlEntryRow.snapshot_id == gl_snapshot_id)
                .order_by(GlEntryRow.line_no)
            )
        )
        .scalars()
        .all()
    )
    return tuple(
        MonthRegisterLine(
            source_ref=r.source_ref,
            account_external_id=r.account_code,
            external_txn_id=r.external_txn_id,
            txn_date=r.posted_on,
            txn_type=r.txn_type,
            doc_number=r.reference,
            payee=r.payee,
            memo=r.description,
            offset_account_ref=r.offset_account_ref,
            # The stored sides are re-signed by the account when read back (natural sign).
            amount=r.debit - r.credit,
        )
        for r in rows
    )


async def month_register_snapshot(session: AsyncSession, tb_snapshot_id: UUID) -> GlSnapshot | None:
    return (
        await session.execute(
            select(GlSnapshot).where(
                GlSnapshot.tb_snapshot_id == tb_snapshot_id, GlSnapshot.kind == "month"
            )
        )
    ).scalar_one_or_none()


def _resign(lines: Sequence[MonthRegisterLine], kinds: dict[str, str]) -> tuple[MonthRegisterLine, ...]:
    """Carried-forward rows come back as debit − credit; turn them into natural signs again."""
    out: list[MonthRegisterLine] = []
    for line in lines:
        kind = kinds.get(line.account_external_id, "asset")
        natural = line.amount if kind in _DEBIT_NATURAL else -line.amount
        out.append(
            MonthRegisterLine(
                line.source_ref, line.account_external_id, line.external_txn_id, line.txn_date,
                line.txn_type, line.doc_number, line.payee, line.memo, line.offset_account_ref,
                natural,
            )
        )  # fmt: skip
    return tuple(out)


def _check_register(
    register: Sequence[MonthRegisterLine], kinds: dict[str, str], start: date, end: date
) -> None:
    debit = credit = Decimal(0)
    for line in register:
        kind = kinds.get(line.account_external_id)
        if kind is None:
            raise Unvalidated("register_unknown_account")
        if not start <= line.txn_date <= end:
            raise Unvalidated("register_outside_month")
        d, c = _sides(kind, line.amount)
        debit, credit = debit + d, credit + c
    if debit != credit:
        raise Unvalidated("register_unbalanced")


async def record_month_snapshot(
    tx: UnitOfWork,
    *,
    client_entity_id: UUID,
    period: str,
    tb: NormalisedTrialBalance | None,
    accounts: Sequence[MonthAccount] | None,
    register: Sequence[MonthRegisterLine] | None,
    pulled_at: datetime,
    source: str,
) -> MonthSnapshotRef:
    """Record the month's set inside the caller's unit of work. A dataset passed as None is
    carried forward from the month's newest set (`MonthIncomplete` when there is none)."""
    start, end = month_bounds(period)
    session = tx.session
    previous = await latest_month_snapshot(session, client_entity_id, period)
    if tb is None or accounts is None or register is None:
        if previous is None:
            raise MonthIncomplete(period)
        if tb is None:
            tb = await _tb_of(session, previous)
        if accounts is None:
            accounts = await accounts_of(session, previous.id)
        if register is None:
            prior_gl = await month_register_snapshot(session, previous.id)
            kinds_prior = {a.external_id: a.classification for a in accounts}
            register = (
                ()
                if prior_gl is None
                else _resign(await register_of(session, prior_gl.id), kinds_prior)
            )
    failure = validate(tb, period_start=start, period_end=end)
    if failure is not None:
        raise Unvalidated(failure)
    if any(a.classification not in _CLASSIFICATIONS for a in accounts):
        raise Unvalidated("unknown_classification")
    kinds = {a.external_id: a.classification for a in accounts}
    _check_register(register, kinds, start, end)
    fingerprint = content_fingerprint(tb, accounts, register)
    existing = (
        await session.execute(
            select(LedgerSnapshot).where(
                LedgerSnapshot.client_entity_id == client_entity_id,
                LedgerSnapshot.period_start == start,
                LedgerSnapshot.period_end == end,
                LedgerSnapshot.raw_fingerprint == fingerprint,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        gl = await month_register_snapshot(session, existing.id)
        return MonthSnapshotRef(existing.id, False, None if gl is None else gl.id, period)

    tenant = await transaction_context(session)
    snapshot_id = uuid4()
    session.add(
        LedgerSnapshot(
            id=snapshot_id,
            tenant_id=tenant.tenant_id,
            client_entity_id=client_entity_id,
            period_start=start,
            period_end=end,
            pulled_at=pulled_at,
            source=source[:MONTH_SOURCE_MAX],
            raw_fingerprint=fingerprint,
            line_count=len(tb.lines),
            total_debit=tb.total_debit,
            total_credit=tb.total_credit,
            period_kind="month",
            period=period,
        )
    )
    await session.flush()
    await insert_lines(session, tenant.tenant_id, snapshot_id, tb.lines)
    for account in accounts:
        await session.execute(
            _INSERT_ACCOUNT,
            {
                "tenant_id": tenant.tenant_id,
                "client_entity_id": client_entity_id,
                "snapshot_id": snapshot_id,
                "external_id": account.external_id,
                "number": account.number,
                "name": account.name,
                "classification": account.classification,
                "account_type": account.account_type,
                "account_subtype": account.account_subtype,
                "parent_external_id": account.parent_external_id,
                "mask": account.mask,
                "is_contra": account.is_contra,
                "active": account.active,
            },
        )
    gl_snapshot_id: UUID | None = None
    if register:
        gl_snapshot_id = uuid4()
        rows: list[dict[str, object]] = []
        total = Decimal(0)
        for no, line in enumerate(register, start=1):
            debit, credit = _sides(kinds[line.account_external_id], line.amount)
            total += debit
            rows.append(
                {
                    "tenant_id": tenant.tenant_id,
                    "snapshot_id": gl_snapshot_id,
                    "line_no": no,
                    "account_code": line.account_external_id,
                    "posted_on": line.txn_date,
                    "reference": line.doc_number,
                    "kind": line.txn_type,
                    "counterparty": line.payee,
                    "description": line.memo,
                    "debit": debit,
                    "credit": credit,
                    "source_ref": line.source_ref[:40],
                    "offset_account_ref": line.offset_account_ref,
                    "payee": line.payee,
                    "txn_type": line.txn_type,
                    "external_txn_id": line.external_txn_id,
                }
            )
        session.add(
            GlSnapshot(
                id=gl_snapshot_id,
                tenant_id=tenant.tenant_id,
                client_entity_id=client_entity_id,
                period_start=start,
                period_end=end,
                source=source[:MONTH_SOURCE_MAX],
                raw_fingerprint=fingerprint,
                tb_snapshot_id=snapshot_id,
                kind="month",
                line_count=len(rows),
                total_debit=total,
                total_credit=total,
            )
        )
        await session.flush()
        await insert_gl_rows(session, GlEntryRow, rows)
    tx.record(
        "ledger_snapshot.created",
        target=Target("ledger_snapshot", snapshot_id),
        after=Ref(client_entity_id=client_entity_id, raw_fingerprint=fingerprint),
    )
    return MonthSnapshotRef(snapshot_id, True, gl_snapshot_id, period)

"""C9 v2.1 served: the CAS ledger reads for closes (C-01-T18; C-01 §4.4, §8; SPEC-655 F5, F6, F9;
`docs/contracts/c09-ledger.md` "C9 v2.1"; red).

Every read takes the tenant only: the caller (closes, an agent tool) authorised the person on the
close's engagement first and holds the entity. Each read picks the entity's newest monthly set
for the period (`period_kind = 'month'`, C-01-T17), so a newer sync is always what is shown.

- **Balances** are in the account's natural sign: debit - credit for assets and expenses, credit -
  debit for liabilities, equity and income. `activity` is the month's movement: the balance less
  the prior month's (when the prior month's set exists and is in the same year; otherwise the
  balance itself, as a year-to-date income statement account opens the year at zero).
- **The tree foots in code** (`foots`): Asset = Liability + Equity + (Income - Expense), the
  undistributed result standing in for the unclosed year (AC-35). Never asked of a model.
- **Register** pages are at most 200 rows (`REGISTER_PAGE`), in line order; the cursor is the
  last line number. Each row's `line_ref` is `<monthly snapshot>:<line>`: a `ledger_line`
  citation `{ledger_snapshot_id, account_code, register_line}` verifies against that snapshot.
- **Month tie** (`month_tie`): per account, the register's net movement against the trial balance
  movement for the month; the close engine reads which accounts do not tie.

Money is `Decimal`; client content (names, payees, memos) is untrusted and only ever rendered as
text. Read only: there is no write method in C9 (CONN-001, ADR-040).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.ledger.cas_contract import (
    AccountTreeOut,
    Classification,
    LedgerAccountOut,
    MonthlyBalanceOut,
    PeriodComparisonLineOut,
    PeriodComparisonOut,
    PeriodNotAvailable,
    RegisterLineOut,
)
from abacus.modules.ledger.models import GlEntryRow, LedgerSnapshot, TrialBalanceLineRow
from abacus.modules.ledger.month_ledger import (
    MonthAccount,
    accounts_of,
    latest_month_snapshot,
    month_register_snapshot,
)

REGISTER_PAGE: Final = 200
ZERO: Final = Decimal("0.00")
_DEBIT_NATURAL: Final = frozenset({"asset", "expense"})
_ORDER: Final[tuple[Classification, ...]] = ("asset", "liability", "equity", "income", "expense")


def natural(classification: str, debit: Decimal, credit: Decimal) -> Decimal:
    net = debit - credit
    return net if classification in _DEBIT_NATURAL else -net


def prior_period(period: str) -> str:
    year, month = int(period[:4]), int(period[5:7])
    return f"{year - 1}-12" if month == 1 else f"{year}-{month - 1:02d}"


def foots(totals: dict[Classification, Decimal]) -> bool:
    """Asset = Liability + Equity + (Income - Expense) (AC-35)."""
    left = totals.get("asset", ZERO)
    right = (
        totals.get("liability", ZERO)
        + totals.get("equity", ZERO)
        + totals.get("income", ZERO)
        - totals.get("expense", ZERO)
    )
    return left == right


@dataclass(frozen=True)
class _Month:
    snapshot: LedgerSnapshot
    accounts: tuple[MonthAccount, ...]
    balances: dict[str, Decimal]  # external id → natural balance


async def _month(session: AsyncSession, entity: UUID, period: str) -> _Month | None:
    snapshot = await latest_month_snapshot(session, entity, period)
    if snapshot is None:
        return None
    accounts = await accounts_of(session, snapshot.id)
    kinds = {a.external_id: a.classification for a in accounts}
    lines = (
        (
            await session.execute(
                select(TrialBalanceLineRow).where(TrialBalanceLineRow.snapshot_id == snapshot.id)
            )
        )
        .scalars()
        .all()
    )
    balances = {
        line.account_code: natural(kinds.get(line.account_code, "asset"), line.debit, line.credit)
        for line in lines
    }
    return _Month(snapshot, accounts, balances)


def _activity(period: str, balance: Decimal, prior: _Month | None, external_id: str) -> Decimal:
    if prior is None or prior.snapshot.period is None or prior.snapshot.period[:4] != period[:4]:
        return balance
    return balance - prior.balances.get(external_id, ZERO)


def _account_out(a: MonthAccount) -> LedgerAccountOut:
    return LedgerAccountOut(
        external_id=a.external_id,
        number=a.number,
        name=a.name,
        classification=a.classification,  # pyright: ignore[reportArgumentType] -- CHECKed in the table
        account_type=a.account_type,
        account_subtype=a.account_subtype,
        parent_external_id=a.parent_external_id,
        mask=a.mask,
        is_contra=a.is_contra,
        active=a.active,
    )


async def account_tree(
    tenant: TenantContext, client_entity_id: UUID, period: str
) -> AccountTreeOut:
    """The month's tree with balances (`PeriodNotAvailable` when the month was never synced)."""
    async with tenant_session(tenant) as session:
        month = await _month(session, client_entity_id, period)
        if month is None:
            raise PeriodNotAvailable(facts={"period": period})
        prior = await _month(session, client_entity_id, prior_period(period))
    totals: dict[Classification, Decimal] = {k: ZERO for k in _ORDER}
    balances: list[MonthlyBalanceOut] = []
    for account in month.accounts:
        balance = month.balances.get(account.external_id, ZERO)
        kind = account.classification
        if kind in totals:
            totals[kind] += balance  # pyright: ignore[reportArgumentType] -- narrowed by the check
        balances.append(
            MonthlyBalanceOut(
                external_id=account.external_id,
                period=period,
                balance=balance,
                activity=_activity(period, balance, prior, account.external_id),
            )
        )
    return AccountTreeOut(
        client_entity_id=client_entity_id,
        snapshot_id=month.snapshot.id,
        period=period,
        accounts=[_account_out(a) for a in month.accounts],
        balances=balances,
        totals=totals,
    )


async def monthly_balances(
    tenant: TenantContext, client_entity_id: UUID, periods: Sequence[str]
) -> list[MonthlyBalanceOut]:
    """Balances by account for each synced period, in the order asked (absent months skipped)."""
    out: list[MonthlyBalanceOut] = []
    async with tenant_session(tenant) as session:
        cache: dict[str, _Month | None] = {}
        for period in periods:
            for wanted in (period, prior_period(period)):
                if wanted not in cache:
                    cache[wanted] = await _month(session, client_entity_id, wanted)
            month = cache[period]
            if month is None:
                continue
            for account in month.accounts:
                balance = month.balances.get(account.external_id, ZERO)
                out.append(
                    MonthlyBalanceOut(
                        external_id=account.external_id,
                        period=period,
                        balance=balance,
                        activity=_activity(
                            period, balance, cache[prior_period(period)], account.external_id
                        ),
                    )
                )
    return out


def _cursor(value: str | None) -> int:
    if value is None:
        return 0
    if not value.isdigit() or len(value) > 9:
        raise PeriodNotAvailable(facts={"cursor": "invalid"})
    return int(value)


async def register_lines(
    tenant: TenantContext,
    client_entity_id: UUID,
    external_id: str,
    period: str,
    *,
    cursor: str | None = None,
    limit: int = REGISTER_PAGE,
) -> tuple[list[RegisterLineOut], str | None]:
    """One account's register for the month, at most 200 rows a page; the next cursor or None."""
    size = max(1, min(limit, REGISTER_PAGE))
    after = _cursor(cursor)
    async with tenant_session(tenant) as session:
        month = await _month(session, client_entity_id, period)
        if month is None:
            raise PeriodNotAvailable(facts={"period": period})
        gl = await month_register_snapshot(session, month.snapshot.id)
        if gl is None:
            return [], None
        kinds = {a.external_id: a.classification for a in month.accounts}
        rows = (
            (
                await session.execute(
                    select(GlEntryRow)
                    .where(
                        GlEntryRow.snapshot_id == gl.id,
                        GlEntryRow.account_code == external_id,
                        GlEntryRow.line_no > after,
                    )
                    .order_by(GlEntryRow.line_no)
                    .limit(size + 1)
                )
            )
            .scalars()
            .all()
        )
    page = rows[:size]
    out = [
        RegisterLineOut(
            line_ref=f"{month.snapshot.id}:{r.line_no}",
            external_txn_id=r.external_txn_id,
            txn_date=r.posted_on,
            txn_type=r.txn_type,
            offset_account_ref=r.offset_account_ref,
            payee=r.payee,
            memo=r.description,
            amount=natural(kinds.get(r.account_code, "asset"), r.debit, r.credit),
        )
        for r in page
    ]
    following = str(page[-1].line_no) if len(rows) > size else None
    return out, following


async def compare_periods(
    tenant: TenantContext, client_entity_id: UUID, current: str, prior: str
) -> PeriodComparisonOut:
    """Two months side by side by account (prior None when that month was never synced)."""
    async with tenant_session(tenant) as session:
        now = await _month(session, client_entity_id, current)
        if now is None:
            raise PeriodNotAvailable(facts={"period": current})
        before = await _month(session, client_entity_id, prior)
    lines = [
        PeriodComparisonLineOut(
            external_id=a.external_id,
            prior=None if before is None else before.balances.get(a.external_id, ZERO),
            current=now.balances.get(a.external_id, ZERO),
        )
        for a in now.accounts
    ]
    return PeriodComparisonOut(current_period=current, prior_period=prior, lines=lines)


@dataclass(frozen=True)
class AccountTie:
    external_id: str
    tb_movement: Decimal
    register_movement: Decimal

    @property
    def ties(self) -> bool:
        return self.tb_movement == self.register_movement


async def month_tie(
    tenant: TenantContext, client_entity_id: UUID, period: str
) -> list[AccountTie]:
    """The month-scoped GL check (C-01-T18): per account, the trial balance's movement for the
    month against the register's net, in natural signs. An account without register rows moves
    by zero in the register."""
    async with tenant_session(tenant) as session:
        month = await _month(session, client_entity_id, period)
        if month is None:
            raise PeriodNotAvailable(facts={"period": period})
        prior = await _month(session, client_entity_id, prior_period(period))
        gl = await month_register_snapshot(session, month.snapshot.id)
        moved: dict[str, Decimal] = defaultdict(lambda: ZERO)
        if gl is not None:
            kinds = {a.external_id: a.classification for a in month.accounts}
            for r in (
                await session.execute(select(GlEntryRow).where(GlEntryRow.snapshot_id == gl.id))
            ).scalars():
                moved[r.account_code] += natural(
                    kinds.get(r.account_code, "asset"), r.debit, r.credit
                )
    return [
        AccountTie(
            a.external_id,
            _activity(period, month.balances.get(a.external_id, ZERO), prior, a.external_id),
            moved[a.external_id],
        )
        for a in month.accounts
    ]


# --- The register row a `ledger_line` citation names (A-02-T22's citable, C-01-T18) -----------


@dataclass(frozen=True)
class CitedRegisterRow:
    snapshot_id: UUID  # the monthly ledger snapshot the citation names
    client_entity_id: UUID
    line_no: int
    account_code: str
    debit: Decimal
    credit: Decimal
    payee: str | None
    memo: str | None


async def register_row(
    session: AsyncSession, snapshot_id: UUID, line_no: int
) -> tuple[UUID, CitedRegisterRow | None] | None:
    """The monthly snapshot's entity and the named register row (None when it has no such row),
    in the caller's session. None when the snapshot is not visible or not monthly. The caller
    authorised on an engagement first and compares the entity to that engagement's."""
    snapshot = (
        await session.execute(select(LedgerSnapshot).where(LedgerSnapshot.id == snapshot_id))
    ).scalar_one_or_none()
    if snapshot is None or snapshot.period_kind != "month":
        return None
    gl = await month_register_snapshot(session, snapshot_id)
    if gl is None:
        return snapshot.client_entity_id, None
    row = (
        await session.execute(
            select(GlEntryRow).where(
                GlEntryRow.snapshot_id == gl.id, GlEntryRow.line_no == line_no
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return snapshot.client_entity_id, None
    return snapshot.client_entity_id, CitedRegisterRow(
        snapshot_id, snapshot.client_entity_id, row.line_no, row.account_code, row.debit,
        row.credit, row.payee, row.description,
    )  # fmt: skip

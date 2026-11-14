"""C9 v2.1, the additive CAS ledger stub (C-01-T07; C-01 §4.4, §8; SPEC-655 F5, F6, F9;
`docs/contracts/c09-ledger.md` "C9 v2.1"). Provider: ledger (red). Consumers: closes (CLS-04,
CLS-05, CLS-10).

Monthly datasets for closes, read only: the account tree (classification, type, subtype, mask,
contra, active), monthly balances by period, register lines (offset account, payee, memo,
external id; each citable as a `ledger_line`) and a period comparison. Snapshots stay immutable
(ADR-004): a sync records a new one, never an update. Readers of C9 v1 and v2 are unaffected.
There is no write method anywhere in C9 (CONN-001, ADR-040).

Every function raises `NotImplementedYet` until C-01-T18 (S46) serves it. Classification
(ADR-031): client ledger content is `confidential`; nothing is TRI. Money is `Decimal`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, NotImplementedYet

Internal = classified("internal")
Confidential = classified("confidential")
Money = Annotated[Decimal, Field(max_digits=18, decimal_places=2), Confidential]
MaybeMoney = Annotated[Decimal | None, Field(max_digits=18, decimal_places=2), Confidential]
Period = Annotated[str, Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"), Internal]
Classification = Literal["asset", "liability", "equity", "income", "expense"]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class StaleSource(DomainConflict):
    """The snapshot asked for was superseded by a newer sync; read the newest
    (`facts.snapshot`)."""

    code = "stale_source"


class PeriodNotAvailable(DomainConflict):
    """No monthly snapshot for the period (August 2025 is not in the seed: CLS-10 d)."""

    code = "period_not_available"


class LedgerAccountOut(BaseModel):
    """One QuickBooks account as of a snapshot (`ledger_accounts`, C-01-T10)."""

    model_config = _cfg()

    external_id: Annotated[str, Field(min_length=1, max_length=64), Internal]
    number: Annotated[str | None, Confidential] = None
    name: Annotated[str, Confidential]
    classification: Annotated[Classification, Internal]
    account_type: Annotated[str, Confidential]  # "Bank", "Other Current Asset"
    account_subtype: Annotated[str | None, Confidential] = None
    parent_external_id: Annotated[str | None, Internal] = None
    mask: Annotated[str | None, Field(pattern=r"^••[0-9]{4}$"), Internal] = None
    is_contra: Annotated[bool, Internal] = False
    active: Annotated[bool, Internal] = True


class MonthlyBalanceOut(BaseModel):
    model_config = _cfg()

    external_id: Annotated[str, Internal]
    period: Period
    balance: Money  # natural sign; contra accounts render in parentheses (CLS-04)
    activity: Money


class AccountTreeOut(BaseModel):
    """The month's tree with balances; footed in code (Asset = Liability + Equity, AC-35)."""

    model_config = _cfg()

    client_entity_id: Annotated[UUID, Internal]
    snapshot_id: Annotated[UUID, Internal]
    period: Period
    accounts: list[LedgerAccountOut]
    balances: list[MonthlyBalanceOut]
    totals: Annotated[dict[Classification, Decimal], Confidential]


class RegisterLineOut(BaseModel):
    """A register row, citable as a `ledger_line` (A-02-T22's citable)."""

    model_config = _cfg()

    line_ref: Annotated[str, Field(min_length=1, max_length=120), Internal]
    external_txn_id: Annotated[str | None, Internal] = None
    txn_date: Annotated[date, Internal]
    txn_type: Annotated[str | None, Confidential] = None
    offset_account_ref: Annotated[str | None, Internal] = None
    payee: Annotated[str | None, Confidential] = None
    memo: Annotated[str | None, Confidential] = None
    amount: Money


class PeriodComparisonLineOut(BaseModel):
    model_config = _cfg()

    external_id: Annotated[str, Internal]
    prior: MaybeMoney = None  # None when the prior period is not available
    current: Money


class PeriodComparisonOut(BaseModel):
    model_config = _cfg()

    current_period: Period
    prior_period: Period
    lines: list[PeriodComparisonLineOut]


async def account_tree(
    tenant: TenantContext, client_entity_id: UUID, period: str
) -> AccountTreeOut:
    """The newest monthly snapshot's tree (C-01-T18)."""
    raise NotImplementedYet


async def monthly_balances(
    tenant: TenantContext, client_entity_id: UUID, periods: list[str]
) -> list[MonthlyBalanceOut]:
    """Balances by account for each period (C-01-T18)."""
    raise NotImplementedYet


async def register_lines(
    tenant: TenantContext,
    client_entity_id: UUID,
    external_id: str,
    period: str,
    *,
    cursor: str | None = None,
) -> tuple[list[RegisterLineOut], str | None]:
    """One account's register for the month, paged (C-01-T18)."""
    raise NotImplementedYet


async def compare_periods(
    tenant: TenantContext, client_entity_id: UUID, current: str, prior: str
) -> PeriodComparisonOut:
    """Two periods side by side for flux (C-01-T18; `ledger.compare_periods` on C17)."""
    raise NotImplementedYet

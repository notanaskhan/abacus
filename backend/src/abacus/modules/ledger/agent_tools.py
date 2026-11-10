"""Ledger read and compute tools for the Accrued Agent (P-10-T28; C17; ADR-233, ADR-049, ADR-050).

Declared as `ToolDecl` records (`kernel.agent_tools`) and registered by `agents` (ledger imports
nothing; the slot is in the kernel). Ledger rows belong to a client entity: the model names the
`client_entity_id`, which the runtime checks against the run's pinned `client_scope` and
authorises (`trial_balance.read`) before a handler runs. Every total, variance and tie-out is
computed here in `Decimal`, never by the model (ADR-050). Account names come from the client's
system: untrusted.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from abacus.kernel.agent_tools import MAX_ROWS, ToolCaller, ToolDecl
from abacus.kernel.classification import classified
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.ledger.models import LedgerSnapshot, TrialBalanceLineRow

Int = classified("internal")
Conf = classified("confidential")
READ: Final = "trial_balance.read"
ZERO: Final = Decimal("0.00")


class TbIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    client_entity_id: Annotated[UUID, Int]
    period_end: Annotated[date | None, Int] = None  # the latest snapshot when none
    account_code_prefix: Annotated[str | None, Field(max_length=20), Int] = None


class CompareIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    client_entity_id: Annotated[UUID, Int]
    current_period_end: Annotated[date, Int]
    prior_period_end: Annotated[date, Int]
    account_code_prefix: Annotated[str | None, Field(max_length=20), Int] = None


class TieOutIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    client_entity_id: Annotated[UUID, Int]
    period_end: Annotated[date | None, Int] = None
    account_codes: Annotated[
        list[Annotated[str, Field(max_length=40)]], Field(min_length=1, max_length=MAX_ROWS), Int
    ]
    expected: Annotated[Decimal, Int]  # the figure to tie, e.g. a workpaper total


class TbRow(BaseModel):
    id: Annotated[UUID, Int]
    account_code: Annotated[str, Int]
    account_name: Annotated[str, Conf]
    debit: Annotated[Decimal, Conf]
    credit: Annotated[Decimal, Conf]
    balance: Annotated[Decimal, Conf]  # debit - credit


class TbOut(BaseModel):
    snapshot_id: Annotated[UUID, Int]
    period_end: Annotated[date, Int]
    lines: Annotated[list[TbRow], Field(max_length=MAX_ROWS), Int]
    total_lines: Annotated[int, Field(ge=0), Int]
    total_debit: Annotated[Decimal, Conf]
    total_credit: Annotated[Decimal, Conf]
    in_balance: Annotated[bool, Int]
    truncated: Annotated[bool, Int]  # more lines than the page: narrow by prefix


class CompareRow(BaseModel):
    id: Annotated[UUID, Int]  # the current line (or the prior one when gone this year)
    account_code: Annotated[str, Int]
    account_name: Annotated[str, Conf]
    current: Annotated[Decimal, Conf]
    prior: Annotated[Decimal, Conf]
    change: Annotated[Decimal, Conf]
    change_pct: Annotated[Decimal | None, Conf] = None  # None when the prior is zero


class CompareOut(BaseModel):
    current_snapshot_id: Annotated[UUID, Int]
    prior_snapshot_id: Annotated[UUID, Int]
    accounts: Annotated[list[CompareRow], Field(max_length=MAX_ROWS), Int]
    total_accounts: Annotated[int, Field(ge=0), Int]
    truncated: Annotated[bool, Int]


class TieOutOut(BaseModel):
    snapshot_id: Annotated[UUID, Int]
    accounts_found: Annotated[list[str], Int]
    accounts_missing: Annotated[list[str], Int]
    tb_total: Annotated[Decimal, Conf]
    expected: Annotated[Decimal, Conf]
    difference: Annotated[Decimal, Conf]
    ties: Annotated[bool, Int]


async def _snapshot(caller: ToolCaller, entity: UUID, period_end: date | None) -> LedgerSnapshot:
    query = select(LedgerSnapshot).where(LedgerSnapshot.client_entity_id == entity)
    if period_end is not None:
        query = query.where(LedgerSnapshot.period_end == period_end)
    async with tenant_session(caller.tenant) as session:
        found = (
            await session.execute(
                query.order_by(
                    LedgerSnapshot.period_end.desc(), LedgerSnapshot.pulled_at.desc()
                ).limit(1)
            )
        ).scalar_one_or_none()
    if found is None:
        raise NotFound("ledger_snapshot")
    return found


async def _lines(
    caller: ToolCaller, snapshot_id: UUID, prefix: str | None
) -> list[TrialBalanceLineRow]:
    query = select(TrialBalanceLineRow).where(TrialBalanceLineRow.snapshot_id == snapshot_id)
    if prefix:
        query = query.where(TrialBalanceLineRow.account_code.startswith(prefix, autoescape=True))
    async with tenant_session(caller.tenant) as session:
        rows = (await session.execute(query.order_by(TrialBalanceLineRow.account_code))).scalars()
        return list(rows)


async def read_tb(caller: ToolCaller, args: TbIn) -> TbOut:
    snapshot = await _snapshot(caller, args.client_entity_id, args.period_end)
    lines = await _lines(caller, snapshot.id, args.account_code_prefix)
    debit = sum((line.debit for line in lines), ZERO)
    credit = sum((line.credit for line in lines), ZERO)
    return TbOut(
        snapshot_id=snapshot.id,
        period_end=snapshot.period_end,
        lines=[
            TbRow(
                id=line.id,
                account_code=line.account_code,
                account_name=line.account_name,
                debit=line.debit,
                credit=line.credit,
                balance=line.debit - line.credit,
            )
            for line in lines[:MAX_ROWS]
        ],
        total_lines=len(lines),
        total_debit=debit,
        total_credit=credit,
        in_balance=debit == credit,
        truncated=len(lines) > MAX_ROWS,
    )


def change_pct(current: Decimal, prior: Decimal) -> Decimal | None:
    if prior == 0:
        return None
    return ((current - prior) / abs(prior) * 100).quantize(Decimal("0.1"))


async def compare_periods(caller: ToolCaller, args: CompareIn) -> CompareOut:
    current = await _snapshot(caller, args.client_entity_id, args.current_period_end)
    prior = await _snapshot(caller, args.client_entity_id, args.prior_period_end)
    now = {
        line.account_code: line
        for line in await _lines(caller, current.id, args.account_code_prefix)
    }
    then = {
        line.account_code: line
        for line in await _lines(caller, prior.id, args.account_code_prefix)
    }
    rows: list[CompareRow] = []
    for code in sorted(set(now) | set(then)):
        a, b = now.get(code), then.get(code)
        cur = a.debit - a.credit if a else ZERO
        pri = b.debit - b.credit if b else ZERO
        line = a or b
        if line is None:
            continue
        rows.append(
            CompareRow(
                id=line.id,
                account_code=code,
                account_name=line.account_name,
                current=cur,
                prior=pri,
                change=cur - pri,
                change_pct=change_pct(cur, pri),
            )
        )
    return CompareOut(
        current_snapshot_id=current.id,
        prior_snapshot_id=prior.id,
        accounts=rows[:MAX_ROWS],
        total_accounts=len(rows),
        truncated=len(rows) > MAX_ROWS,
    )


async def tie_out(caller: ToolCaller, args: TieOutIn) -> TieOutOut:
    """Whether the named accounts' balances sum to the expected figure, to the cent."""
    snapshot = await _snapshot(caller, args.client_entity_id, args.period_end)
    lines = {line.account_code: line for line in await _lines(caller, snapshot.id, None)}
    wanted = list(dict.fromkeys(args.account_codes))
    found = [c for c in wanted if c in lines]
    total = sum((lines[c].debit - lines[c].credit for c in found), ZERO)
    expected = args.expected.quantize(Decimal("0.01"))
    return TieOutOut(
        snapshot_id=snapshot.id,
        accounts_found=found,
        accounts_missing=[c for c in wanted if c not in lines],
        tb_total=total,
        expected=expected,
        difference=total - expected,
        ties=total == expected and len(found) == len(wanted),
    )


AGENT_TOOLS: Final = (
    ToolDecl(
        "ledger.read_tb", "read", READ, "confidential", TbIn, TbOut, read_tb,
        untrusted=("lines",), records_read="trial_balance_line",
    ),
    ToolDecl(
        "ledger.compare_periods", "compute", READ, "confidential", CompareIn, CompareOut,
        compare_periods, untrusted=("accounts",), records_read="trial_balance_line",
    ),
    ToolDecl(
        "ledger.tie_out", "compute", READ, "confidential", TieOutIn, TieOutOut, tie_out,
        records_read="trial_balance_line",
    ),
)  # fmt: skip

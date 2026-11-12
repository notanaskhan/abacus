"""The entity return's TB and TTB read model for TXP-02 (T-05-T33; T-05 F3; ADR-050; DEC-4618).
Amber; reads only: C8's tax layers (`adjustments.adjusted_tb`, layer `ttb`: UTB, AJE, RJE, ATB,
TJE, TTB per account, computed and never stored), the trial balance's tax form-line mapping set
(T-05-T26) and C8's entries. Every figure is a `Decimal` from those reads; no total is typed.

- **Views.** `account`: one row per account with its form line; `line`: one row per form line,
  its accounts' columns summed. `statement` narrows to the balance sheet (Schedule L lines, `L…`)
  or the income statement (every other mapped line); `full` is every row. `filter=unmapped` keeps
  accounts with no form line.
- **Tallies.** Each column foots to $0 (UTB, ATB, TTB: `tie` or `off` with the difference), and
  `unmapped` reads `check` while any account lacks a line: the export gate (TXP-02's sync chip
  shows export disabled while it is above 0).
- **Journal entries.** C8's AJEs, RJEs and TJEs on the return, with their state; proposing and
  approving go through A-06's own endpoints (`propose_entry`, `record_entry_decision`), never here.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from abacus.modules.adjustments.api import TaxLayersView, adjusted_tb, entries_of
from abacus.modules.identity.api import AuthContext
from abacus.modules.ledger.api import engagement_trial_balances, form_line_rows, tax_mapping_set

ZERO: Final = Decimal("0")
View = Literal["account", "line"]
Statement = Literal["full", "balance_sheet", "income_statement"]


@dataclass(frozen=True)
class TbRow:
    account_code: str
    account_name: str
    form_line_key: str | None
    unadjusted: Decimal
    aje: Decimal
    rje: Decimal
    tje: Decimal
    tax_basis: Decimal
    adjusted: Decimal | None = None  # ATB (C8's, never summed here); line rows sum it
    group: str = "unmapped"


Group = Literal["assets", "liabilities", "equity", "income", "deductions", "unmapped"]
GROUPS: Final[tuple[tuple[Group, str], ...]] = (
    ("assets", "Total assets"),
    ("liabilities", "Total liabilities"),
    ("equity", "Total equity"),
    ("income", "Total income"),
    ("deductions", "Total deductions"),
    ("unmapped", "Total unmapped"),
)
_SCHEDULE_L: Final = re.compile(r"^L(\d{1,2})[a-z]?$")
_INCOME: Final = ("8825 Rents", "K ", "M-3")


def group_of(form_line_key: str | None) -> Group:
    """TXP-02's sections from the form line (T-05-T37): Schedule L lines 1 to 14 are assets, 15
    to 20 liabilities, 21 and M-2 equity; Form 8825 rents, Schedule K and M-3 lines are income;
    every other mapped line (Form 8825's expense lines) is a deduction."""
    if form_line_key is None:
        return "unmapped"
    found = _SCHEDULE_L.match(form_line_key)
    if found is not None:
        n = int(found.group(1))
        return "assets" if n <= 14 else ("liabilities" if n <= 20 else "equity")
    if form_line_key.startswith("M-2"):
        return "equity"
    if form_line_key.startswith(_INCOME):
        return "income"
    return "deductions"


@dataclass(frozen=True)
class TbTotal:
    key: str
    label: str
    unadjusted: Decimal
    aje: Decimal
    rje: Decimal
    adjusted: Decimal
    tje: Decimal
    tax_basis: Decimal


def _total(key: str, label: str, rows: Sequence[TbRow]) -> TbTotal:
    def col(name: str) -> Decimal:
        return sum((getattr(r, name) or ZERO for r in rows), ZERO)

    return TbTotal(
        key, label, col("unadjusted"), col("aje"), col("rje"), col("adjusted"), col("tje"),
        col("tax_basis"),
    )  # fmt: skip


def totals(rows: Sequence[TbRow]) -> list[TbTotal]:
    """Each section's totals, then the TB total (debits less credits), all computed here."""
    out = [
        _total(key, label, [r for r in rows if r.group == key])
        for key, label in GROUPS
        if any(r.group == key for r in rows)
    ]
    out.append(_total("tb_total", "TB total (debits less credits)", rows))
    return out


@dataclass(frozen=True)
class TbFigure:
    key: str
    label: str
    amount: Decimal


def figures(rows: Sequence[TbRow]) -> list[TbFigure]:
    """TXP-02's figure cards, from the tax basis: gross rents (Form 8825 rents, shown positive),
    total deductions, net rental real estate income (rents less deductions), book total assets."""
    rents = -sum((r.tax_basis for r in rows if (r.form_line_key or "") == "8825 Rents"), ZERO)
    deductions = sum((r.tax_basis for r in rows if r.group == "deductions"), ZERO)
    assets = sum((r.tax_basis for r in rows if r.group == "assets"), ZERO)
    return [
        TbFigure("gross_rents", "Gross rents", rents),
        TbFigure("total_deductions", "Total deductions", deductions),
        TbFigure("net_rental_income", "Net rental RE income", rents - deductions),
        TbFigure("book_total_assets", "Book total assets", assets),
    ]


@dataclass(frozen=True)
class TbTally:
    key: str
    label: str
    state: Literal["tie", "off", "check"]
    difference: Decimal | None = None


def _d(value: Decimal | None) -> Decimal:
    return ZERO if value is None else value


async def _mapping(ctx: AuthContext, engagement_id: UUID) -> dict[str, str | None]:
    tbs = await engagement_trial_balances(ctx.tenant, engagement_id)
    if not tbs:
        return {}
    newest = max(tbs, key=lambda t: (t.period_end, t.current_version_no))
    set_id = await tax_mapping_set(ctx.tenant, newest.id)
    return {} if set_id is None else await form_line_rows(ctx.tenant, set_id)


def account_rows(layers: TaxLayersView, mapping: dict[str, str | None]) -> list[TbRow]:
    return [
        TbRow(
            account_code=ln.account_code,
            account_name=ln.account_name,
            form_line_key=mapping.get(ln.account_code),
            unadjusted=_d(ln.eoy),
            aje=_d(ln.aje),
            rje=_d(ln.rje),
            tje=_d(ln.tje),
            tax_basis=ln.ttb,
            adjusted=ln.atb,
            group=group_of(mapping.get(ln.account_code)),
        )
        for ln in layers.lines
    ]


def by_line(rows: Sequence[TbRow]) -> list[TbRow]:
    """One row per mapped form line, its accounts' columns summed (unmapped accounts left out)."""
    sums: dict[str, list[Decimal]] = {}
    for r in rows:
        if r.form_line_key is None:
            continue
        acc = sums.setdefault(r.form_line_key, [ZERO] * 6)
        for i, v in enumerate((r.unadjusted, r.aje, r.rje, r.tje, r.tax_basis, r.adjusted)):
            acc[i] += v or ZERO
    return [
        TbRow(key, key, key, *vals[:5], adjusted=vals[5], group=group_of(key))
        for key, vals in sorted(sums.items())
    ]


def narrowed(rows: Sequence[TbRow], statement: Statement, unmapped_only: bool) -> list[TbRow]:
    out = list(rows)
    if unmapped_only:
        out = [r for r in out if r.form_line_key is None]
    if statement == "balance_sheet":
        out = [r for r in out if (r.form_line_key or "").startswith("L")]
    elif statement == "income_statement":
        out = [r for r in out if r.form_line_key and not r.form_line_key.startswith("L")]
    return out


def tallies(rows: Sequence[TbRow]) -> list[TbTally]:
    out: list[TbTally] = []
    for key, label, values in (
        ("utb_foot", "Unadjusted foots", [r.unadjusted for r in rows]),
        ("atb_foot", "Adjusted foots", [r.unadjusted + r.aje + r.rje for r in rows]),
        ("ttb_foot", "Tax basis foots", [r.tax_basis for r in rows]),
    ):
        total = sum(values, ZERO)
        out.append(TbTally(key, label, "tie" if total == ZERO else "off", total))
    unmapped = sum(1 for r in rows if r.form_line_key is None)
    out.append(
        TbTally("unmapped", "Unmapped accounts", "check" if unmapped else "tie", Decimal(unmapped))
    )
    return out


async def trial_balance(
    ctx: AuthContext,
    return_id: UUID,
    engagement_id: UUID,
    view: View,
    statement: Statement,
    unmapped_only: bool,
) -> tuple[list[TbRow], int]:
    """The rows TXP-02 shows and the unmapped count over the whole TB (the export gate)."""
    layers = await adjusted_tb(ctx, return_id, "ttb")
    rows = account_rows(layers, await _mapping(ctx, engagement_id))  # type: ignore[arg-type] -- a test double or the review api's own context alias
    unmapped = sum(1 for r in rows if r.form_line_key is None)
    shown = by_line(rows) if view == "line" else rows
    return narrowed(shown, statement, unmapped_only and view == "account"), unmapped


async def tb_tallies(
    ctx: AuthContext, return_id: UUID, engagement_id: UUID
) -> tuple[list[TbTally], list[TbFigure]]:
    layers = await adjusted_tb(ctx, return_id, "ttb")
    rows = account_rows(layers, await _mapping(ctx, engagement_id))  # type: ignore[arg-type] -- a test double or the review api's own context alias
    return tallies(rows), figures(rows)


async def journal_entries(
    ctx: AuthContext, return_id: UUID
) -> list[tuple[UUID, str, str, Decimal, str]]:
    """C8's entries on the return: `(id, kind, ref, amount, status)`."""
    return [(e.id, e.kind, e.ref, e.amount, e.status) for e in await entries_of(ctx, return_id)]


__all__ = [
    "GROUPS",
    "TbFigure",
    "TbRow",
    "TbTally",
    "TbTotal",
    "by_line",
    "figures",
    "group_of",
    "journal_entries",
    "narrowed",
    "tallies",
    "tb_tallies",
    "totals",
    "trial_balance",
]

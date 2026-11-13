"""The entity return's schedule read models for TXP-05 and TXP-07 (T-05-T34; T-05 F6, F7; ADR-050;
DEC-4619). Amber; reads only the return's workbook cells (`review.current_values` on
`tax_workbook`), the sheets the run steps write (T-05-T32), and K-1 recipients for partner ids.
Every total is computed here so the screens render server totals only (E4 tables, decimal strings).

Sheet layout (T-05-T32):

- `05 Capital`: one row per partner from row 2 while column A names one: B beginning,
  C contributions, D distributions, E income share, F ending.
- `06 Schedule K`: one row per line from row 2: A the line ("1", "2", "13d"), B its label, C the
  federal amount, D the state amount once apportionment runs (T-05-T40).
- `07 M-2`: column B by M-2 line number (B1 beginning … B9 ending).
- `08 State`: per-property rows of Form 8825 (A property, B line, C amount), the breakdown source.
- `09 K-1s`: one column per recipient from B (row 1 the name), rows matching 06.

- **Schedule K.** Per line the total and each partner's share; `tie` when the partners' shares sum
  to the total, else `off` (a rounding or allocation gap the reviewer sees). The state view reads
  06's column D; with no state amounts yet it answers no lines.
- **Capital accounts.** `by_partner` and `by_movement` read the same rows (the screen pivots);
  `tie` when each partner's ending equals beginning + contributions - distributions + income.
- **M-2.** `as_drafted` reads 07 as it is; `with_fix` is the M-2 rebuilt from 05's partner totals
  (lines 2, 3, 6, 9), which is what an approved fix writes (T-05-T50). The M-2 foots when
  1 + 2 + 3 + 4 - 6 - 7 - 8 = 9.
- **Item L.** The K-1s' Item L ending capital is 05's partner endings; it ties when their sum
  equals the M-2's line 9, else `off` with the difference (the seed's off 6,200 before the fix).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.review.api import current_values
from abacus.modules.tax.workbook_service import WORKBOOK

ZERO: Final = Decimal("0")
Values = Mapping[str, Mapping[str, object]]
Tie = Literal["tie", "off"]
M2_LINES: Final[tuple[tuple[int, str], ...]] = (
    (1, "Balance at beginning of year"),
    (2, "Capital contributed: cash"),
    (3, "Net income (loss) per books"),
    (4, "Other increases"),
    (5, "Add lines 1 through 4"),
    (6, "Distributions: cash"),
    (7, "Distributions: property"),
    (8, "Other decreases"),
    (9, "Balance at end of year"),
)
_RECIPIENTS: Final = text(
    "SELECT id, display_name FROM k1_recipients WHERE work_item_id = :r ORDER BY display_name"
)


def dec(values: Values, key: str) -> Decimal:
    cell = values.get(key)
    if cell is None or cell.get("v") in (None, ""):
        return ZERO
    try:
        return Decimal(str(cell["v"]))
    except ArithmeticError:
        return ZERO


def _text(values: Values, key: str) -> str:
    cell = values.get(key)
    return "" if cell is None or cell.get("v") is None else str(cell["v"])


def _tie(difference: Decimal) -> Tie:
    return "tie" if difference == ZERO else "off"


# --- Schedule K ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class KLine:
    line: str
    label: str
    total: Decimal
    by_partner: tuple[tuple[UUID, Decimal], ...]
    tie: Tie


def schedule_k(
    values: Values, partners: Sequence[UUID], view: Literal["federal", "state"]
) -> list[KLine]:
    """06's lines with 09's per-partner shares (federal); the state view has no partner split."""
    column = "C" if view == "federal" else "D"
    out: list[KLine] = []
    n = 2
    while f"06!A{n}" in values:
        if view == "state" and f"06!D{n}" not in values:
            n += 1
            continue
        total = dec(values, f"06!{column}{n}")
        shares: tuple[tuple[UUID, Decimal], ...] = ()
        if view == "federal":
            shares = tuple(
                (pid, dec(values, f"09!{chr(ord('B') + i)}{n}")) for i, pid in enumerate(partners)
            )
        allocated = sum((a for _p, a in shares), ZERO)
        out.append(
            KLine(
                line=_text(values, f"06!A{n}"),
                label=_text(values, f"06!B{n}"),
                total=total,
                by_partner=shares,
                tie="tie" if not shares else _tie(total - allocated),
            )
        )
        n += 1
    return out


def breakdown(values: Values, line: str) -> list[tuple[str, Decimal]]:
    """Form 8825's per-property amounts behind a Schedule K line (08: A property, B line, C)."""
    out: list[tuple[str, Decimal]] = []
    n = 2
    while f"08!A{n}" in values:
        if _text(values, f"08!B{n}") == line:
            out.append((_text(values, f"08!A{n}"), dec(values, f"08!C{n}")))
        n += 1
    return out


# T-05-T43 (DEC-4707): Analysis of Net Income, line 1: Schedule K lines 1 to 11 less 12 to 13e
# and 21, per partner and in total (tax-exempt income, 18a to 18c, is excluded).
ANALYSIS_ADD: Final = frozenset({"1", "2", "3c", "4c", "5", "6a", "7", "8", "9a", "10", "11"})
ANALYSIS_LESS: Final = frozenset({"12", "13a", "13b", "13c", "13d", "13e", "21"})


def analysis(lines: Sequence[KLine]) -> KLine:
    """Analysis of Net Income line 1 from the Schedule K lines (code's sum; ADR-050)."""
    total = ZERO
    shares: dict[UUID, Decimal] = {}
    order: list[UUID] = []
    for line in lines:
        sign = 1 if line.line in ANALYSIS_ADD else -1 if line.line in ANALYSIS_LESS else 0
        if sign == 0:
            continue
        total += sign * line.total
        for pid, amount in line.by_partner:
            if pid not in shares:
                order.append(pid)
                shares[pid] = ZERO
            shares[pid] += sign * amount
    by_partner = tuple((pid, shares[pid]) for pid in order)
    allocated = sum((a for _p, a in by_partner), ZERO)
    return KLine(
        line="analysis_1",
        label="Net income (loss)",
        total=total,
        by_partner=by_partner,
        tie="tie" if not by_partner else _tie(total - allocated),
    )


# --- capital accounts ----------------------------------------------------------------------------


@dataclass(frozen=True)
class CapitalRow:
    partner_id: UUID
    name: str
    beginning: Decimal
    contributions: Decimal
    income: Decimal
    distributions: Decimal
    ending: Decimal

    @property
    def rolls_forward(self) -> bool:
        computed = self.beginning + self.contributions - self.distributions + self.income
        return computed == self.ending


def partner_id_for(return_id: UUID, name: str, known: Mapping[str, UUID]) -> UUID:
    """The K-1 recipient's id for a 05 row's name; a name with no recipient yet gets a stable id
    derived from the return and the name, so the row still shows and stays addressable."""
    return known.get(name) or uuid.uuid5(return_id, f"capital:{name}")


def capital_rows(values: Values, return_id: UUID, known: Mapping[str, UUID]) -> list[CapitalRow]:
    out: list[CapitalRow] = []
    n = 2
    while _text(values, f"05!A{n}"):
        name = _text(values, f"05!A{n}")
        out.append(
            CapitalRow(
                partner_id=partner_id_for(return_id, name, known),
                name=name,
                beginning=dec(values, f"05!B{n}"),
                contributions=dec(values, f"05!C{n}"),
                distributions=dec(values, f"05!D{n}"),
                income=dec(values, f"05!E{n}"),
                ending=dec(values, f"05!F{n}"),
            )
        )
        n += 1
    return out


@dataclass(frozen=True)
class CapitalTotals:
    beginning: Decimal
    contributions: Decimal
    income: Decimal
    distributions: Decimal
    ending: Decimal


def capital_totals(rows: Sequence[CapitalRow]) -> CapitalTotals:
    return CapitalTotals(
        beginning=sum((r.beginning for r in rows), ZERO),
        contributions=sum((r.contributions for r in rows), ZERO),
        income=sum((r.income for r in rows), ZERO),
        distributions=sum((r.distributions for r in rows), ZERO),
        ending=sum((r.ending for r in rows), ZERO),
    )


def capital_tie(rows: Sequence[CapitalRow]) -> Tie:
    return "tie" if all(r.rolls_forward for r in rows) else "off"


# --- M-2 and Item L ------------------------------------------------------------------------------


@dataclass(frozen=True)
class M2:
    lines: tuple[tuple[int, str, Decimal], ...]
    tie: Tie
    difference: Decimal

    @property
    def beginning(self) -> Decimal:
        return self.lines[0][2]

    @property
    def ending(self) -> Decimal:
        return self.lines[-1][2]


def _m2_of(amounts: Mapping[int, Decimal]) -> M2:
    a = {n: amounts.get(n, ZERO) for n, _l in M2_LINES}
    a[5] = a[1] + a[2] + a[3] + a[4]
    footed = a[5] - a[6] - a[7] - a[8]
    return M2(
        lines=tuple((n, label, a[n]) for n, label in M2_LINES),
        tie=_tie(footed - a[9]),
        difference=a[9] - footed,
    )


def m2_as_drafted(values: Values) -> M2:
    return _m2_of({n: dec(values, f"07!B{n}") for n, _l in M2_LINES})


def m2_with_fix(values: Values, rows: Sequence[CapitalRow]) -> M2:
    """The M-2 rebuilt from the partners' capital rows: what an approved fix writes (T-05-T50)."""
    t = capital_totals(rows)
    drafted = {n: dec(values, f"07!B{n}") for n, _l in M2_LINES}
    drafted.update({1: t.beginning, 2: t.contributions, 3: t.income, 6: t.distributions})
    drafted[9] = t.ending
    return _m2_of(drafted)


@dataclass(frozen=True)
class ItemL:
    capital_ending: Decimal
    m2_ending: Decimal
    tie: Tie
    difference: Decimal


def item_l(rows: Sequence[CapitalRow], m2: M2) -> ItemL:
    capital = capital_totals(rows).ending
    return ItemL(capital, m2.ending, _tie(capital - m2.ending), capital - m2.ending)


# --- reads ---------------------------------------------------------------------------------------


async def recipients(tenant: TenantContext, return_id: UUID) -> list[tuple[UUID, str]]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_RECIPIENTS, {"r": return_id})).mappings().all()
    return [(r["id"], str(r["display_name"])) for r in rows]


async def workbook_values(tenant: TenantContext, return_id: UUID) -> dict[str, dict[str, object]]:
    return await current_values(tenant, WORKBOOK, return_id)


__all__ = [
    "ANALYSIS_ADD",
    "ANALYSIS_LESS",
    "M2",
    "M2_LINES",
    "CapitalRow",
    "CapitalTotals",
    "ItemL",
    "KLine",
    "analysis",
    "breakdown",
    "capital_rows",
    "capital_tie",
    "capital_totals",
    "item_l",
    "m2_as_drafted",
    "m2_with_fix",
    "partner_id_for",
    "recipients",
    "schedule_k",
    "workbook_values",
]

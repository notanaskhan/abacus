"""E1: the entity trial balance pipeline (T-05-T09; T-05 §4.4; SPEC-651 §1; ADR-050; DEC-77,
DEC-3408). PROTECTED (red files of the compute package).

Pure `Decimal` over the accounts (debits positive, credits negative, as the TB grid stores them):

- **Columns.** ATB = UTB + AJE + RJE; TTB = ATB + TJE, per account. Every column foots to $0 (a
  balanced trial balance; `tieouts.foot` over the column, against 0).
- **Ties.** Balance sheet: total assets = total liabilities + total equity + current-year income
  (assets ≥ 0 by sign; the others credits), on ATB and on TTB. Capital: beginning capital +
  contributions - distributions + book income = ending capital (the M-2's closing), on ATB.
  Retained earnings: the book income closes to partners' capital.
- **Roll-ups.** Statement totals by section (assets, liabilities, equity, income, deductions) and
  the TTB grouped by form line (`L1`, `8825 Rents`, `K 18a`, …): the Form 1065 export's lines.
- **Unmapped.** An account with no form line counts as unmapped; any unmapped account, or any tie
  that does not hold, closes the export gate (`export_ready = False`) with the reasons named.
- **Stamp.** Every result carries `engine_name`, `engine_version` and `inputs_hash`.

Never a model's arithmetic; never a float.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final, Literal

from abacus.modules.tax.compute.entity.stamp import Stamp, stamp
from abacus.modules.tax.compute.entity.ties import Tally, foot, tie

ENGINE: Final = "entity.tb_pipeline"
ZERO: Final = Decimal(0)
Section = Literal["assets", "liabilities", "equity", "income", "deductions"]
SECTIONS: Final[tuple[Section, ...]] = ("assets", "liabilities", "equity", "income", "deductions")
Column = Literal["py", "utb", "aje", "rje", "atb", "tje", "ttb"]
COLUMNS: Final[tuple[Column, ...]] = ("py", "utb", "aje", "rje", "atb", "tje", "ttb")


@dataclass(frozen=True, slots=True)
class TbAccount:
    number: str
    name: str
    section: Section
    form_line: str | None
    utb: Decimal
    aje: Decimal = ZERO
    rje: Decimal = ZERO
    tje: Decimal = ZERO
    py: Decimal = ZERO
    # The equity account's role in the capital roll-forward (M-2): beginning, contributions or
    # distributions; None for every other account.
    capital_role: Literal["beginning", "contributions", "distributions"] | None = None

    @property
    def atb(self) -> Decimal:
        return self.utb + self.aje + self.rje

    @property
    def ttb(self) -> Decimal:
        return self.atb + self.tje

    def value(self, column: Column) -> Decimal:
        return getattr(self, column)


@dataclass(frozen=True)
class TbResult:
    stamp: Stamp
    totals: Mapping[Column, Mapping[Section, Decimal]]
    column_foots: Mapping[Column, Tally]
    balance_sheet: Mapping[Column, Tally]
    capital: Tally
    book_income: Decimal  # ATB, as a positive income figure
    by_form_line: Mapping[str, Decimal]  # TTB
    unmapped: tuple[str, ...]
    export_ready: bool
    blocked_by: tuple[str, ...] = field(default_factory=tuple[str, ...])

    def total_assets(self, column: Column = "atb") -> Decimal:
        return self.totals[column]["assets"]


def _totals(accounts: Sequence[TbAccount], column: Column) -> dict[Section, Decimal]:
    out: dict[Section, Decimal] = dict.fromkeys(SECTIONS, ZERO)
    for a in accounts:
        out[a.section] += a.value(column)
    return out


def run(accounts: Sequence[TbAccount]) -> TbResult:
    """The pipeline over one entity's TB (module docstring)."""
    totals = {c: _totals(accounts, c) for c in COLUMNS}
    foots = {c: foot([a.value(c) for a in accounts], ZERO, label=f"{c} column") for c in COLUMNS}
    sheet: dict[Column, Tally] = {}
    for c in ("atb", "ttb"):
        t = totals[c]
        income = -(t["income"] + t["deductions"])  # credits less debits: a profit is positive
        claims = -(t["liabilities"] + t["equity"]) + income
        sheet[c] = tie(t["assets"], claims, label=f"balance sheet {c}")
    book_income = -(totals["atb"]["income"] + totals["atb"]["deductions"])
    role = {r: ZERO for r in ("beginning", "contributions", "distributions")}
    for a in accounts:
        if a.capital_role is not None:
            role[a.capital_role] += -a.atb  # credits as positive capital
    ending = role["beginning"] + role["contributions"] + role["distributions"] + book_income
    claims_equity = -totals["atb"]["equity"] + book_income
    capital = tie(ending, claims_equity, label="capital")
    lines: dict[str, Decimal] = {}
    for a in accounts:
        if a.form_line is not None:
            lines[a.form_line] = lines.get(a.form_line, ZERO) + a.ttb
    unmapped = tuple(a.number for a in accounts if a.form_line is None)
    blocked = [f"unmapped:{n}" for n in unmapped]
    blocked += [f"column:{c}" for c, t in foots.items() if not t.ok]
    blocked += [f"balance_sheet:{c}" for c, t in sheet.items() if not t.ok]
    if not capital.ok:
        blocked.append("capital")
    return TbResult(
        stamp=stamp(ENGINE, list(accounts)),
        totals=totals,
        column_foots=foots,
        balance_sheet=sheet,
        capital=capital,
        book_income=book_income,
        by_form_line=dict(sorted(lines.items())),
        unmapped=unmapped,
        export_ready=not blocked,
        blocked_by=tuple(blocked),
    )

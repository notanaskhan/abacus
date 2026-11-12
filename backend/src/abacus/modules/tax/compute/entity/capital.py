"""E7: partners' capital and Schedule M-2 (T-05-T19; T-05 §4.4, F7; SPEC-651; Form 1065
instructions for Schedule M-2 and Item L; Reg. §1.704-1(b)(2)(iv)(l); ADR-050; DEC-77,
DEC-4405). PROTECTED (red files of the compute package).

Code computes every capital figure; nothing here asks a model. Whole dollars throughout.

- **Three bases.** Each partner's capital is rolled on the tax basis, the §704(b) book basis and
  the books (`tax`, `704b`, `book`): beginning, contributions (cash, property), the partner's
  share of income or loss, other increases (tax-exempt income), distributions (cash, property),
  other decreases (nondeductible expenses), transfers in and out, and ending.
- **Transferee succession** (Reg. §1.704-1(b)(2)(iv)(l)). On a transfer of `points` of the
  transferor's `transferor_points`, the transferee succeeds to the transferred share of the
  transferor's capital at the transfer date, in every basis: the transferor's beginning capital
  plus its items through the date (its first-half tax-exempt share included) less its
  distributions through the date, times `points / transferor_points`, half up to the dollar.
  The same amount leaves the transferor, so Transfers nets to 0 in each basis. The items after
  the date are each partner's own allocation (E5), given in `bases`.
- **Crossfoot.** Every movement column sums across partners, and each basis' ending total equals
  its beginning plus its movements; transfers net to zero.
- **Schedule M-2** on the basis the return keeps its books on: line 1 beginning, 2a cash and 2b
  property contributed, 3 net income per books, 4 other increases, 5 the sum, 6a cash and 6b
  property distributions, 7 other decreases, 8 the sum of 6 and 7, 9 = 5 - 8; and line 9's tie
  to Schedule L line 21 (TXP-07 "M-2 ties · off 6,200" until the tax-exempt interest is in).
- **§743(b) placeholder.** For each transfer, the price less the transferred tax capital: a fact
  for the `section_754` decision card, never an adjustment (T-06 computes the step-up).
- **§704(b) and book.** Partners whose §704(b) and book columns differ (a revaluation or a
  §704(c) item), for the reviewer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

from abacus.modules.tax.compute.entity.stamp import Stamp, plain, stamp

ENGINE: Final = "entity.capital"
ZERO: Final = Decimal(0)
Basis = Literal["tax", "704b", "book"]
BASES: Final[tuple[Basis, ...]] = ("tax", "704b", "book")
MOVEMENTS: Final = (
    "beginning",
    "contributions_cash",
    "contributions_property",
    "income",
    "other_increases",
    "distributions_cash",
    "distributions_property",
    "other_decreases",
    "transfers",
    "ending",
)


class CapitalInvalid(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class Movements:
    """One partner's items on one basis (whole dollars; increases and decreases positive, a loss
    a negative `income`)."""

    beginning: Decimal = ZERO
    contributions_cash: Decimal = ZERO
    contributions_property: Decimal = ZERO
    income: Decimal = ZERO
    other_increases: Decimal = ZERO
    distributions_cash: Decimal = ZERO
    distributions_property: Decimal = ZERO
    other_decreases: Decimal = ZERO

    def values(self) -> tuple[Decimal, ...]:
        return (
            self.beginning,
            self.contributions_cash,
            self.contributions_property,
            self.income,
            self.other_increases,
            self.distributions_cash,
            self.distributions_property,
            self.other_decreases,
        )

    def capital(self) -> Decimal:
        """Beginning plus increases less decreases (no transfers)."""
        return (
            self.beginning
            + self.contributions_cash
            + self.contributions_property
            + self.income
            + self.other_increases
            - self.distributions_cash
            - self.distributions_property
            - self.other_decreases
        )


@dataclass(frozen=True, slots=True)
class CapitalPartner:
    key: str
    bases: Mapping[Basis, Movements]  # the partner's whole-year items per basis (E5's shares)


@dataclass(frozen=True, slots=True)
class Transfer:
    on: date
    transferor: str
    transferee: str
    points: Decimal  # the interest transferred, in percentage points
    transferor_points: Decimal  # the transferor's interest just before the transfer
    price: Decimal
    # The transferor's beginning and items from the year's start through `on`, per basis.
    through: Mapping[Basis, Movements]


@dataclass(frozen=True)
class CapitalRow:
    partner: str
    basis: Basis
    columns: Mapping[str, Decimal]  # MOVEMENTS → amount


@dataclass(frozen=True)
class TransferOut:
    on: date
    transferor: str
    transferee: str
    capital_at_date: Mapping[Basis, Decimal]
    transferred: Mapping[Basis, Decimal]
    section_743b_placeholder: Decimal  # price - transferred tax capital


@dataclass(frozen=True)
class ScheduleM2:
    basis: Basis
    lines: Mapping[str, Decimal]  # "1", "2a", "2b", "3", "4", "5", "6a", "6b", "7", "8", "9"
    schedule_l_line_21: Decimal | None
    off: Decimal | None  # line 9 - Schedule L line 21

    @property
    def ties(self) -> bool:
        return self.off is None or self.off == 0


@dataclass(frozen=True)
class Capital:
    stamp: Stamp
    rows: tuple[CapitalRow, ...]
    totals: Mapping[Basis, Mapping[str, Decimal]]
    transfers: tuple[TransferOut, ...]
    m2: ScheduleM2
    ending: Mapping[str, Decimal]  # Item L: each partner's ending capital on the M-2 basis
    book_704b_differs: tuple[str, ...]
    checks: Mapping[str, bool] = field(default_factory=dict[str, bool])

    def row(self, partner: str, basis: Basis) -> CapitalRow:
        return next(r for r in self.rows if r.partner == partner and r.basis == basis)


def _dollars(value: Decimal) -> None:
    if value != value.to_integral_value():
        raise CapitalInvalid("whole_dollars_only")


def _transferred(capital_at: Decimal, points: Decimal, of: Decimal) -> Decimal:
    return (capital_at * points / of).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def _validate(partners: Sequence[CapitalPartner], transfers: Sequence[Transfer]) -> list[str]:
    keys = [p.key for p in partners]
    if not keys or len(set(keys)) != len(keys):
        raise CapitalInvalid("partners_required")
    for p in partners:
        if set(p.bases) != set(BASES):
            raise CapitalInvalid("every_basis_required")
        for moves in p.bases.values():
            for v in moves.values():
                _dollars(v)
    for t in transfers:
        if t.transferor not in keys or t.transferee not in keys:
            raise CapitalInvalid("unknown_partner")
        if t.transferor == t.transferee:
            raise CapitalInvalid("transfer_to_self")
        if t.transferor_points <= 0 or t.points <= 0 or t.points > t.transferor_points:
            raise CapitalInvalid("transfer_points_invalid")
        if set(t.through) != set(BASES):
            raise CapitalInvalid("every_basis_required")
        _dollars(t.price)
        for moves in t.through.values():
            for v in moves.values():
                _dollars(v)
    return keys


def capital(
    partners: Sequence[CapitalPartner],
    transfers: Sequence[Transfer] = (),
    *,
    m2_basis: Basis = "book",
    schedule_l_line_21: Decimal | None = None,
) -> Capital:
    """Each partner's capital in three bases, the transfers, Schedule M-2 and its tie (module
    docstring). `m2_basis` is the basis the return's books are kept on (`book` for books kept on
    the income tax basis, as Ridgeline's)."""
    keys = _validate(partners, transfers)
    if schedule_l_line_21 is not None:
        _dollars(schedule_l_line_21)
    moved: dict[tuple[str, Basis], Decimal] = {(k, b): ZERO for k in keys for b in BASES}
    outs: list[TransferOut] = []
    for t in sorted(transfers, key=lambda x: (x.on, x.transferor, x.transferee)):
        at: dict[Basis, Decimal] = {b: t.through[b].capital() for b in BASES}
        amount: dict[Basis, Decimal] = {
            b: _transferred(at[b], t.points, t.transferor_points) for b in BASES
        }
        for b in BASES:
            moved[(t.transferor, b)] -= amount[b]
            moved[(t.transferee, b)] += amount[b]
        outs.append(
            TransferOut(
                on=t.on,
                transferor=t.transferor,
                transferee=t.transferee,
                capital_at_date=at,
                transferred=amount,
                section_743b_placeholder=t.price - amount["tax"],
            )
        )
    rows: list[CapitalRow] = []
    for p in partners:
        for b in BASES:
            m = p.bases[b]
            columns: dict[str, Decimal] = dict(zip(MOVEMENTS[:-2], m.values(), strict=True))
            columns["transfers"] = moved[(p.key, b)]
            columns["ending"] = m.capital() + moved[(p.key, b)]
            rows.append(CapitalRow(p.key, b, columns))
    totals: dict[Basis, dict[str, Decimal]] = {
        b: {col: sum((r.columns[col] for r in rows if r.basis == b), ZERO) for col in MOVEMENTS}
        for b in BASES
    }
    t = totals[m2_basis]
    line5 = (
        t["beginning"]
        + t["contributions_cash"]
        + t["contributions_property"]
        + t["income"]
        + t["other_increases"]
    )
    line8 = t["distributions_cash"] + t["distributions_property"] + t["other_decreases"]
    m2_lines = {
        "1": t["beginning"],
        "2a": t["contributions_cash"],
        "2b": t["contributions_property"],
        "3": t["income"],
        "4": t["other_increases"],
        "5": line5,
        "6a": t["distributions_cash"],
        "6b": t["distributions_property"],
        "7": t["other_decreases"],
        "8": line8,
        "9": line5 - line8,
    }
    off = None if schedule_l_line_21 is None else m2_lines["9"] - schedule_l_line_21
    m2 = ScheduleM2(m2_basis, m2_lines, schedule_l_line_21, off)
    ending = {r.partner: r.columns["ending"] for r in rows if r.basis == m2_basis}
    differs = tuple(
        p.key for p in partners if p.bases["704b"].values() != p.bases["book"].values()
    )
    checks = {
        "crossfoot": all(
            totals[b]["ending"]
            == sum((totals[b][c] for c in MOVEMENTS[:5]), ZERO)
            - totals[b]["distributions_cash"]
            - totals[b]["distributions_property"]
            - totals[b]["other_decreases"]
            + totals[b]["transfers"]
            for b in BASES
        ),
        "transfers_net_zero": all(totals[b]["transfers"] == 0 for b in BASES),
        "m2_line_9_is_ending": m2_lines["9"] == totals[m2_basis]["ending"],
        "m2_ties": m2.ties,
    }
    return Capital(
        stamp=stamp(
            ENGINE,
            {
                "partners": [{"key": p.key, "bases": plain(dict(p.bases))} for p in partners],
                "transfers": [plain(t) for t in transfers],
                "m2_basis": m2_basis,
                "schedule_l_line_21": schedule_l_line_21,
            },
        ),
        rows=tuple(rows),
        totals=totals,
        transfers=tuple(outs),
        m2=m2,
        ending=ending,
        book_704b_differs=differs,
        checks=checks,
    )


__all__ = [
    "BASES",
    "ENGINE",
    "MOVEMENTS",
    "Basis",
    "Capital",
    "CapitalInvalid",
    "CapitalPartner",
    "CapitalRow",
    "Movements",
    "ScheduleM2",
    "Transfer",
    "TransferOut",
    "capital",
]

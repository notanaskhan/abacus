"""E6: Schedule K and the K-1s (T-05-T15; T-05 §4.4, F6; SPEC-651 AC-6.1 to AC-6.3; Form 1065
instructions; ADR-050; DEC-77, DEC-4306). PROTECTED (red files of the compute package).

Every Schedule K line is allocated to the partners by the approved structure, so that each line's
K-1 amounts sum to the line exactly (Σ K-1 = K), and the K-1 items code can state are built:

- **Lines.** A line is allocated through E5 (`allocation.allocate_item`) over the structure's
  ownership segments: interim closing with the line's per-segment amounts from the closed books,
  or proration. A line that follows actual payments (distributions, line 19a; guaranteed
  payments) carries its amounts per partner instead, which must sum to the line.
- **Item J.** Each partner's profit, loss and capital percentages at the beginning and the end of
  the year (the first and the last segment).
- **Item K.** Each liability total (recourse, nonrecourse, qualified nonrecourse) shared by the
  ending profit percentage, in whole dollars, footing exactly.
- **Item L.** Each partner's ending capital as E7 states it (given here), and whether their sum
  ties to Schedule L line 21; when it does not, the difference (TXP-05 a4 "off 6,200").
- **Analysis of Net Income.** The income lines (1 to 11) less the deduction lines (12, 13a to 13d,
  21), never the tax-exempt lines (18a to 18c); per partner, the same over their K-1 amounts.
- **§199A.** A partner that is not a corporation receives a statement (box 20, code Z, "stmt") when
  any trade or business line (1, 2, 3c) is not zero.
- **Item I and the K-1 count.** One K-1 per partner; the count by entity kind sums to it.
- **State K-1 amounts.** A view over sheet 08's cells (imported or keyed, each with its
  provenance); E6 totals them per state and computes no state amount (T-06's E9 does).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final, Literal

from abacus.kernel.numeric import allocate
from abacus.modules.tax.compute.entity.allocation import (
    Convention,
    Method,
    Segment,
    allocate_item,
)
from abacus.modules.tax.compute.entity.stamp import Stamp, stamp

ENGINE: Final = "entity.schedule_k"
ZERO: Final = Decimal(0)
INCOME_LINES: Final = frozenset({"1", "2", "3c", "4", "5", "6a", "7", "8", "9a", "10", "11"})
DEDUCTION_LINES: Final = frozenset({"12", "13a", "13b", "13c", "13d", "21"})
TAX_EXEMPT_LINES: Final = frozenset({"18a", "18b", "18c"})
QBI_LINES: Final = frozenset({"1", "2", "3c"})
LIABILITY_KINDS: Final = ("recourse", "nonrecourse", "qualified_nonrecourse")
EntityKind = Literal["individual", "llc", "partnership", "corporation", "trust", "estate", "other"]


class ScheduleKInvalid(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class KPartner:
    key: str
    entity_kind: EntityKind
    # (profit, loss, capital) percentages at the year's beginning and end (Item J).
    beginning: tuple[Decimal, Decimal, Decimal]
    ending: tuple[Decimal, Decimal, Decimal]


@dataclass(frozen=True, slots=True)
class KLine:
    key: str
    total: Decimal
    segment_amounts: tuple[Decimal, ...] | None = None  # interim closing
    by_partner: Mapping[str, Decimal] | None = None  # actual payments


@dataclass(frozen=True, slots=True)
class StateCell:
    state: str
    partner: str
    amount: Decimal
    provenance: Literal["imported", "keyed"]


@dataclass(frozen=True)
class K1:
    partner: str
    lines: Mapping[str, Decimal]
    item_j: Mapping[str, tuple[Decimal, Decimal]]  # profit, loss, capital: (beginning, ending)
    item_k: Mapping[str, Decimal]
    item_l_ending: Decimal | None
    net_income: Decimal
    section_199a_statement: bool


@dataclass(frozen=True)
class ScheduleK:
    stamp: Stamp
    lines: Mapping[str, Decimal]
    k1s: tuple[K1, ...]
    item_k_totals: Mapping[str, Decimal]
    item_l: Mapping[str, object]  # ties, total, schedule_l_line_21, off
    net_income: Decimal
    k1_count: int
    item_i: Mapping[str, int]
    states: Mapping[str, Mapping[str, Decimal]]
    state_totals: Mapping[str, Decimal]
    checks: Mapping[str, bool] = field(default_factory=dict[str, bool])


def _line_shares(
    line: KLine,
    partners: Sequence[str],
    segs: Sequence[Segment],
    method: Method,
    convention: Convention,
) -> dict[str, Decimal]:
    if line.total != line.total.to_integral_value():
        raise ScheduleKInvalid("whole_dollars_only")
    if line.by_partner is not None:
        if any(p not in partners for p in line.by_partner):
            raise ScheduleKInvalid("unknown_partner")
        if sum(line.by_partner.values(), ZERO) != line.total:
            raise ScheduleKInvalid(f"line_{line.key}_does_not_foot")
        return {p: line.by_partner.get(p, ZERO) for p in partners}
    allocated = allocate_item(
        line.total,
        segs,
        method=method,
        convention=convention,
        segment_amounts=line.segment_amounts,
    )
    return {p: allocated.totals.get(p, ZERO) for p in partners}


def _net(lines: Mapping[str, Decimal]) -> Decimal:
    income = sum((v for k, v in lines.items() if k in INCOME_LINES), ZERO)
    deductions = sum((v for k, v in lines.items() if k in DEDUCTION_LINES), ZERO)
    return income - deductions


def schedule_k(
    partners: Sequence[KPartner],
    segs: Sequence[Segment],
    lines: Sequence[KLine],
    *,
    method: Method,
    convention: Convention,
    liabilities: Mapping[str, Decimal],
    ending_capital: Mapping[str, Decimal] | None = None,
    schedule_l_line_21: Decimal | None = None,
    state_cells: Sequence[StateCell] = (),
) -> ScheduleK:
    """Schedule K, the K-1s and their items (module docstring)."""
    keys = [p.key for p in partners]
    if len(set(keys)) != len(keys) or not keys:
        raise ScheduleKInvalid("partners_required")
    if len({line.key for line in lines}) != len(lines):
        raise ScheduleKInvalid("duplicate_line")
    if any(k not in LIABILITY_KINDS for k in liabilities):
        raise ScheduleKInvalid("unknown_liability_kind")
    shares = {line.key: _line_shares(line, keys, segs, method, convention) for line in lines}
    ending_profit = [p.ending[0] for p in partners]
    if sum(ending_profit, ZERO) != Decimal(100):
        raise ScheduleKInvalid("ending_profit_must_sum_to_100")
    item_k: dict[str, dict[str, Decimal]] = {}
    for kind, total in liabilities.items():
        if total != total.to_integral_value():
            raise ScheduleKInvalid("whole_dollars_only")
        split = allocate(total, ending_profit, places=0)
        item_k[kind] = dict(zip(keys, split, strict=True))
    k1s: list[K1] = []
    for p in partners:
        mine = {line.key: shares[line.key][p.key] for line in lines}
        qbi = any(mine.get(k, ZERO) != 0 for k in QBI_LINES)
        k1s.append(
            K1(
                partner=p.key,
                lines=mine,
                item_j={
                    "profit": (p.beginning[0], p.ending[0]),
                    "loss": (p.beginning[1], p.ending[1]),
                    "capital": (p.beginning[2], p.ending[2]),
                },
                item_k={kind: item_k[kind][p.key] for kind in item_k},
                item_l_ending=(ending_capital or {}).get(p.key),
                net_income=_net(mine),
                section_199a_statement=qbi and p.entity_kind != "corporation",
            )
        )
    totals = {line.key: line.total for line in lines}
    l_total = sum((ending_capital or {}).values(), ZERO) if ending_capital else None
    off = (
        l_total - schedule_l_line_21
        if l_total is not None and schedule_l_line_21 is not None
        else None
    )
    item_i: dict[str, int] = {}
    for p in partners:
        item_i[p.entity_kind] = item_i.get(p.entity_kind, 0) + 1
    states: dict[str, dict[str, Decimal]] = {}
    for cell in state_cells:
        if cell.partner not in keys:
            raise ScheduleKInvalid("unknown_partner")
        row = states.setdefault(cell.state, {})
        row[cell.partner] = row.get(cell.partner, ZERO) + cell.amount
    state_totals = {s: sum(v.values(), ZERO) for s, v in states.items()}
    net = _net(totals)
    checks = {
        "k_equals_sum_of_k1s": all(
            sum((k.lines[line] for k in k1s), ZERO) == totals[line] for line in totals
        ),
        "item_k_foots": all(
            sum(item_k[kind].values(), ZERO) == liabilities[kind] for kind in liabilities
        ),
        "net_income_foots": sum((k.net_income for k in k1s), ZERO) == net,
        "k1_count_is_item_i": sum(item_i.values(), 0) == len(k1s),
        "item_l_ties": off is None or off == 0,
    }
    return ScheduleK(
        stamp=stamp(
            ENGINE,
            {
                "partners": [
                    {"key": p.key, "kind": p.entity_kind, "begin": p.beginning, "end": p.ending}
                    for p in partners
                ],
                "segments": [
                    {"start": s.start, "end": s.end, "interests": dict(s.interests)} for s in segs
                ],
                "lines": [
                    {
                        "key": line.key,
                        "total": line.total,
                        "segments": list(line.segment_amounts or ()),
                        "by_partner": dict(line.by_partner or {}),
                    }
                    for line in lines
                ],
                "method": method,
                "convention": convention,
                "liabilities": dict(liabilities),
                "ending_capital": dict(ending_capital or {}),
                "schedule_l_line_21": schedule_l_line_21,
            },
        ),
        lines=totals,
        k1s=tuple(k1s),
        item_k_totals=dict(liabilities),
        item_l={
            "total": l_total,
            "schedule_l_line_21": schedule_l_line_21,
            "off": off,
            "ties": off is None or off == 0,
        },
        net_income=net,
        k1_count=len(k1s),
        item_i=item_i,
        states=states,
        state_totals=state_totals,
        checks=checks,
    )

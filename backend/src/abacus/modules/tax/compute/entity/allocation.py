"""E5 part 1: allocation by ownership period (T-05-T10; T-05 §4.4; SPEC-651 AC-2.3, AC-5.3; Reg.
§1.706-4; ADR-050; DEC-77, DEC-3409). PROTECTED (red files of the compute package).

A partnership's year is split at each interest transfer into segments; each partner's share of an
item in a segment is its percentage interest during that segment, straight percentage.

- **Segments.** The transfers' dates, moved by the convention (Reg. §1.706-4(c)): `calendar_day`
  (the transfer is at the end of its day), `semi_monthly` (on or before the 15th: the end of the
  15th; after it: the end of the month) and `monthly` (the end of the month). Each segment runs
  from the day after the previous boundary to its own, the last to the year's end.
- **Method.** `interim_closing`: each segment's amount comes from the books closed at the boundary
  (given; they must sum to the year's item), under any of the three conventions. `proration`: the
  year's item is split across segments by calendar days, calendar-day convention only (the
  regulation allows proration with no other).
- **Splits.** Every split goes through `kernel.numeric.allocate` (largest remainder) in whole
  dollars, so each segment's shares foot to the segment and the segments to the year exactly.
  A partner with no interest in a segment (0%, or absent) receives nothing in it.
- **Stamp.** Every result carries the engine's name, version and inputs hash.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Final, Literal

from abacus.kernel.numeric import allocate
from abacus.modules.tax.compute.entity.stamp import Stamp, stamp

ENGINE: Final = "entity.allocation"
ZERO: Final = Decimal(0)
HUNDRED: Final = Decimal(100)
Method = Literal["interim_closing", "proration"]
Convention = Literal["calendar_day", "semi_monthly", "monthly"]
CONVENTIONS: Final[tuple[Convention, ...]] = ("calendar_day", "semi_monthly", "monthly")


class AllocationInvalid(ValueError):
    """The inputs cannot be allocated: the code says why (never a partner's figures)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class Segment:
    start: date
    end: date
    # Percentage interest per partner during the segment (0 to 100; they sum to 100).
    interests: Mapping[str, Decimal]

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


@dataclass(frozen=True)
class Allocation:
    stamp: Stamp
    segments: tuple[Segment, ...]
    segment_amounts: tuple[Decimal, ...]
    shares: tuple[Mapping[str, Decimal], ...]  # per segment, per partner
    totals: Mapping[str, Decimal]
    total: Decimal


def _month_end(day: date) -> date:
    first_next = date(day.year + (day.month == 12), day.month % 12 + 1, 1)
    return first_next - timedelta(days=1)


def boundary(transfer: date, convention: Convention) -> date:
    """The day a transfer is treated as happening at the end of (Reg. §1.706-4(c))."""
    if convention == "calendar_day":
        return transfer
    if convention == "monthly":
        return _month_end(transfer)
    return transfer.replace(day=15) if transfer.day <= 15 else _month_end(transfer)


def segments(
    year_start: date,
    year_end: date,
    interests_by_transfer: Sequence[tuple[date | None, Mapping[str, Decimal]]],
    convention: Convention,
) -> tuple[Segment, ...]:
    """The year's segments: the first entry's transfer date is None (the opening interests);
    each later entry starts after its transfer's boundary."""
    if not interests_by_transfer or interests_by_transfer[0][0] is not None:
        raise AllocationInvalid("opening_interests_required")
    cuts = [boundary(t, convention) for t, _ in interests_by_transfer[1:] if t is not None]
    if any(not year_start <= c < year_end for c in cuts) or cuts != sorted(set(cuts)):
        raise AllocationInvalid("transfer_out_of_year")
    starts = [year_start, *(c + timedelta(days=1) for c in cuts)]
    ends = [*cuts, year_end]
    out: list[Segment] = []
    for start, end, (_, interests) in zip(starts, ends, interests_by_transfer, strict=True):
        if sum(interests.values(), ZERO) != HUNDRED or any(v < 0 for v in interests.values()):
            raise AllocationInvalid("interests_must_sum_to_100")
        out.append(Segment(start, end, dict(interests)))
    return tuple(out)


def _partners(segs: Sequence[Segment]) -> list[str]:
    seen: dict[str, None] = {}
    for s in segs:
        for partner in s.interests:
            seen.setdefault(partner, None)
    return list(seen)


def allocate_item(
    total: Decimal,
    segs: Sequence[Segment],
    *,
    method: Method,
    convention: Convention,
    segment_amounts: Sequence[Decimal] | None = None,
) -> Allocation:
    """One item (income, a K line) across the segments and their partners (module docstring)."""
    if convention not in CONVENTIONS:
        raise AllocationInvalid("unknown_convention")
    if total != total.to_integral_value():
        raise AllocationInvalid("whole_dollars_only")
    if method == "proration":
        if convention != "calendar_day":
            raise AllocationInvalid("proration_is_calendar_day_only")
        amounts = allocate(total, [Decimal(s.days) for s in segs], places=0)
    else:
        if segment_amounts is None or len(segment_amounts) != len(segs):
            raise AllocationInvalid("segment_amounts_required")
        if sum(segment_amounts, ZERO) != total:
            raise AllocationInvalid("segments_do_not_sum_to_the_year")
        amounts = tuple(segment_amounts)
    partners = _partners(segs)
    shares: list[dict[str, Decimal]] = []
    for seg, amount in zip(segs, amounts, strict=True):
        weights = [seg.interests.get(p, ZERO) for p in partners]
        split = allocate(amount, weights, places=0)
        shares.append(dict(zip(partners, split, strict=True)))
    totals = {p: sum((s[p] for s in shares), ZERO) for p in partners}
    return Allocation(
        stamp=stamp(
            ENGINE,
            {
                "total": total,
                "method": method,
                "convention": convention,
                "segments": [
                    {"start": s.start, "end": s.end, "interests": dict(s.interests)} for s in segs
                ],
                "segment_amounts": list(amounts),
            },
        ),
        segments=tuple(segs),
        segment_amounts=tuple(amounts),
        shares=tuple(shares),
        totals=totals,
        total=total,
    )

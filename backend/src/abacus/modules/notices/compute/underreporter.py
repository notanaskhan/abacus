"""The underreporter comparison (CP2000, CP3219A; N-04 US-4.3): the notice, the return as filed
and the information returns compared by code, never by a model.

Rows: each proposed line change beside the return's line and the difference. Information returns:
each one, whether the return shows it. The difference is explained when the information returns
missing from the return foot to the income difference the notice proposes. Whitley: interest
412.00 → 3,532.00 (+3,120.00) = Front Range Bank 1,870.00 + Lakeview Credit Union 1,250.00.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Final

from abacus.kernel.numeric import CONTEXT, quantize_half_up
from abacus.modules.notices.compute.stamp import Stamp, stamp

# The proposed lines whose difference information returns can explain (income lines).
INCOME_LINES: Final = frozenset(
    {"interest", "dividends", "wages", "capital_gains", "nonemployee_compensation", "other_income"}
)


@dataclass(frozen=True)
class ProposedLine:
    key: str
    label: str
    shown: Decimal | None
    corrected: Decimal


@dataclass(frozen=True)
class InformationReturn:
    payer_name: str
    form: str
    amount: Decimal
    on_return: bool
    line_key: str = "interest"


@dataclass(frozen=True)
class Row:
    key: str
    label: str
    as_filed: Decimal | None
    irs: Decimal
    difference: Decimal
    agrees_with_return: bool  # the notice's "shown on return" equals the return as filed


@dataclass(frozen=True)
class Comparison:
    rows: tuple[Row, ...]
    information_returns: tuple[InformationReturn, ...]
    income_difference: Decimal
    unreported: Decimal
    difference_explained: bool
    stamp: Stamp


def compare(
    as_filed: Mapping[str, Decimal],
    proposed: Sequence[ProposedLine],
    information_returns: Sequence[InformationReturn],
) -> Comparison:
    rows: list[Row] = []
    with localcontext(CONTEXT):
        income_difference = Decimal(0)
        for line in proposed:
            filed = as_filed.get(line.key)
            base = filed if filed is not None else (line.shown or Decimal(0))
            difference = quantize_half_up(line.corrected - base, 2)
            if line.key in INCOME_LINES:
                income_difference += difference
            rows.append(
                Row(
                    line.key,
                    line.label,
                    filed,
                    line.corrected,
                    difference,
                    line.shown is None or filed is None or line.shown == filed,
                )
            )
        unreported = quantize_half_up(
            sum((r.amount for r in information_returns if not r.on_return), Decimal(0)), 2
        )
        income_difference = quantize_half_up(income_difference, 2)
    inputs = {
        "as_filed": dict(as_filed),
        "proposed": [(p.key, p.shown, p.corrected) for p in proposed],
        "information_returns": [
            (r.payer_name, r.form, r.amount, r.on_return, r.line_key) for r in information_returns
        ],
    }
    return Comparison(
        tuple(rows),
        tuple(information_returns),
        income_difference,
        unreported,
        income_difference != 0 and unreported == income_difference,
        stamp("underreporter.compare", inputs),
    )

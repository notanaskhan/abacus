"""An amendment's lines, pure (T-08-T30; TAX-16 a; SPEC-710 AC6.1, AC6.2; ADR-050; DEC-77).

Code computes; nothing here reads a database, the clock or a model. As filed is the original's
approved engine summary (the baseline); as amended is the amendment return's newest engine
summary (an engine import; until one exists, as amended equals as filed). Each line's change is
as amended less as filed. The total change is the tax's change; the refund due or balance due is
the change in what the taxpayer is owed: (payments less tax) as amended less (payments less tax) as
filed, positive a refund, negative a balance due. A jurisdiction with no payments line (Illinois,
whose payments are not on these lines) has only its tax change.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

Jurisdiction = Literal["federal", "il"]
ZERO: Final = Decimal("0.00")

# The 1040-X and IL-1040-X lines over engine summary keys, in the order TAX-16 reads them
# (OQ-15: repo files a CPA reviews yearly, not firm content).
LINES: Final[dict[str, tuple[tuple[str, str], ...]]] = {
    "federal": (
        ("1040.11", "1 Adjusted gross income"),
        ("1040.12", "2 Itemized deductions or standard deduction"),
        ("1040.15", "5 Taxable income"),
        ("1040.16", "6 Tax"),
        ("1040.24", "11 Total tax"),
        ("1040.33", "Payments"),
    ),
    "il": (
        ("il1040.agi", "1 Federal adjusted gross income"),
        ("il1040.tax", "IL tax"),
    ),
}
TAX: Final = {"federal": "1040.24", "il": "il1040.tax"}
PAYMENTS: Final = {"federal": "1040.33"}


@dataclass(frozen=True)
class Line:
    line_key: str
    label: str
    as_filed: Decimal
    as_amended: Decimal

    @property
    def change(self) -> Decimal:
        return (self.as_amended - self.as_filed).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class Amended:
    jurisdiction: Jurisdiction
    lines: tuple[Line, ...]
    total_change: Decimal
    refund_due: Decimal | None
    balance_due: Decimal | None


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def amend(
    jurisdiction: Jurisdiction,
    as_filed: Mapping[str, Decimal],
    as_amended: Mapping[str, Decimal] | None,
) -> Amended:
    """The jurisdiction's lines; a key missing on either side reads 0.00."""
    amended = as_filed if as_amended is None else as_amended
    lines = tuple(
        Line(key, label, _q(as_filed.get(key, ZERO)), _q(amended.get(key, ZERO)))
        for key, label in LINES[jurisdiction]
    )
    tax_key = TAX[jurisdiction]
    tax_change = _q(amended.get(tax_key, ZERO) - as_filed.get(tax_key, ZERO))
    pay_key = PAYMENTS.get(jurisdiction)
    if pay_key is None:
        owed = -tax_change
    else:
        filed_net = as_filed.get(pay_key, ZERO) - as_filed.get(tax_key, ZERO)
        amended_net = amended.get(pay_key, ZERO) - amended.get(tax_key, ZERO)
        owed = _q(amended_net - filed_net)
    refund = owed if owed > 0 else None
    balance = -owed if owed < 0 else None
    return Amended(jurisdiction, lines, tax_change, refund, balance)

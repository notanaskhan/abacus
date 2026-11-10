"""Form 1040 leadsheets and NY IT-201 line arithmetic (T-04-T11; T-04 §4.4, AC-3.2; DEC-3124).

Feld 2025 goldens: 1040 line 2b = 2,310 + 4,600 = 6,910; IT-201 line 33 = 19 + 20 + 22 =
598,030 + 1,550 + 16,025 = 615,605; line 37 = 33 - 34 = 615,605 - 16,050 = 599,555; tax 29,791
(line 39, NY, imported) + 23,014 (line 47a, NYC, imported) = 52,805; payments 17,400 + 9,390 +
20,000 + 4,746 = 51,536; balance due 52,805 - 51,536 = 1,269.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from abacus.modules.tax.compute.individual.engine import Stamp, stamp


@dataclass(frozen=True)
class LineTotal:
    line: str
    total: Decimal
    parts: tuple[Decimal, ...]
    stamp: Stamp


def leadsheet_line(line: str, parts: Sequence[Decimal]) -> LineTotal:
    """A Form 1040 leadsheet line: the sum of its contributing approved fields."""
    total = sum(parts, Decimal(0))
    return LineTotal(
        line, total, tuple(parts), stamp(f"leadsheets.form_1040.{line}", {"parts": list(parts)})
    )


@dataclass(frozen=True)
class It201Inputs:
    line19_federal_agi: Decimal
    line20_interest_other_states: Decimal
    line22_ptet_addback: Decimal
    line34_deduction: Decimal
    line39_ny_tax_import: Decimal  # from the engine of record (DEC-77)
    line47a_nyc_tax_import: Decimal  # from the engine of record (DEC-77)
    payments: tuple[Decimal, ...]


@dataclass(frozen=True)
class It201:
    line33_ny_agi: Decimal
    line37_taxable: Decimal
    total_tax: Decimal
    total_payments: Decimal
    balance_due: Decimal
    overpayment: Decimal
    stamp: Stamp


def it201(i: It201Inputs) -> It201:
    """The derived lines, recomputed on every input change; NY and NYC tax are imports."""
    line33 = i.line19_federal_agi + i.line20_interest_other_states + i.line22_ptet_addback
    line37 = line33 - i.line34_deduction
    tax = i.line39_ny_tax_import + i.line47a_nyc_tax_import
    paid = sum(i.payments, Decimal(0))
    due = tax - paid
    return It201(
        line33,
        line37,
        tax,
        paid,
        max(due, Decimal(0)),
        max(-due, Decimal(0)),
        stamp("worksheets.it201", {"inputs": i.__dict__}),
    )

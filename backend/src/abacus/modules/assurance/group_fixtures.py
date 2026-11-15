"""Harlow & Pike's FY2026 interim group figures for the A-09 stubs (A-09-T03; SPEC-658 AC-0.3,
AC-4.1, AC-4.2, AC-5.2, AC-5.3; DEC-5039).

The AUD-33 a table (entity columns, eliminations E1a…E5, consolidated), the AUD-32 d interim
debits, the AUD-31 account counts and the AUD-34 materiality and coverage figures, transcribed
from the handoff (AUD-31 to AUD-34 spec.md, blueprint §9.2). Every derived figure (totals, Dr =
Cr, Level 2, coverage, component PM percentages) is computed here by code, never typed; the
consolidation engine (A-09-T13, `ledger/compute/consolidation.py`) replaces these computations
and the goldens (`tests/golden/consolidation/`) pin them. Signs: debits positive, credits
negative.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

D = Decimal
ENTITIES: Final = ("holdings", "operating", "manufacturing", "distribution", "real_estate")
NAMES: Final = {
    "holdings": "Harlow & Pike Holdings, Inc.",
    "operating": "Harlow & Pike Operating Co.",
    "manufacturing": "Harlow & Pike Manufacturing, Inc.",
    "distribution": "Harlow & Pike Distribution, Inc.",
    "real_estate": "Harlow & Pike Real Estate, LLC",
}
# (entity, level, parent)
STRUCTURE: Final = (
    ("holdings", 1, None),
    ("operating", 2, "holdings"),
    ("manufacturing", 3, "operating"),
    ("distribution", 3, "operating"),
    ("real_estate", 2, "holdings"),
)
Section = Literal["assets", "liabilities_equity", "income"]
_ = None
# (caption, section, holdings, operating, manufacturing, distribution, real estate)
ROWS: Final[tuple[tuple[str, Section, tuple[Decimal | None, ...]], ...]] = (
    ("Cash", "assets", (D(2_600_000), _, D(1_800_000), D(1_400_000), D(300_000))),
    ("Accounts receivable", "assets", (_, _, D(7_200_000), D(4_100_000), _)),
    ("Intercompany receivable", "assets", (_, _, D(2_400_000), _, _)),
    ("Inventory", "assets", (_, _, D(9_600_000), D(6_300_000), _)),
    (
        "Property, plant & equipment, net",
        "assets",
        (_, _, D(8_400_000), D(1_200_000), D(8_100_000)),
    ),
    ("Investment in Operating Co.", "assets", (D(20_000_000), _, _, _, _)),
    ("Investment in Real Estate", "assets", (D(6_000_000), _, _, _, _)),
    ("Investment in Manufacturing", "assets", (_, D(14_000_000), _, _, _)),
    ("Investment in Distribution", "assets", (_, D(6_000_000), _, _, _)),
    ("Accounts payable", "liabilities_equity", (_, _, D(-4_600_000), D(-2_300_000), _)),
    ("Intercompany payable", "liabilities_equity", (_, _, _, D(-2_400_000), _)),
    ("Accrued liabilities", "liabilities_equity", (D(-400_000), _, D(-1_500_000), D(-600_000), _)),
    ("Mortgage note", "liabilities_equity", (_, _, _, _, D(-1_200_000))),
    ("Term loan", "liabilities_equity", (D(-9_000_000), _, _, _, _)),
    (
        "Common stock / contributed capital",
        "liabilities_equity",
        (D(-12_000_000), D(-20_000_000), D(-14_000_000), D(-6_000_000), D(-6_000_000)),
    ),
    (
        "Retained earnings 1/1/2026",
        "liabilities_equity",
        (D(-9_360_000), _, D(-5_900_000), D(-100_000), D(-300_000)),
    ),
    ("Net sales — third party", "income", (_, _, D(-42_000_000), D(-31_000_000), _)),
    ("Net sales — intercompany", "income", (_, _, D(-18_000_000), _, _)),
    ("Rental income — intercompany", "income", (_, _, _, _, D(-1_200_000))),
    ("Cost of goods sold", "income", (_, _, D(45_600_000), D(24_800_000), _)),
    ("Rent expense — intercompany", "income", (_, _, D(1_200_000), _, _)),
    ("Operating expenses", "income", (D(1_800_000), _, D(9_800_000), D(4_600_000), D(260_000))),
    ("Interest expense", "income", (D(360_000), _, _, _, D(40_000))),
)

# Eliminations: (code, level, description, lines as (caption, debit amount, credit amount)).
ELIMINATIONS: Final = (
    (
        "E1a",
        2,
        "Investment in subsidiaries vs contributed capital",
        (
            ("Common stock / contributed capital", D(20_000_000), D(0)),
            ("Investment in Manufacturing", D(0), D(14_000_000)),
            ("Investment in Distribution", D(0), D(6_000_000)),
        ),
    ),
    (
        "E1b",
        1,
        "Investment in subsidiaries vs contributed capital",
        (
            ("Common stock / contributed capital", D(26_000_000), D(0)),
            ("Investment in Operating Co.", D(0), D(20_000_000)),
            ("Investment in Real Estate", D(0), D(6_000_000)),
        ),
    ),
    (
        "E2",
        2,
        "Intercompany sales, Manufacturing → Distribution",
        (
            ("Net sales — intercompany", D(18_000_000), D(0)),
            ("Cost of goods sold", D(0), D(18_000_000)),
        ),
    ),
    (
        "E3",
        2,
        "Unrealized profit in Distribution's ending inventory",
        (
            ("Cost of goods sold", D(240_000), D(0)),
            ("Inventory", D(0), D(240_000)),
        ),
    ),
    (
        "E4",
        2,
        "Intercompany balances",
        (
            ("Intercompany payable", D(2_400_000), D(0)),
            ("Intercompany receivable", D(0), D(2_400_000)),
        ),
    ),
    (
        "E5",
        1,
        "Intercompany rent, Real Estate → Manufacturing",
        (
            ("Rental income — intercompany", D(1_200_000), D(0)),
            ("Rent expense — intercompany", D(0), D(1_200_000)),
        ),
    ),
)

ACCOUNTS_BY_ENTITY: Final = {
    "holdings": 32,
    "operating": 8,
    "manufacturing": 98,
    "distribution": 76,
    "real_estate": 30,
}
MAPPING_SPLIT: Final = {"prior_year": 201, "number_range": 25, "description": 12}  # 238 mapped
GROUP_MATERIALITY: Final = (D(4_800_000), D(5))  # forecast income before taxes, percent
COMPONENT_PMS: Final = {
    "manufacturing": D(135_000),
    "distribution": D(105_000),
    "real_estate": D(54_000),
    "holdings": D(90_000),
}
FULL_SCOPE: Final = ("manufacturing", "distribution")
SPECIFIC_PROCEDURES: Final = ("real_estate", "holdings")


def _z(v: Decimal | None) -> Decimal:
    return v if v is not None else D(0)


def entity_column(entity: str) -> dict[str, Decimal]:
    i = ENTITIES.index(entity)
    return {caption: _z(values[i]) for caption, _section, values in ROWS}


def eliminations_column(level: int | None = None) -> dict[str, Decimal]:
    """Net debit per caption from the eliminations at `level` (all levels when None)."""
    out: dict[str, Decimal] = {caption: D(0) for caption, _s, _v in ROWS}
    for _code, lvl, _desc, lines in ELIMINATIONS:
        if level is None or lvl == level:
            for caption, debit, credit in lines:
                out[caption] += debit - credit
    return out


def total_assets(column: dict[str, Decimal]) -> Decimal:
    return sum((column[c] for c, s, _v in ROWS if s == "assets"), D(0))


def net_income(column: dict[str, Decimal]) -> Decimal:
    """Income shown positive (the memo row): the negative of the income-statement net debit."""
    return -sum((column[c] for c, s, _v in ROWS if s == "income"), D(0))


def consolidated(level: int = 1) -> dict[str, Decimal]:
    """Level 1: every entity plus every elimination. Level 2 (Operating Co.): Operating,
    Manufacturing and Distribution plus the Level 2 eliminations."""
    members = ENTITIES if level == 1 else ("operating", "manufacturing", "distribution")
    out = {c: D(0) for c, _s, _v in ROWS}
    for e in members:
        for c, v in entity_column(e).items():
            out[c] += v
    for c, v in eliminations_column(None if level == 1 else 2).items():
        out[c] += v
    return out


def eliminations_total() -> tuple[Decimal, Decimal]:
    debit = sum((d for _c, _l, _x, lines in ELIMINATIONS for _cap, d, _cr in lines), D(0))
    credit = sum((cr for _c, _l, _x, lines in ELIMINATIONS for _cap, _d, cr in lines), D(0))
    return debit, credit


def interim_debits(entity: str) -> Decimal:
    """AUD-32 d's total debits per entity (the debit side of its interim TB)."""
    return sum((v for v in entity_column(entity).values() if v > 0), D(0))


def group_materiality() -> tuple[Decimal, Decimal, Decimal]:
    base, rate = GROUP_MATERIALITY
    overall = (base * rate / 100).quantize(D(1), rounding=ROUND_HALF_UP)
    pm = (overall * D("0.75")).quantize(D(1), rounding=ROUND_HALF_UP)
    ct = (overall * D("0.05")).quantize(D(1), rounding=ROUND_HALF_UP)
    return overall, pm, ct


def coverage() -> tuple[Decimal, Decimal, Decimal]:
    """Total assets after eliminations by entity attribution: (full scope, specific, total)."""
    attributed = {
        "manufacturing": D(27_000_000),
        "distribution": D(12_760_000),
        "real_estate": D(8_400_000),
        "holdings": D(2_600_000),
    }
    full = sum((attributed[e] for e in FULL_SCOPE), D(0))
    specific = sum((attributed[e] for e in SPECIFIC_PROCEDURES), D(0))
    return full, specific, total_assets(consolidated(1))

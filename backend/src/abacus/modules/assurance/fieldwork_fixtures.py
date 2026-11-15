"""A-08's seed-derived typed fixtures for the stub contracts (A-08-T05; SPEC-657 AC-0.4, AC-0.5).

Granite Peak's JE criteria (as entry-reference sets whose union code counts), its 14 analytics
lines (AUD-13 a) and the confirmation coverage line (AUD-14), and Lakeshore's SSARS review lines
(AUD-26 a), typed with the contract models. Figures are the handoff's (AUD-12, AUD-13, AUD-14,
AUD-26 spec.md); every derived figure (unique hits, change, change %, over, tallies, coverage) is
computed here by code, never typed. The real values come from the Brightwater Hale scenario
(A-08-T08) and the engines (A-08-T10, T20); these fixtures pin the shapes and the footings the
consumer tests and the front end's fixture mode read.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from abacus.modules.assurance.analytics_contract import TalliesOut
from abacus.modules.assurance.confirmations_contract_models import ConfirmationCoverageOut

_HUNDRED: Final = Decimal(100)
_TENTH: Final = Decimal("0.1")

# --- JE criteria (AUD-12 a): entry sets so the union is code's -----------------------------------


def _refs(first: int, last: int) -> frozenset[str]:
    return frozenset(f"JE-26-{n:05d}" for n in range(first, last + 1))


# Synthetic entry references with the seed's hit counts and overlaps (the scenario's own entries
# arrive with A-08-T08): weekend/holiday 142, round 38 (12 also weekend), post-close 61, manual by
# senior management 17 (10 also post-close), keywords 9 (all also manual).
JE_CRITERIA_HITS: Final[dict[str, frozenset[str]]] = {
    "weekend_holiday": _refs(1, 142),
    "round_amount": _refs(131, 168),
    "post_close": _refs(169, 229),
    "manual_by_role": _refs(220, 236),
    "keywords": _refs(228, 236),
}


def unique_flagged(
    hits: dict[str, frozenset[str]], unavailable: frozenset[str] = frozenset()
) -> int:
    """The unique count: the union of the available criteria's hits (P-58 excludes the rest)."""
    union: set[str] = set()
    for key, refs in hits.items():
        if key not in unavailable:
            union |= refs
    return len(union)


# --- analytics -----------------------------------------------------------------------------------


def pct(change: Decimal, base: Decimal) -> Decimal:
    """Change % to one decimal place, half up (the statement grammar's)."""
    return (change / base * _HUNDRED).quantize(_TENTH, rounding=ROUND_HALF_UP)


def over(
    change: Decimal, base: Decimal, threshold_pct: Decimal, threshold_amount: Decimal
) -> bool:
    """The dual threshold: |Δ%| ≥ pct **and** |Δ$| ≥ amount (A-08 F5)."""
    return abs(pct(change, base)) >= threshold_pct and abs(change) >= threshold_amount


# (caption, FY2026, FY2025, explained?) for the 14 evaluated lines; subtotals are derived.
GRANITE_PEAK_LINES: Final[tuple[tuple[str, int, int, bool | None], ...]] = (
    ("Revenue", 48_600_000, 44_900_000, None),
    ("Cost of goods sold", 29_160_000, 26_490_000, False),
    ("Operating expenses", 15_820_000, 14_960_000, None),
    ("Interest expense", 520_000, 410_000, None),
    ("Cash", 2_140_000, 2_610_000, True),
    ("Accounts receivable, net", 5_860_000, 4_720_000, True),
    ("Inventory, net", 11_420_000, 9_180_000, False),
    ("PP&E, net", 6_380_000, 6_050_000, None),
    ("Other assets", 610_000, 640_000, None),
    ("Accounts payable", 4_180_000, 3_310_000, True),
    ("Accrued liabilities", 1_630_000, 1_540_000, None),
    ("Revolver — Front Range Bank", 6_500_000, 4_900_000, True),
    ("Term loan", 3_200_000, 3_800_000, True),
    ("Stockholders' equity", 10_900_000, 9_650_000, True),
)
GRANITE_PEAK_THRESHOLD: Final = (Decimal(10), Decimal(116_250))  # PM = 155,000 x 75%

LAKESHORE_REVENUE: Final = (
    ("Contributions", 2_840_000, 2_610_000),
    ("Grants", 1_120_000, 1_480_000),
    ("Other revenue", 214_000, 198_000),
)
LAKESHORE_EXPENSES: Final = (
    ("Program services", 3_210_000, 3_050_000),
    ("Management and general", 486_000, 471_000),
    ("Fundraising", 318_000, 342_000),
)
LAKESHORE_THRESHOLD: Final = (Decimal(10), Decimal(50_000))
LAKESHORE_NET_ASSETS: Final = (4_920_000, 4_760_000)


def tallies(
    lines: tuple[tuple[str, int, int, bool | None], ...], threshold: tuple[Decimal, Decimal]
) -> TalliesOut:
    flagged = [
        explained
        for _, cy, py, explained in lines
        if over(Decimal(cy - py), Decimal(py), *threshold)
    ]
    return TalliesOut(
        lines=len(lines),
        over_threshold=len(flagged),
        explained=sum(1 for e in flagged if e is True),
        unexplained=sum(1 for e in flagged if e is False),
        tb_balanced=True,
    )


def lakeshore_over() -> list[str]:
    rows = (*LAKESHORE_REVENUE, *LAKESHORE_EXPENSES)
    return [c for c, cy, py in rows if over(Decimal(cy - py), Decimal(py), *LAKESHORE_THRESHOLD)]


# --- confirmations coverage (AUD-14) -------------------------------------------------------------

AR_POPULATION: Final = Decimal("5860000.00")
# C2 Summit Trail, C3 Alpine Ridge, C4 Canyon Basecamp (C1 is the bank).
AR_SENT: Final = (Decimal("412600.00"), Decimal("286900.00"), Decimal("198450.00"))
# Confirmed: Summit Trail agrees; Alpine Ridge confirms 282,600.00 (CM-6281 reconciles 4,300.00).
AR_CONFIRMED: Final = (Decimal("412600.00"), Decimal("282600.00"))
AR_DIFFERENCES: Final = (Decimal("4300.00"),)
CLEARLY_TRIVIAL: Final = Decimal("7750.00")


def coverage() -> ConfirmationCoverageOut:
    sent = sum(AR_SENT, Decimal("0.00"))
    return ConfirmationCoverageOut(
        population_total=AR_POPULATION,
        sent_total=sent,
        sent_pct=pct(sent, AR_POPULATION),
        confirmed_total=sum(AR_CONFIRMED, Decimal("0.00")),
        differences_total=sum(AR_DIFFERENCES, Decimal("0.00")),
        clearly_trivial=CLEARLY_TRIVIAL,
    )

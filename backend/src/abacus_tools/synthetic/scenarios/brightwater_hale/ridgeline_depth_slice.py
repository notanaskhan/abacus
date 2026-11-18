"""The Brightwater Hale Ridgeline depth slice (T-06-T22; TASK-8635; T-06 §5.3; DEC-5635):
Ridgeline Property Partners, LP's 2025 Form 1065 at E0 (Mon Sep 14, 2026, 9:24 AM CT), for the
TXP-03 depreciation register, TXP-08 basis, TXP-09 states and PTET and the TXP-10 issue badge
(DF-34: 11, then 10 after TXP-10 d, then 9 after TXP-09 e; never "10" twice).

Every name, date and figure is the TXP-03, TXP-08, TXP-09 and TXP-10 handoffs' (spec.md rows).
Totals, shares, PTET and differences are computed here by code from those rows (ADR-050), never
typed, so a changed row fails the tallies in `tests/unit/synthetic/test_t06t22_ridgeline_depth.py`.
No database code: the service-API load under kernel.clock follows the T-06 service tasks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal
from zoneinfo import ZoneInfo

D = Decimal
CT: Final = ZoneInfo("America/Chicago")
E0: Final = datetime(2026, 9, 14, 9, 24, tzinfo=CT)
BONUS_CUTOFF: Final = date(2025, 1, 19)  # 100% after, 40% before (TXP-03 note row)
LARIMER_BINDING_CONTRACT: Final = date(2025, 2, 3)  # TXP-03 c, matched at 10:12 AM
PTET_PAID: Final = date(2026, 3, 12)


@dataclass(frozen=True)
class Asset:
    name: str
    site: str
    placed: str  # as the register shows it
    cost: Decimal
    life: str
    method: str
    convention: str
    bonus_pct: int | None
    prior_depreciation: Decimal
    depreciation_2025: Decimal
    flag: str | None = None


# TXP-03 a, the register's rows.
REGISTER: Final = (
    Asset("Elm Street building", "Chicago, IL", "Apr 2018", D("6240000"),
          "39-yr nonresidential", "SL", "MM", None, D("1073333"), D("160000")),
    Asset("Larimer Lofts", "Denver, CO", "Jun 2021", D("4950000"),
          "27.5-yr residential", "SL", "MM", None, D("637500"), D("180000")),
    Asset("Bergen Street", "Brooklyn, NY", "Sep 2023", D("3850000"),
          "27.5-yr residential", "SL", "MM", None, D("180834"), D("140000")),
    Asset("Elm Street roof replacement", "Chicago, IL", "Mar 10, 2025", D("468000"),
          "39-yr nonresidential", "SL", "MM", None, D("0"), D("9500"),
          "Contractor invoice and placed-in-service date requested"),
    Asset("Larimer parking lot resurfacing", "Denver, CO", "Feb 14, 2025", D("180000"),
          "15-yr land improvement", "150DB", "HY", 100, D("0"), D("180000"), "Check"),
    Asset("Bergen Street appliances", "Brooklyn, NY", "Aug 2025", D("64000"),
          "5-yr personal property", "200DB", "HY", 100, D("0"), D("64000")),
)  # fmt: skip
# TXP-03 b, land per site (not depreciable).
LAND: Final = {"Elm Street": D("1400000"), "Larimer": D("1300000"), "Bergen": D("900000")}
# The Form 8825 property each asset depreciates under (TXP-03 a, pane a).
PROPERTY_OF: Final = {
    "Elm Street building": "Elm Street, Chicago",
    "Elm Street roof replacement": "Elm Street, Chicago",
    "Larimer Lofts": "Larimer Lofts, Denver",
    "Larimer parking lot resurfacing": "Larimer Lofts, Denver",
    "Bergen Street": "Bergen Street, Brooklyn",
    "Bergen Street appliances": "Bergen Street, Brooklyn",
}
LARIMER_INVOICE: Final = "Larimer_Parking_Invoice_Feb2025.pdf"


def register_totals() -> dict[str, Decimal]:
    cost = sum((a.cost for a in REGISTER), D("0"))
    prior = sum((a.prior_depreciation for a in REGISTER), D("0"))
    current = sum((a.depreciation_2025 for a in REGISTER), D("0"))
    return {"cost": cost, "prior": prior, "current": current, "accumulated": prior + current}


def depreciation_by_property() -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for a in REGISTER:
        prop = PROPERTY_OF[a.name]
        out[prop] = out.get(prop, D("0")) + a.depreciation_2025
    return out


def bonus_check(binding_contract: date | None) -> Literal["check", "tie"]:
    """TXP-03 a vs c: the Larimer 100% bonus holds only on a contract after the cutoff."""
    return "tie" if binding_contract is not None and binding_contract > BONUS_CUTOFF else "check"


@dataclass(frozen=True)
class PartnerBasis:
    partner: str
    role: Literal["GP", "LP"]
    tax_capital: Decimal
    share_752: Decimal
    outside: Decimal  # as the reconciliation shows it (Pell Street II's carries its premium)

    @property
    def inside_share(self) -> Decimal:
        return self.tax_capital + self.share_752

    @property
    def off(self) -> Decimal:
        return self.outside - self.inside_share


# TXP-08 a: basis by partner at 12/31/2025 (tax capital, §752 share, outside basis).
BASIS: Final = (
    PartnerBasis("Ridgeline GP LLC", "GP", D("93124"), D("220966"), D("314090")),
    PartnerBasis("Meera Shah", "LP", D("2529356"), D("4198354"), D("6727710")),
    PartnerBasis("Pell Street Ventures LLC", "LP", D("1996860"), D("3314490"), D("5311350")),
    PartnerBasis("Pell Street II LLC", "LP", D("332810"), D("552415"), D("913820")),
    PartnerBasis("Jonah Feld", "LP", D("1914050"), D("2762075"), D("4676125")),
)
PELL_II_PRICE: Final = D("360000")
PELL_II_ACQUIRED_SHARE: Final = D("331405")  # the premium is price minus this (TXP-08 note)


@dataclass(frozen=True)
class StatePtet:
    state: str
    property: str
    numerator: Decimal
    rate_pct: Decimal
    form: str
    paid: date | None


# TXP-09 a: rental income sourced by property location; PTET elected in all three.
STATES: Final = (
    StatePtet("IL", "Elm Street, Chicago", D("566536"), D("4.95"), "IL-1065 (PTE tax)", PTET_PAID),
    StatePtet("CO", "Larimer Lofts, Denver", D("387954"), D("4.40"), "DR 0106 (SALT parity)",
              PTET_PAID),
    StatePtet("NY", "Bergen Street, Brooklyn", D("277110"), D("6.85"),
              "PTET annual return (online)", PTET_PAID),
)  # fmt: skip
# TXP-09 a pane 7: each partner's PTET credit by state (IL, CO, NY).
PTET_CREDITS: Final = {
    "Ridgeline GP LLC": (D("561"), D("341"), D("380")),
    "Meera Shah": (D("10657"), D("6486"), D("7213")),
    "Pell Street Ventures LLC": (D("9114"), D("5548"), D("6169")),
    "Pell Street II LLC": (D("701"), D("427"), D("474")),
    "Jonah Feld": (D("7011"), D("4268"), D("4746")),
}


def apportionment(states: tuple[StatePtet, ...] = STATES) -> dict[str, Decimal]:
    base = sum((s.numerator for s in states), D("0"))
    return {s.state: (s.numerator * 100 / base).quantize(D("0.1"), ROUND_HALF_UP) for s in states}


def ptet(states: tuple[StatePtet, ...] = STATES) -> dict[str, Decimal]:
    return {
        s.state: (s.numerator * s.rate_pct / 100).quantize(D("1"), ROUND_HALF_UP) for s in states
    }


def ny_gap_variant() -> tuple[StatePtet, ...]:
    """TXP-09 c: the NY payment missing (Not paid + flag; PAID reads 2 of 3)."""
    return tuple(
        StatePtet(s.state, s.property, s.numerator, s.rate_pct, s.form, None)
        if s.state == "NY"
        else s
        for s in STATES
    )


# TXP-10 a: the 11 issues that block the return (5 waiting on the client, 6 review points).
IssueKind = Literal["waiting_on_client", "review_point"]
ISSUES: Final[tuple[tuple[str, IssueKind], ...]] = (
    ("§754 election: partners' decision and support for Pell Street II's $360,000 purchase price",
     "waiting_on_client"),
    ("Pell Street transfer (6/30/2025): assignment agreement and transfer-date balances",
     "waiting_on_client"),
    ("Elm Street roof replacement: contractor invoice and placed-in-service date",
     "waiting_on_client"),
    ("Bergen Street tenant security deposit ledger supporting 121,800", "waiting_on_client"),
    ("December real estate tax installment: county bill supporting the 18,500 accrual",
     "waiting_on_client"),
    ("Tax-exempt interest 6,200 omitted from the capital rollforward", "review_point"),
    ("Larimer parking lot: 100% bonus requires acquisition after Jan 19, 2025", "review_point"),
    ("§743(b) placeholder 28,595 pending the §754 decision", "review_point"),
    ("Apportionment by property: IL 46.0% · CO 31.5% · NY 22.5%", "review_point"),
    ("Nonrecourse mortgage shared by year-end profit percentages under §752", "review_point"),
    ("Schedules K-2/K-3 required — domestic filing exception unavailable", "review_point"),
)  # fmt: skip
# DF-34: the two resolutions that move the badge, in order (TXP-10 d at 9:52, then TXP-09 e).
RESOLUTIONS: Final = (
    ("txp10_d", ISSUES[5][0], datetime(2026, 9, 14, 9, 52, tzinfo=CT)),
    ("txp09_e", ISSUES[8][0], datetime(2026, 9, 14, 10, 30, tzinfo=CT)),
)


def badge_after(steps: int) -> int:
    resolved = {title for _, title, _ in RESOLUTIONS[:steps]}
    return sum(1 for title, _ in ISSUES if title not in resolved)

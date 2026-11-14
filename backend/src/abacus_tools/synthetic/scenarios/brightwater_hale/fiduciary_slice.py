"""The trusts-and-estates slice, part 1 (T-07-T08; TASK-8022; T-07 §5.3; SPEC-656 AC-15.6;
DEC-5011): the Calloway Family Trust 2025 Form 1041 and the Estate of Walter Thornbury Form 706,
as the figures the seed loads and every TXT screen reads.

Every figure here is the epic's and the handoff's (T-07 §3, TXT-01 to TXT-04), never typed fresh
elsewhere: the footing tests (`tests/unit/synthetic/test_t07t08_fiduciary_slice.py`) and the
FE's fixture seed read these constants. The firm, not the names, is flagged synthetic (P-37);
Calloway holds signed `use` and `ai_disclosure` consents (`consents_7216.py`, Feb 9, 2026),
Thornbury's are not requested, so no agent runs on the estate.

Part 2 loads these through tax's services once they exist (T-07-T12 instrument and determinations,
T-07-T16 FAI lines, expenses and distributions, T-07-T22 the estate, T-07-T23 the election), as
an opt-in slice after `tax_board`; the 11-page agreement's text layer and its scanned page 4 come
from P-11-T28's corpus (`scanned_corpus.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final, Literal

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT

D = Decimal
CALLOWAY_TRUST: Final = "Calloway Family Trust"
THORNBURY_ESTATE: Final = "Estate of Walter Thornbury"
AGREEMENT_FILE: Final = "Calloway_Family_Trust_Agreement_2011.pdf"
AGREEMENT_PAGES: Final = 11
SCANNED_PAGE: Final = 4
FLAGS: Final = ("tax.fiduciary_workpapers", "tax.fiduciary_k1_release", "tax.estate_workpapers")

# Named snapshots (T-07 §5.3): E0, the release days, the estate day and the election day.
E0: Final = datetime(2026, 9, 14, 9, 24, tzinfo=CT)
SNAPSHOTS: Final = {
    "e0": E0,
    "ready_to_release": datetime(2026, 9, 28, 9, 24, tzinfo=CT),
    "released": datetime(2026, 9, 29, 18, 40, tzinfo=CT),
    "estate": datetime(2026, 10, 19, 9, 24, tzinfo=CT),  # DV-10
    "election": datetime(2027, 3, 1, 9, 24, tzinfo=CT),  # DV-4 (inferred)
}

# --- Calloway Family Trust (TXT-01, TXT-02, TXT-03) ----------------------------------------------

TRUSTEE: Final = "Eleanor Calloway"
BENEFICIARIES: Final = ("Nora Calloway", "Theo Calloway")
CLAUSES: Final = (
    "Art. I",
    "Art. II",
    "Art. III(a)",
    "Art. III(b)",
    "Art. IV(a)",
    "Art. IV(b)",
    "Art. V(c)",
)
# The seven determinations and the clause each rests on (TXT-01 a; six chips, AC-1.4).
DeterminationKey = Literal[
    "grantor_status",
    "trust_type",
    "fai_definition",
    "trustee_fees",
    "principal_invaded",
    "exemption",
    "election_65_day",
]
DETERMINATIONS: Final[dict[DeterminationKey, tuple[str, str | None]]] = {
    "grantor_status": ("non_grantor", "Art. I"),
    "trust_type": ("complex", "Art. III(a)"),
    "fai_definition": ("gains_to_principal", "Art. II"),
    "trustee_fees": ("principal", "Art. V(c)"),
    "principal_invaded": ("no", "Art. IV(b)"),
    "exemption": ("100", None),
    "election_65_day": ("not_made", None),
}
READ_ON: Final = date(2026, 9, 3)  # "Read by Accrued Agent Sep 3"
ADOPTED_ON: Final = date(2026, 9, 4)  # L1 by Kevin Osei
APPROVED_ON: Final = date(2026, 9, 14)  # L3 by Samuel Ito (TXT-01 b)


@dataclass(frozen=True)
class FaiLine:
    kind: Literal["interest", "ordinary_dividends", "qualified_dividends"]
    amount: Decimal
    parent: str | None = None


@dataclass(frozen=True)
class Distribution:
    beneficiary: str
    paid_on: date
    amount: Decimal
    source: Literal["income", "principal"] = "income"
    clause: str | None = None


FAI_LINES: Final = (
    FaiLine("interest", D("107500.00")),
    FaiLine("ordinary_dividends", D("322500.00")),
    FaiLine("qualified_dividends", D("258000.00"), parent="ordinary_dividends"),
)
TRUSTEE_FEES: Final = D("30000.00")  # charged to principal, deductible, Art. V(c)
DISTRIBUTIONS: Final = (
    Distribution("Nora Calloway", date(2025, 6, 30), D("80000.00")),
    Distribution("Nora Calloway", date(2025, 12, 15), D("80000.00")),
    Distribution("Theo Calloway", date(2025, 12, 15), D("80000.00")),
)
# TXT-02 d: Theo's Dec 15 distribution corrected after L2 on version 3.
CHANGED_THEO_DEC_15: Final = D("100000.00")
# TXT-01 c: 25,000 of principal for Theo's tuition under Art. IV(b) (HEMS).
SCENARIO_PRINCIPAL: Final = Distribution(
    "Theo Calloway", date(2025, 12, 15), D("25000.00"), source="principal", clause="Art. IV(b)"
)
ELECTION_TY2026: Final = (date(2027, 2, 20), D("50000.00"))  # TXT-03 c

# The figures the engine must reproduce (T-07-T09 goldens; TXT-02 a, TXT-03 a).
CALLOWAY: Final = {
    "fai": D("430000.00"),
    "fees_to_interest": D("7500.00"),
    "fees_to_dividends": D("22500.00"),
    "dni": D("400000.00"),
    "dni_interest": D("100000.00"),
    "dni_dividends": D("300000.00"),
    "dni_qualified": D("240000.00"),
    "idd": D("240000.00"),
    "retained_dni": D("160000.00"),
    "exemption": D("100.00"),
    "taxable_income": D("159900.00"),
    "fai_not_distributed": D("190000.00"),
}
# (beneficiary, DNI allocated, box 1, box 2a, box 2b)
ALLOCATIONS: Final = (
    ("Nora Calloway", D("160000.00"), D("40000.00"), D("120000.00"), D("96000.00")),
    ("Theo Calloway", D("80000.00"), D("20000.00"), D("60000.00"), D("48000.00")),
)
CHANGED: Final = {  # TXT-02 d, version 4
    "distributions": D("260000.00"),
    "idd": D("260000.00"),
    "retained_dni": D("140000.00"),
    "taxable_income": D("139900.00"),
}
# Theo on version 4: (DNI allocated, box 1, box 2a, box 2b).
CHANGED_THEO: Final = (D("100000.00"), D("25000.00"), D("75000.00"), D("60000.00"))
SCENARIO: Final = {  # TXT-01 c
    "distributions": D("265000.00"),
    "nora": D("160000.00"),
    "theo": D("105000.00"),
    "retained": D("135000.00"),
}

# --- Estate of Walter Thornbury (TXT-04) ---------------------------------------------------------

DATE_OF_DEATH: Final = date(2026, 2, 2)
EXECUTOR: Final = "Paul Thornbury"
PREDECEASED_SPOUSE: Final = "Helen Thornbury"
DSUE: Final = D("3000000.00")


@dataclass(frozen=True)
class EstateAsset:
    schedule: Literal["A", "B", "C", "D", "F", "I"]
    description: str
    dod_value: Decimal
    avd_value: Decimal
    basis_to_1041: Decimal | None
    status: Literal["valued", "gathering_support"]


ESTATE_ASSETS: Final = (
    EstateAsset("A", "Residence", D("3850000.00"), D("3790000.00"), D("3850000.00"), "valued"),
    EstateAsset(
        "B", "Harborline brokerage", D("8240000.00"), D("7965000.00"), D("8240000.00"), "valued"
    ),
    EstateAsset("C", "Cash", D("412000.00"), D("412000.00"), D("412000.00"), "valued"),
    EstateAsset(
        "D",
        "Life insurance (Form 712 requested)",
        D("1000000.00"),
        D("1000000.00"),
        None,
        "gathering_support",
    ),
    EstateAsset(
        "F",
        "Tangible personal property",
        D("186000.00"),
        D("186000.00"),
        D("186000.00"),
        "gathering_support",
    ),
    EstateAsset("I", "IRA (IRD; no step-up)", D("2712000.00"), D("2640000.00"), None, "valued"),
)
ESTATE_DEDUCTIONS: Final = (
    ("J_funeral", D("28500.00"), "none"),
    ("J_administration", D("240000.00"), "s642g_pending"),
    ("K", D("131500.00"), "none"),
    ("O", D("500000.00"), "none"),
)
# (year, donee, asset, gift, annual exclusion, form 709 filed on)
GIFTS: Final = (
    (2023, "Paul Thornbury", "Cash", D("1217000.00"), D("17000.00"), date(2024, 4, 15)),
)
ANNUAL_EXCLUSIONS: Final = {
    2023: D("17000.00"),
    2024: D("18000.00"),
    2025: D("19000.00"),
    2026: D("19000.00"),
}
THORNBURY: Final = {
    "gross_estate": D("16400000.00"),
    "avd_total": D("15993000.00"),
    "basis_to_1041": D("12688000.00"),
    "deductions": D("900000.00"),
    "taxable_estate": D("15500000.00"),
    "adjusted_taxable_gifts": D("1200000.00"),
    "tentative_base": D("16700000.00"),
    "tentative_tax": D("6625800.00"),
    "bea": D("15000000.00"),
    "applicable_exclusion": D("18000000.00"),
    "credit": D("7145800.00"),
    "without_dsue_credit": D("5945800.00"),
    "without_dsue_tax": D("680000.00"),
    "filing_threshold_test": D("17600000.00"),
}
DUE: Final = (date(2026, 11, 2), date(2027, 5, 3))  # 706 and the 4768 extension (AC-14.1)

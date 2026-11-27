"""The Brightwater Hale other-entity slice (T-06-T28; TASK-8723; T-06 §5.3; DEC-5717): Bluestem
Analytics, LLC's 2025 Form 1120-S (Accepted Mar 13, read-only), Ashford Manufacturing Co.'s 2025
Form 1120 provision (on the NetSuite seed) and Lakeshore Literacy Alliance's 990 (FYE June) for
TXP-13 a to c.

Every name and figure is the TXP-13 handoff's. The AAA end, the shareholder shares, the provision
and the ETR are computed here by the engines (E10, E11; ADR-050), never typed, so a changed row
fails `tests/unit/synthetic/test_t06t28_other_entities.py`. No database code: the service-API
load follows T-06-T42's other-entity service.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final

from abacus.modules.tax.api import provision_engine as e11
from abacus.modules.tax.api import s_corp_engine as e10

D = Decimal
BLUESTEM: Final = "Bluestem Analytics, LLC"
ASHFORD: Final = "Ashford Manufacturing Co."
LAKESHORE: Final = "Lakeshore Literacy Alliance"
BLUESTEM_ACCEPTED_ON: Final = date(2026, 3, 13)

# TXP-13 a: Schedule M-2 and the shareholder allocation (per share, per day; full year).
AAA_BEGIN: Final = D("1240000")
ORDINARY_INCOME: Final = D("860000")
INTEREST: Final = D("12400")
NONDEDUCTIBLE: Final = D("4200")
DISTRIBUTIONS: Final = D("620000")
SHAREHOLDERS: Final = {"Arjun Mehta": (70, 365), "Sunita Rao": (30, 365)}
# The handoff's rows per shareholder: ordinary income, interest, nondeductible, distributions.
ALLOCATION_ROWS: Final = {
    "Arjun Mehta": (D("602000"), D("8680"), D("2940"), D("434000")),
    "Sunita Rao": (D("258000"), D("3720"), D("1260"), D("186000")),
}

# TXP-13 b and b2: Ashford's provision and the variant 1,200 off.
ASHFORD_CURRENT: Final = D("2134650")
ASHFORD_DEFERRED: Final = D("122550")
ASHFORD_ETR_PCT: Final = D("28.9")
ASHFORD_B2_OFF: Final = D("1200")

# TXP-13 c: Lakeshore's Part IX, program ratio and public support.
LAKESHORE_PART_IX: Final = D("4014000")
LAKESHORE_PROGRAM_PCT: Final = D("80.0")
LAKESHORE_PUBLIC_SUPPORT_PCT: Final = D("87.4")


def bluestem_aaa() -> e10.AaaRoll:
    return e10.aaa_roll(
        AAA_BEGIN,
        income=ORDINARY_INCOME + INTEREST,
        losses=D("0"),
        nondeductible=NONDEDUCTIBLE,
        distributions=DISTRIBUTIONS,
    )


def bluestem_split(item: Decimal) -> dict[str, Decimal]:
    return e10.per_share_per_day(item, SHAREHOLDERS)


def ashford_provision() -> Decimal:
    return e11.provision(ASHFORD_CURRENT, ASHFORD_DEFERRED)


# --- T-06-T52 (DEC-6036): the frames' lines in the other-entity reads' shapes -----------------

# Ashford's computation: pre-tax book income, permanent differences, and the deferred inventory's
# temporary differences (bonus depreciation a DTL, accrued bonuses a DTA) at the blended rate.
ASHFORD_PRETAX: Final = D("7800000")
ASHFORD_PERMANENT: Final = D("120000")
ASHFORD_BLENDED: Final = D("28.5")
ASHFORD_DEFERRED_ITEMS: Final = (
    ("dtl", "Bonus depreciation in excess of book", D("640000"), D("182400")),
    ("dta", "Accrued bonuses not yet paid", D("210000"), D("-59850")),
)
ASHFORD_RECON: Final = (
    ("statutory", "Statutory federal", D("1638000"), D("21.0"), "rate"),
    ("state", "State, net of federal benefit", D("585000"), D("7.5"), "rate"),
    ("permanent", "Permanent differences", D("34200"), D("0.4"), "permanent"),
)
# Lakeshore's Part IX (FYE Jun 30, 2026): line, expense, total, program, M&G, fundraising. The
# compensation lines are allocated by the time study (their percentages are each line's split).
LAKESHORE_FYE: Final = date(2026, 6, 30)
PART_IX: Final = (
    ("5", "Compensation of current officers, directors, trustees and key employees",
     D("162000"), D("81000"), D("65000"), D("16000")),
    ("7", "Other salaries and wages", D("2248000"), D("1809000"), D("247000"), D("192000")),
    ("9", "Other employee benefits", D("361000"), D("283000"), D("47000"), D("31000")),
    ("10", "Payroll taxes", D("184000"), D("144000"), D("24000"), D("16000")),
    ("11c", "Fees for services — accounting", D("48000"), D("0"), D("48000"), D("0")),
    ("16", "Occupancy", D("396000"), D("340000"), D("34000"), D("22000")),
    ("24a", "Books and learning materials", D("412000"), D("412000"), D("0"), D("0")),
    ("24e", "All other expenses", D("203000"), D("141000"), D("21000"), D("41000")),
)  # fmt: skip
TIME_STUDY_LINES: Final = frozenset({"5", "7", "9", "10"})


def _pct(part: Decimal, whole: Decimal) -> str:
    return f"{(part * 100 / whole).quantize(D('0.1'))}"


def txp13_frames() -> dict[str, object]:
    """TXP-13 a, b, b2, c and c2 as the AAA, provision and functional-expense reads answer them
    (T-06-T52's additive lines). The figures foot by the engines and are asserted here."""
    roll = bluestem_aaa()
    m2 = {1: AAA_BEGIN, 2: ORDINARY_INCOME, 3: INTEREST, 4: D("0"), 5: NONDEDUCTIBLE}
    m2[6] = m2[1] + m2[2] + m2[3] - m2[4] - m2[5]
    m2[7] = DISTRIBUTIONS
    m2[8] = m2[6] - m2[7]
    if m2[8] != roll.ending:
        raise ValueError("Schedule M-2 line 8 is not E10's AAA ending")
    for i, rows in enumerate(zip(*ALLOCATION_ROWS.values(), strict=True)):
        if sum(rows) != (ORDINARY_INCOME, INTEREST, NONDEDUCTIBLE, DISTRIBUTIONS)[i]:
            raise ValueError("the shareholder allocation does not foot")
    temporary = sum((d if k == "dtl" else -d) for k, _l, d, _a in ASHFORD_DEFERRED_ITEMS)
    taxable = ASHFORD_PRETAX + ASHFORD_PERMANENT - temporary
    deferred = sum((a for *_x, a in ASHFORD_DEFERRED_ITEMS), D("0"))
    if deferred != ASHFORD_DEFERRED or ashford_provision() != sum(
        (a for _k, _d, a, _e, _c in ASHFORD_RECON), D("0")
    ):
        raise ValueError("Ashford's provision does not reconcile")
    totals = [sum((r[i] for r in PART_IX), D("0")) for i in range(2, 6)]
    if totals[0] != LAKESHORE_PART_IX or totals[0] != sum(totals[1:], D("0")):
        raise ValueError("Part IX does not foot")
    provision = {
        "current": f"{ASHFORD_CURRENT}", "deferred": f"{ASHFORD_DEFERRED}",
        "total": f"{ashford_provision()}", "effective_rate": f"{ASHFORD_ETR_PCT}",
        "pretax_book_income": f"{ASHFORD_PRETAX}", "permanent_total": f"{ASHFORD_PERMANENT}",
        "temporary_total": f"{-temporary}", "taxable_income": f"{taxable}",
        "blended_rate": f"{ASHFORD_BLENDED}",
        "recon_items": [
            {"key": k, "description": d, "amount": f"{a}", "rate_effect": f"{e}",
             "classification": c} for k, d, a, e, c in ASHFORD_RECON
        ],
        "deferred_items": [
            {"kind": k, "label": lb, "temporary_difference": f"{d}", "rate": f"{ASHFORD_BLENDED}",
             "amount": f"{a}"} for k, lb, d, a in ASHFORD_DEFERRED_ITEMS
        ],
    }  # fmt: skip
    return {
        "a": {
            "client": BLUESTEM,
            "accepted_on": BLUESTEM_ACCEPTED_ON.isoformat(),
            "aaa": f"{roll.ending}",
            "lines": [{"line_no": n, "aaa": f"{v}"} for n, v in sorted(m2.items())],
            "shareholders": [
                {
                    "name": name,
                    "pct": f"{SHAREHOLDERS[name][0]}",
                    "ordinary_income": f"{r[0]}",
                    "interest": f"{r[1]}",
                    "nondeductible": f"{r[2]}",
                    "distributions": f"{r[3]}",
                }
                for name, r in ALLOCATION_ROWS.items()
            ],
        },
        "b": {"client": ASHFORD, **provision},
        "b2_unclassified": f"{ASHFORD_B2_OFF}",
        "c": {
            "client": LAKESHORE,
            "fiscal_year_end": LAKESHORE_FYE.isoformat(),
            "program": f"{totals[1]}",
            "management": f"{totals[2]}",
            "fundraising": f"{totals[3]}",
            "total": f"{totals[0]}",
            "program_ratio": f"{LAKESHORE_PROGRAM_PCT}",
            "public_support": f"{LAKESHORE_PUBLIC_SUPPORT_PCT}",
            "lines": [
                {
                    "line": ln,
                    "label": lb,
                    "total": f"{t}",
                    "program": f"{p}",
                    "management": f"{m}",
                    "fundraising": f"{f}",
                    "basis": "time_study" if ln in TIME_STUDY_LINES else "direct",
                    "time_study": {
                        "program": _pct(p, t),
                        "management_general": _pct(m, t),
                        "fundraising": _pct(f, t),
                    }
                    if ln in TIME_STUDY_LINES
                    else None,
                }
                for ln, lb, t, p, m, f in PART_IX
            ],
        },
    }


__all__ = [
    "ALLOCATION_ROWS",
    "ASHFORD",
    "BLUESTEM",
    "LAKESHORE",
    "ashford_provision",
    "bluestem_aaa",
    "bluestem_split",
    "txp13_frames",
]

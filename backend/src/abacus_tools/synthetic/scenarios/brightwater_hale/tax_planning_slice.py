"""TAX-15's TY2025 planning portfolio (T-08-T32, TASK-9033; DEC-6038). Synthetic content for the
fixture export, never product code.

Daniel Reyes's queue at Mon Sep 14, 2026, 9:24 AM CT: nine of the 71 opportunities across his 58
clients (Open 4, Raised 1, Accepted 2, Declined 1, Not screened 1), the Feld donor-advised-fund
bunching selected with its rationale and two sources, the portfolio strip (58 to contact, $1.2M
estimated, talking points drafted, one consent-blocked) and Ferris's half-signed §7216 envelope
E17. The Feld figure is code's: 5,659 of extra deductions over two years at 32% is about 1,810.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Final

D = Decimal
FELD: Final = "Jonah & Claire Feld"
# The two-year arithmetic (TAX-15 a): the 0.5% floor paid once, not twice, plus 2027's standard
# deduction over itemizing without gifts.
FLOOR: Final = D("2990")
STANDARD_2027_GAIN: Final = D("2669")
BRACKET: Final = D("0.32")

# (title, client, sub, status, est. savings, rule, category)
ROWS: Final = (
    ("Bunch 2026–2027 gifts through a donor-advised fund", FELD, "est. 1,810 over 2 years",  # noqa: RUF001 -- the design's en dash
     "open", "1810", "charitable.daf_bunching", "Charitable giving"),
    ("Solo 401(k) for the consulting practice", "Meera Shah", "est. 8,225", "open", "8225",
     "retirement.solo_401k", "Retirement"),
    ("Dependent care FSA at the new 7,500 limit (2026)", "Marcus & Dana Whitley", "est. 1,650",
     "open", "1650", "benefits.dcfsa_limit", "Benefits"),
    ("Reasonable compensation review for the owner", "Copperleaf Coffee Roasters, Inc.",
     "risk reduction", "open", None, "scorp.reasonable_comp", "Compensation"),
    ("Section 754 election for the Pell Street II transfer", "Ridgeline Property Partners, LP",
     "§743(b) step-up 28,595 · waiting on Owen Calder", "raised", None,
     "partnership.section_754", "Elections"),
    ("Cost segregation study — Elm Street building (method change)",
     "Ridgeline Property Partners, LP", "project Scoping", "accepted", None,
     "depreciation.cost_seg", "Depreciation"),
    ("Amend 2025 for the missed Unit 3B mortgage interest and roof depreciation",
     "Daniel & Ruth Okafor", "3,203 (federal 2,708 + IL 495)", "accepted", "3203",
     "amendment.missed_items", "Amendments"),
    ("Qualified charitable distributions from the IRA", "Elena Varga",
     "not eligible until age 70½ (she is 68)", "declined", None, "retirement.qcd",
     "Charitable giving"),
    ("Roth conversion window", "Morgan & Kai Ferris",
     "§7216 consents (use · AI disclosure) half-signed — agents cannot use return "
     "information yet",
     "not_screened", None, "retirement.roth_window", "Retirement"),
)  # fmt: skip
FELD_RATIONALE: Final = (
    "The Felds give about 12,500 a year. Without gifts their itemized deductions would be 28,831 "
    "(SALT 10,591 + mortgage interest 18,240), below the 31,500 standard deduction. From 2026, "
    "itemizers also lose the first 0.5% of AGI in gifts — about 2,990 at this year's AGI of "
    "598,030. Giving two years of gifts (25,000) to a donor-advised fund in 2026 and taking the "
    "standard deduction in 2027 adds about 5,659 of deductions over the two years (the 2,990 "
    "floor is paid once, not twice, plus 2,669 more from the 2027 standard deduction): about "
    "1,810 of federal tax at 32%."
)
FELD_SOURCES: Final = (
    ("2025 Charitable Contributions Summary — Feld", "6 receipts"),
    ("Knowledge › Research: 'OBBBA individual changes for TY2026'",  # noqa: RUF001 -- the UI's crumb
     "Brightwater Hale tax research memo v2"),
)  # fmt: skip
FELD_TALKING_POINTS: Final = (
    "Your gifts stay the same; only the timing of the deduction changes.",
    "One contribution in 2026 covers 2026 and 2027 grants.",
    "We'll confirm the amount after your 2026 estimates in January.",
)
FERRIS_ENVELOPE: Final = "E17"
RIDGELINE_PROJECT: Final = "Ridgeline cost segregation & §754 analysis"


def tax15_portfolio() -> dict[str, object]:
    """TAX-15 a-f in the planning reads' shapes (queue rows, summary, the Feld detail)."""
    # "About 1,810": the federal tax on 5,659 at 32% (1,810.88), to the nearest ten.
    savings = ((FLOOR + STANDARD_2027_GAIN) * BRACKET / 10).quantize(
        D("1"), rounding=ROUND_HALF_UP
    ) * 10
    if savings != D("1810"):
        raise ValueError("the Feld estimate no longer computes to 1,810")
    counts = {s: sum(1 for r in ROWS if r[3] == s) for s in
              ("open", "raised", "accepted", "declined", "not_screened")}  # fmt: skip
    if sum(counts.values()) != len(ROWS):
        raise ValueError("the bands do not add up")
    return {
        "tax_year": 2025,
        "summary": {
            "clients_to_contact": 58,
            "est_savings": "1200000",
            "talking_points": "drafted",
            "consent_blocked": 1,
            "opportunities": 71,
            "clients": 58,
        },
        "rows": [
            {
                "title": t,
                "client": c,
                "sub": sub,
                "status": st,
                "est_savings": est,
                "rule_key": rule,
                "category": cat,
            }
            for t, c, sub, st, est, rule, cat in ROWS
        ],
        "feld": {
            "rationale": FELD_RATIONALE,
            "sources": [{"title": t, "loc": loc} for t, loc in FELD_SOURCES],
            "talking_points": list(FELD_TALKING_POINTS),
        },
        "ferris_envelope": FERRIS_ENVELOPE,
        "ridgeline_project": RIDGELINE_PROJECT,
    }

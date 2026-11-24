"""The TAX-10 line maps (T-08-T11; S51 partials, TASK-8740; OQ-15: repo files reviewed yearly by
a CPA, not firm content). Engine summary keys (`<form>.<line>`) to the comparison's labels, in the
order TAX-10 reads them. Form 1040 is TAX-10's; other forms have no map yet (no comparison)."""

from __future__ import annotations

from typing import Final

LINE_MAPS: Final[dict[str, tuple[tuple[str, str], ...]]] = {
    "1040": (
        ("1040.1a", "1a Wages, salaries, tips"),
        ("1040.2a", "2a Tax-exempt interest"),
        ("1040.2b", "2b Taxable interest"),
        ("1040.3a", "3a Qualified dividends"),
        ("1040.3b", "3b Ordinary dividends"),
        ("sch1.5", "Sch 1 line 5 Rental real estate, royalties, partnerships"),
        ("1040.9", "9 Total income"),
        ("1040.11", "11 Adjusted gross income"),
        ("scha.5e", "Sch A 5e State and local taxes (capped)"),
        ("scha.8a", "Sch A 8a Home mortgage interest"),
        ("scha.11", "Sch A 11 Gifts by cash or check"),
        ("1040.12", "12 Itemized deductions"),
        ("1040.13", "13 Qualified business income deduction"),
        ("1040.15", "15 Taxable income"),
        ("1040.16", "16 Tax"),
        ("1040.23", "23 Other taxes (Schedule 2)"),
        ("1040.24", "24 Total tax"),
        ("1040.25d", "25d Federal income tax withheld"),
        ("1040.26", "26 Estimated tax payments"),
        ("sch3.10", "Sch 3 line 10 Amount paid with extension"),
        ("1040.33", "33 Total payments"),
        ("1040.34", "34 Overpaid / refund"),
    ),
}
# T-08-T22 (TAX-10's statement grammar): each line's group band, its printed reference, and the
# totals (a stroke rule) and grand total (a double rule).
_GROUP_OF_1040: Final = {
    **dict.fromkeys(
        ("1040.1a", "1040.2a", "1040.2b", "1040.3a", "1040.3b", "sch1.5", "1040.9", "1040.11"),
        "income",
    ),
    **dict.fromkeys(
        ("scha.5e", "scha.8a", "scha.11", "1040.12", "1040.13", "1040.15"), "deductions"
    ),
    **dict.fromkeys(
        ("1040.16", "1040.23", "1040.24", "1040.25d", "1040.26", "sch3.10", "1040.33", "1040.34"),
        "tax_and_payments",
    ),
}
LINE_GROUPS: Final[dict[str, str]] = _GROUP_OF_1040
LINE_TOTALS: Final[dict[str, str]] = {
    **dict.fromkeys(("1040.9", "1040.11", "1040.12", "1040.15", "1040.24", "1040.33"), "total"),
    "1040.34": "grand",
}
LINE_REFS: Final[dict[str, str]] = {
    code: label.split(" ", 3)[0]
    if not label.startswith("Sch ")
    else " ".join(label.split(" ")[: (4 if label.split(" ")[2] == "line" else 3)])
    for code, label in LINE_MAPS["1040"]
}
AGI: Final = "1040.11"
TOTAL_TAX: Final = "1040.24"
REFUND: Final = "1040.34"

__all__ = ["AGI", "LINE_GROUPS", "LINE_MAPS", "LINE_REFS", "LINE_TOTALS", "REFUND", "TOTAL_TAX"]

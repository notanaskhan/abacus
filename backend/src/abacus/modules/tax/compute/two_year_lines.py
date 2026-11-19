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
AGI: Final = "1040.11"
TOTAL_TAX: Final = "1040.24"
REFUND: Final = "1040.34"

__all__ = ["AGI", "LINE_MAPS", "REFUND", "TOTAL_TAX"]

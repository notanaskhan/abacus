"""Scenario trial balances for the connections slice (A-02-T27; A-02 §5.3; blueprint §9.4).
Synthetic, Brightwater Hale only.

- **Granite Peak FY2026** (FYE Jun 30, 2026), from A-02 §5.3: cash 2,140,000 · AR 5,860,000 ·
  inventory 11,420,000 · PP&E 6,380,000 · other 610,000 = total assets **26,410,000**; AP
  4,180,000 · accrued 1,630,000 · revolver 6,500,000 · term loan 3,200,000; revenue 48,600,000 ·
  COGS 29,160,000 · operating expenses 15,820,000 · interest 520,000; opening equity 7,800,000.
  Debits = credits = 71,910,000 (the plan marks that total inferred).
- **Granite Peak FY2025** (FYE Jun 30, 2025): only the total assets, 23,200,000, are canon. The
  lines are **inferred** to foot (DEC-710) and are named so in the file's title row.
- **Northwind Robotics 401(k) Plan PY2025** (Dec 31, 2025), from the blueprint's statement of
  net assets, **unadjusted**: the 48,600 contributions receivable found in fieldwork is left out,
  so net assets read 16,812,400 (AUD-07's planning base).

Granite Peak's files render as NetSuite CSV exports (`ledger_exports.netsuite_trial_balance_csv`)
and Northwind's as the trial balance template (`accrued_template`), under `files/`.
"""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final

from openpyxl import Workbook

from abacus_tools.synthetic.ledger_exports import netsuite_trial_balance_csv
from abacus_tools.synthetic.model import TrialBalance, TrialBalanceLine

FILES: Final = Path(__file__).parent / "files"
GRANITE_PEAK: Final = "Granite Peak Outdoor Supply, Inc."
NORTHWIND_PLAN: Final = "Northwind Robotics 401(k) Plan"


def _line(code: str, name: str, debit: int | str = 0, credit: int | str = 0) -> TrialBalanceLine:
    return TrialBalanceLine(code, name, Decimal(debit), Decimal(credit))


GRANITE_PEAK_FY2026: Final = TrialBalance(
    date(2026, 6, 30),
    (
        _line("1000", "Cash and cash equivalents", debit=2_140_000),
        _line("1200", "Accounts receivable, net", debit=5_860_000),
        _line("1400", "Inventories", debit=11_420_000),
        _line("1600", "Property, plant and equipment, net", debit=6_380_000),
        _line("1900", "Other assets", debit=610_000),
        _line("2000", "Accounts payable", credit=4_180_000),
        _line("2100", "Accrued liabilities", credit=1_630_000),
        _line("2300", "Revolving line of credit", credit=6_500_000),
        _line("2500", "Term loan", credit=3_200_000),
        _line("3000", "Stockholders' equity, beginning of year", credit=7_800_000),
        _line("4000", "Net sales", credit=48_600_000),
        _line("5000", "Cost of goods sold", debit=29_160_000),
        _line("6000", "Operating expenses", debit=15_820_000),
        _line("7000", "Interest expense", debit=520_000),
    ),
    GRANITE_PEAK,
)

# Inferred to foot (DEC-710): only total assets 23,200,000 are canon.
GRANITE_PEAK_FY2025: Final = TrialBalance(
    date(2025, 6, 30),
    (
        _line("1000", "Cash and cash equivalents", debit=1_880_000),
        _line("1200", "Accounts receivable, net", debit=5_120_000),
        _line("1400", "Inventories", debit=10_150_000),
        _line("1600", "Property, plant and equipment, net", debit=5_500_000),
        _line("1900", "Other assets", debit=550_000),
        _line("2000", "Accounts payable", credit=3_700_000),
        _line("2100", "Accrued liabilities", credit=1_450_000),
        _line("2300", "Revolving line of credit", credit=5_900_000),
        _line("2500", "Term loan", credit=3_600_000),
        _line("3000", "Stockholders' equity, beginning of year", credit=6_300_000),
        _line("4000", "Net sales", credit=44_100_000),
        _line("5000", "Cost of goods sold", debit=26_460_000),
        _line("6000", "Operating expenses", debit=14_900_000),
        _line("7000", "Interest expense", debit=490_000),
    ),
    GRANITE_PEAK,
)

NORTHWIND_PY2025: Final = TrialBalance(
    date(2025, 12, 31),
    (
        _line("1010", "KRS 500 Index Fund", debit="6120450.00"),
        _line("1020", "KRS Target 2035 Fund", debit="2384910.00"),
        _line("1030", "KRS Target 2045 Fund", debit="2915330.00"),
        _line("1040", "KRS Bond Index Fund", debit="1408220.00"),
        _line("1050", "KRS International Index Fund", debit="902610.00"),
        _line("1060", "Harborline Stable Value Fund", debit="1163480.00"),
        _line("1100", "Self-directed brokerage (BrokerWindow)", debit="1605000.00"),
        _line("1200", "Notes receivable from participants", debit="312400.00"),
        _line("3000", "Net assets available for benefits", credit="16812400.00"),
    ),
    NORTHWIND_PLAN,
)


def total_assets(tb: TrialBalance) -> Decimal:
    """Accounts 1000-1999 (code, never a model)."""
    return sum((x.debit - x.credit for x in tb.lines if x.account_code < "2000"), Decimal(0))


def tb_template_xlsx(tb: TrialBalance) -> bytes:
    """The `accrued_template` layout: a period line, then Account, Account name, Debit, Credit,
    and a Total row."""
    book = Workbook()
    sheet = book.active
    if sheet is None:
        raise RuntimeError("openpyxl made a workbook without a sheet")
    sheet.append(["Period end:", tb.as_of.isoformat()])
    sheet.append(["Account", "Account name", "Debit", "Credit"])
    for line in tb.lines:
        sheet.append(
            [
                line.account_code,
                line.account_name,
                float(line.debit) or None,
                float(line.credit) or None,
            ]
        )
    sheet.append(["Total", None, float(tb.total_debits), float(tb.total_credits)])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def write_files(directory: Path = FILES) -> list[Path]:
    """Render the three files (run by `python -m abacus_tools.synthetic.scenarios.
    brightwater_hale.ledgers`); the outputs are committed beside the other scenario files."""
    written: list[Path] = []
    for tb, name, title in (
        (GRANITE_PEAK_FY2026, "granite-peak-fy2026-netsuite-tb.csv", GRANITE_PEAK),
        (GRANITE_PEAK_FY2025, "granite-peak-fy2025-netsuite-tb.csv", f"{GRANITE_PEAK} (inferred)"),
    ):
        path = directory / name
        path.write_bytes(netsuite_trial_balance_csv(tb, company=title))
        written.append(path)
    path = directory / "northwind-py2025-tb-template.xlsx"
    path.write_bytes(tb_template_xlsx(NORTHWIND_PY2025))
    written.append(path)
    return written


if __name__ == "__main__":
    for written in write_files():
        print(written.name)

"""The `ebp` slice, part 2 (A-05-T34; A-05 §3 F6 to F9, §5.3; DEC-2252): the investments, Form
5500, distributions and administration documents for Northwind Robotics 401(k) Plan PY2025, and
Granite Peak's estimates, masters and minutes.

- **Net assets** foot by code: the Harborline certified Summary of Net Trust Assets holds five
  funds (14,800,000.00), the BrokerWindow self-directed accounts (19 accounts, 1,700,000.00) and
  the participant loans (312,400.00): 16,812,400.00 at Dec 31, 2025; with the contributions
  receivable of 48,600.00 (part 1), net assets available for benefits are 16,861,000.00. The
  Keystone schedule of account balances (301 participants) foots to the same 16,812,400.00, and the
  draft Form 5500 Schedule H line 1l reports 16,861,000.00.
- **Distributions**: 64 in the year; the sample is 10 of them by the scenario seed 0x7B13C4.
- **Documents**: the trust report with its certification page (page 4), BrokerWindow detail, the
  Keystone loan report and schedule of account balances, the distributions register, 408(b)(2)
  disclosures for Keystone and Harborline, two invoices, the ERISA budget statement, Summit's
  testing report (ADP/ACP passed) and draft Form 5500 (uploaded Sep 21, 2026), and for Granite
  Peak its estimates, vendor and customer masters and four sets of board minutes.

Every provider and person is fictional; every figure is allocated by `kernel.numeric.allocate`
so totals foot exactly. Uploaded through `evidence.api` (`evidence.ebp_documents_part2_uploaded`).

TASK-7815 (DEC-4813): the slice also carries EBP-03's eligibility test, Sep 17 to Sep 24
(`ebp_eligibility.py`: EBP-02's entry rule, the census and HR imports, the test and its marks).
They read A-03's approved Participants sample, so they load with `--slice sampling`: the Sep 24
nightly's slices, never E0's (every one is dated after it).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Final

from abacus.kernel.numeric import allocate
from abacus_tools.synthetic.scenarios.brightwater_hale import ebp_eligibility
from abacus_tools.synthetic.scenarios.brightwater_hale.ebp import (
    PARTICIPANTS_EOY,
    PDF,
    PLAN,
    RECEIVABLE,
    XLSX,
    _lines,  # pyright: ignore[reportPrivateUsage] -- the sibling module's own helper
    _sheet,  # pyright: ignore[reportPrivateUsage] -- the sibling module's own helper
    _weights,  # pyright: ignore[reportPrivateUsage] -- the sibling module's own helper
)
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import Rng
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "ebp2"
NEEDS: Final = ("ebp",)
YEAR_END: Final = date(2025, 12, 31)
FUNDS: Final[tuple[tuple[str, Decimal, Decimal], ...]] = (
    # fund, Dec 31, 2024, Dec 31, 2025
    ("Harborline Stable Value Fund", Decimal("1204300.00"), Decimal("1311800.00")),
    ("Harborline S&P 500 Index Fund", Decimal("4318900.00"), Decimal("4920300.00")),
    ("Harborline International Equity Fund", Decimal("1488200.00"), Decimal("1604500.00")),
    ("Harborline Aggregate Bond Index Fund", Decimal("2006100.00"), Decimal("2118700.00")),
    ("Harborline Target Date Funds (2030-2060)", Decimal("4211500.00"), Decimal("4844700.00")),
)
BROKERWINDOW_ACCOUNTS: Final = 19
BROKERWINDOW_TOTAL: Final = Decimal("1700000.00")
LOANS_TOTAL: Final = Decimal("312400.00")
TRUST_TOTAL: Final = sum((f[2] for f in FUNDS), Decimal(0)) + BROKERWINDOW_TOTAL + LOANS_TOTAL
NET_ASSETS: Final = TRUST_TOTAL + RECEIVABLE  # 16,861,000.00
DISTRIBUTIONS: Final = 64
DISTRIBUTIONS_TOTAL: Final = Decimal("1284600.00")
SAMPLE_SEED: Final = 0x7B13C4
SAMPLE_SIZE: Final = 10
FORM_5500_UPLOADED: Final = date(2026, 9, 21)


def brokerwindow_accounts() -> tuple[Decimal, ...]:
    return allocate(BROKERWINDOW_TOTAL, _weights(BROKERWINDOW_ACCOUNTS, "brokerwindow"))


def account_balances() -> tuple[Decimal, ...]:
    """The 301 participants' balances, footing to the trust's 16,812,400.00."""
    return allocate(TRUST_TOTAL, _weights(PARTICIPANTS_EOY, "balances"))


def distributions() -> tuple[Decimal, ...]:
    return allocate(DISTRIBUTIONS_TOTAL, _weights(DISTRIBUTIONS, "distributions"))


def distribution_sample() -> tuple[int, ...]:
    """10 of 64 by seed 0x7B13C4: distinct row numbers (1-based), in draw order."""
    rng = Rng(f"ebp:distributions:{SAMPLE_SEED:#x}")
    picked: list[int] = []
    while len(picked) < SAMPLE_SIZE:
        row = rng.integer(1, DISTRIBUTIONS)
        if row not in picked:
            picked.append(row)
    return tuple(picked)


def trust_report_pdf() -> bytes:
    lines = [
        f"{name}: 12/31/2024 {boy:,.2f} 12/31/2025 {eoy:,.2f}" for name, boy, eoy in FUNDS
    ] + [
        f"BrokerWindow self-directed accounts ({BROKERWINDOW_ACCOUNTS}): "
        f"{BROKERWINDOW_TOTAL:,.2f}",
        f"Participant loans: {LOANS_TOTAL:,.2f}",
        f"Total net trust assets 12/31/2025: {TRUST_TOTAL:,.2f}",
        "Page 4 - Certification: Harborline Trust Company, a qualifying institution, certifies "
        "that the information is complete and accurate (29 CFR 2520.103-5), signed 02/14/2026.",
        "The certification does not cover participant loans or the BrokerWindow accounts.",
    ]
    return _lines("Harborline Trust Company - Summary of Net Trust Assets", lines)


def brokerwindow_xlsx() -> bytes:
    rows = [(f"BW-{n:03d}", str(v)) for n, v in enumerate(brokerwindow_accounts(), start=1)]
    return _sheet("BrokerWindow", ("Account", "Value 12/31/2025"), rows)


def loan_report_xlsx() -> bytes:
    rows = [("Participant loans outstanding", str(LOANS_TOTAL))]
    return _sheet("Loans", ("Keystone loan report", "Balance 12/31/2025"), rows)


def balances_xlsx() -> bytes:
    rows = [(f"P{n:04d}", str(v)) for n, v in enumerate(account_balances(), start=1)]
    return _sheet("Balances", ("Participant", "Balance 12/31/2025"), rows)


def distributions_xlsx() -> bytes:
    rows = [(n, str(v)) for n, v in enumerate(distributions(), start=1)]
    return _sheet("Distributions", ("Row", "Amount"), rows)


def _letter(title: str, *lines: str) -> Callable[[], bytes]:
    return lambda: _lines(title, lines)


def form5500_pdf() -> bytes:
    return _lines(
        "Draft Form 5500 Schedule H - Northwind Robotics 401(k) Plan PY2025",
        (
            f"Line 1c(8) Participant loans: {LOANS_TOTAL:,.2f}",
            f"Line 1b(2) Participant contributions receivable: {RECEIVABLE:,.2f}",
            f"Line 1l Net assets: {NET_ASSETS:,.2f}",
            "Part IV line 4a: Were there late participant contributions? No.",
            "Prepared by Summit Plan Administrators.",
        ),
    )


@dataclass(frozen=True)
class Ebp2File:
    file_name: str
    media_type: str
    build: Callable[[], bytes]
    client: str = "Northwind Robotics, Inc."

    def content(self) -> bytes:
        return self.build()


FILES: Final[tuple[Ebp2File, ...]] = (
    Ebp2File("Harborline certified trust report 2025.pdf", PDF, trust_report_pdf),
    Ebp2File("BrokerWindow account detail 2025.xlsx", XLSX, brokerwindow_xlsx),
    Ebp2File("Keystone loan report 2025.xlsx", XLSX, loan_report_xlsx),
    Ebp2File("Keystone schedule of account balances 2025.xlsx", XLSX, balances_xlsx),
    Ebp2File("Keystone distributions register 2025.xlsx", XLSX, distributions_xlsx),
    Ebp2File(
        "Keystone 408(b)(2) disclosure.pdf",
        PDF,
        _letter("Keystone 408(b)(2) disclosure", "Direct compensation: 0.12% of plan assets."),
    ),
    Ebp2File(
        "Harborline 408(b)(2) disclosure.pdf",
        PDF,
        _letter("Harborline 408(b)(2) disclosure", "Trustee fee: 0.04% of plan assets."),
    ),
    Ebp2File(
        "Summit invoice 2025-11.pdf",
        PDF,
        _letter("Summit Plan Administrators invoice", "Form 5500 preparation: 3,400.00."),
    ),
    Ebp2File(
        "Keystone invoice 2025-Q4.pdf",
        PDF,
        _letter("Keystone Retirement Svcs invoice", "Recordkeeping Q4 2025: 5,060.00."),
    ),
    Ebp2File(
        "ERISA budget statement 2025.pdf",
        PDF,
        _letter("ERISA budget account statement", "Revenue credits allocated to participants."),
    ),
    Ebp2File(
        "Summit nondiscrimination testing report 2025.pdf",
        PDF,
        _letter("Summit testing report PY2025", "ADP test: passed. ACP test: passed."),
    ),
    Ebp2File("Draft Form 5500 PY2025.pdf", PDF, form5500_pdf),
    Ebp2File(
        "Granite Peak significant estimates FY2025.pdf",
        PDF,
        _letter("Granite Peak estimates", "Inventory reserve and allowance for credit losses."),
        "Granite Peak Outdoor Supply",
    ),
    Ebp2File(
        "Granite Peak vendor master.xlsx",
        XLSX,
        lambda: _sheet("Vendors", ("Vendor", "Terms"), [("Alpine Freight Co", "Net 30")]),
        "Granite Peak Outdoor Supply",
    ),
    Ebp2File(
        "Granite Peak customer master.xlsx",
        XLSX,
        lambda: _sheet(
            "Customers", ("Customer", "Terms"), [("Summit Trail Outfitters", "Net 45")]
        ),
        "Granite Peak Outdoor Supply",
    ),
    *(
        Ebp2File(
            f"Granite Peak board minutes {q}.pdf",
            PDF,
            _letter(f"Board minutes {q}", "Quorum present. Minutes approved by the board."),
            "Granite Peak Outdoor Supply",
        )
        for q in ("Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025")
    ),
)


@register_slice(SLICE)
def _ebp2_slice() -> list[Event]:
    return [
        Event(
            "ebp:northwind:documents:part2",
            SETUP_AT + timedelta(days=11),
            "evidence.ebp_documents_part2_uploaded",
            "system",
            SLICE,
            {"files": len(FILES), "plan": PLAN},
            client="Northwind Robotics, Inc.",
        ),
        # TASK-7815 (DEC-4813): EBP-02's entry rule, the census and HR imports and EBP-03's
        # eligibility test, Sep 17 to Sep 24, so the Sep 24 seed reads EBP-03's grid.
        *ebp_eligibility.events(SLICE),
    ]


def totals() -> dict[str, Decimal]:
    """The figure book the goldens check."""
    return {
        "funds": sum((f[2] for f in FUNDS), Decimal(0)),
        "brokerwindow": sum(brokerwindow_accounts(), Decimal(0)),
        "loans": LOANS_TOTAL,
        "trust": TRUST_TOTAL,
        "balances": sum(account_balances(), Decimal(0)),
        "receivable": RECEIVABLE,
        "net_assets": NET_ASSETS,
        "distributions": sum(distributions(), Decimal(0)),
    }


def sample_rows() -> Sequence[int]:
    return distribution_sample()

"""The `ebp` slice, part 1 (A-05-T07; A-05 §3 F1 to F5, §5.3; DF-34; DEC-1862): Northwind Robotics
401(k) Plan PY2025's figure book and source documents.

- **Plan facts** (EBP-01): PN 001 (the recordkeeper's plan ID 58217 is not a PN), 286
  participants with balances at the beginning of the year and 301 at the end, a QACA safe harbor
  (6% default, +1% a year to 15%), a 3.5% maximum match, entry at age 21 and 3 months of service.
- **Four providers**: Keystone Retirement Svcs LLC (recordkeeper; its SOC 1 Type 2 covers Jan 1
  to Sep 30, 2025, leaving Oct to Dec uncovered; its service agreement shows EIN ending 4420 where
  Summit's draft Schedule C lists 4402), Harborline Trust Company (trustee and custodian; it
  certifies), PayGrid Payroll (payroll) and Summit Plan Administrators (TPA, the 5500 preparer).
- **Documents**: adoption agreement v1 (before the 2024 amendment) and v2, the 2024 amendment,
  the 2025 SPD (its entry dates are quarterly where the plan's are monthly: EBP-02 c), the census
  (301 rows), 25 HR records (the eligibility sample), the PayGrid register (26 payrolls every 14
  days from Jan 10, 2025; the Dec 26 deposit landed Jan 9, 2026, 9 business days with Jan 1
  excluded and 10 calendar days from the expected date: DF-34) and the W-3 (Box 1 13,813,400 +
  Box 12 D 746,600 = census compensation 14,560,000).

Every per-row figure is allocated by `kernel.numeric.allocate` so the totals foot exactly; the seed
tests check every figure-book total. Uploaded through `evidence.api` onto the Northwind engagement
(`evidence.ebp_documents_uploaded`); the plan facts and providers load through A-05-T08's service
when it exists (the golden YAML holds them meanwhile). Synthetic, Brightwater Hale only.
Opt-in (`--slice ebp`, which brings `people`).
"""

from __future__ import annotations

import io
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Final

from openpyxl import Workbook

from abacus.kernel.calendar import add_business_days, is_business_day
from abacus.kernel.numeric import allocate
from abacus_tools.synthetic.documents import positioned_pdf
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import stable_id
from abacus_tools.synthetic.scenarios.brightwater_hale.scenario import SETUP_AT
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import register_slice
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import Event

SLICE: Final = "ebp"
NEEDS: Final = ("people",)
PLAN: Final = "Northwind Robotics 401(k) Plan"
PLAN_NUMBER: Final = "001"
RECORDKEEPER_PLAN_ID: Final = "58217"
PARTICIPANTS_BOY: Final = 286
PARTICIPANTS_EOY: Final = 301
TERMINATED_2025: Final = 6  # DF-34: EBP-08's vesting covers these six
HR_RECORDS: Final = 25
PAYROLLS: Final = 26
FIRST_PAYROLL: Final = date(2025, 1, 10)
LATE_PAYROLL: Final = date(2025, 12, 26)
LATE_DEPOSIT: Final = date(2026, 1, 9)
ESTABLISHED_PRACTICE_DAYS: Final = 2
HOLIDAYS: Final = frozenset({date(2026, 1, 1), date(2025, 12, 25), date(2025, 11, 27)})
W3_BOX1: Final = Decimal("13813400.00")
W3_BOX12D: Final = Decimal("746600.00")
COMPENSATION: Final = W3_BOX1 + W3_BOX12D  # 14,560,000.00, the census total
LATE_AMOUNT: Final = Decimal("33540.00")
RECEIVABLE_REGULAR: Final = Decimal("15060.00")
RECEIVABLE: Final = RECEIVABLE_REGULAR + LATE_AMOUNT  # 48,600.00 (AUD-07's caption)


@dataclass(frozen=True)
class Provider:
    name: str
    role: str
    ein_last4: str | None
    soc: str | None
    note: str | None = None


PROVIDERS: Final[tuple[Provider, ...]] = (
    Provider(
        "Keystone Retirement Svcs LLC",
        "recordkeeper",
        "4420",
        "SOC 1 Type 2, Jan 1 to Sep 30, 2025",
        "Summit's draft Schedule C lists EIN ending 4402",
    ),
    Provider("Harborline Trust Company", "trustee_custodian", None, None, "certifies"),
    Provider("PayGrid Payroll", "payroll", None, None),
    Provider("Summit Plan Administrators", "tpa", None, None, "5500 preparer"),
)
SOC_GAP: Final = (date(2025, 10, 1), date(2025, 12, 31))


# --- the census and the payroll register ---------------------------------------------------------


@dataclass(frozen=True)
class CensusRow:
    key: str  # "NW-1001"
    name: str
    ssn_last4: str
    hire_on: date
    status: str  # active | terminated
    compensation: Decimal
    deferrals: Decimal


def _weights(n: int, salt: str) -> list[Decimal]:
    """Deterministic varied weights (from stable ids), so allocations look like real pay."""
    return [Decimal(40 + int(stable_id(f"ebp:{salt}:{i}")[:4], 16) % 120) for i in range(n)]


def census() -> tuple[CensusRow, ...]:
    """301 participants: compensation foots to 14,560,000 and deferrals to W-3 Box 12 D."""
    comp = allocate(COMPENSATION, _weights(PARTICIPANTS_EOY, "comp"))
    deferring = [i for i in range(PARTICIPANTS_EOY) if i % 7 != 3]  # some elect 0%
    deferral_shares = allocate(W3_BOX12D, [comp[i] for i in deferring])
    deferrals = dict(zip(deferring, deferral_shares, strict=True))
    rows: list[CensusRow] = []
    for i in range(PARTICIPANTS_EOY):
        terminated = i >= PARTICIPANTS_EOY - TERMINATED_2025
        hire = date(2012, 1, 9) + timedelta(days=(int(stable_id(f"ebp:hire:{i}")[:5], 16) % 4800))
        rows.append(
            CensusRow(
                key=f"NW-{1001 + i}",
                name=f"Participant {1001 + i}",
                ssn_last4=f"{int(stable_id(f'ebp:ssn:{i}')[:6], 16) % 10000:04d}",
                hire_on=min(hire, date(2025, 9, 30)),
                status="terminated" if terminated else "active",
                compensation=comp[i],
                deferrals=deferrals.get(i, Decimal("0.00")),
            )
        )
    return tuple(rows)


def business_days_between(start: date, end: date, holidays: frozenset[date]) -> int:
    """Business days after `start` up to and including `end` (Dec 26 to Jan 9: 9, Jan 1 out)."""
    count, day = 0, start
    while day < end:
        day += timedelta(days=1)
        count += is_business_day(day, holidays)
    return count


@dataclass(frozen=True)
class Payroll:
    pay_on: date
    wages: Decimal
    deferrals: Decimal
    expected_on: date
    deposited_on: date

    @property
    def business_days(self) -> int:
        return business_days_between(self.pay_on, self.deposited_on, HOLIDAYS)

    @property
    def calendar_days_late(self) -> int:
        return (self.deposited_on - self.expected_on).days


def payrolls() -> tuple[Payroll, ...]:
    """26 payrolls every 14 days from Jan 10, 2025; wages foot to the census total and deferrals
    to Box 12 D, the Dec 26 payroll carrying the 33,540 that was deposited late."""
    dates = [FIRST_PAYROLL + timedelta(days=14 * i) for i in range(PAYROLLS)]
    wages = allocate(COMPENSATION, [Decimal(1)] * PAYROLLS)
    regular = allocate(W3_BOX12D - LATE_AMOUNT, _weights(PAYROLLS - 1, "deferral"))
    out: list[Payroll] = []
    for i, day in enumerate(dates):
        expected = add_business_days(day, ESTABLISHED_PRACTICE_DAYS, HOLIDAYS)
        late = day == LATE_PAYROLL
        out.append(
            Payroll(
                pay_on=day,
                wages=wages[i],
                deferrals=LATE_AMOUNT if late else regular[i],
                expected_on=expected,
                deposited_on=LATE_DEPOSIT if late else expected,
            )
        )
    return tuple(out)


# --- the documents -------------------------------------------------------------------------------

PDF: Final = "application/pdf"
XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _lines(title: str, lines: Sequence[str]) -> bytes:
    runs = [(72.0, 720.0, title)] + [(72.0, 696.0 - 16.0 * i, t) for i, t in enumerate(lines)]
    return positioned_pdf([runs])


_PROVISIONS_V1: Final = (
    "Plan: Northwind Robotics 401(k) Plan, plan number 001",
    "Eligibility: age 21 and 3 months of service",
    "Entry dates: first of the month following eligibility",
    "Automatic enrollment: QACA, 6% default, increasing 1% a year to 15%",
    "Employer match: 100% of the first 1% and 50% of the next 5% (3.5% maximum)",
    "Vesting: QACA safe harbor contributions vest after 2 years of service",
)


def adoption_agreement(version: int) -> bytes:
    lines = list(_PROVISIONS_V1)
    if version >= 2:
        lines += [
            "Long-term part-time employees: eligible after 2 consecutive years of 500 hours",
            "Catch-up contributions: permitted from age 50",
        ]
    return _lines(f"Adoption agreement, version {version}", lines)


def amendment_2024() -> bytes:
    return _lines(
        "Amendment 2024-1 (SECURE 2.0)",
        (
            "Effective January 1, 2025: long-term part-time employees after 2 years of 500 hours",
            "Effective January 1, 2025: catch-up contributions for ages 60 to 63 increased",
        ),
    )


def spd_2025() -> bytes:
    return _lines(
        "Summary Plan Description 2025",
        (
            "Eligibility: age 21 and 3 months of service",
            "Entry dates: the first day of each calendar quarter",
            "Automatic enrollment at 6% of pay",
        ),
    )


def _sheet(title: str, header: Sequence[str], rows: Sequence[Sequence[object]]) -> bytes:
    book = Workbook()
    sheet = book.active
    if sheet is None:  # pragma: no cover -- openpyxl always opens a sheet
        raise RuntimeError("no sheet")
    sheet.title = title
    sheet.append(list(header))
    for row in rows:
        sheet.append(list(row))
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def census_xlsx() -> bytes:
    return _sheet(
        "Census",
        ("Participant", "Name", "SSN", "Hire date", "Status", "Compensation", "Deferrals"),
        [
            (
                r.key,
                r.name,
                f"XXX-XX-{r.ssn_last4}",
                r.hire_on,
                r.status,
                float(r.compensation),
                float(r.deferrals),
            )
            for r in census()
        ],
    )


def hr_records_xlsx() -> bytes:
    rows = census()[:HR_RECORDS]
    return _sheet(
        "HR records",
        ("Participant", "Name", "Hire date", "Status"),
        [(r.key, r.name, r.hire_on, r.status) for r in rows],
    )


def payroll_register_xlsx() -> bytes:
    return _sheet(
        "PayGrid register",
        ("Pay date", "Gross wages", "401(k) deferrals", "Deposited"),
        [(p.pay_on, float(p.wages), float(p.deferrals), p.deposited_on) for p in payrolls()],
    )


def w3_pdf() -> bytes:
    return _lines(
        "Form W-3 2025 — Northwind Robotics, Inc.",
        (f"Box 1 Wages: {W3_BOX1:,.2f}", f"Box 12 D 401(k) deferrals: {W3_BOX12D:,.2f}"),
    )


@dataclass(frozen=True)
class EbpFile:
    file_name: str
    media_type: str
    build: Callable[[], bytes]

    def content(self) -> bytes:
        return self.build()


FILES: Final[tuple[EbpFile, ...]] = (
    EbpFile("Northwind 401k - Adoption agreement v1.pdf", PDF, lambda: adoption_agreement(1)),
    EbpFile("Northwind 401k - Adoption agreement v2.pdf", PDF, lambda: adoption_agreement(2)),
    EbpFile("Northwind 401k - Amendment 2024-1.pdf", PDF, amendment_2024),
    EbpFile("Northwind 401k - Summary Plan Description 2025.pdf", PDF, spd_2025),
    EbpFile("Northwind Census PY2025.xlsx", XLSX, census_xlsx),
    EbpFile("Northwind HR records - eligibility sample.xlsx", XLSX, hr_records_xlsx),
    EbpFile("PayGrid payroll register 2025.xlsx", XLSX, payroll_register_xlsx),
    EbpFile("Northwind W-3 2025.pdf", PDF, w3_pdf),
)


@register_slice(SLICE)
def _ebp_slice() -> list[Event]:
    return [
        Event(
            "ebp:northwind:documents",
            SETUP_AT + timedelta(days=10),
            "evidence.ebp_documents_uploaded",
            "system",
            SLICE,
            {"files": len(FILES), "plan": PLAN},
            client="Northwind Robotics, Inc.",
        )
    ]

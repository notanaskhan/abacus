"""Double-entry ledger simulation (SPEC-001 AC-4, AC-5).

Every journal entry is built from balanced lines, so the books balance by construction. Activity is
generated as documents first (invoices, bills, payroll runs, recurring charges) and then posted, so
agings and bank statements derive from the same documents the ledger was posted from.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from random import Random

from abacus_tools.synthetic import names
from abacus_tools.synthetic.model import (
    ZERO,
    Account,
    BankAccount,
    JournalEntry,
    JournalLine,
    money,
)
from abacus_tools.synthetic.rng import stream

CASH_OPERATING = "1000"
CASH_PAYROLL = "1010"
AR = "1100"
AP = "2000"
RETAINED_EARNINGS = "3100"

ACCOUNTS: tuple[Account, ...] = (
    Account("1000", "Cash - operating", "asset"),
    Account("1010", "Cash - payroll", "asset"),
    Account("1100", "Accounts receivable", "asset"),
    Account("1150", "Allowance for doubtful accounts", "asset"),
    Account("1200", "Inventory", "asset"),
    Account("1300", "Prepaid expenses", "asset"),
    Account("1500", "Property and equipment", "asset"),
    Account("1550", "Accumulated depreciation", "asset"),
    Account("2000", "Accounts payable", "liability"),
    Account("2100", "Accrued expenses", "liability"),
    Account("2200", "Payroll liabilities", "liability"),
    Account("2300", "Deferred revenue", "liability"),
    Account("2500", "Long-term debt", "liability"),
    Account("3000", "Common stock", "equity"),
    Account("3100", "Retained earnings", "equity"),
    Account("4000", "Product revenue", "revenue"),
    Account("4100", "Service revenue", "revenue"),
    Account("4900", "Interest income", "revenue"),
    Account("5000", "Cost of goods sold", "expense"),
    Account("6000", "Salaries and wages", "expense"),
    Account("6100", "Payroll taxes", "expense"),
    Account("6200", "Rent", "expense"),
    Account("6300", "Utilities", "expense"),
    Account("6400", "Software subscriptions", "expense"),
    Account("6500", "Professional fees", "expense"),
    Account("6600", "Travel", "expense"),
    Account("6700", "Marketing", "expense"),
    Account("6800", "Insurance", "expense"),
    Account("6900", "Depreciation expense", "expense"),
    Account("7000", "Interest expense", "expense"),
    Account("7100", "Bank fees", "expense"),
    Account("7200", "Office supplies", "expense"),
)
PROFIT_AND_LOSS = tuple(a.code for a in ACCOUNTS if a.type in ("revenue", "expense"))
OPERATING_EXPENSES = ("6300", "6400", "6500", "6600", "6700", "7200")
SIZES = {"small": {"sales": 700, "bills": 300, "other": 50}}


@dataclass
class OpenItem:
    """An invoice (AR) or bill (AP) and the date it is settled, if within reach."""

    counterparty: str
    issued: date
    due: date
    amount: Decimal
    settles: date | None


@dataclass(frozen=True)
class BankEvent:
    """A cash movement: posted to the GL on `posted`, cleared by the bank on `cleared`."""

    gl_account: str
    posted: date
    cleared: date
    amount: Decimal  # signed: + into the account
    description: str


@dataclass
class Books:
    period_start: date
    period_end: date
    month_ends: tuple[date, ...]
    bank_accounts: tuple[BankAccount, ...]
    customers: tuple[str, ...]
    vendors: tuple[str, ...]
    opening_cash: dict[str, Decimal] = field(default_factory=dict[str, Decimal])
    entries: tuple[JournalEntry, ...] = ()
    receivables: list[OpenItem] = field(default_factory=list[OpenItem])
    payables: list[OpenItem] = field(default_factory=list[OpenItem])
    bank_events: list[BankEvent] = field(default_factory=list[BankEvent])


def add_months(d: date, months: int) -> date:
    index = d.month - 1 + months
    year, month = d.year + index // 12, index % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def month_end(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def month_ends(start: date, months: int) -> tuple[date, ...]:
    first = date(start.year, start.month, 1)
    return tuple(month_end(add_months(first, i)) for i in range(months))


def business_days(first: date, last: date) -> list[date]:
    return [
        first + timedelta(days=n)
        for n in range((last - first).days + 1)
        if (first + timedelta(days=n)).weekday() < 5
    ]


def business_day_after(d: date, lag: int) -> date:
    out = d
    while out.weekday() >= 5:
        out += timedelta(days=1)
    while lag > 0:
        out += timedelta(days=1)
        if out.weekday() < 5:
            lag -= 1
    return out


def dr(code: str, amount: Decimal, desc: str, party: str | None = None) -> JournalLine:
    return JournalLine(code, amount, ZERO, desc, party)


def cr(code: str, amount: Decimal, desc: str, party: str | None = None) -> JournalLine:
    return JournalLine(code, ZERO, amount, desc, party)


def _settlement(rng: Random, issued: date) -> date | None:
    r = rng.random()
    if r < 0.80:
        return issued + timedelta(days=rng.randint(10, 55))
    if r < 0.93:
        return issued + timedelta(days=rng.randint(56, 95))
    if r < 0.98:
        return issued + timedelta(days=rng.randint(96, 150))
    return None


class _Simulation:
    def __init__(self, seed: int, prefix: str, start: date, months: int, size: str) -> None:
        self.seed, self.prefix, self.volume = seed, prefix, SIZES[size]
        setup = self.rng("setup")
        bank = names.bank_name(setup)
        ends = month_ends(start, months)
        self.books = Books(
            period_start=start,
            period_end=ends[-1],
            month_ends=ends,
            bank_accounts=(
                BankAccount(
                    f"{bank} operating",
                    names.routing_number(setup),
                    names.account_number(setup),
                    CASH_OPERATING,
                ),
                BankAccount(
                    f"{bank} payroll",
                    names.routing_number(setup),
                    names.account_number(setup),
                    CASH_PAYROLL,
                ),
            ),
            customers=names.counterparties(self.rng("customers"), 40),
            vendors=names.counterparties(self.rng("vendors"), 25),
        )
        self.drafts: list[tuple[date, int, str, tuple[JournalLine, ...]]] = []
        self.cheques = {CASH_OPERATING: 1001, CASH_PAYROLL: 5001}

    def rng(self, name: str) -> Random:
        return stream(self.seed, f"{self.prefix}:{name}")

    # --- posting -------------------------------------------------------------------------------

    def post(self, on: date, memo: str, lines: list[JournalLine]) -> None:
        debits = sum((ln.debit for ln in lines), ZERO)
        credits = sum((ln.credit for ln in lines), ZERO)
        if debits != credits:  # a construction bug, never a data condition
            raise AssertionError(f"unbalanced entry {memo!r}: {debits} != {credits}")
        kept = tuple(ln for ln in lines if ln.debit or ln.credit)
        if len(kept) < 2:  # a zero entry would desynchronise the bank events posted with it
            raise AssertionError(f"degenerate entry {memo!r} on {on}")
        self.drafts.append((on, len(self.drafts), memo, kept))

    def pay_out(
        self, code: str, on: date, amount: Decimal, payee: str, rng: Random, *, cheque: bool
    ) -> None:
        if cheque:
            description = f"CHECK {self.cheques[code]}"
            self.cheques[code] += 1
            cleared = business_day_after(on, rng.randint(2, 12))
        else:
            description = f"ACH {payee}".upper()
            cleared = business_day_after(on, rng.randint(0, 1))
        self.books.bank_events.append(BankEvent(code, on, cleared, -amount, description))

    def pay_in(self, code: str, on: date, amount: Decimal, description: str, rng: Random) -> None:
        cleared = business_day_after(on, rng.randint(0, 3))
        self.books.bank_events.append(BankEvent(code, on, cleared, amount, description))

    def same_day(self, code: str, on: date, amount: Decimal, description: str) -> None:
        self.books.bank_events.append(BankEvent(code, on, on, amount, description))

    # --- activity ------------------------------------------------------------------------------

    def run(self) -> Books:
        self.opening()
        for i, end in enumerate(self.books.month_ends):
            first = max(date(end.year, end.month, 1), self.books.period_start)
            days = business_days(first, end) or [first]  # never post before the opening entry
            self.sales(i, days)
            self.bills(i, days)
            self.payroll(i, days)
            self.recurring(i, days, end)
        self.settle()
        self.close()
        self.books.entries = self.finish()
        return self.books

    def opening(self) -> None:
        rng, start, books = self.rng("opening"), self.books.period_start, self.books
        for customer in rng.sample(books.customers, 25):
            issued = start - timedelta(days=rng.randint(1, 100))
            books.receivables.append(
                OpenItem(
                    customer,
                    issued,
                    issued + timedelta(days=30),
                    money(rng.randint(100_000, 1_500_000)),
                    start + timedelta(days=rng.randint(0, 60)),
                )
            )
        for vendor in rng.sample(books.vendors, 15):
            issued = start - timedelta(days=rng.randint(1, 60))
            books.payables.append(
                OpenItem(
                    vendor,
                    issued,
                    issued + timedelta(days=30),
                    money(rng.randint(50_000, 900_000)),
                    start + timedelta(days=rng.randint(0, 40)),
                )
            )
        books.opening_cash = {
            CASH_OPERATING: money(rng.randint(20_000_000, 40_000_000)),
            CASH_PAYROLL: money(rng.randint(500_000, 2_000_000)),
        }
        debits = {
            **books.opening_cash,
            AR: sum((item.amount for item in books.receivables), ZERO),
            "1200": money(rng.randint(10_000_000, 20_000_000)),
            "1300": money(rng.randint(1_000_000, 3_000_000)),
            "1500": money(rng.randint(30_000_000, 50_000_000)),
        }
        credits = {
            "1150": money(rng.randint(200_000, 800_000)),
            "1550": money(rng.randint(8_000_000, 15_000_000)),
            AP: sum((item.amount for item in books.payables), ZERO),
            "2500": money(rng.randint(15_000_000, 25_000_000)),
            "3000": money(10_000_000),
        }
        plug = sum(debits.values(), ZERO) - sum(credits.values(), ZERO)
        lines = [dr(c, a, "Opening balance") for c, a in debits.items()]
        lines += [cr(c, a, "Opening balance") for c, a in credits.items()]
        lines.append(
            cr(RETAINED_EARNINGS, plug, "Opening balance")
            if plug >= 0
            else dr(RETAINED_EARNINGS, -plug, "Opening balance")
        )
        self.post(start, "Opening balances", lines)

    def sales(self, i: int, days: list[date]) -> None:
        rng = self.rng(f"sales:{i}")
        for _ in range(self.volume["sales"]):
            on, customer = rng.choice(days), rng.choice(self.books.customers)
            amount = money(rng.randint(20_000, 1_500_000))
            product = rng.random() < 0.6
            lines = [
                dr(AR, amount, "Invoice", customer),
                cr("4000" if product else "4100", amount, "Invoice", customer),
            ]
            if product:
                cost = money(amount * Decimal(rng.randint(40, 55)) / 100)
                lines += [
                    dr("5000", cost, "Cost of goods sold"),
                    cr("1200", cost, "Inventory relief"),
                ]
            self.post(on, f"Sales invoice - {customer}", lines)
            self.books.receivables.append(
                OpenItem(customer, on, on + timedelta(days=30), amount, _settlement(rng, on))
            )

    def bills(self, i: int, days: list[date]) -> None:
        rng = self.rng(f"bills:{i}")
        for _ in range(self.volume["bills"]):
            on, vendor = rng.choice(days), rng.choice(self.books.vendors)
            if rng.random() < 0.5:
                code, amount = "1200", money(rng.randint(200_000, 2_000_000))
            else:
                code, amount = rng.choice(OPERATING_EXPENSES), money(rng.randint(5_000, 800_000))
            self.post(
                on,
                f"Vendor bill - {vendor}",
                [dr(code, amount, "Bill", vendor), cr(AP, amount, "Bill", vendor)],
            )
            self.books.payables.append(
                OpenItem(vendor, on, on + timedelta(days=30), amount, _settlement(rng, on))
            )

    def payroll(self, i: int, days: list[date]) -> None:
        rng = self.rng(f"payroll:{i}")
        mid = [d for d in days if d.day <= 15]
        for run_day in (mid[-1] if mid else days[0], days[-1]):
            gross = money(rng.randint(9_000_000, 11_000_000))
            employer_tax = money(gross * Decimal("0.0765"))
            withheld = money(gross * Decimal("0.22"))
            net = gross - withheld
            self.post(
                run_day,
                "Payroll transfer",
                [
                    dr(CASH_PAYROLL, net, "Payroll funding"),
                    cr(CASH_OPERATING, net, "Payroll funding"),
                ],
            )
            self.same_day(CASH_OPERATING, run_day, -net, "TRANSFER TO PAYROLL")
            self.same_day(CASH_PAYROLL, run_day, net, "TRANSFER FROM OPERATING")
            self.post(
                run_day,
                "Payroll",
                [
                    dr("6000", gross, "Gross pay"),
                    dr("6100", employer_tax, "Employer taxes"),
                    cr(CASH_PAYROLL, net, "Net pay"),
                    cr("2200", withheld + employer_tax, "Withholdings and employer taxes"),
                ],
            )
            self.same_day(CASH_PAYROLL, run_day, -net, "PAYROLL DIRECT DEPOSITS")
            remit_day = business_day_after(run_day, 5)
            if remit_day <= self.books.period_end:
                amount = withheld + employer_tax
                self.post(
                    remit_day,
                    "Payroll tax remittance",
                    [dr("2200", amount, "Remittance"), cr(CASH_OPERATING, amount, "Remittance")],
                )
                self.same_day(CASH_OPERATING, remit_day, -amount, "ACH PAYROLL TAXES")

    def recurring(self, i: int, days: list[date], end: date) -> None:
        rng, first = self.rng(f"recurring:{i}"), days[0]
        for code, low, high, payee in (
            ("6200", 1_800_000, 1_800_000, "Landlord"),
            ("6300", 150_000, 400_000, "Utility"),
            ("6400", 300_000, 900_000, "Software"),
            ("6800", 250_000, 250_000, "Insurer"),
        ):
            amount = money(rng.randint(low, high))
            self.post(
                first,
                f"{payee} payment",
                [dr(code, amount, payee), cr(CASH_OPERATING, amount, payee)],
            )
            self.pay_out(CASH_OPERATING, first, amount, payee, rng, cheque=False)
        for _ in range(self.volume["other"]):
            on, code = rng.choice(days), rng.choice(("6600", "6700", "7200"))
            amount = money(rng.randint(2_000, 150_000))
            self.post(
                on,
                "Card and ACH expense",
                [dr(code, amount, "Expense"), cr(CASH_OPERATING, amount, "Expense")],
            )
            self.pay_out(CASH_OPERATING, on, amount, "Card settlement", rng, cheque=False)
        mid = next(d for d in days if d.day >= 15)
        interest, principal = money(rng.randint(90_000, 120_000)), money(250_000)
        self.post(
            mid,
            "Loan payment",
            [
                dr("7000", interest, "Interest"),
                dr("2500", principal, "Principal"),
                cr(CASH_OPERATING, interest + principal, "Loan payment"),
            ],
        )
        self.same_day(CASH_OPERATING, mid, -(interest + principal), "LOAN PAYMENT")
        last = days[-1]
        fee = money(rng.randint(2_500, 9_500))
        self.post(
            last,
            "Bank service fee",
            [dr("7100", fee, "Service fee"), cr(CASH_OPERATING, fee, "Service fee")],
        )
        self.same_day(CASH_OPERATING, last, -fee, "SERVICE FEE")
        earned = money(rng.randint(5_000, 40_000))
        self.post(
            last,
            "Interest earned",
            [dr(CASH_OPERATING, earned, "Interest"), cr("4900", earned, "Interest")],
        )
        self.same_day(CASH_OPERATING, last, earned, "INTEREST PAID")
        depreciation = money(rng.randint(600_000, 700_000))
        self.post(
            end,
            "Depreciation",
            [
                dr("6900", depreciation, "Monthly depreciation"),
                cr("1550", depreciation, "Monthly depreciation"),
            ],
        )
        accrual = money(rng.randint(500_000, 1_500_000))
        self.post(
            end,
            "Accrued professional fees",
            [dr("6500", accrual, "Accrual"), cr("2100", accrual, "Accrual")],
        )
        reverse_on = end + timedelta(days=1)
        if reverse_on <= self.books.period_end:
            self.post(
                reverse_on,
                "Reverse accrued professional fees",
                [dr("2100", accrual, "Reversal"), cr("6500", accrual, "Reversal")],
            )

    def settle(self) -> None:
        rng, end = self.rng("settle"), self.books.period_end
        for item in self.books.receivables:
            if item.settles is not None and item.settles <= end:
                self.post(
                    item.settles,
                    f"Customer receipt - {item.counterparty}",
                    [
                        dr(CASH_OPERATING, item.amount, "Receipt", item.counterparty),
                        cr(AR, item.amount, "Receipt", item.counterparty),
                    ],
                )
                self.pay_in(CASH_OPERATING, item.settles, item.amount, "DEPOSIT", rng)
        for item in self.books.payables:
            if item.settles is not None and item.settles <= end:
                self.post(
                    item.settles,
                    f"Vendor payment - {item.counterparty}",
                    [
                        dr(AP, item.amount, "Payment", item.counterparty),
                        cr(CASH_OPERATING, item.amount, "Payment", item.counterparty),
                    ],
                )
                self.pay_out(
                    CASH_OPERATING,
                    item.settles,
                    item.amount,
                    item.counterparty,
                    rng,
                    cheque=rng.random() < 0.7,
                )

    def close(self) -> None:
        """Close revenue and expenses to retained earnings at each fiscal year end."""
        start = self.books.period_start
        year_ends = [month_end(add_months(start, n)) for n in range(11, 400, 12)]
        opened = start
        for year_end in (d for d in year_ends if d <= self.books.period_end):
            balances = {code: ZERO for code in PROFIT_AND_LOSS}
            for on, _, _, posted in self.drafts:
                if opened <= on <= year_end:
                    for ln in posted:
                        if ln.account_code in balances:
                            balances[ln.account_code] += ln.debit - ln.credit
            lines: list[JournalLine] = []
            for code, net in balances.items():
                if net > 0:
                    lines.append(cr(code, net, "Year-end close"))
                elif net < 0:
                    lines.append(dr(code, -net, "Year-end close"))
            result = sum(balances.values(), ZERO)  # net debit = loss
            lines.append(
                dr(RETAINED_EARNINGS, result, "Year-end close")
                if result > 0
                else cr(RETAINED_EARNINGS, -result, "Year-end close")
            )
            self.post(year_end, "Year-end close", lines)
            opened = year_end + timedelta(days=1)

    def finish(self) -> tuple[JournalEntry, ...]:
        out: list[JournalEntry] = []
        counters: dict[str, int] = {}
        for on, _, memo, lines in sorted(self.drafts, key=lambda d: (d[0], d[1])):
            month = f"{on:%Y%m}"
            counters[month] = counters.get(month, 0) + 1
            out.append(JournalEntry(f"JE-{month}-{counters[month]:05d}", on, memo, lines))
        return tuple(out)


def build_books(seed: int, prefix: str, start: date, months: int, size: str) -> Books:
    """Simulate one client entity's books from `start` for `months` months."""
    return _Simulation(seed, prefix, start, months, size).run()

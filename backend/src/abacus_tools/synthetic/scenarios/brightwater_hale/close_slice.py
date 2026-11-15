"""The CAS close slice (C-01-T13; TASK-8031; C-01 §5.3; SPEC-655): Copperleaf Coffee Roasters,
Inc.'s August 2026 close and the 22-close August portfolio, as the figures the seed loads and
every CLS screen reads.

Every figure is the epic's and the handoff's (C-01 §5.3 seed facts; CLS-01, CLS-02, CLS-05,
CLS-06, CLS-09, CLS-10 and POR-11), never typed fresh elsewhere. The figure book
(`tests/golden/scenario/brightwater_hale/copperleaf_close_figures.json`) is the independent
transcription; `tests/golden/scenario/test_c01t13_close_figures.py` foots this slice against it and
`apps/web/src/fixtures/contracts/close-figures.test.ts` foots the screens' fixtures against it.

Rules the slice keeps (C-01 §5.3): no kit sample data (no "13-task close run", no "Closed", no
Elena Ruiz); the savings request keeps its designed "due Sep 5" (a Saturday) in POR-11 a, and the
business-day rules apply from plan v4 (DF-34). Due dates follow QC-7: Copperleaf is due Tue
Sep 8 (BD5) and Bluebird Bakery Thu Sep 10 (BD7), so past due reads 4 and 2 business days; the
CLS-01 artboard's "Sep 10" and "Sep 12" are the designed cells. The close records load through
the closes services (C-01-T14 kind provider and record service, C-01-T15 plans); this module holds
no database code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final, Literal

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT

D = Decimal
COPPERLEAF: Final = "Copperleaf Coffee Roasters, Inc."
PERIOD: Final = "2026-08"
E0: Final = datetime(2026, 9, 14, 9, 24, tzinfo=CT)

CloseStatus = Literal["not_started", "in_progress", "in_review", "approved", "delivered", "locked"]

# --- people (CLS-01: the initials pairs) ---------------------------------------------------------

PEOPLE: Final = {
    "RM": "Raj Malhotra",
    "PR": "Priya Raman",
    "EG": "Ezra Gold",
    "IV": "Ivy Vance",
    "EW": "Erin Walsh",
    "RF": "Rosa Fuentes",
    "HV": "Helen Voss",
}
CLIENT_CONTACT: Final = "Tess Moreno"  # owner; portal "Active"
CLIENT_ANSWERER: Final = "Ben Ashby"


# --- CLS-01 the August portfolio -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PortfolioClose:
    ref: str  # "C1"
    client: str
    status: CloseStatus
    reconciled: int
    accounts: int
    open_issues: int
    due_on: date  # the due date, or the delivery date on a delivered row
    days_past_due: int | None
    preparer: str
    reviewer: str
    running: bool = False
    note: str | None = None

    @property
    def reconciled_pct(self) -> int:
        """Whole percent, half up (9 / 21 = 42.86 → 43)."""
        return int((D(self.reconciled) * 100 / D(self.accounts)).quantize(D(1), "ROUND_HALF_UP"))


def _c(
    ref: str,
    client: str,
    status: CloseStatus,
    rec: tuple[int, int],
    issues: int,
    due: tuple[int, int],
    pair: str,
    *,
    past_due: int | None = None,
    running: bool = False,
    note: str | None = None,
) -> PortfolioClose:
    prep, rev = pair.split("/")
    return PortfolioClose(
        ref, client, status, rec[0], rec[1], issues, date(2026, *due), past_due, prep, rev,
        running, note,
    )  # fmt: skip


PORTFOLIO: Final = (
    _c("C1", COPPERLEAF, "in_progress", (9, 21), 7, (9, 8), "RM/PR", past_due=4, running=True),
    _c("C2", "Juniper & Oak Interiors, LLC", "delivered", (21, 21), 0, (9, 10), "EG/PR"),
    _c("C3", "Two Rivers Brewing Co.", "in_progress", (13, 21), 3, (9, 15), "EG/HV"),
    _c("C4", "Larkspur Floral, Inc.", "in_review", (21, 21), 2, (9, 15), "IV/HV"),
    _c("C5", "Pinecrest Pediatrics, PC", "delivered", (21, 21), 0, (9, 9), "EW/PR"),
    _c("C6", "Cedar Hollow Farms, LLC", "in_progress", (8, 21), 5, (9, 18), "EG/HV", running=True),
    _c("C7", "Summit Line Logistics, Inc.", "in_progress", (12, 22), 4, (9, 15), "RF/HV"),
    _c("C8", "Bramble & Finch Design, LLC", "in_review", (21, 21), 1, (9, 16), "IV/RF"),
    _c("C9", "Hollis Creek Veterinary, PC", "in_progress", (10, 21), 3, (9, 18), "EW/HV",
       running=True),
    _c("C10", "Alder & Ash Furniture Co.", "in_progress", (15, 21), 2, (9, 16), "RF/PR"),
    _c("C11", "Bluebird Bakery Co.", "in_progress", (6, 21), 6, (9, 10), "IV/RF", past_due=2),
    _c("C12", "Canyon Pass Climbing Gym, LLC", "not_started", (0, 21), 0, (9, 20), "EG/HV",
       note="statements not received"),
    _c("C13", "Foxglove Studio, LLC", "in_review", (21, 21), 1, (9, 16), "IV/RF"),
    _c("C14", "Granary Row Market, Inc.", "in_progress", (11, 21), 4, (9, 17), "RF/PR"),
    _c("C15", "Ironwood Landscape Co.", "not_started", (0, 21), 0, (9, 21), "EW/HV"),
    _c("C16", "Kettle & Kiln Pottery, LLC", "in_progress", (14, 21), 2, (9, 17), "IV/RF"),
    _c("C17", "Lumen Dental Lab, Inc.", "in_review", (21, 21), 2, (9, 15), "EW/HV"),
    _c("C18", "Maple & Main Hardware, Inc.", "in_progress", (10, 23), 5, (9, 18), "RF/PR"),
    _c("C19", "Northfield Pet Clinic, PC", "in_progress", (12, 21), 3, (9, 17), "EG/HV"),
    _c("C20", "Orchard Lane Wellness, LLC", "delivered", (21, 21), 0, (9, 11), "IV/RF"),
    _c("C21", "Prairie Wind Solar Installers, Inc.", "not_started", (0, 21), 0, (9, 25), "EW/HV"),
    _c("C22", "Quill & Press Printing Co.", "in_review", (21, 21), 1, (9, 16), "RF/PR"),
)  # fmt: skip


def tiles() -> dict[str, int]:
    """The four tiles (DV-9): Approved counts under In review, Locked under Delivered."""
    fold = {"approved": "in_review", "locked": "delivered"}
    out = {"not_started": 0, "in_progress": 0, "in_review": 0, "delivered": 0}
    for close in PORTFOLIO:
        out[fold.get(close.status, close.status)] += 1
    return out


# --- CLS-02 the close record and its runs --------------------------------------------------------

DOCUMENTS_IN_BINDER: Final = 58
REQUESTS_PUBLISH_ON: Final = date(2026, 9, 1)  # BD1
PORTAL_REQUESTS_PENDING: Final = 2

ProcedureState = Literal["queued", "running", "needs_attention", "done", "failed"]


@dataclass(frozen=True, slots=True)
class Procedure:
    label: str
    status: ProcedureState
    meta: str
    open_count: int = 0


@dataclass(frozen=True, slots=True)
class TaskGroup:
    key: str
    label: str
    procedures: tuple[Procedure, ...]

    @property
    def done(self) -> int:
        return sum(p.status in ("done", "needs_attention") for p in self.procedures)


_4410 = "Operating Checking (Front Range Bank) ••4410"
_AMEX = "Amex Business Card ••1009"

RUN_2_STARTED: Final = datetime(2026, 9, 14, 9, 6, tzinfo=CT)
RUN_2: Final = (
    TaskGroup("recategorize", "Recategorize Revenue and Expenses", (
        Procedure(_4410, "needs_attention",
                  "1 agent-reported recategorization proposal · 1 open", 1),
        Procedure(_AMEX, "done", "No issues"),
    )),
    TaskGroup("reconcile_statements", "Reconcile to Statements", (
        Procedure(_4410, "needs_attention", "2 open · difference $0.00", 2),
        Procedure("Payroll Checking (Front Range Bank) ••4428", "done",
                  "No issues · Reconciled"),
        Procedure(_AMEX, "running",
                  "Running… cycle Jul 23–Aug 22 plus the card feed through Aug 31"),  # noqa: RUF001
    )),
    TaskGroup("third_party_sales", "Reconcile Third Party Sales (Square, Shopify)", (
        Procedure("Square", "done", "No issues · Reconciled · 21 transfers · net $71,482.36"),
        Procedure("Shopify", "running", "Running…"),
    )),
    TaskGroup("amortize_prepaids", "Identify and Amortize Prepaids", (
        Procedure("Prepaid insurance", "needs_attention", "1 open · Ties once posted", 1),
    )),
    TaskGroup("depreciate_fixed_assets", "Identify and Depreciate Fixed Assets", (
        Procedure("Fixed asset register", "running",
                  "Running… testing Sound Electric $3,200.00 against the $2,500 "
                  "capitalization policy"),
    )),
)  # fmt: skip
RUN_1_STARTED: Final = datetime(2026, 9, 2, 8, 15, tzinfo=CT)
RUN_1_TOTAL: Final = 22
RUN_1_ISSUES_RAISED: Final = 8
MAX_RUNNING: Final = 3  # "3 tasks running at once" (kernel/slots.py)


# --- CLS-06 the review queue ---------------------------------------------------------------------

Severity = Literal["high", "medium", "low"]
IssueClass = Literal["bank_rec", "schedule", "flux", "recategorize", "intake"]


@dataclass(frozen=True, slots=True)
class CloseIssue:
    severity: Severity
    issue_class: IssueClass
    title: str
    account: str
    waiting_on_client: bool = False


ISSUES: Final = (
    CloseIssue("medium", "flux",
               "Sound Electric $3,200.00 booked to Repairs & Maintenance — up 400% on July",
               "Repairs & Maintenance", waiting_on_client=True),
    CloseIssue("medium", "schedule",
               "Accrued expenses entry $14,900.00 is above the $10,000 other-accruals threshold",
               "Accrued Expenses"),
    CloseIssue("low", "bank_rec", "Outstanding check #2281 dated Feb 2026 has not cleared", _4410),
    CloseIssue("low", "bank_rec",
               "Vendor refund $380.00 on the Aug 27 statement is not recorded in the books",
               "Operating Checking ••4410"),
    CloseIssue("low", "schedule",
               "Prepaid insurance ties once the $700 August amortization posts",
               "Prepaid Insurance"),
    CloseIssue("low", "flux",
               "Payroll up 12.5% on July — new hires, merit increases and overtime",
               "Payroll Expenses"),
    CloseIssue("low", "bank_rec", "Amex statement cycle ends Aug 22, not on the calendar month",
               _AMEX),
)  # fmt: skip
NOTES: Final = 4  # CLS-06 e; never counted in the badge


# --- CLS-04 the account tree ---------------------------------------------------------------------

TREE: Final = {
    "assets": D("539055.45"),
    "liabilities": D("163543.05"),
    "equity": D("375512.40"),
    "bank": D("256610.50"),
    "other_current_assets_after_aje_02": D("49124.95"),
}


# --- CLS-05 Operating Checking ••4410 at Aug 31 --------------------------------------------------


@dataclass(frozen=True, slots=True)
class OutstandingCheck:
    number: str
    issued_on: date
    payee: str
    amount: Decimal

    def days_at(self, period_end: date) -> int:
        return (period_end - self.issued_on).days


PERIOD_END: Final = date(2026, 8, 31)
BALANCE_PER_BANK: Final = D("184236.18")
DEPOSIT_IN_TRANSIT: Final = D(
    "6412.40"
)  # Square transfer Aug 31 (sales Aug 28–30)  # noqa: RUF003
OUTSTANDING_CHECKS: Final = (
    OutstandingCheck("#2281", date(2026, 2, 19), "Highline Espresso Service", D("1240.00")),
    OutstandingCheck("#2287", date(2026, 8, 26), "Denver Paper Supply", D("3615.75")),
    OutstandingCheck("#2290", date(2026, 8, 28), "Mile High Window Cleaning", D("802.33")),
)
BOOK_BALANCE: Final = D("184610.50")
UNRECORDED_REFUND: Final = D("380.00")  # Rocky Ridge Dairy Co., statement line Aug 27
STALE_AFTER_DAYS: Final = 90


def adjusted_bank() -> Decimal:
    return (
        BALANCE_PER_BANK + DEPOSIT_IN_TRANSIT - sum((c.amount for c in OUTSTANDING_CHECKS), D(0))
    )


def adjusted_book() -> Decimal:
    return BOOK_BALANCE + UNRECORDED_REFUND


# Statement page 2 (CLS-05 viewer): (date, description, withdrawal, deposit).
STATEMENT_PAGE_2: Final = (
    (date(2026, 8, 24), "SQUARE INC TRANSFER", None, D("2427.05")),
    (date(2026, 8, 25), "SQUARE INC TRANSFER", None, D("7637.03")),
    (date(2026, 8, 25), "ROCKY RIDGE DAIRY ACH PMT", D("2860.00"), None),
    (date(2026, 8, 26), "SQUARE INC TRANSFER", None, D("2058.31")),
    (date(2026, 8, 27), "SQUARE INC TRANSFER", None, D("2046.59")),
    (date(2026, 8, 27), "ROCKY RIDGE DAIRY CO REFUND", None, D("380.00")),
    (date(2026, 8, 28), "SQUARE INC TRANSFER", None, D("2131.10")),
    (date(2026, 8, 31), "SQUARE INC TRANSFER", None, D("2356.11")),
    (date(2026, 8, 31), "TRANSFER TO ••4428 PAYROLL", D("24600.00"), None),
)
STATEMENT_FILE: Final = "FrontRange_4410_Statement_2026-08.pdf"
STATEMENT_PAGES: Final = 3


# --- Square and the prepaid schedule -------------------------------------------------------------

SQUARE: Final = {"gross": D("73166.90"), "fees": D("1684.54"), "net": D("71482.36")}
SQUARE_TRANSFERS: Final = 21
PREPAID_ANNUAL: Final = D("8400.00")
PREPAID_MONTHS: Final = 12
PREPAID_GL: Final = D("3500.00")
PREPAID_SCHEDULE: Final = D("2800.00")


# --- CLS-10 flux, August vs July (whole dollars, as adjusted) ------------------------------------


@dataclass(frozen=True, slots=True)
class FluxLine:
    key: str
    caption: str
    prior: int
    current: int
    kind: Literal["revenue", "cogs", "opex", "other"]

    @property
    def change(self) -> int:
        return self.current - self.prior

    @property
    def change_pct(self) -> Decimal:
        return (D(self.change) * 100 / D(self.prior)).quantize(D("0.1"), "ROUND_HALF_UP")

    def over_both(self, pct: Decimal, usd: int) -> bool:
        """Both thresholds must be exceeded (KNW-04: "10% and $2,500")."""
        return abs(self.change_pct) > pct and abs(self.change) > usd


FLUX_THRESHOLD_PCT: Final = D("10")
FLUX_THRESHOLD_USD: Final = 2500
FLUX: Final = (
    FluxLine("revenue", "Revenue", 205_300, 214_600, "revenue"),
    FluxLine("cogs", "Cost of goods sold", 81_170, 84_860, "cogs"),
    FluxLine("payroll", "Payroll", 61_240, 68_910, "opex"),
    FluxLine("rent", "Rent", 9_800, 9_800, "opex"),
    FluxLine("merchant_fees", "Merchant fees", 4_710, 4_980, "opex"),
    FluxLine("legal_professional", "Legal & professional fees", 4_800, 4_840, "opex"),
    FluxLine("repairs_maintenance", "Repairs & maintenance", 640, 3_200, "opex"),
    FluxLine("utilities_facilities", "Utilities & facilities", 2_960, 3_140, "opex"),
    FluxLine("marketing", "Marketing", 3_980, 2_450, "opex"),
    FluxLine("depreciation", "Depreciation", 2_140, 2_140, "opex"),
    FluxLine("software", "Software & subscriptions", 1_180, 1_265, "opex"),
    FluxLine("insurance", "Insurance", 700, 700, "opex"),
    FluxLine("interest", "Interest expense", 525, 520, "other"),
)
PAYROLL_DRIVERS: Final = (("New hires", 4_350), ("Merit increases", 1_850), ("Overtime", 1_470))


def flux_totals(period: Literal["prior", "current"]) -> dict[str, int]:
    def total(kind: str) -> int:
        return sum(getattr(line, period) for line in FLUX if line.kind == kind)

    gross = total("revenue") - total("cogs")
    opex = total("opex")
    return {"gross_profit": gross, "operating_expenses": opex,
            "net_income": gross - opex - total("other")}  # fmt: skip


# --- CLS-09 the close plan, v3 -------------------------------------------------------------------

Review = Literal["senior_signoff", "manager_approval"]


@dataclass(frozen=True, slots=True)
class PlanRow:
    account_class: str
    account: str
    procedure: str
    method: str
    evidence: str
    source: str
    review: Review
    threshold: str


_S, _M = "senior_signoff", "manager_approval"
_FA = ("Beginning assets + additions − disposals", "Asset register + invoices", "accrued_register")  # noqa: RUF001
PLAN_V3: Final = (
    PlanRow("bank", _4410, "reconciliation", "Bank statement → GL; outstanding items aged",
            "Bank statement", "bank_feed", _S,
            "Difference $0.00 · outstanding items > 90 days flagged"),
    PlanRow("bank", "Payroll Checking (Front Range Bank) ••4428", "reconciliation",
            "Bank statement → GL", "Bank statement", "bank_feed", _S, "Difference $0.00"),
    PlanRow("bank", "Business Savings (Front Range Bank) ••4436", "reconciliation",
            "Bank statement → GL", "Bank statement", "client_upload", _S, "Difference $0.00"),
    PlanRow("accounts_receivable", "Accounts Receivable", "aging",
            "Subledger → GL; wholesale aging reviewed", "AR aging", "quickbooks_online", _S,
            "Subledger = GL"),
    PlanRow("other_current_assets", "Undeposited Funds", "clear_and_age",
            "Deposit detail → bank deposits", "Deposit detail", "quickbooks_online", _S,
            "Items > 5 days flagged"),
    PlanRow("other_current_assets", "Square Clearing", "third_party_sales",
            "Gross − fees → net transfers → bank", "Square payout report", "client_upload", _S,  # noqa: RUF001
            "Clears to the next-day transfer"),
    PlanRow("other_current_assets", "Shopify Clearing", "third_party_sales",
            "Gross − fees − refunds → payouts → bank", "Shopify payout report", "client_upload",  # noqa: RUF001
            _S, "Clears to the next payout"),
    PlanRow("other_current_assets", "Inventory", "rollforward", "Roast log (perpetual) → GL",
            "Inventory valuation report", "quickbooks_online", _M, "Difference ≤ $500"),
    PlanRow("other_current_assets", "Prepaid Insurance", "amortization",
            "Arrangement → monthly entry", "Policy declarations", "files", _S,
            "Prepaids ≤ $10,000"),
    PlanRow("fixed_assets", "Roasting Equipment", "rollforward", _FA[0], _FA[1], _FA[2], _M,
            "Capitalize > $2,500 (de minimis)"),
    PlanRow("fixed_assets", "Furniture & Fixtures", "rollforward", _FA[0], _FA[1], _FA[2], _M,
            "Capitalize > $2,500 (de minimis)"),
    PlanRow("fixed_assets", "Leasehold Improvements", "rollforward", _FA[0], _FA[1], _FA[2], _M,
            "Capitalize > $2,500 (de minimis)"),
    PlanRow("fixed_assets", "Accumulated Depreciation", "depreciation",
            "Calculate monthly, straight-line", "Asset register", "accrued_register", _M,
            "Depreciation ≤ $10,000"),
    PlanRow("credit_cards", _AMEX, "reconciliation",
            "Statement → GL; cycle-date cutoff to month end", "Card statement + card feed",
            "client_upload", _S, "Difference $0.00"),
    PlanRow("accounts_payable", "Accounts Payable", "aging_cutoff",
            "Subledger → GL; unrecorded liabilities search", "AP aging", "client_upload", _S,
            "Subledger = GL"),
    PlanRow("other_current_liabilities", "Accrued Payroll", "accrual",
            "Days worked after the last pay period × rate; reverses next month",  # noqa: RUF001
            "Payroll register", "client_upload", _S, "Payroll accruals ≤ $15,000"),
    PlanRow("other_current_liabilities", "Accrued Expenses", "accrual",
            "Received-not-invoiced + recurring bills; reverses next month",
            "AP detail + receiving log", "quickbooks_online", _M, "Other accruals ≤ $10,000"),
    PlanRow("other_current_liabilities", "Deferred Revenue — Subscriptions", "rollforward",
            "Prior balance + billings − recognized → ending balance",  # noqa: RUF001
            "Subscription billing report", "client_upload", _M, "Deferred revenue ≤ $10,000"),
    PlanRow("other_current_liabilities", "Sales Tax Payable", "tie_to_return",
            "Collected vs remitted", "Sales tax liability report", "quickbooks_online", _S,
            "Liability = return"),
    PlanRow("other_current_liabilities", "Payroll Liabilities", "tie_to_filings",
            "Payroll register → GL; liabilities paid", "Payroll register", "client_upload", _S,
            "Liabilities = filings"),
    PlanRow("long_term_liabilities", "Equipment Loan (Front Range Bank)", "amortization",
            "Lender balance → GL; current portion split", "Loan statement", "client_upload", _S,
            "Lender balance = GL"),
    PlanRow("income_statement", "Revenue & expenses", "recategorize",
            "Transaction coding review by account feed", "GL detail", "quickbooks_online", _S,
            "—"),
    PlanRow("income_statement", "Revenue & expenses", "flux", "Month over month vs threshold",
            "GL detail", "quickbooks_online", _M, "10% and $2,500"),
)  # fmt: skip
PLAN_V3_PUBLISHED: Final = (date(2026, 6, 2), "Priya Raman")
PLAN_TEMPLATE: Final = "Café with Square/Shopify"
AJE_POLICY: Final = "BH AJE thresholds v2"
# Distinct client-upload requests the plan generates (the payroll register serves two rows).
REQUEST_TEMPLATES: Final = (
    "Business Savings ••4436 statement",
    "Square payout report",
    "Shopify payout report",
    "Amex statement",
    "AP aging",
    "Payroll register",
    "Subscription billing report",
    "Loan statement",
)
V4_REQUESTS_PER_MONTH: Final = 7


def plan_accounts() -> int:
    """Balance-sheet accounts in the plan: the income-statement rows are not accounts."""
    return sum(row.account_class != "income_statement" for row in PLAN_V3)


# --- POR-11 the client's month -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PortalRequest:
    title: str
    received: bool


PORTAL_REQUESTS: Final = (
    PortalRequest("Front Range Bank savings ••4436 statement — August", received=False),
    PortalRequest("Square payouts report — August", received=True),
    PortalRequest("Shopify payouts report — August", received=True),
    PortalRequest("American Express ••1009 statement — cycle ending Aug 22", received=True),
    PortalRequest(
        "Payroll register — August (biweekly pay dates Aug 3, 17 and 31)", received=True
    ),
    PortalRequest("AP aging — Aug 31", received=True),
    PortalRequest("Equipment loan statement — August", received=True),
    PortalRequest("Subscription billing report — August", received=True),
    PortalRequest("Sound Electric invoice — Aug 18 ($3,200)", received=False),
)
TRANSACTION_QUESTIONS: Final = (
    "Check #2281 for $1,240.00 to Highline Espresso Service, dated February 19, 2026, still "
    "hasn't cleared. Was it lost, voided or reissued?",
    "Front Range Bank shows a $380.00 deposit from Rocky Ridge Dairy Co. on August 27. What was "
    "it for?",
    "What was the $3,200 payment to Sound Electric?",
)

# KNW-04 a: the accruals within threshold and the entry held above it.
KNW_04A: Final = {
    "within": (D("11860.00"), D("700.00"), D("2140.00"), D("5320.00")),
    "held": D("14900.00"),
}

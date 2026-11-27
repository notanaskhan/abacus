"""The CAS posting and delivery slice (C-02-T09; TASK-8508; C-02 §5.3; SPEC-700, SPEC-701):
Copperleaf Coffee Roasters, Inc.'s August 2026 adjusting entries and their posting to QuickBooks
Online, the ledger-sync history, the August statements, the December 2026 close handed to tax, and
the 2026 1099 / W-9 tracker; plus Bluestem Analytics' empty tracker and the attest-flagged CAS
client of CLS-07g.

Every figure is the handoff's (CLS-07, CLS-08, CLS-11, CLS-12, CLS-13 specs) or the epic's §5.3,
never typed fresh elsewhere. The figure book
(`tests/golden/scenario/brightwater_hale/copperleaf_cas_delivery_figures.json`) is the
independent transcription; `tests/golden/scenario/test_c02t09_cas_delivery_figures.py` foots this
slice against it. Where the handoff gives a row count but not the row (AJE-01, 02 and 04 lines;
the Jan-Apr batches below the fold; the 2025 forms), the slice keeps the count and invents no row.

Seed contradictions settled (DEC-5508): the QBO connection is Mar 4, 2026 (POR-16e) and the write
grant Mar 9, 2026 (CLS-11 "Authorized by"); "Elena Ruiz Design" is a CLS-13 vendor, allowlisted by
exact string in the kit-contamination scan. The attest-flagged CAS client (CLS-07g, "not
Copperleaf") is Juniper & Oak Interiors, LLC: the seed's CAS client with an audit engagement.
This module holds no database code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final, Literal, cast

from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import CT

D = Decimal
_ZERO: Final = Decimal("0.00")
COPPERLEAF: Final = "Copperleaf Coffee Roasters, Inc."
ATTEST_CAS_CLIENT: Final = "Juniper & Oak Interiors, LLC"
EMPTY_TRACKER_CLIENT: Final = "Bluestem Analytics, LLC"
E0: Final = datetime(2026, 9, 14, 9, 24, tzinfo=CT)
POLICY: Final = "BH AJE thresholds v2"
CONNECTED_ON: Final = date(2026, 3, 4)  # POR-16e
WRITE_GRANT_ON: Final = date(2026, 3, 9)  # CLS-11 "Authorized by — Tess Moreno · Mar 9, 2026"
CONSENT_COPY: Final = "por16.qbo.post_entries.v2"

# Client personas added for C-02 (chapter 04 §6.5): the owner grants writes and approves the
# package; the approver of record answers W-9 requests and may approve the package (DEC-63).
CLIENT_PERSONAS: Final = {"tess-moreno": "Tess Moreno", "ben-ashby": "Ben Ashby"}

# --- CLS-07 August entries -----------------------------------------------------------------------

EntryStatus = Literal["within_threshold", "review_required"]


@dataclass(frozen=True, slots=True)
class Line:
    account: str
    debit: Decimal = _ZERO
    credit: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class Entry:
    ref: str
    title: str
    account_class: str | None  # None: "No threshold class (bank adjustments)"
    class_limit: Decimal | None
    line_count: int
    amount: Decimal
    initial: EntryStatus
    reverses_on: date | None
    qbo_id: str  # after batch 2026-08-A
    lines: tuple[Line, ...] = ()  # only where the handoff names them


THRESHOLDS: Final = {
    "payroll_accruals": D("15000.00"),
    "prepaids": D("10000.00"),
    "depreciation": D("10000.00"),
    "deferred_revenue": D("10000.00"),
    "other_accruals": D("10000.00"),
}
ENTRIES: Final = (
    Entry("AJE-01", "Payroll accrual", "payroll_accruals", THRESHOLDS["payroll_accruals"], 3,
          D("11860.00"), "within_threshold", date(2026, 9, 1), "48213"),
    Entry("AJE-02", "Prepaid insurance", "prepaids", THRESHOLDS["prepaids"], 2, D("700.00"),
          "within_threshold", None, "48214"),
    Entry("AJE-03", "Depreciation", "depreciation", THRESHOLDS["depreciation"], 2, D("2140.00"),
          "within_threshold", None, "48215"),
    Entry("AJE-04", "Deferred revenue (subscriptions)", "deferred_revenue",
          THRESHOLDS["deferred_revenue"], 2, D("5320.00"), "within_threshold", None, "48216"),
    Entry("AJE-05", "Accrued expenses", "other_accruals", THRESHOLDS["other_accruals"], 4,
          D("14900.00"), "review_required", date(2026, 9, 1), "48217",
          lines=(
              Line("Inventory — Green Coffee", debit=D("12600.00")),
              Line("Utilities & Facilities", debit=D("1480.00")),
              Line("Legal & Professional Fees", debit=D("820.00")),
              Line("Accrued Expenses", credit=D("14900.00")),
          )),
    # CLS-07c (10:12 AM): from the ••4410 reconciliation (CLS-05).
    Entry("AJE-06", "Vendor refund — Rocky Ridge Dairy Co.", None, None, 2, D("380.00"),
          "review_required", None, "48218",
          lines=(
              Line("Operating Checking", debit=D("380.00")),
              Line("Cost of Goods Sold — Dairy", credit=D("380.00")),
          )),
)  # fmt: skip
FIRST_FIVE: Final = ENTRIES[:5]


def cls07_rows() -> dict[str, object]:
    """CLS-07's entries as plain JSON (C-02-T17; DEC-5637): `make fixtures` writes them to
    `apps/web/src/fixtures/seed/scenario.cls07-entries.json` with no database. Amounts are strings
    with cents; the class limit is the K-02 policy's; lines only where the handoff names them."""
    return {
        "client": COPPERLEAF,
        "period": "2026-08",
        "policy": POLICY,
        "entries": [
            {
                "ref": e.ref,
                "title": e.title,
                "account_class": e.account_class,
                "class_limit": None if e.class_limit is None else str(e.class_limit),
                "line_count": e.line_count,
                "amount": str(e.amount),
                "initial": e.initial,
                "reverses_on": None if e.reverses_on is None else e.reverses_on.isoformat(),
                "qbo_id": e.qbo_id,
                "lines": [
                    {"account": ln.account, "debit": str(ln.debit), "credit": str(ln.credit)}
                    for ln in e.lines
                ],
            }
            for e in ENTRIES
        ],
    }


# CLS-07e and CLS-11's July failure: the account the fake QBO reports inactive.
INACTIVE_ACCOUNT: Final = "Accumulated Depreciation"

# --- CLS-11 posting log --------------------------------------------------------------------------

BatchStatus = Literal["proposed", "posted"]


@dataclass(frozen=True, slots=True)
class Batch:
    code: str
    period: str
    entries: int
    amount: Decimal | None  # None: below the fold (Jan-Apr), not given by the handoff
    status: BatchStatus
    posted_at: datetime | None
    qbo_first: str | None
    qbo_last: str | None
    resolved_failures: int = 0


BATCHES: Final = (
    Batch("2026-08-A", "2026-08", 5, D("34920.00"), "proposed", None, None, None),
    Batch("2026-07-A", "2026-07", 6, D("31480.00"), "posted",
          datetime(2026, 8, 11, 14, 41, tzinfo=CT), "47602", "47607", resolved_failures=1),
    Batch("2026-06-A", "2026-06", 5, D("27915.00"), "posted",
          datetime(2026, 7, 10, 11, 5, tzinfo=CT), "46955", "46959"),
    Batch("2026-05-A", "2026-05", 5, D("26340.00"), "posted",
          datetime(2026, 6, 10, 15, 18, tzinfo=CT), "46310", "46314"),
)  # fmt: skip
# January to April, below the fold in CLS-11a (C-02-T35: the canvas shows their figures).
BELOW_THE_FOLD_BATCHES: Final = (
    Batch("2026-04-A", "2026-04", 5, D("25075.00"), "posted",
          datetime(2026, 5, 11, 13, 36, tzinfo=CT), "45663", "45667"),
    Batch("2026-03-A", "2026-03", 5, D("24410.00"), "posted",
          datetime(2026, 4, 10, 10, 48, tzinfo=CT), "45024", "45028"),
    Batch("2026-02-A", "2026-02", 5, D("21935.00"), "posted",
          datetime(2026, 3, 27, 14, 55, tzinfo=CT), "44719", "44723"),
    Batch("2026-01-A", "2026-01", 5, D("22860.00"), "posted",
          datetime(2026, 3, 20, 16, 12, tzinfo=CT), "44568", "44572"),
)  # fmt: skip
BELOW_THE_FOLD_POSTED: Final = tuple(b.code for b in reversed(BELOW_THE_FOLD_BATCHES))
# C-02-T44 (DEC-6029): posted at 10:20 AM (CLS-11 b's row and b2's drawer read "Sep 14, 10:20
# AM"); the closing date moved to Aug 31 at 10:22 AM, after it.
AUGUST_POSTED_BATCH: Final = Batch(
    "2026-08-A", "2026-08", 6, D("35300.00"), "posted",
    datetime(2026, 9, 14, 10, 20, tzinfo=CT), "48213", "48218",
)  # fmt: skip
CLOSING_DATES: Final = (
    (date(2026, 7, 31), datetime(2026, 8, 11, 14, 42, tzinfo=CT)),  # set by Raj Malhotra
    (date(2026, 8, 31), datetime(2026, 9, 14, 10, 22, tzinfo=CT)),  # after 2026-08-A
)
SYNC_EVENTS: Final = (
    (datetime(2026, 9, 14, 9, 2, tzinfo=CT), "sync", 1214),
    (datetime(2026, 9, 14, 8, 2, tzinfo=CT), "sync", 1209),
    (datetime(2026, 8, 11, 14, 42, tzinfo=CT), "closing_date", None),
    (datetime(2026, 8, 11, 14, 41, tzinfo=CT), "post", 6),
    (datetime(2026, 8, 11, 14, 38, tzinfo=CT), "sync_failed", None),  # Failed post AJE-03
)

# Fake QBO scripted write outcomes, by CLS state (C-02 §5.3).
FakeOutcome = Literal["inactive_account", "rate_limited", "unauthorized", "closing_date_locked"]
FAKE_QBO_SCRIPT: Final[dict[str, tuple[FakeOutcome, str | None]]] = {
    "CLS-07e": ("inactive_account", "AJE-03"),
    "CLS-11c": ("rate_limited", None),  # 429 at 10:03, retrying 10:07
    "CLS-11d": ("unauthorized", None),  # 401 at 09:14: Needs reauth
    "CLS-11e": ("closing_date_locked", None),  # an Aug 31 entry against closing date Aug 31
}

# --- CLS-08 August statements --------------------------------------------------------------------

BALANCE_SHEET: Final = {
    "current_assets": (
        ("Cash", D("256990.50")),
        ("Merchant clearing (Square, Shopify)", D("3464.95")),
        ("Accounts receivable", D("18420.00")),
        ("Inventory", D("55460.00")),
        ("Prepaid insurance", D("2800.00")),
    ),
    "property_and_equipment": (
        ("Roasting equipment", D("156000.00")),
        ("Furniture and fixtures", D("25200.00")),
        ("Leasehold improvements", D("97200.00")),
        ("Less accumulated depreciation", D("-66340.00")),
    ),
    "current_liabilities": (
        ("Accounts payable", D("21380.45")),
        ("Credit card payable", D("9846.12")),
        ("Accrued payroll", D("11860.00")),
        ("Accrued expenses", D("14900.00")),
        ("Deferred revenue — subscriptions", D("26600.00")),
        ("Sales tax payable", D("7284.10")),
        ("Payroll liabilities", D("4612.38")),
        ("Current portion of equipment loan", D("18000.00")),
    ),
    "long_term_liabilities": (("Equipment loan, less current portion", D("70500.00")),),
    "equity": (
        ("Common stock", D("10000.00")),
        ("Retained earnings, Jan 1, 2026", D("263792.40")),
        ("Net income, Jan\N{EN DASH}Aug 2026", D("186420.00")),
        ("Distributions", D("-96000.00")),
    ),
}
# (August, July)
INCOME_STATEMENT: Final = {
    "revenue": (
        ("Café sales", D("96400.00"), D("92100.00")),
        ("Online sales", D("41880.00"), D("39600.00")),
        ("Wholesale", D("61000.00"), D("58300.00")),
        ("Subscription revenue", D("15320.00"), D("15300.00")),
    ),
    "cost_of_goods_sold": (("Cost of goods sold", D("84860.00"), D("81170.00")),),
    "operating_expenses": (
        ("Payroll", D("68910.00"), D("61240.00")),
        ("Rent", D("9800.00"), D("9800.00")),
        ("Merchant fees", D("4980.00"), D("4710.00")),
        ("Legal & professional fees", D("4840.00"), D("4800.00")),
        ("Repairs & maintenance", D("3200.00"), D("640.00")),
        ("Utilities & facilities", D("3140.00"), D("2960.00")),
        ("Marketing", D("2450.00"), D("3980.00")),
        ("Depreciation", D("2140.00"), D("2140.00")),
        ("Software & subscriptions", D("1265.00"), D("1180.00")),
        ("Insurance", D("700.00"), D("700.00")),
    ),
    "interest_expense": (("Interest expense", D("520.00"), D("525.00")),),
}
PACKAGE_ROUTE: Final = "ar_c_70_preparation"
PACKAGE_LEGEND: Final = "No assurance is provided."
RELEASED_AT: Final = datetime(2026, 9, 14, 16, 25, tzinfo=CT)
RELEASED_BY: Final = "Priya Raman"  # the engagement Partner (CLS-08d)
CLIENT_APPROVED_AT: Final = datetime(2026, 9, 15, 8, 42, tzinfo=CT)

# --- CLS-12 the December 2026 close handed to tax ------------------------------------------------

DECEMBER_LOCKED_ON: Final = date(2027, 1, 11)
HANDED_OFF_AT: Final = datetime(2027, 1, 12, 14, 15, tzinfo=CT)
REOPENED_ON: Final = date(2027, 1, 20)
TB_VERSION: Final = "TB v1"
TARGET_RETURN: Final = "2026 Form 1120-S"
TAX_TEAM: Final = {"preparer": "Olivia Brandt", "reviewer": "Samuel Ito"}
MONTHLY_DEPRECIATION: Final = D("2140.00")
ACCUMULATED_DEPRECIATION_JUL_31: Final = D("64200.00")
FIXED_ASSET_COST: Final = D("278400.00")
PREPAID_INSURANCE_YEAR: Final = D("8400.00")
MONTHLY_DISTRIBUTION: Final = D("12000.00")
TAX_ISSUES_CREATED: Final = 3
# C-02-T48 (DEC-6031): CLS-12's open tax-relevant items, the close's CLS-06 notes as the sheet
# lists them (each with "Create tax issue" on).
HANDOFF_ITEMS: Final = (
    "Accrued payroll at Dec 31 includes wages of Tess Moreno, a shareholder-employee; deductible "
    "only when paid (§267(a)(2) and §267(e)).",
    "Sound Electric $3,200.00 repair (Aug 18): keep the repair analysis in the tax file (Treas. "
    "Reg. §1.263(a)-3).",
    "Square and Shopify 2026 Forms 1099-K: reconcile gross amounts to gross receipts.",
)
ENGINE: Final = "CCH Axcess Tax"


def cls12_handoff() -> dict[str, object]:
    """CLS-12 in C-02-T39's read shape with C-02-T48's additive target and provenance fields.
    `make fixtures` writes it to `apps/web/src/fixtures/seed/scenario.cls12-handoff.json`. Figures
    are code's over the seed (ADR-050): accumulated depreciation at Dec 31 is July's 64,200.00
    plus five months at 2,140.00; the year's book depreciation twelve months; distributions
    twelve months at 12,000.00; the prepaid policy fully amortized."""
    accumulated = ACCUMULATED_DEPRECIATION_JUL_31 + 5 * MONTHLY_DEPRECIATION
    return {
        "client": COPPERLEAF,
        "locked_on": DECEMBER_LOCKED_ON.isoformat(),
        "handed_off_at": HANDED_OFF_AT.isoformat(),
        "handed_off_by": "Priya Raman",
        "reopened_on": REOPENED_ON.isoformat(),
        "tb_version": TB_VERSION,
        "target_form": TARGET_RETURN.split(" ", 1)[1].removeprefix("Form "),
        "target_tax_year": int(TARGET_RETURN.split(" ", 1)[0]),
        "engine": ENGINE,
        "tax_team": TAX_TEAM,
        "tax_issues_created": TAX_ISSUES_CREATED,
        "schedules": [
            {"key": "fixed_assets", "figures": {
                "cost": f"{FIXED_ASSET_COST:.2f}",
                "accumulated_depreciation": f"{accumulated:.2f}",
                "book_depreciation": f"{12 * MONTHLY_DEPRECIATION:.2f}"}},
            {"key": "prepaid_expenses", "figures": {
                "amortized": f"{PREPAID_INSURANCE_YEAR:.2f}", "ending_balance": "0.00"}},
            {"key": "deferred_revenue", "figures": {}},
            {"key": "shareholder_distributions", "figures": {
                "total": f"{12 * MONTHLY_DISTRIBUTION:.2f}"}},
            {"key": "accrued_liabilities", "figures": {}},
        ],
        "items": list(HANDOFF_ITEMS),
    }  # fmt: skip


# --- CLS-13 1099 / W-9 tracker (payments Jan 1 - Aug 31, 2026) -----------------------------------

W9 = Literal["on_file", "requested", "tin_mismatch", "missing"]
Treatment = Literal["reportable", "below_threshold", "exempt_corporation", "paid_by_card"]


@dataclass(frozen=True, slots=True)
class Vendor:
    name: str
    entity: str
    w9: W9 | None
    tin_last4: str | None
    form: str | None
    amount: Decimal
    treatment: Treatment
    is_attorney: bool = False


THRESHOLD_2026: Final = D("2000.00")  # the C21 rules row (DEC-76), copied here for the seed test
VENDORS: Final = (
    Vendor("Larimer Street Properties, LLC", "LLC (partnership)", "on_file", "4471",
           "1099-MISC · Box 1 Rents", D("78400.00"), "reportable"),
    Vendor("Brightwater Hale LLP", "LLP (partnership)", "on_file", "2050", "1099-NEC",
           D("25600.00"), "reportable"),
    Vendor("Sound Electric Contractors, LLC", "Single-member LLC (individual)", "on_file",
           "6612", "1099-NEC", D("5840.00"), "reportable"),
    Vendor("Elena Ruiz Design", "Sole proprietor", "tin_mismatch", "3308", "1099-NEC",
           D("4200.00"), "reportable"),
    Vendor("Hartwell & Lowe LLP", "Law firm (partnership)", "on_file", "7719",
           "1099-NEC · attorney fees", D("3600.00"), "reportable", is_attorney=True),
    Vendor("Mile High Window Cleaning", "Sole proprietor", "requested", None, "1099-NEC",
           D("2640.00"), "reportable"),
    Vendor("Front Range Plumbing Co.", "Sole proprietor", "requested", None, "1099-NEC",
           D("1450.00"), "below_threshold"),
    Vendor("Rocky Ridge Dairy Co.", "C corporation", "on_file", "0935", None, D("16980.00"),
           "exempt_corporation"),
    Vendor("Kestrel Marketing Co.", "S corporation", "on_file", "5126", None, D("9600.00"),
           "exempt_corporation"),
    Vendor("Cedar Mutual Insurance Co.", "C corporation", "on_file", "8840", None,
           D("8400.00"), "exempt_corporation"),
    Vendor("Front Range Bank", "Bank (corporation)", "on_file", "3102", None, D("6120.00"),
           "exempt_corporation"),
    Vendor("Cascade Coffee Importers, Inc.", "—", None, None, None, D("41260.00"),
           "paid_by_card"),
)  # fmt: skip
W9_REQUESTED_ON: Final = date(2026, 9, 11)
MONTHLY_RENT: Final = D("9800.00")
MONTHLY_FIRM_FEE: Final = D("3200.00")
MONTHS_PAID: Final = 8
PRIOR_YEAR_ACCEPTED: Final = (2025, 5, date(2026, 1, 29))  # CLS-13e: five rows Accepted
# C-02-T47 (DEC-6030): CLS-13e's five 2025 returns as the artboard reads them (filed before the
# ledger connected Mar 9, 2026, so no 2025 payment ever synced).
PRIOR_YEAR_RETURNS: Final = (
    ("Larimer Street Properties, LLC", "misc", "1", D("114000.00")),
    ("Brightwater Hale LLP", "nec", "1", D("6800.00")),
    ("Sound Electric Contractors, LLC", "nec", "1", D("3120.00")),
    ("Elena Ruiz Design", "nec", "1", D("5400.00")),
    ("Hartwell & Lowe LLP", "nec", "1", D("4250.00")),
)
TIN_MISMATCH_ON: Final = date(2026, 8, 28)  # CLS-13c: "IRS TIN Matching, Aug 28"
DECEMBER_CLOSE_DUE: Final = date(2027, 1, 11)  # CLS-13a tooltip: "(target Jan 11, 2027)"
# C-02-T47: the C-02-T45 enum each seed label is classified as; the label is what CLS-13 shows.
ENTITY_TYPE_OF: Final = {
    "LLC (partnership)": "llc_p", "LLP (partnership)": "partnership",
    "Single-member LLC (individual)": "single_member_llc", "Sole proprietor": "individual",
    "Law firm (partnership)": "partnership", "C corporation": "c_corporation",
    "S corporation": "s_corporation", "Bank (corporation)": "c_corporation", "—": "unknown",
}  # fmt: skip
DUE_ON_2026: Final = date(2027, 2, 1)  # Jan 31, 2027 is a Sunday
BATCH_APPROVED_AT: Final = datetime(2027, 1, 26, 10, 0, tzinfo=CT)


def _form_of(vendor: Vendor) -> tuple[str | None, str | None]:
    if vendor.form is None:
        return None, None
    return ("misc", "1") if vendor.form.startswith("1099-MISC") else ("nec", "1")


def cls13_tracker() -> dict[str, object]:
    """CLS-13 for 2026 (a, b, c and d's rows) and 2025 (e), in C-02-T45's read shape with
    C-02-T47's additive fields. `make fixtures` writes it to
    `apps/web/src/fixtures/seed/scenario.cls13-tracker.json`. Copperleaf pays its vendors by ACH
    bill payment in the scenario (DEC-6030: the handoff gives totals only, so no transaction count
    is invented); Cascade Coffee Importers is paid by card, never counted toward 1099-NEC."""
    individual = {"Sole proprietor", "Single-member LLC (individual)"}
    rows: list[dict[str, object]] = []
    for v in VENDORS:
        form, box = _form_of(v)
        card = v.treatment == "paid_by_card"
        rows.append({
            "display_name": v.name, "entity_label": v.entity,
            "entity_type": ENTITY_TYPE_OF[v.entity], "is_attorney": v.is_attorney,
            "reportability": v.treatment, "form": form, "box": box,
            "amount": "0.00" if card else f"{v.amount:.2f}",
            "tin_last4": v.tin_last4,
            "tin_kind": None if v.tin_last4 is None
            else ("ssn" if v.entity in individual else "ein"),
            "w9_status": v.w9 or "missing",
            "w9_requested_on": W9_REQUESTED_ON.isoformat() if v.w9 == "requested" else None,
            "tin_mismatch_on": TIN_MISMATCH_ON.isoformat() if v.w9 == "tin_mismatch" else None,
            "backup_withholding": "watch" if v.w9 == "tin_mismatch" else "none",
            "payments": [{"method": "card" if card else "ach", "amount": f"{v.amount:.2f}",
                          "counted": not card}],
        })  # fmt: skip
    year, count, accepted_on = PRIOR_YEAR_ACCEPTED
    if len(PRIOR_YEAR_RETURNS) != count:
        raise ValueError("CLS-13e names five 2025 returns")
    by_name = {v.name: v for v in VENDORS}
    prior = [
        {"display_name": name, "entity_label": by_name[name].entity,
         "entity_type": ENTITY_TYPE_OF[by_name[name].entity],
         "is_attorney": by_name[name].is_attorney, "form": form, "box": box,
         "amount": f"{amount:.2f}", "tin_last4": by_name[name].tin_last4,
         "tin_kind": "ssn" if by_name[name].entity in individual else "ein"}
        for name, form, box, amount in PRIOR_YEAR_RETURNS
    ]  # fmt: skip
    reportable_n = sum(1 for v in VENDORS if v.treatment == "reportable")
    return {
        "client": COPPERLEAF,
        "w9_requested_on": W9_REQUESTED_ON.isoformat(),
        "due_on": DUE_ON_2026.isoformat(),
        "batch_approved_at": BATCH_APPROVED_AT.isoformat(),
        "december_close_due": DECEMBER_CLOSE_DUE.isoformat(),
        "tiles": {
            "vendors_paid": len(VENDORS),
            "reportable": reportable_n,
            "requested": sum(1 for v in VENDORS if v.w9 == "requested"),
            "w9_mismatches": sum(1 for v in VENDORS if v.w9 == "tin_mismatch"),
        },
        "rows": rows,
        "prior": {"tax_year": year, "accepted_on": accepted_on.isoformat(), "rows": prior},
    }


def reportable(vendor: Vendor) -> bool:
    """Code's rule over the seed: attorneys regardless of entity; corporations exempt; card
    payments excluded; otherwise at or above the year's threshold."""
    if vendor.treatment == "paid_by_card":
        return False
    if vendor.is_attorney:
        return True
    if vendor.treatment == "exempt_corporation":
        return False
    return vendor.amount >= THRESHOLD_2026


# --- C-02-T26: the Copperleaf QuickBooks sandbox's vendor recordings (fake_quickbooks_online) ----

PaidBy = Literal["check", "ach", "card"]
# How each vendor was paid Jan 1 - Aug 31, 2026 (DF note: the handoff names the card vendor only;
# rent, the firm's fee, insurance and bank charges are ACH, the rest by check).
PAID_BY: Final[dict[str, PaidBy]] = {
    "Larimer Street Properties, LLC": "ach",
    "Brightwater Hale LLP": "ach",
    "Cedar Mutual Insurance Co.": "ach",
    "Front Range Bank": "ach",
    "Cascade Coffee Importers, Inc.": "card",
}
YEAR_TO_DATE: Final = (date(2026, 1, 1), date(2026, 8, 31))


def _vendor_id(index: int) -> str:
    return str(56 + index)


def copperleaf_vendor_recordings() -> dict[str, bytes]:
    """The recorded Intuit answers for Copperleaf's 12 vendors and their year-to-date payments:
    file name to bytes, for `fake_quickbooks_online`'s connection folder. Rent and the firm's fee
    are paid monthly (8 payments each); every other vendor once. Tax ids are masked as Intuit
    masks them; amounts foot to the CLS-13 seed."""
    import json

    vendors: list[dict[str, object]] = []
    bill_payments: list[dict[str, object]] = []
    purchases: list[dict[str, object]] = []
    txn = 9001
    for index, vendor in enumerate(VENDORS):
        vid = _vendor_id(index)
        row: dict[str, object] = {
            "Id": vid,
            "DisplayName": vendor.name,
            "Vendor1099": vendor.form is not None,
            "Active": True,
        }
        if vendor.tin_last4 is not None:
            row["TaxIdentifier"] = f"XXX-XX-{vendor.tin_last4}"
        vendors.append(row)
        paid_by = PAID_BY.get(vendor.name, "check")
        if vendor.name == "Larimer Street Properties, LLC":
            amounts = [MONTHLY_RENT] * MONTHS_PAID
        elif vendor.name == "Brightwater Hale LLP":
            amounts = [MONTHLY_FIRM_FEE] * MONTHS_PAID
        else:
            amounts = [vendor.amount]
        for month, amount in enumerate(amounts, start=1):
            when = date(2026, month if len(amounts) > 1 else 6, 15).isoformat()
            if paid_by == "check":
                bill_payments.append({
                    "Id": str(txn), "VendorRef": {"value": vid, "name": vendor.name},
                    "TxnDate": when, "TotalAmt": float(amount), "PayType": "Check",
                })  # fmt: skip
            else:
                purchases.append(
                    {
                        "Id": str(txn),
                        "EntityRef": {"value": vid, "name": vendor.name, "type": "Vendor"},
                        "TxnDate": when,
                        "TotalAmt": float(amount),
                        "PaymentType": "CreditCard" if paid_by == "card" else "Cash",
                        **(
                            {"PaymentMethodRef": {"value": "7", "name": "ACH"}}
                            if paid_by == "ach"
                            else {}
                        ),
                    }
                )
            txn += 1
    start, end = (d.isoformat() for d in YEAR_TO_DATE)

    def dump(body: object) -> bytes:
        return json.dumps(body, sort_keys=True).encode()

    return {
        "qbo-vendors.json": dump({"QueryResponse": {"Vendor": vendors}}),
        f"qbo-vendor_payments-BillPayment-{start}_{end}.json": dump(
            {"QueryResponse": {"BillPayment": bill_payments}}
        ),
        f"qbo-vendor_payments-Purchase-{start}_{end}.json": dump(
            {"QueryResponse": {"Purchase": purchases}}
        ),
    }


# --- C-02-T23: CLS-08's package rows (statement lines with subtotals, computed here by code) ----

_BS_TOTALS: Final = {
    "current_assets": "Total current assets",
    "property_and_equipment": "Net property and equipment",
    "current_liabilities": "Total current liabilities",
    "long_term_liabilities": "Total long-term liabilities",
    "equity": "Total stockholders' equity",
}
_IS_TOTALS: Final = {
    "revenue": "Total revenue",
    "cost_of_goods_sold": "Total cost of goods sold",
    "operating_expenses": "Total operating expenses",
    "interest_expense": "Total interest expense",
}


def _slug(label: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in label.lower()).strip("_")


def _money(x: Decimal) -> str:
    return f"{x.quantize(D('0.01'))}"


COMMENTARY: Final = (
    "Revenue rose 4.5% to $214,600. Payroll rose 12.5% to $68,910: two baristas joined at the end "
    "of July, merit increases took effect Aug 1, and the roastery ran overtime during the "
    "Aug 10\u201314 changeover. Repairs and maintenance of $3,200 was an electrical repair at the "
    "espresso bar. Net income was $27,795 (July $31,455)."
)


def cls08_package() -> dict[str, object]:
    """CLS-08 a's statements as the package read returns them (`DeliveryPackageOut` lines), with
    the section subtotals and grand totals computed here (ADR-050): total assets 549,195.45,
    total liabilities and equity the same, August net income 27,795.00 against July 31,455.00."""
    bs: list[dict[str, object]] = []
    for section, rows in BALANCE_SHEET.items():
        for label, amount in rows:
            bs.append({"key": _slug(label), "label": label, "amount": _money(amount),
                       "account_refs": [_slug(label)]})  # fmt: skip
        total = sum((a for _, a in rows), _ZERO)
        bs.append({"key": f"total_{section}", "label": _BS_TOTALS[section],
                   "amount": _money(total), "account_refs": []})  # fmt: skip
    assets = sum((a for s in ("current_assets", "property_and_equipment")
                  for _, a in BALANCE_SHEET[s]), _ZERO)  # fmt: skip
    liabilities_equity = sum(
        (a for s in ("current_liabilities", "long_term_liabilities", "equity")
         for _, a in BALANCE_SHEET[s]), _ZERO)  # fmt: skip
    bs.insert(
        next(i for i, ln in enumerate(bs) if ln["key"] == "total_property_and_equipment") + 1,
        {"key": "total_assets", "label": "Total assets", "amount": _money(assets),
         "account_refs": []},
    )  # fmt: skip
    liabilities = sum((a for s in ("current_liabilities", "long_term_liabilities")
                       for _, a in BALANCE_SHEET[s]), _ZERO)  # fmt: skip
    bs.insert(
        next(i for i, ln in enumerate(bs) if ln["key"] == "total_long_term_liabilities") + 1,
        {"key": "total_liabilities", "label": "Total liabilities", "amount": _money(liabilities),
         "account_refs": []},
    )  # fmt: skip
    bs.append({"key": "total_liabilities_and_equity", "label": "Total liabilities and equity",
               "amount": _money(liabilities_equity), "account_refs": []})  # fmt: skip
    inc: list[dict[str, object]] = []
    for section, rows3 in INCOME_STATEMENT.items():
        for label, aug, jul in rows3:
            inc.append({"key": _slug(label), "label": label, "amount": _money(aug),
                        "prior": _money(jul), "account_refs": [_slug(label)]})  # fmt: skip
        inc.append({"key": f"total_{section}", "label": _IS_TOTALS[section],
                    "amount": _money(sum((a for _, a, _ in rows3), _ZERO)),
                    "prior": _money(sum((p for _, _, p in rows3), _ZERO)),
                    "account_refs": []})  # fmt: skip

    def ni(i: int) -> Decimal:
        rev = sum((cast(Decimal, r[i]) for r in INCOME_STATEMENT["revenue"]), _ZERO)
        out = sum((cast(Decimal, r[i]) for s in ("cost_of_goods_sold", "operating_expenses",
                   "interest_expense") for r in INCOME_STATEMENT[s]), _ZERO)  # fmt: skip
        return rev - out

    def subtotal(after: str, key: str, label: str, sections: tuple[str, ...]) -> None:
        def at(i: int) -> Decimal:
            rev = sum((cast(Decimal, r[i]) for r in INCOME_STATEMENT["revenue"]), _ZERO)
            spent = (cast(Decimal, r[i]) for sec in sections for r in INCOME_STATEMENT[sec])
            return rev - sum(spent, _ZERO)

        idx = next(i for i, ln in enumerate(inc) if ln["key"] == after) + 1
        inc.insert(idx, {"key": key, "label": label, "amount": _money(at(1)),
                         "prior": _money(at(2)), "account_refs": []})  # fmt: skip

    subtotal("total_cost_of_goods_sold", "gross_profit", "Gross profit", ("cost_of_goods_sold",))
    subtotal("total_operating_expenses", "operating_income", "Operating income",
             ("cost_of_goods_sold", "operating_expenses"))  # fmt: skip
    inc.append({"key": "net_income", "label": "Net income", "amount": _money(ni(1)),
                "prior": _money(ni(2)), "account_refs": []})  # fmt: skip
    return {
        # CLS-08's outline note, page 6 (S51 partials, TASK-8736): the commentary Raj's accepted
        # flux explanations give (CLS-10), as the paper reads it.
        "commentary": COMMENTARY,
        # CLS-08's outline note: the two agings by bucket (they foot to the control accounts).
        "ar_aging": [["current", "12960.00"], ["1_30", "4180.00"], ["31_60", "1280.00"]],
        "ap_aging": [["current", "17240.45"], ["1_30", "3620.00"], ["31_60", "520.00"]],
        "route": PACKAGE_ROUTE,
        "legend": PACKAGE_LEGEND,
        "released_at": RELEASED_AT.isoformat(),
        "client_approved_at": CLIENT_APPROVED_AT.isoformat(),
        # C-02-T37 (DEC-5925): who released, whom approval was asked of, who approved (POR-08).
        "released_by": RELEASED_BY,
        "approval_requested_from": [CLIENT_PERSONAS["tess-moreno"], CLIENT_PERSONAS["ben-ashby"]],
        "client_approved_by": CLIENT_PERSONAS["tess-moreno"],
        "balance_sheet": bs,
        "income_statement": inc,
    }


# --- CLS-11 ledger console (C-02-T35, DEC-5924) ------------------------------------------------

CAS_SENIOR: Final = "Raj Malhotra"  # runs Copperleaf's posts and set the closing date
CLIENT_OWNER: Final = "Tess Moreno"
QBO_COMPANY: Final = "Copperleaf Coffee Roasters"  # the company name QuickBooks Online reports
LAST_SYNC: Final = (datetime(2026, 9, 14, 9, 2, tzinfo=CT), 1214, 0)  # at, read, errors
NEXT_SYNC: Final = datetime(2026, 9, 14, 10, 2, tzinfo=CT)  # hourly
DEPENDENTS: Final = ("Close agent", "Close Planner", "1099 vendor screen")
JULY_FAILURE: Final = (
    datetime(2026, 8, 11, 14, 38, tzinfo=CT), "2026-07-A", "AJE-03", "Depreciation",
    f"QuickBooks Online: account '{INACTIVE_ACCOUNT}' is inactive",
    datetime(2026, 8, 11, 14, 41, tzinfo=CT),
)  # fmt: skip


def _batch_row(b: Batch) -> dict[str, object]:
    return {
        "batch_code": b.code, "period": b.period, "status": b.status, "entry_count": b.entries,
        "approved_count": b.entries if b.status == "posted" else 0,
        "first_external_ref": b.qbo_first, "last_external_ref": b.qbo_last,
        "resolved_failures": b.resolved_failures,
        "amount": None if b.amount is None else _money(b.amount),
        "posted_at": None if b.posted_at is None else b.posted_at.isoformat(),
        "posted_by": CAS_SENIOR if b.posted_at is not None else None,
    }  # fmt: skip


def cls11_console() -> dict[str, object]:
    """CLS-11 a at 9:24 AM, Sep 14, 2026, as the console reads return it (C20 v2.1 W1 shapes,
    with C-02-T35's additive fields): the tiles (batches, DEC-5924: 7 posted January to July, 1
    proposed), the connection pane under Tess Moreno's Mar 9 grant, the eight batches (January to
    April below the fold), the July failure resolved at 2:41 PM, and the sync events. `make
    fixtures` writes it to `apps/web/src/fixtures/seed/scenario.cls11-console.json`; the CLS-11
    scenarios vary it per state (c, d) and `screens/CLS-11` is held to it."""
    at, read, errors = LAST_SYNC
    posted = [b for b in BATCHES if b.status == "posted"]
    failed_at, batch, ref, title, message, resolved_at = JULY_FAILURE
    sync_rows: list[dict[str, object]] = []
    for when, kind, n in SYNC_EVENTS:
        row: dict[str, object] = {"at": when.isoformat(), "kind": kind}
        if kind == "sync":
            row["count"] = n
        elif kind == "post":
            row |= {"batch_code": batch, "count": n, "actor_name": CAS_SENIOR}
        elif kind == "closing_date":
            row["actor_name"] = CAS_SENIOR
        else:
            row |= {"batch_code": batch, "entry_ref": ref}
        sync_rows.append(row)
    return {
        "client": COPPERLEAF,
        "tiles": {
            "posted": len(posted) + len(BELOW_THE_FOLD_BATCHES),
            "proposed": sum(1 for b in BATCHES if b.status == "proposed"),
            "failed_post": 0,
            "resolved_failures": sum(b.resolved_failures for b in BATCHES),
            "closing_date": CLOSING_DATES[0][0].isoformat(),
        },
        "connection": {
            "health": "connected",
            "company_name": QBO_COMPANY,
            "authorized_by": CLIENT_OWNER,
            "authorized_at": datetime.combine(WRITE_GRANT_ON, datetime.min.time(), CT).isoformat(),
            "write_granted": True,
            "last_sync_at": at.isoformat(),
            "last_sync_transactions": read,
            "last_sync_errors": errors,
            "next_sync_at": NEXT_SYNC.isoformat(),
            "closing_date": CLOSING_DATES[0][0].isoformat(),
            "closing_date_set_by": CAS_SENIOR,
            "closing_date_set_at": CLOSING_DATES[0][1].isoformat(),
            "dependents": list(DEPENDENTS),
        },
        "batches": [_batch_row(b) for b in (*BATCHES, *BELOW_THE_FOLD_BATCHES)],
        "august_posted": _batch_row(AUGUST_POSTED_BATCH),
        # C-02-T44 (CLS-11 b2): the posted batch's six entries, each with its QuickBooks id.
        "august_entries": [
            {
                "ref": e.ref,
                "description": e.title,
                "amount": f"{e.amount:.2f}",
                "external_txn_ref": e.qbo_id,
            }
            for e in ENTRIES
        ],
        "failures": [
            {
                "at": failed_at.isoformat(),
                "batch_code": batch,
                "entry_ref": ref,
                "entry_description": title,
                "provider_message": message,
                "resolved_at": resolved_at.isoformat(),
                "resolved_by": CAS_SENIOR,
            },
        ],
        "activity": sync_rows,
    }

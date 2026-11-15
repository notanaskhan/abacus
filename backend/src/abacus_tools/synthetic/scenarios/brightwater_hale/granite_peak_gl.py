"""Granite Peak Outdoor Supply's FY2026 general ledger detail (A-08-T08; TASK-8050; A-08 §5.4;
SPEC-657 AC-0.8, AC-1.1, AC-1.2; DEC-5035).

A deterministic NetSuite-format GL export of 18,426 journal entries and 412,903 lines over 214
accounts for Jul 1, 2025 to Jun 30, 2026, posted through the Jul 15, 2026 post-close window,
with the JE fields NetSuite carries (Created By, Date Created, Source, Approved By; ADR-400). It
is built so that the firm's risk criteria, scored by `sampling.compute.je_scoring`, hit exactly
what AUD-12 a shows: weekend/holiday 142 · round ≥ $50,000 38 · post-close 61 · manual by
senior management 17 · keywords 9, for 236 unique entries, 34 of them scoring 61 or more. The
in-period activity ties to the Jun 30, 2026 trial balance for all 214 accounts at $0.00
(`trial_balance`).

Two entries carry the screens' facts: JE-26-17994 accrues $100,000.00 of revolver interest on
Jun 30, entered Jul 8 (round and post-close); JE-26-17950 reduces the bonus accrual by $50,000.00,
entered by the CFO with no independent approver (manual by senior management and round).

Posting users are synthetic usernames with a role map (firm-entered with citations in the
product). The criteria weights and parameters, the role map and the holiday set are the data the
scenario loads as firm content through the import endpoints (A-08-T12 adds the
`je_risk_criteria` kind); they live here as the scenario's inputs, never as product defaults.
No database code here.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from typing import Final, Literal

from abacus.modules.sampling.compute import je_scoring as js
from abacus_tools.synthetic.scenarios.brightwater_hale.prng import Rng

CLIENT: Final = "Granite Peak Outdoor Supply, Inc."
PERIOD_START: Final = date(2025, 7, 1)
PERIOD_END: Final = date(2026, 6, 30)
POST_CLOSE_THROUGH: Final = date(2026, 7, 15)
ENTRIES: Final = 18_426
LINES: Final = 412_903
ACCOUNTS: Final = 214
CENT: Final = Decimal("0.01")

# The published holiday set the criterion reads (K-02-T05 reference data; its version enters the
# scores' inputs hash). Fri Jul 3, 2026 is Independence Day observed, inside the post-close window.
HOLIDAYS: Final = js.HolidaySet(
    "us_federal/2026.1",
    frozenset(
        {
            date(2025, 7, 4),
            date(2025, 9, 1),
            date(2025, 11, 11),
            date(2025, 11, 27),
            date(2025, 12, 25),
            date(2026, 1, 1),
            date(2026, 1, 19),
            date(2026, 2, 16),
            date(2026, 5, 25),
            date(2026, 6, 19),
            date(2026, 7, 3),
        }
    ),
)

# Firm content: Brightwater Hale's JE risk criteria (threshold_policies kind je_risk_criteria).
CRITERIA: Final[tuple[js.Criterion, ...]] = (
    js.Criterion("weekend_holiday", 20, {"holiday_set": HOLIDAYS.version}),
    js.Criterion("round_amount", 30, {"at_least": "50000", "unit": "1000"}),
    js.Criterion("post_close", 35, {"through": POST_CLOSE_THROUGH.isoformat()}),
    js.Criterion("manual_by_role", 61, {"role_class": "senior_management"}),
    js.Criterion("keywords", 15, {"words": "plug, adjust"}),
)
SCORE_MIN: Final = 61
UNPREDICTABLE: Final = 6

# Synthetic posting users (the client's people; the role map is the engagement team's, cited).
CFO: Final = "lferrante"  # Luis Ferrante, Chief Financial Officer
CONTROLLER: Final = "mdavies"
STAFF: Final = ("kowens", "jpatel", "rtorres")
SYSTEM_USER: Final = "-System-"  # how NetSuite names system-generated entries
ROLES: Final[dict[str, js.RoleClass]] = {
    CFO: "senior_management",
    CONTROLLER: "senior_management",
    "kowens": "accounting_staff",
    "jpatel": "accounting_staff",
    "rtorres": "accounting_staff",
    SYSTEM_USER: "system",
}
JE_FIELDS: Final = frozenset({"posted_by", "entered_at", "source", "approver"})

Combo = Literal["M", "MR", "MK", "RP", "WP", "WR", "W", "R", "P", "none"]
# How many entries meet each combination of criteria (W weekend/holiday, R round, P post-close,
# M manual by senior management, K keywords): their union is 236 and 34 score at least 61
# (M 61; M+R 91; M+K 76; R+P 65), with W+P 55 and W+R 50 below.
COMBOS: Final[dict[Combo, int]] = {
    "MR": 1,  # JE-26-17950
    "MK": 9,
    "M": 7,
    "RP": 17,  # JE-26-17994 among them
    "WP": 3,  # posted Fri Jul 3, 2026 (holiday, post-close)
    "WR": 1,
    "W": 138,
    "R": 19,
    "P": 41,
}

_NAMES: Final = (
    ("1", "Cash", 30),
    ("1", "Inventory", 20),
    ("1", "Fixed assets", 22),
    ("2", "Payables", 36),
    ("2", "Debt", 8),
    ("3", "Equity", 6),
    ("4", "Revenue", 22),
    ("5", "COGS", 20),
    ("6", "Opex", 44),
    ("7", "Other", 6),
)
_MEMOS: Final = (
    "Daily sales batch",
    "Customer receipts",
    "Vendor bill",
    "Payroll",
    "Inventory receipt",
    "Depreciation",
    "Freight",
    "Credit card settlement",
    "Prepaid amortization",
    "Sales tax",
)


@dataclass(frozen=True)
class Line:
    account_code: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class Entry:
    ref: str
    posted_on: date
    entered_at: datetime
    kind: str
    source: Literal["manual", "system"]
    posted_by: str
    approver: str | None
    memo: str
    amount: Decimal  # total debit
    line_count: int
    combo: Combo


def accounts() -> list[tuple[str, str]]:
    """214 accounts: (code, name), by the common US numbering."""
    out: list[tuple[str, str]] = []
    seen: dict[str, int] = {}
    for digit, name, count in _NAMES:
        for i in range(count):
            seen[digit] = seen.get(digit, 0) + 1
            out.append((f"{digit}{seen[digit]:03d}", f"{name} {i + 1}"))
    named = {
        "1001": "Cash - Front Range Bank",
        "1002": "Accounts receivable",
        "1031": "Inventory",
        "2001": "Accounts payable",
        "2002": "Accrued interest",
        "2003": "Accrued bonuses",
        "2037": "Revolver - Front Range Bank",
        "2038": "Term loan",
        "6001": "Salaries and wages",
        "7001": "Interest expense",
    }
    return [(code, named.get(code, name)) for code, name in out]


def _amount(rng: Rng, low: int, high: int) -> Decimal:
    """A non-round amount: never a whole multiple of 1,000 (nonzero cents)."""
    return Decimal(rng.integer(low, high)) + Decimal(rng.integer(1, 99)) * CENT


def _weekday(rng: Rng) -> date:
    while True:
        d = PERIOD_START + timedelta(days=rng.integer(0, (PERIOD_END - PERIOD_START).days))
        if d.weekday() < 5 and d not in HOLIDAYS.dates:
            return d


def _weekend(rng: Rng, n: int) -> date:
    holidays = sorted(d for d in HOLIDAYS.dates if d <= PERIOD_END)
    if n < len(holidays):
        return holidays[n]  # one entry on each in-period holiday
    while True:
        d = PERIOD_START + timedelta(days=rng.integer(0, (PERIOD_END - PERIOD_START).days))
        if d.weekday() >= 5:
            return d


def _post_close_day(rng: Rng) -> date:
    while True:
        d = PERIOD_END + timedelta(days=rng.integer(1, (POST_CLOSE_THROUGH - PERIOD_END).days))
        if d.weekday() < 5 and d not in HOLIDAYS.dates:
            return d


def _at(d: date, hour: int) -> datetime:
    return datetime(d.year, d.month, d.day, hour, 0)  # NetSuite's local time, as exported


def _flagged(rng: Rng) -> list[Entry]:
    """The 236 flagged entries, built combination by combination."""
    out: list[Entry] = []
    n = 0
    for combo, count in COMBOS.items():
        for i in range(count):
            n += 1
            ref = f"JE-26-{17000 + n:05d}"
            posted, entered_hour = _weekday(rng), 10
            entered_on: date | None = None
            kind, source, user, approver = "Journal", "manual", STAFF[i % 3], CONTROLLER
            memo, amount = "Accrual true-up", _amount(rng, 1_000, 40_000)
            if "M" in combo:
                user, approver = CFO, None  # no independent approval
            if "R" in combo:
                amount = Decimal(rng.integer(50, 400) * 1000)
            if "K" in combo:
                memo = "Adjust reserve to plan" if i % 2 else "Plug to suspense"
            if combo in ("RP", "P"):
                if i % 2 == 0 or combo == "RP":
                    entered_on = _post_close_day(rng)  # posted into June, entered late
                    posted = PERIOD_END
                else:
                    posted = _post_close_day(rng)  # posted in the post-close window
            if combo == "WP":
                posted = date(2026, 7, 3)
            if combo in ("W", "WR"):
                posted = _weekend(rng, i)
            out.append(
                Entry(
                    ref,
                    posted,
                    _at(entered_on or posted, entered_hour),
                    kind,
                    source,
                    user,
                    approver,
                    memo,
                    amount,
                    2,
                    combo,
                )
            )
    # The two the screens name.
    by_combo = {e.combo: e for e in out}
    fixed = {
        by_combo["MR"].ref: (
            "JE-26-17950",
            PERIOD_END - timedelta(days=4),
            "Reduce bonus accrual",
            Decimal("50000.00"),
        ),
        next(e.ref for e in out if e.combo == "RP"): (
            "JE-26-17994",
            PERIOD_END,
            "Accrue Q4 interest - revolver",
            Decimal("100000.00"),
        ),
    }
    return [
        Entry(
            fixed[e.ref][0],
            fixed[e.ref][1],
            e.entered_at,
            e.kind,
            e.source,
            e.posted_by,
            e.approver,
            fixed[e.ref][2],
            fixed[e.ref][3],
            2,
            e.combo,
        )
        if e.ref in fixed
        else e
        for e in out
    ]


def entries() -> list[Entry]:
    """All 18,426 entries in reference order: 236 flagged and the rest, none of which any
    criterion selects; 1,000 system batches carry the extra lines to reach 412,903."""
    rng = Rng("granite-peak:fy2026:gl")
    flagged = _flagged(rng)
    taken = {e.ref for e in flagged}  # after the two named entries took their references
    rest_count = ENTRIES - len(flagged)
    extra = LINES - 2 * ENTRIES
    batches, per, more = 1_000, extra // 1_000, extra % 1_000
    rest: list[Entry] = []
    serial = 0
    for i in range(rest_count):
        serial += 1
        ref = f"JE-26-{serial:05d}"
        while ref in taken:
            serial += 1
            ref = f"JE-26-{serial:05d}"
        posted = _weekday(rng)
        batch = i < batches
        lines = 2 + (per + (1 if i < more else 0) if batch else 0)
        amount = _amount(rng, 2_000 * lines if batch else 10, 4_000 * lines if batch else 45_000)
        rest.append(
            Entry(
                ref,
                posted,
                _at(posted, 9 + i % 8),
                "Journal" if i % 7 == 0 and not batch else "Invoice" if i % 2 else "Payment",
                "manual" if i % 7 == 0 and not batch else "system",
                STAFF[i % 3] if i % 7 == 0 and not batch else SYSTEM_USER,
                CONTROLLER if i % 7 == 0 and not batch else None,
                _MEMOS[i % len(_MEMOS)],
                amount,
                lines,
                "none",
            )
        )
    return sorted([*flagged, *rest], key=lambda e: e.ref)


def _split(rng: Rng, total: Decimal, parts: int) -> list[Decimal]:
    """`total` in `parts` positive cent amounts that sum to it exactly."""
    cents = int(total / CENT)
    cuts = sorted({rng.integer(1, cents - 1) for _ in range(parts - 1)})
    while len(cuts) < parts - 1:  # a repeated cut: add distinct ones
        cuts = sorted({*cuts, rng.integer(1, cents - 1)})
    bounds = [0, *cuts, cents]
    return [Decimal(b - a) * CENT for a, b in pairwise(bounds)]


def lines(entry: Entry, codes: list[str], rng: Rng) -> list[Line]:
    """The entry's balanced lines: one debit and the credits that sum to it."""
    debit_code = codes[rng.integer(0, len(codes) - 1)]
    credits = _split(rng, entry.amount, entry.line_count - 1)
    out = [Line(debit_code, entry.amount, Decimal(0))]
    for k, amount in enumerate(credits):
        code = codes[(rng.integer(0, len(codes) - 1) + k) % len(codes)]
        out.append(Line(code if code != debit_code else codes[0], Decimal(0), amount))
    return out


def je_entries(all_entries: list[Entry] | None = None) -> list[js.JeEntry]:
    """The entries as JE scoring reads them (`ledger.api.journal_entries` in the product)."""
    return [
        js.JeEntry(
            e.ref,
            e.posted_on,
            e.amount,
            (e.memo,),
            e.posted_by,
            e.entered_at,
            e.source,
        )
        for e in (all_entries if all_entries is not None else entries())
    ]


def inputs() -> js.Inputs:
    return js.Inputs(CRITERIA, HOLIDAYS, PERIOD_END, ROLES, JE_FIELDS)


def iter_rows(all_entries: list[Entry] | None = None) -> Iterator[tuple[Entry, Line]]:
    """Every line, entry by entry, deterministically (412,903 of them)."""
    rng = Rng("granite-peak:fy2026:lines")
    codes = [code for code, _ in accounts()]
    for e in all_entries if all_entries is not None else entries():
        for line in lines(e, codes, rng):
            yield e, line


def trial_balance(all_entries: list[Entry] | None = None) -> list[tuple[str, str, Decimal]]:
    """The Jun 30, 2026 trial balance (code, name, net debit) that the in-period activity ties
    to: balance-sheet accounts carry an opening (netting to zero against the last equity account),
    income and expense accounts open at zero, and each closes at opening plus its in-period
    debits less credits. The post-close window's postings are not in it."""
    rng = Rng("granite-peak:fy2026:openings")
    accts = accounts()
    sheet = [code for code, _ in accts if code[0] in "123"]
    openings = {code: Decimal(0) for code, _ in accts}
    for code in sheet[:-1]:
        openings[code] = Decimal(rng.integer(-500_000, 500_000))
    openings[sheet[-1]] = -sum(openings.values(), Decimal(0))
    net = dict(openings)
    for e, line in iter_rows(all_entries):
        if e.posted_on <= PERIOD_END:
            net[line.account_code] += line.debit - line.credit
    return [(code, name, net[code]) for code, name in accts]


def netsuite_csv(
    all_entries: list[Entry] | None = None, *, through: date = POST_CLOSE_THROUGH
) -> bytes:
    """The export, flat NetSuite layout with the JE columns (`gl_formats.netsuite_gl_csv`),
    posted through `through` (the period end alone for the trial balance tie)."""
    names = dict(accounts())
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow([CLIENT])
    w.writerow(["General Ledger"])
    w.writerow(["Jul 2025 - Jul 2026"])
    w.writerow([])
    w.writerow(
        [
            *("Account", "Date", "Type", "Document Number", "Name", "Memo", "Debit", "Credit"),
            *("Created By", "Date Created", "Source", "Approved By"),
        ]
    )
    for e, line in iter_rows(all_entries):
        if e.posted_on > through:
            continue
        w.writerow(
            [
                f"{line.account_code} - {names[line.account_code]}",
                e.posted_on.strftime("%m/%d/%Y"),
                e.kind,
                e.ref,
                "",
                e.memo,
                f"{line.debit:.2f}" if line.debit else "",
                f"{line.credit:.2f}" if line.credit else "",
                e.posted_by,
                e.entered_at.strftime("%m/%d/%Y %I:%M %p"),
                "Manual" if e.source == "manual" else "System",
                e.approver or "",
            ]
        )
    return out.getvalue().encode("utf-8")

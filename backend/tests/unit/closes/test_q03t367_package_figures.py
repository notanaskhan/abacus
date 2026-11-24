"""Q-03-T367 (TASK-8959): the CAS package's figures, whole (C-02-T21; SPEC-701; CLS-08; ADR-050).

The quarterly mutation sweep found `closes/compute/package.py` checked by its totals only: a lost
label, a dropped lineage, a second account on the same line or a skipped account mid-loop
survived. Each test here compares the engine's whole output for one small books, so every figure,
label and account reference is held, with the arithmetic written out beside it.
"""

from __future__ import annotations

from decimal import Decimal as D

from abacus.modules.closes.compute import package as pkg

_FS = {
    "1000": pkg.FsLine("cash", "Cash", "cash", "Cash", "assets", 1),
    "1010": pkg.FsLine("cash", "Cash", "cash", "Cash", "assets", 1),
    "1200": pkg.FsLine("ar", "Accounts receivable", "current", "Current assets", "assets", 2),
    "1500": pkg.FsLine("equipment", "Equipment", "fixed", "Fixed assets", "assets", 3),
    "1510": pkg.FsLine(
        "acc_dep", "Accumulated depreciation", "fixed", "Fixed assets", "assets", 4
    ),
    "2000": pkg.FsLine(
        "ap", "Accounts payable", "current_liab", "Current liabilities", "liabilities", 5
    ),
    "2700": pkg.FsLine("loan", "Bank loan", "long_term", "Long-term debt", "liabilities", 6),
    "3000": pkg.FsLine("capital", "Owner capital", "equity", "Equity", "equity", 7),
    "4000": pkg.FsLine("sales", "Sales", "revenue", "Revenue", "revenue", 8),
    "4010": pkg.FsLine("sales", "Sales", "revenue", "Revenue", "revenue", 8),
    "6000": pkg.FsLine("rent", "Rent", "opex", "Operating expenses", "expenses", 9),
    "6100": pkg.FsLine("dep", "Depreciation", "opex", "Operating expenses", "expenses", 10),
}


def _acct(ref: str, balance: str) -> pkg.LedgerAccount:
    return pkg.LedgerAccount(ref, f"acct {ref}", D(balance))


# --- the posted TB ------------------------------------------------------------------------------


def test_only_posted_and_recorded_entries_reach_the_tb_each_on_its_own_account() -> None:
    accounts = [_acct("1000", "100.00"), _acct("4000", "-100.00")]
    entries = [
        pkg.EntryLine("1000", D("10.00"), D("0.00"), "proposed"),  # never applied
        pkg.EntryLine("1000", D("25.00"), D("5.00"), "posted"),
        pkg.EntryLine("1000", D("0.00"), D("1.00"), "recorded"),  # a second entry, same account
        pkg.EntryLine("6000", D("7.50"), D("0.00"), "posted"),  # an account the TB lacked
        pkg.EntryLine("4000", D("0.00"), D("7.50"), "posted"),
    ]
    assert pkg.posted_tb(accounts, entries) == [
        pkg.LedgerAccount("1000", "acct 1000", D("119.00")),  # 100 + 25 - 5 - 1
        pkg.LedgerAccount("4000", "acct 4000", D("-107.50")),  # -100 - 7.50
        pkg.LedgerAccount("6000", "6000", D("7.50")),  # named by its ref until the TB names it
    ]


# --- statement lines, the income statement and the balance sheet --------------------------------

_TB = [
    _acct("1000", "500.00"),
    _acct("1010", "250.00"),  # two accounts on one line
    _acct("9999", "1.00"),  # unmapped: C9's open item, never placed
    _acct("1200", "300.00"),
    _acct("2000", "-400.00"),
    _acct("3000", "-200.00"),
    _acct("4000", "-900.00"),
    _acct("4010", "-100.00"),
    _acct("6000", "600.00"),
]
_PRIOR = [_acct("4000", "-700.00"), _acct("6000", "500.00"), _acct("6100", "40.00")]


def test_statement_lines_sum_each_line_in_catalogue_order_with_its_lineage() -> None:
    lines = pkg.statement_lines(_TB, _FS, frozenset({"assets", "liabilities", "equity"}))
    assert lines == [
        pkg.StatementLine("cash", "Cash", "cash", "assets", D("750.00"), ("1000", "1010")),
        pkg.StatementLine(
            "ar", "Accounts receivable", "current", "assets", D("300.00"), ("1200",)
        ),
        pkg.StatementLine(
            "ap", "Accounts payable", "current_liab", "liabilities", D("400.00"), ("2000",)
        ),  # credit-positive
        pkg.StatementLine("capital", "Owner capital", "equity", "equity", D("200.00"), ("3000",)),
    ]


def test_the_prior_column_adds_lines_only_the_prior_month_carried() -> None:
    lines = pkg.statement_lines(_TB, _FS, frozenset({"revenue", "expenses"}), _PRIOR)
    assert lines == [
        pkg.StatementLine(
            "sales", "Sales", "revenue", "revenue", D("1000.00"), ("4000", "4010"), D("700.00")
        ),
        pkg.StatementLine("rent", "Rent", "opex", "expenses", D("600.00"), ("6000",), D("500.00")),
        # Depreciation ran only in the prior month: the line shows, at 0.00 now, no lineage.
        pkg.StatementLine("dep", "Depreciation", "opex", "expenses", D("0.00"), (), D("40.00")),
    ]


def test_the_income_statement_against_the_prior_month() -> None:
    income = pkg.income_statement(_TB, _FS, _PRIOR)
    assert (income.revenue, income.expenses, income.net_income) == (
        D("1000.00"),
        D("600.00"),
        D("400.00"),
    )
    assert income.prior_net_income == D("160.00")  # 700 - (500 + 40)
    assert [ln.key for ln in income.lines] == ["sales", "rent", "dep"]
    alone = pkg.income_statement(_TB, _FS)
    assert alone.prior_net_income is None
    assert all(ln.prior is None for ln in alone.lines)
    # A prior month with only revenue: its expenses sum from zero.
    only = pkg.income_statement(_TB, _FS, [_acct("4000", "-50.00")])
    assert only.prior_net_income == D("50.00")


def test_the_balance_sheet_carries_the_years_net_income_as_a_derived_equity_line() -> None:
    sheet = pkg.balance_sheet(
        _TB, _FS, net_income_label="Net income (year to date)", equity_grouping_key="equity"
    )
    derived = pkg.StatementLine(
        pkg.NET_INCOME_KEY,
        "Net income (year to date)",
        "equity",
        "equity",
        D("400.00"),  # -(-900 - 100 + 600)
        ("4000", "4010", "6000"),
    )
    assert sheet.lines[-1] == derived
    assert (sheet.total_assets, sheet.total_liabilities, sheet.total_equity) == (
        D("1050.00"),
        D("400.00"),
        D("600.00"),  # capital 200 + net income 400
    )
    assert not sheet.balanced  # 1,050 against 1,000: the unmapped 1.00 and rounding are C9's
    # An expenses-only year still derives the line (a loss).
    loss = pkg.balance_sheet(
        [_acct("1000", "-50.00"), _acct("6000", "50.00")],
        _FS,
        net_income_label="Net income",
        equity_grouping_key="equity",
    )
    assert loss.lines[-1].amount == D("-50.00")
    assert loss.lines[-1].account_refs == ("6000",)
    # No income-statement account: nothing is derived.
    flat = pkg.balance_sheet(
        [_acct("1000", "10.00"), _acct("3000", "-10.00")],
        _FS,
        net_income_label="Net income",
        equity_grouping_key="equity",
    )
    assert [ln.key for ln in flat.lines] == ["cash", "capital"]
    assert flat.balanced


# --- the cash flow statement --------------------------------------------------------------------


def test_cash_flows_by_the_indirect_method_whole() -> None:
    opening = [
        _acct("1000", "1000.00"),
        _acct("1010", "200.00"),
        _acct("1200", "300.00"),
        _acct("1500", "5000.00"),
        _acct("1510", "-1000.00"),
        _acct("2000", "-400.00"),
        _acct("2700", "-3000.00"),
        _acct("3000", "-2100.00"),
    ]
    closing = [
        _acct("1000", "1600.00"),
        _acct("1010", "150.00"),
        _acct("1200", "450.00"),  # AR up 150: uses cash
        _acct("1500", "5800.00"),  # equipment bought for 800
        _acct("1510", "-1100.00"),  # depreciation 100 (its change is the add-back)
        _acct("2000", "-520.00"),  # AP up 120: provides cash
        _acct("2700", "-3200.00"),  # borrowed 200
        _acct("3000", "-2100.00"),
        _acct("9999", "5.00"),  # unmapped: skipped, never stops the walk
        _acct("4000", "-1500.00"),
        _acct("6000", "500.00"),
        _acct("6100", "100.00"),
    ]
    flows = pkg.cash_flows_ytd(
        opening,
        closing,
        _FS,
        cash_groupings=frozenset({"cash"}),
        noncash_expense_lines=frozenset({"dep"}),
        noncash_contra_lines=frozenset({"acc_dep"}),
        investing_groupings=frozenset({"fixed"}),
        financing_groupings=frozenset({"long_term", "equity"}),
    )
    assert flows == pkg.CashFlows(
        operating=(
            pkg.StatementLine(
                pkg.NET_INCOME_KEY, "Net income", "operating", "equity", D("900.00"), ()
            ),  # 1,500 - 500 - 100
            pkg.StatementLine(
                "noncash", "Non-cash expenses", "operating", "expenses", D("100.00"), ("6100",)
            ),
            pkg.StatementLine(
                "ar", "Accounts receivable", "current", "assets", D("-150.00"), ("1200",)
            ),
            pkg.StatementLine(
                "ap", "Accounts payable", "current_liab", "liabilities", D("120.00"), ("2000",)
            ),
        ),
        investing=(
            pkg.StatementLine(
                "equipment", "Equipment", "fixed", "assets", D("-800.00"), ("1500",)
            ),
        ),
        financing=(
            pkg.StatementLine(
                "loan", "Bank loan", "long_term", "liabilities", D("200.00"), ("2700",)
            ),
            pkg.StatementLine(
                "capital", "Owner capital", "equity", "equity", D("0.00"), ("3000",)
            ),
        ),
        net_change=D("370.00"),
        opening_cash=D("1200.00"),  # two cash accounts
        closing_cash=D("1750.00"),
    )
    assert not flows.ties  # 1,200 + 370 against 1,750: the unmapped account's 5 and the rest


def test_cash_flows_without_a_noncash_expense_have_no_add_back_line() -> None:
    flows = pkg.cash_flows_ytd(
        [_acct("1000", "100.00")],
        [_acct("1000", "160.00"), _acct("4000", "-60.00")],
        _FS,
        cash_groupings=frozenset({"cash"}),
        noncash_expense_lines=frozenset({"dep"}),
        investing_groupings=frozenset(),
        financing_groupings=frozenset(),
    )
    assert [ln.key for ln in flows.operating] == [pkg.NET_INCOME_KEY]
    assert flows.operating[0].amount == D("60.00")
    assert (flows.investing, flows.financing) == ((), ())
    assert flows.ties


# --- agings, preconditions, the route, commentary and the hash ---------------------------------


def test_the_aging_sums_every_item_in_its_bucket() -> None:
    items = [
        pkg.AgingItem("Acme", "current", D("100.00")),
        pkg.AgingItem("Bolt", "current", D("50.00")),  # a second item, same bucket
        pkg.AgingItem("Acme", "over_90", D("25.00")),
    ]
    assert pkg.aging(items, gl_balance=D("175"), account_refs=["1200"]) == pkg.Aging(
        buckets=(
            ("current", D("150.00")),
            ("1_30", D("0.00")),
            ("31_60", D("0.00")),
            ("61_90", D("0.00")),
            ("over_90", D("25.00")),
        ),
        total=D("175.00"),
        gl_balance=D("175.00"),
        account_refs=("1200",),
    )


def test_each_precondition_names_its_count() -> None:
    assert pkg.preconditions(reconciled=3, accounts=3, open_issues=0, unposted_entries=0) == []
    assert pkg.preconditions(reconciled=2, accounts=3, open_issues=1, unposted_entries=1) == [
        pkg.Precondition("accounts_unreconciled", 2, 3),
        pkg.Precondition("issues_open", 1, None),
        pkg.Precondition("entries_unposted", 1, None),
    ]


def test_commentary_signs_and_rounds_each_change() -> None:
    accepted = [
        pkg.AcceptedFlux("Revenue", D("12345.60"), D("12.34"), "Two new clients."),
        pkg.AcceptedFlux("Rent", D("-800"), None, "Lease renegotiated."),
        pkg.AcceptedFlux("Supplies", D("0"), D("0"), "Flat."),
    ]
    assert pkg.commentary("Month at a glance:\n{flux}", accepted) == (
        "Month at a glance:\n"
        "- Revenue: +12,346 (12.3%). Two new clients.\n"
        "- Rent: -800. Lease renegotiated.\n"
        "- Supplies: +0 (0.0%). Flat."
    )
    assert pkg.commentary("No slot here.", accepted) == "No slot here."


def test_the_content_hash_is_canonical_and_pinned() -> None:
    sheet = pkg.Aging((("current", D("1.00")),), D("1.00"), D("1.00"), ("1200",))
    parts = (sheet, {"b": D("2.50"), "a": [D("1"), ("x", None)]}, "text", 3)
    digest = pkg.content_hash(*parts)
    assert digest == "21228a2d7496acf564b63cb282d41658d15f3ecc50b201b8975877a8f499dcab"
    # Key order never matters; a value, a key, a part or the decimal text does.
    assert (
        pkg.content_hash(sheet, {"a": [D("1"), ("x", None)], "b": D("2.50")}, "text", 3) == digest
    )
    assert (
        pkg.content_hash(sheet, {"b": D("2.5"), "a": [D("1"), ("x", None)]}, "text", 3) != digest
    )
    assert (
        pkg.content_hash(sheet, {"c": D("2.50"), "a": [D("1"), ("x", None)]}, "text", 3) != digest
    )
    assert (
        pkg.content_hash(sheet, {"b": D("2.50"), "a": [D("1"), ("y", None)]}, "text", 3) != digest
    )
    assert pkg.content_hash(*parts[:3]) != digest

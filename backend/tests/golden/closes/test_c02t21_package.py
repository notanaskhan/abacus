"""C-02-T21 (TASK-8706; SPEC-701; CLS-08 a): Copperleaf's August 2026 package from the posted TB,
exact `Decimal`: total assets 549,195.45, August net income 27,795.00 (July 31,455.00), AR aging
18,420.00 and AP aging 21,380.45 tied to their control accounts, every figure's lineage, and
Aug 31, 2026 routed to AR-C 70 preparation with the legend (Dec 31, 2026 is a CAS by-product)."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from uuid import uuid4

from abacus.modules.closes.compute import package as pkg
from abacus.modules.methodology.standards_contract import (
    PolicyRef,
    SsarsCasSettingsPayload,
    ssars_framework_for,
)
from abacus_tools.synthetic.scenarios.brightwater_hale import cas_delivery_slice as s

D = Decimal
SECTIONS = {
    "current_assets": ("assets", 10),
    "property_and_equipment": ("assets", 20),
    "current_liabilities": ("liabilities", 30),
    "long_term_liabilities": ("liabilities", 40),
    "equity": ("equity", 50),
    "revenue": ("revenue", 60),
    "cost_of_goods_sold": ("expenses", 70),
    "operating_expenses": ("expenses", 80),
    "interest_expense": ("expenses", 90),
}
NI_LABEL = "Net income, Jan\N{EN DASH}Aug 2026"


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _fs(section: str, label: str, n: int) -> pkg.FsLine:
    cls, order = SECTIONS[section]
    return pkg.FsLine(_slug(label), label, section, section, cls, order * 100 + n)  # type: ignore[arg-type]


def _debit_balance(cls: str, amount: Decimal) -> Decimal:
    return -amount if cls in pkg.CREDIT_NORMAL else amount


def _book() -> tuple[list[pkg.Account], list[pkg.Account], dict[str, pkg.FsLine]]:
    """August and July posted accounts (one per line of the figure book) and the C9 mapping."""
    mapping: dict[str, pkg.FsLine] = {}
    august: list[pkg.Account] = []
    july: list[pkg.Account] = []
    for section, rows in s.BALANCE_SHEET.items():
        for n, (label, amount) in enumerate(rows):
            if label == NI_LABEL:
                continue  # the year's net income comes from the I/S accounts, never an account
            fs = _fs(section, label, n)
            mapping[fs.key] = fs
            august.append(pkg.Account(fs.key, label, _debit_balance(fs.grouping_class, amount)))
    for section, rows3 in s.INCOME_STATEMENT.items():
        for n, (label, aug, jul) in enumerate(rows3):
            fs = _fs(section, label, n)
            mapping[fs.key] = fs
            august.append(pkg.Account(fs.key, label, _debit_balance(fs.grouping_class, aug)))
            july.append(pkg.Account(fs.key, label, _debit_balance(fs.grouping_class, jul)))
    return august, july, mapping


def _month(accounts: list[pkg.Account], mapping: dict[str, pkg.FsLine]) -> list[pkg.Account]:
    return [a for a in accounts if mapping[a.ref].grouping_class in ("revenue", "expenses")]


def test_ac_total_assets_549_195_45_with_lineage() -> None:
    august, _, mapping = _book()
    # The I/S accounts on the Aug 31 TB are year to date: Jan-Aug net income 186,420.00.
    ytd = [pkg.Account("ytd_income", "Year-to-date income", D("-186420.00"))]
    mapping["ytd_income"] = pkg.FsLine("ytd_income", "Income", "revenue", "Revenue", "revenue", 1)
    bs_accounts = [
        a for a in august if mapping[a.ref].grouping_class not in ("revenue", "expenses")
    ]
    bs = pkg.balance_sheet(
        bs_accounts + ytd, mapping, net_income_label=NI_LABEL, equity_grouping_key="equity"
    )
    assert bs.total_assets == D("549195.45")
    assert bs.balanced
    ni = next(ln for ln in bs.lines if ln.key == pkg.NET_INCOME_KEY)
    assert ni.amount == D("186420.00") and ni.account_refs == ("ytd_income",)
    ar = next(ln for ln in bs.lines if ln.label == "Accounts receivable")
    assert ar.amount == D("18420.00") and ar.account_refs == ("accounts_receivable",)


def test_ac_august_net_income_27_795_against_july_31_455() -> None:
    august, july, mapping = _book()
    inc = pkg.income_statement(_month(august, mapping), mapping, _month(july, mapping))
    assert inc.net_income == D("27795.00")
    assert inc.prior_net_income == D("31455.00")
    repairs = next(ln for ln in inc.lines if ln.label == "Repairs & maintenance")
    assert (repairs.amount, repairs.prior) == (D("3200.00"), D("640.00"))
    assert [ln.grouping_class for ln in inc.lines][:4] == ["revenue"] * 4


def test_ac_agings_tie_to_their_control_accounts() -> None:
    ar = pkg.aging(
        [pkg.AgingItem("wholesale", "current", D("18420.00"))],
        gl_balance=D("18420.00"),
        account_refs=["accounts_receivable"],
    )
    ap = pkg.aging(
        [pkg.AgingItem("vendors", "current", D("21380.45"))],
        gl_balance=D("21380.45"),
        account_refs=["accounts_payable"],
    )
    assert (ar.total, ar.ties, ap.total, ap.ties) == (D("18420.00"), True, D("21380.45"), True)
    short = pkg.aging(
        [pkg.AgingItem("vendors", "1_30", D("21000.00"))],
        gl_balance=D("21380.45"),
        account_refs=["accounts_payable"],
    )
    assert not short.ties


def test_ac_only_posted_or_recorded_entries_reach_the_tb() -> None:
    base = [pkg.Account("prepaid", "Prepaid insurance", D("3500.00"))]
    entries = [
        pkg.EntryLine("prepaid", D("0"), D("700.00"), "posted"),
        pkg.EntryLine("prepaid", D("0"), D("14900.00"), "proposed"),
    ]
    (after,) = pkg.posted_tb(base, entries)
    assert after.balance == D("2800.00")


def _framework(end: date, early: bool = False) -> str:
    policy = PolicyRef("bh_ssars_cas", uuid4(), 1, "BH SSARS/CAS settings")
    payload = SsarsCasSettingsPayload(kind="ssars_cas_settings", early_adopt_ssars27=early)
    return ssars_framework_for(payload, policy, period_end=end).framework  # type: ignore[attr-defined]


def test_ac_aug_31_2026_routes_to_ar_c_70_with_the_legend() -> None:
    aug = pkg.route(_framework(date(2026, 8, 31)), cas_answer=True)
    assert aug == pkg.PackageRoute(s.PACKAGE_ROUTE, pkg.NO_ASSURANCE)  # type: ignore[arg-type]
    dec = pkg.route(_framework(date(2026, 12, 31)), cas_answer=True)
    assert dec == pkg.PackageRoute("cas_by_product", None)
    assert pkg.route(_framework(date(2026, 12, 31)), cas_answer=False).route == "standalone_letter"
    assert pkg.route(_framework(date(2026, 8, 31), early=True), cas_answer=True).legend_key is None


def test_ac_preconditions_name_the_three_reasons_of_cls08c() -> None:
    reasons = pkg.preconditions(reconciled=9, accounts=21, open_issues=7, unposted_entries=1)
    assert [p.blocker for p in reasons] == [
        "accounts_unreconciled",
        "issues_open",
        "entries_unposted",
    ]
    assert (reasons[0].done, reasons[0].of) == (9, 21)
    assert pkg.preconditions(reconciled=21, accounts=21, open_issues=0, unposted_entries=0) == []


def test_ac_commentary_takes_accepted_flux_only_and_hashes_are_stable() -> None:
    text = pkg.commentary(
        "August commentary.\n{flux}",
        [
            pkg.AcceptedFlux(
                "Payroll", D("7670"), D("12.5"), "New hires, merit increases, overtime."
            )
        ],
    )
    assert "- Payroll: +7,670 (12.5%). New hires" in text
    august, _, mapping = _book()
    inc = pkg.income_statement(_month(august, mapping), mapping)
    assert pkg.content_hash(inc) == pkg.content_hash(inc)


def test_ac_cash_flows_tie_to_the_change_in_cash() -> None:
    m = {
        "cash": pkg.FsLine("cash", "Cash", "cash", "Cash", "assets", 1),
        "ar": pkg.FsLine("ar", "Accounts receivable", "current_assets", "CA", "assets", 2),
        "ppe": pkg.FsLine("ppe", "Equipment", "property_and_equipment", "PPE", "assets", 3),
        "acc": pkg.FsLine(
            "acc", "Accumulated depreciation", "property_and_equipment", "PPE", "assets", 3
        ),
        "loan": pkg.FsLine(
            "loan", "Equipment loan", "long_term_liabilities", "LTL", "liabilities", 4
        ),
        "rev": pkg.FsLine("rev", "Sales", "revenue", "Revenue", "revenue", 5),
        "dep": pkg.FsLine("dep", "Depreciation", "operating_expenses", "Opex", "expenses", 6),
    }
    opening = [
        pkg.Account("cash", "Cash", D("100.00")),
        pkg.Account("ar", "AR", D("50.00")),
        pkg.Account("ppe", "PPE", D("300.00")),
        pkg.Account("acc", "Acc dep", D("0.00")),
        pkg.Account("loan", "Loan", D("-200.00")),
    ]
    closing = [
        pkg.Account("cash", "Cash", D("190.00")),
        pkg.Account("ar", "AR", D("70.00")),
        pkg.Account("ppe", "PPE", D("300.00")),
        pkg.Account("acc", "Acc dep", D("-20.00")),
        pkg.Account("loan", "Loan", D("-190.00")),
        pkg.Account("rev", "Sales", D("-120.00")),
        pkg.Account("dep", "Depreciation", D("20.00")),
    ]
    cf = pkg.cash_flows_ytd(
        opening,
        closing,
        m,
        cash_groupings=frozenset({"cash"}),
        noncash_expense_lines=frozenset({"dep"}),
        noncash_contra_lines=frozenset({"acc"}),
        investing_groupings=frozenset({"property_and_equipment"}),
        financing_groupings=frozenset({"long_term_liabilities"}),
    )
    assert cf.ties and cf.net_change == D("90.00")

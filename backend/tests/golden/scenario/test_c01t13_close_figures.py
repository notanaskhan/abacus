"""C-01-T13 (TASK-8031; SPEC-655; C-01 §5.3): the Copperleaf CAS figure book against the slice.

Acceptance (the task row): every figure "with footing assertions". The book
(`brightwater_hale/copperleaf_close_figures.json`) is transcribed from the epic and the handoff;
this side foots the synthetic close slice the seed loads, and
`apps/web/src/fixtures/contracts/close-figures.test.ts` foots the screens' fixtures against the
same book. A drift anywhere fails here or there.
"""

from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

from abacus_tools.synthetic.scenarios.brightwater_hale import close_slice as seed

HERE: Final = Path(__file__).resolve().parent
BOOK: Final[dict[str, Any]] = json.loads(
    (HERE / "brightwater_hale" / "copperleaf_close_figures.json").read_text(encoding="utf-8")
)
D = Decimal


# --- CLS-01 -------------------------------------------------------------------------------------


def test_ac_twenty_two_closes_in_four_tiles() -> None:
    book = BOOK["portfolio"]
    assert len(seed.PORTFOLIO) == book["closes"] == 22
    assert seed.tiles() == book["tiles"]
    assert sum(book["tiles"].values()) == 22  # 3 + 11 + 5 + 3


def test_ac_summary_line_51_open_2_past_due_3_running() -> None:
    book = BOOK["portfolio"]
    assert sum(c.open_issues for c in seed.PORTFOLIO) == book["open_issues"] == 51
    assert sum(c.days_past_due is not None for c in seed.PORTFOLIO) == book["past_due"]
    assert sum(c.running for c in seed.PORTFOLIO) == book["running"]


def test_ac_rows_match_the_book_row_for_row() -> None:
    for close, row in zip(seed.PORTFOLIO, BOOK["portfolio"]["rows"], strict=True):
        client, status, rec, total, issues, due, past_due, prep, rev, running = row
        assert (close.client, close.status, close.reconciled, close.accounts) == (
            client, status, rec, total,
        )  # fmt: skip
        assert (close.open_issues, close.due_on.isoformat(), close.days_past_due) == (
            issues, due, past_due,
        )  # fmt: skip
        assert (close.preparer, close.reviewer, close.running) == (prep, rev, running)
        assert close.preparer in seed.PEOPLE and close.reviewer in seed.PEOPLE


def test_ac_delivered_and_in_review_rows_are_fully_reconciled_and_not_started_rows_are_empty() -> (
    None
):
    for close in seed.PORTFOLIO:
        if close.status in ("delivered", "in_review"):
            assert close.reconciled == close.accounts and close.reconciled_pct == 100
        if close.status == "delivered":
            assert close.open_issues == 0
        if close.status == "not_started":
            assert close.reconciled == 0 and close.open_issues == 0 and not close.running


def test_ac_copperleaf_reads_43_percent_9_of_21_seven_open_4_days_past_due() -> None:
    c1 = seed.PORTFOLIO[0]
    book = BOOK["record"]
    assert c1.client == seed.COPPERLEAF == BOOK["client"]
    assert c1.reconciled_pct == book["reconciled_pct"] == 43
    assert (c1.reconciled, c1.accounts) == (book["accounts_reconciled"], book["accounts_total"])
    assert c1.open_issues == book["open_issues"] == len(seed.ISSUES)
    assert c1.days_past_due == book["days_past_due"]
    assert book["documents_in_binder"] == seed.DOCUMENTS_IN_BINDER


def test_ac_no_kit_sample_data() -> None:
    names = {c.client for c in seed.PORTFOLIO} | set(seed.PEOPLE.values())
    assert "Elena Ruiz" not in names
    assert all(c.status != "closed" for c in seed.PORTFOLIO)  # type: ignore[comparison-overlap]


# --- CLS-02 runs --------------------------------------------------------------------------------


def test_ac_run_2_is_9_tasks_2_3_2_1_1_with_6_done_and_3_running() -> None:
    book = BOOK["runs"]["run_2"]
    sizes = [len(g.procedures) for g in seed.RUN_2]
    assert sizes == [g[2] for g in book["groups"]] == [2, 3, 2, 1, 1]
    assert sum(sizes) == book["total"] == 9
    assert [g.done for g in seed.RUN_2] == [g[3] for g in book["groups"]]
    assert sum(g.done for g in seed.RUN_2) == book["done"] == 6
    running = sum(p.status == "running" for g in seed.RUN_2 for p in g.procedures)
    assert running == book["running"] == seed.MAX_RUNNING
    assert [(g.key, g.label) for g in seed.RUN_2] == [(g[0], g[1]) for g in book["groups"]]


def test_ac_run_2_open_items_4_and_the_other_3_issues_sit_elsewhere() -> None:
    book = BOOK["runs"]["run_2"]
    open_items = sum(p.open_count for g in seed.RUN_2 for p in g.procedures)
    assert open_items == book["open_items"] == 4
    assert len(seed.ISSUES) - open_items == 3  # Amex cycle, accrued-expenses threshold, payroll


def test_ac_run_1_was_22_of_22() -> None:
    book = BOOK["runs"]["run_1"]
    assert seed.RUN_1_TOTAL == book["total"] == book["done"]
    assert book["issues_raised"] == seed.RUN_1_ISSUES_RAISED
    assert seed.RUN_1_STARTED.isoformat() == book["started_at"]
    assert seed.RUN_2_STARTED.isoformat() == BOOK["runs"]["run_2"]["started_at"]


# --- CLS-06 -------------------------------------------------------------------------------------


def test_ac_seven_open_is_2_medium_plus_5_low_and_4_notes_uncounted() -> None:
    book = BOOK["issues"]
    severities = [i.severity for i in seed.ISSUES]
    assert severities.count("medium") == book["medium"] == 2
    assert severities.count("low") == book["low"] == 5
    assert len(seed.ISSUES) == book["open"] == book["medium"] + book["low"]
    assert book["notes"] == seed.NOTES
    for issue, row in zip(seed.ISSUES, book["items"], strict=True):
        assert (issue.severity, issue.issue_class, issue.title, issue.account) == tuple(row[:4])
        assert issue.waiting_on_client is row[4]


# --- CLS-04 and CLS-05 --------------------------------------------------------------------------


def test_ac_tree_foots_assets_equal_liabilities_plus_equity() -> None:
    book = {k: D(v) for k, v in BOOK["tree"].items()}
    assert book == seed.TREE
    assert book["assets"] == book["liabilities"] + book["equity"]


def test_ac_4410_reconciles_both_sides_to_the_cent() -> None:
    book = BOOK["reconciliation_4410"]
    checks = sum((c.amount for c in seed.OUTSTANDING_CHECKS), D(0))
    assert checks == D(book["outstanding_checks"]) == D("5658.08")
    assert D(book["balance_per_bank"]) == seed.BALANCE_PER_BANK
    assert D(book["deposit_in_transit"]) == seed.DEPOSIT_IN_TRANSIT
    assert seed.adjusted_bank() == D(book["adjusted_bank"]) == D("184990.50")
    assert D(book["adjusted_book"]) == seed.BOOK_BALANCE + seed.UNRECORDED_REFUND
    assert seed.adjusted_bank() - seed.adjusted_book() == D(book["difference"]) == 0


def test_ac_check_2281_is_193_days_old_and_the_only_stale_item() -> None:
    book = BOOK["reconciliation_4410"]
    for check, (number, issued, payee, amount, days) in zip(
        seed.OUTSTANDING_CHECKS, book["checks"], strict=True
    ):
        assert (check.number, check.issued_on.isoformat(), check.payee) == (number, issued, payee)
        assert check.amount == D(amount)
        assert check.days_at(seed.PERIOD_END) == days
    stale = [
        c for c in seed.OUTSTANDING_CHECKS if c.days_at(seed.PERIOD_END) > book["stale_after_days"]
    ]
    assert [c.number for c in stale] == ["#2281"]
    # Two open items: the stale check and the unrecorded refund.
    assert len(stale) + 1 == book["open_items"]


def test_ac_the_refund_is_on_statement_page_2() -> None:
    lines = [line for line in seed.STATEMENT_PAGE_2 if line[3] == seed.UNRECORDED_REFUND]
    assert len(lines) == 1 and "REFUND" in lines[0][1]
    assert all((w is None) != (d is None) for _, _, w, d in seed.STATEMENT_PAGE_2)


def test_ac_square_net_is_gross_less_fees_over_21_transfers() -> None:
    book = BOOK["square"]
    assert {k: D(book[k]) for k in ("gross", "fees", "net")} == seed.SQUARE
    assert seed.SQUARE["gross"] - seed.SQUARE["fees"] == seed.SQUARE["net"]
    assert book["transfers"] == seed.SQUARE_TRANSFERS


def test_ac_prepaid_700_a_month_and_3500_against_2800() -> None:
    book = BOOK["prepaid_insurance"]
    monthly = seed.PREPAID_ANNUAL / seed.PREPAID_MONTHS
    assert monthly == D(book["monthly"]) == D("700.00")
    assert monthly == seed.PREPAID_GL - seed.PREPAID_SCHEDULE  # ties once the August entry posts
    assert (D(book["gl"]), D(book["schedule"])) == (seed.PREPAID_GL, seed.PREPAID_SCHEDULE)


# --- CLS-10 -------------------------------------------------------------------------------------


def test_ac_flux_13_tested_2_over_both() -> None:
    book = BOOK["flux"]
    assert len(seed.FLUX) == book["tested"]
    for line, (key, caption, prior, current, test) in zip(seed.FLUX, book["lines"], strict=True):
        assert (line.key, line.caption, line.prior, line.current) == (
            key, caption, int(prior), int(current),
        )  # fmt: skip
        over = line.over_both(seed.FLUX_THRESHOLD_PCT, seed.FLUX_THRESHOLD_USD)
        assert over is (test == "over_both")
    assert (
        sum(line.over_both(seed.FLUX_THRESHOLD_PCT, seed.FLUX_THRESHOLD_USD) for line in seed.FLUX)
        == book["over"]
    )


def test_ac_payroll_plus_7670_is_125_percent_and_its_drivers_foot() -> None:
    payroll = next(line for line in seed.FLUX if line.key == "payroll")
    assert (payroll.change, payroll.change_pct) == (7_670, D("12.5"))
    drivers = dict(seed.PAYROLL_DRIVERS)
    assert sum(drivers.values()) == payroll.change
    assert [(k, int(v)) for k, v in BOOK["flux"]["payroll_drivers"]] == list(seed.PAYROLL_DRIVERS)


def test_ac_repairs_400_percent_marketing_and_cogs_within() -> None:
    by_key = {line.key: line for line in seed.FLUX}
    assert (by_key["repairs_maintenance"].change, by_key["repairs_maintenance"].change_pct) == (
        2_560, D("400.0"),
    )  # fmt: skip
    marketing, cogs = by_key["marketing"], by_key["cogs"]
    assert (marketing.change, marketing.change_pct) == (-1_530, D("-38.4"))
    assert (cogs.change, cogs.change_pct) == (3_690, D("4.5"))
    for line in (marketing, cogs):
        assert not line.over_both(seed.FLUX_THRESHOLD_PCT, seed.FLUX_THRESHOLD_USD)


def test_ac_net_income_31455_to_27795() -> None:
    book = BOOK["flux"]
    prior, current = seed.flux_totals("prior"), seed.flux_totals("current")
    for key in ("gross_profit", "operating_expenses", "net_income"):
        assert [prior[key], current[key]] == [int(v) for v in book[key]]


# --- CLS-09 and POR-11 --------------------------------------------------------------------------


def test_ac_plan_v3_23_procedures_is_manager_8_plus_senior_15_over_21_accounts() -> None:
    book = BOOK["plan"]
    reviews = [row.review for row in seed.PLAN_V3]
    assert len(seed.PLAN_V3) == book["procedures"] == 23
    assert reviews.count("manager_approval") == book["manager"] == 8
    assert reviews.count("senior_signoff") == book["senior"] == 15
    assert seed.plan_accounts() == book["accounts"] == 21
    for row, (cls, account, procedure, source, review) in zip(
        seed.PLAN_V3, book["rows"], strict=True
    ):
        assert (row.account_class, row.account, row.procedure, row.source, row.review) == (
            cls, account, procedure, source, review,
        )  # fmt: skip


def test_ac_plan_generates_8_requests_and_v4_7() -> None:
    book = BOOK["plan"]
    assert list(seed.REQUEST_TEMPLATES) == book["request_templates"]
    assert len(seed.REQUEST_TEMPLATES) == book["requests_per_month"] == 8
    assert book["v4_requests_per_month"] == seed.V4_REQUESTS_PER_MONTH
    # One request per distinct client-upload evidence (the payroll register serves two rows);
    # bank-feed, QuickBooks, Files and register rows ask the client for nothing (QC-1).
    uploads = {row.evidence for row in seed.PLAN_V3 if row.source == "client_upload"}
    assert len(uploads) == len(seed.REQUEST_TEMPLATES)


def test_ac_portal_9_requests_is_7_received_plus_2_open_and_3_questions() -> None:
    book = BOOK["portal"]
    received = [r for r in seed.PORTAL_REQUESTS if r.received]
    open_ = [r.title for r in seed.PORTAL_REQUESTS if not r.received]
    assert len(seed.PORTAL_REQUESTS) == book["requests"] == len(received) + len(open_)
    assert len(received) == book["received"] and open_ == book["open_requests"]
    assert len(seed.TRANSACTION_QUESTIONS) == book["questions"] == 3
    assert book["open"] == seed.PORTAL_REQUESTS_PENDING


def test_ac_knw_04a_20020_within_and_14900_held() -> None:
    book = BOOK["knw_04a"]
    parts = seed.KNW_04A["within"]
    assert [str(p) for p in parts] == book["parts"]
    assert sum(parts, D(0)) == D(book["total"])
    assert seed.KNW_04A["held"] == D(book["held"]) > D("10000")  # the other-accruals threshold


def test_ac_past_due_counts_business_days_from_due_on() -> None:
    """QC-7 (AC-3): Copperleaf due Tue Sep 8 (BD5) reads 4 on Mon Sep 14; Bluebird Bakery due
    Thu Sep 10 (BD7) reads 2. No legal holiday falls between Sep 9 and Sep 14, 2026 (Labor Day is
    Sep 7), so weekdays are the business days here."""
    today = seed.E0.date()
    for close in seed.PORTFOLIO:
        if close.days_past_due is None:
            continue
        span = (today - close.due_on).days
        weekdays = sum(
            (close.due_on + timedelta(days=d)).weekday() < 5 for d in range(1, span + 1)
        )
        assert weekdays == close.days_past_due

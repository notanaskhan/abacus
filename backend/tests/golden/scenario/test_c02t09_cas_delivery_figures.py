"""C-02-T09 (TASK-8508; SPEC-700, SPEC-701; C-02 §5.3): the Copperleaf posting and delivery
figure book against the slice. Every figure that foots is a seed test: 20,020 + 14,900 + 380 =
35,300; total assets 549,195.45 on both sides; net income 27,795 and 31,455; 74,900 and 25,680;
144,000; rent and the firm's fee; six of twelve vendors reportable."""

from __future__ import annotations

import json
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, cast

from abacus_tools.synthetic.scenarios.brightwater_hale import cas_delivery_slice as seed

HERE: Final = Path(__file__).resolve().parent
BOOK: Final[dict[str, Any]] = json.loads(  # Any: the figure book's JSON
    (HERE / "brightwater_hale" / "copperleaf_cas_delivery_figures.json").read_text(
        encoding="utf-8"
    )
)
D = Decimal
ZERO = D("0.00")


def _sum(values: Iterable[Decimal]) -> Decimal:
    return sum(values, ZERO)


def test_cls07_the_entries_foot_20020_34920_35300() -> None:
    assert {e.ref: str(e.amount) for e in seed.ENTRIES} == BOOK["entries"]
    within = _sum(e.amount for e in seed.ENTRIES if e.initial == "within_threshold")
    five = _sum(e.amount for e in seed.FIRST_FIVE)
    six = _sum(e.amount for e in seed.ENTRIES)
    assert (str(within), str(five), str(six)) == (
        BOOK["within_threshold"],
        BOOK["proposed_five"],
        BOOK["posted_six"],
    )
    assert within + D("14900.00") + D("380.00") == six == D("35300.00")


def test_cls07_named_lines_balance_and_class_limits_hold() -> None:
    for entry in seed.ENTRIES:
        if entry.lines:
            debits = _sum(ln.debit for ln in entry.lines)
            credits = _sum(ln.credit for ln in entry.lines)
            assert debits == credits == entry.amount, entry.ref
            assert len(entry.lines) == entry.line_count, entry.ref
        if entry.class_limit is not None:
            held = entry.amount > entry.class_limit
            assert held == (entry.initial == "review_required"), entry.ref
    assert {k: str(v) for k, v in seed.THRESHOLDS.items()} == BOOK["class_limits"]


def test_cls07d_the_batch_reads_qbo_48213_to_48218_in_order() -> None:
    ids = [e.qbo_id for e in seed.ENTRIES]
    assert ids == [str(n) for n in range(48213, 48219)]
    assert [seed.AUGUST_POSTED_BATCH.qbo_first, seed.AUGUST_POSTED_BATCH.qbo_last] == BOOK[
        "qbo_ids"
    ]
    assert seed.AUGUST_POSTED_BATCH.amount == D(BOOK["posted_six"])


def test_cls11_the_log_and_its_id_ranges() -> None:
    for batch in seed.BATCHES[1:]:
        book = BOOK["batches"][batch.code]
        assert batch.entries == book["entries"]
        assert str(batch.amount) == book["amount"]
        assert [batch.qbo_first, batch.qbo_last] == book["qbo"]
        assert int(batch.qbo_last or 0) - int(batch.qbo_first or 0) + 1 == batch.entries
        assert batch.resolved_failures == book.get("resolved", 0)
    posted = [b for b in seed.BATCHES if b.status == "posted"]
    assert len(posted) + len(seed.BELOW_THE_FOLD_POSTED) == BOOK["posted_batches_before_august"]
    assert str(seed.CONNECTED_ON) == BOOK["authorization"]["connected"]
    assert str(seed.WRITE_GRANT_ON) == BOOK["authorization"]["write_grant"]


def test_cls08_the_balance_sheet_foots_549195_45_on_both_sides() -> None:
    bs = seed.BALANCE_SHEET
    book = BOOK["balance_sheet"]
    current = _sum(v for _, v in bs["current_assets"])
    ppe = _sum(v for _, v in bs["property_and_equipment"])
    liabilities = _sum(v for _, v in bs["current_liabilities"]) + _sum(
        v for _, v in bs["long_term_liabilities"]
    )
    equity = _sum(v for _, v in bs["equity"])
    assert str(current) == book["total_current_assets"]
    assert str(ppe) == book["net_property_and_equipment"]
    assert str(_sum(v for _, v in bs["current_liabilities"])) == book["total_current_liabilities"]
    assert str(liabilities) == book["total_liabilities"]
    assert str(equity) == book["total_equity"]
    assert str(current + ppe) == str(liabilities + equity) == book["total_assets"]


def test_cls08_net_income_27795_august_and_31455_july() -> None:
    inc = seed.INCOME_STATEMENT
    for i, month in ((0, "august"), (1, "july")):
        pick = 1 + i
        revenue = _sum(cast(Decimal, row[pick]) for row in inc["revenue"])
        gross = revenue - _sum(cast(Decimal, row[pick]) for row in inc["cost_of_goods_sold"])
        opex = _sum(cast(Decimal, row[pick]) for row in inc["operating_expenses"])
        operating = gross - opex
        net = operating - _sum(cast(Decimal, row[pick]) for row in inc["interest_expense"])
        book = BOOK["income_statement"][month]
        assert [str(revenue), str(gross), str(opex), str(operating), str(net)] == [
            book["revenue"],
            book["gross_profit"],
            book["operating_expenses"],
            book["operating_income"],
            book["net_income"],
        ]


def test_cls12_year_end_figures_follow_from_the_seed() -> None:
    book = BOOK["handoff"]
    accumulated = seed.ACCUMULATED_DEPRECIATION_JUL_31 + 5 * seed.MONTHLY_DEPRECIATION
    assert str(accumulated) == book["accumulated_depreciation"]  # 64,200 + 5 x 2,140
    assert str(12 * seed.MONTHLY_DEPRECIATION) == book["book_depreciation_2026"]
    assert str(seed.FIXED_ASSET_COST) == book["fixed_asset_cost"]
    assert str(seed.PREPAID_INSURANCE_YEAR) == book["prepaid_insurance"]
    assert str(12 * seed.MONTHLY_DISTRIBUTION) == book["distributions"]
    assert book["tax_issues"] == seed.TAX_ISSUES_CREATED
    assert str(seed.DECEMBER_LOCKED_ON) == book["locked_on"]
    # August's accumulated depreciation on CLS-08 is July's plus one month.
    august = dict(seed.BALANCE_SHEET["property_and_equipment"])["Less accumulated depreciation"]
    assert -august == seed.ACCUMULATED_DEPRECIATION_JUL_31 + seed.MONTHLY_DEPRECIATION


def test_cls13_six_of_twelve_vendors_are_reportable() -> None:
    book = BOOK["vendors"]
    assert len(seed.VENDORS) == book["paid"]
    picked = [v.name for v in seed.VENDORS if seed.reportable(v)]
    assert picked == book["reportable_names"] and len(picked) == book["reportable"]
    assert sum(v.w9 == "requested" for v in seed.VENDORS) == book["requested"]
    assert sum(v.w9 == "tin_mismatch" for v in seed.VENDORS) == book["tin_mismatch"]
    assert str(seed.MONTHLY_RENT * seed.MONTHS_PAID) == book["rent"]
    assert str(seed.MONTHLY_FIRM_FEE * seed.MONTHS_PAID) == book["firm_fee"]
    assert str(seed.DUE_ON_2026) == book["due_on"]
    for vendor in seed.VENDORS:
        assert vendor.tin_last4 is None or len(vendor.tin_last4) == 4  # never a full TIN


def test_the_attest_client_is_not_copperleaf() -> None:
    assert seed.ATTEST_CAS_CLIENT != seed.COPPERLEAF

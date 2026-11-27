"""CV-3 (TASK-9002; ED-331; DEC-6008; C-01-T22; ADR-050): a prior bank-side `bank_error` carries
forward like every other open item.

Engine version 1 matched only deposits in transit and outstanding checks against the statement and
carried only book-side items, so a bank error noted last month was dropped from the next
reconciliation and from `adjusted_bank`. Version 2 carries it, unmatched, with `carried_from`."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal as D

from abacus.modules.closes.compute import reconciliation as rec

END = date(2026, 9, 30)
ERROR = rec.PriorItem(
    "prior-err", "bank", "bank_error", date(2026, 8, 28), D("120.00"), "Bank fee reversal"
)
BASE = rec.Inputs(
    period_end=END,
    balance_per_bank=D("10120.00"),
    book_balance=D("10000.00"),
    statement_lines=(),
    register_lines=(),
    prior_items=(ERROR,),
)


def test_ed331_a_prior_bank_error_is_carried_with_its_origin() -> None:
    result = rec.reconcile(BASE)
    [carried] = [i for i in result.items if i.kind == "bank_error"]
    assert (carried.side, carried.amount, carried.carried_from, carried.ref) == (
        "bank",
        D("120.00"),
        "prior-err",
        "Bank fee reversal",
    )
    assert carried.txn_date == date(2026, 8, 28) and carried.days_at_period_end == 33
    assert "prior-err" not in result.cleared_prior


def test_ed331_the_carried_error_moves_adjusted_bank_so_the_period_ties() -> None:
    result = rec.reconcile(BASE)
    # 10,120.00 per bank less the 120.00 error the bank still shows = 10,000.00, the book.
    assert (result.adjusted_bank, result.adjusted_book, result.difference, result.tally) == (
        D("10000.00"),
        D("10000.00"),
        D("0.00"),
        "tie",
    )


def test_ed331_without_the_carry_the_period_would_be_off_by_the_error() -> None:
    gone = rec.reconcile(replace(BASE, prior_items=()))
    assert (gone.difference, gone.tally) == (D("120.00"), "off")


def test_ed331_a_carried_error_is_never_a_statement_match_candidate() -> None:
    line = rec.StatementLine("s1", date(2026, 9, 3), "Service fee", D("120.00"), None)
    result = rec.reconcile(replace(BASE, statement_lines=(line,)))
    assert [m.statement_line_id for m in result.matches] == []
    kinds = sorted((i.kind, i.carried_from) for i in result.items)
    assert kinds == [("bank_error", "prior-err"), ("unrecorded_withdrawal", None)]


def test_ed331_the_engine_is_version_2() -> None:
    assert rec.ENGINE_VERSION == "2"
    assert rec.reconcile(BASE).engine_version == "closes.reconciliation/2"

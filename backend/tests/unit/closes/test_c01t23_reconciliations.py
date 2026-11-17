"""C-01-T23 (TASK-8415; SPEC-655 AC-39 to AC-42; CLS-05): code's AJE draft for an item, and the
reviewable's blocked code while items are open."""

from __future__ import annotations

from decimal import Decimal as D

from abacus.modules.closes import reconciliations as recs


def test_an_unrecorded_deposit_debits_cash() -> None:
    lines = recs.entry_lines({"kind": "unrecorded_deposit", "amount": D("410.00")}, "1010", "4900")
    assert lines == [("1010", D("410.00"), D(0)), ("4900", D(0), D("410.00"))]


def test_an_unrecorded_withdrawal_credits_cash() -> None:
    lines = recs.entry_lines(
        {"kind": "unrecorded_withdrawal", "amount": D("-35.00")}, "1010", "6100"
    )
    assert lines == [("6100", D("35.00"), D(0)), ("1010", D(0), D("35.00"))]


def test_the_blocked_code_names_open_items() -> None:
    assert recs.BLOCKED == "reconciling_items_open"
    assert recs.TARGET == "reconciliation"

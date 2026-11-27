"""C-01-T22: the bank reconciliation engine (C-01 §3 F7; CLS-05; ADR-050).

The ••4410 fixture is Brightwater Hale's August close (`close_slice`): 184,236.18 + 6,412.40 -
5,658.08 = 184,990.50 = 184,610.50 + 380.00, check #2281 stale at 193 days, and the same inputs
always give the same hash.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest

from abacus.modules.closes.compute import reconciliation as rec
from abacus_tools.synthetic.scenarios.brightwater_hale import close_slice as bh

END = bh.PERIOD_END


def _statement() -> list[rec.StatementLine]:
    return [
        rec.StatementLine(
            id=f"s{n}",
            txn_date=when,
            description=text,
            withdrawal=out,
            deposit=into,
            page_no=2,
            bbox=(D("0.06"), D("0.20") + D(n) / 50, D("0.94"), D("0.215") + D(n) / 50),
            confidence=D("0.990"),
        )
        for n, (when, text, out, into) in enumerate(bh.STATEMENT_PAGE_2)
    ]


def _register() -> list[rec.RegisterLine]:
    """The QBO register: every statement line except the refund is booked on its date, plus the
    Aug 31 Square deposit (in transit) and checks #2287 and #2290 (not yet cleared)."""
    booked = [
        rec.RegisterLine(f"r{n}", when, into if into is not None else -(out or D(0)))
        for n, (when, text, out, into) in enumerate(bh.STATEMENT_PAGE_2)
        if "REFUND" not in text
    ]
    return [
        *booked,
        rec.RegisterLine("r-dit", date(2026, 8, 31), bh.DEPOSIT_IN_TRANSIT, payee="Square"),
        *(
            rec.RegisterLine(
                f"r-{c.number}", c.issued_on, -c.amount, number=c.number, payee=c.payee
            )
            for c in bh.OUTSTANDING_CHECKS
            if c.number != "#2281"
        ),
    ]


def _prior() -> list[rec.PriorItem]:
    """July's reconciliation left #2281 outstanding."""
    c = bh.OUTSTANDING_CHECKS[0]
    return [
        rec.PriorItem("jul-2281", "bank", "outstanding_check", c.issued_on, c.amount, ref="#2281")
    ]


def _inputs(**kw: object) -> rec.Inputs:
    base = rec.Inputs(
        period_end=END,
        book_balance=bh.BOOK_BALANCE,
        balance_per_bank=bh.BALANCE_PER_BANK,
        statement_lines=tuple(_statement()),
        register_lines=tuple(_register()),
        prior_items=tuple(_prior()),
    )
    return replace(base, **kw)


def test_ac_the_4410_fixture_ties_to_the_cent() -> None:
    result = rec.reconcile(_inputs())
    assert result.balance_per_bank == D("184236.18")
    assert result.deposits_in_transit == D("6412.40")
    assert result.outstanding_checks == D("5658.08")
    assert result.adjusted_bank == D("184990.50")
    assert result.book_balance == D("184610.50")
    assert result.unrecorded_deposits == D("380.00")
    assert result.adjusted_book == D("184990.50")
    assert result.difference == D("0.00")
    assert result.tally == "tie"
    assert result.adjusted_bank == bh.adjusted_bank() == bh.adjusted_book()


def test_ac_check_2281_is_stale_at_193_days_and_carried_forward() -> None:
    result = rec.reconcile(_inputs())
    (stale,) = [i for i in result.items if i.stale]
    assert stale.ref == "#2281"
    assert stale.days_at_period_end == 193
    assert stale.carried_from == "jul-2281"
    assert stale.aging == rec.AGING_OVER
    assert result.stale_count == 1
    assert result.aging[rec.AGING_OVER] == D("1240.00")


def test_ac_the_refund_is_an_unrecorded_deposit_traced_to_its_statement_line() -> None:
    result = rec.reconcile(_inputs())
    (refund,) = [i for i in result.items if i.kind == "unrecorded_deposit"]
    assert refund.amount == bh.UNRECORDED_REFUND
    assert refund.side == "book"
    line = next(s for s in _statement() if s.id == refund.statement_line_id)
    assert "REFUND" in line.description
    assert line.txn_date == date(2026, 8, 27)


def test_ac_recomputing_the_same_inputs_yields_the_same_hash() -> None:
    a, b = rec.reconcile(_inputs()), rec.reconcile(_inputs())
    assert a.inputs_hash == b.inputs_hash and a.content_hash == b.content_hash
    assert len(a.inputs_hash) == 64 and len(a.content_hash) == 64
    shuffled = _inputs(
        statement_lines=tuple(reversed(_statement())),
        register_lines=tuple(reversed(_register())),
    )
    assert rec.reconcile(shuffled).inputs_hash == a.inputs_hash
    changed = rec.reconcile(_inputs(book_balance=bh.BOOK_BALANCE + D("1.00")))
    assert changed.inputs_hash != a.inputs_hash and changed.content_hash != a.content_hash
    assert a.engine_version == "closes.reconciliation/2"


def test_run_1_before_the_refund_reads_off_380() -> None:
    """CLS-05 b: the refund is booked nowhere and the book side is unadjusted, so the run that
    did not yet list it reads off by 380.00 (the statement line stays unmatched)."""
    result = rec.reconcile(
        _inputs(statement_lines=tuple(s for s in _statement() if "REFUND" not in s.description))
    )
    assert result.difference == D("380.00") and result.tally == "off"


def test_every_match_is_one_to_one_and_names_its_rule() -> None:
    result = rec.reconcile(_inputs())
    lines = [m.statement_line_id for m in result.matches]
    refs = [m.register_line_ref for m in result.matches]
    assert len(lines) == len(set(lines)) and len(refs) == len(set(refs))
    assert {m.match_rule for m in result.matches} <= {"reference", "amount_date"}
    assert len(result.matches) == len(bh.STATEMENT_PAGE_2) - 1


def test_a_prior_check_clearing_this_period_matches_by_reference() -> None:
    cleared = rec.StatementLine(
        "s-2281", date(2026, 8, 20), "CHECK 2281", D("1240.00"), None, confidence=D("0.99")
    )
    result = rec.reconcile(
        _inputs(
            statement_lines=(*_statement(), cleared),
            balance_per_bank=bh.BALANCE_PER_BANK - D("1240.00"),
        )
    )
    assert "jul-2281" in result.cleared_prior
    assert any(m.match_rule == "carried_reference" for m in result.matches)
    assert result.tally == "tie"
    assert not any(i.stale for i in result.items)


def test_a_line_below_the_confidence_floor_is_never_matched_automatically() -> None:
    lines = _statement()
    low = replace(lines[0], confidence=D("0.420"))
    result = rec.reconcile(_inputs(statement_lines=(low, *lines[1:])))
    assert low.id in result.needs_review
    assert low.id not in {m.statement_line_id for m in result.matches}
    assert low.id not in {i.statement_line_id for i in result.items}


def test_no_statement_yet_is_pending_with_the_book_side_only() -> None:
    """CLS-05 g: the savings statement is still owed."""
    result = rec.reconcile(_inputs(balance_per_bank=None, statement_lines=(), prior_items=()))
    assert result.tally == "pending"
    assert result.adjusted_bank is None and result.difference is None
    assert result.adjusted_book == bh.BOOK_BALANCE
    assert result.items == ()


def test_a_prior_unrecorded_deposit_clears_once_booked() -> None:
    prior = rec.PriorItem(
        "jul-refund", "book", "unrecorded_deposit", date(2026, 7, 30), D("75.00")
    )
    booked = rec.RegisterLine("r-jul-refund", date(2026, 8, 3), D("75.00"))
    result = rec.reconcile(
        _inputs(
            prior_items=(*_prior(), prior),
            register_lines=(*_register(), booked),
            book_balance=bh.BOOK_BALANCE + D("75.00"),
            balance_per_bank=bh.BALANCE_PER_BANK + D("75.00"),
        )
    )
    assert "jul-refund" in result.cleared_prior
    assert result.tally == "tie"


def test_invalid_inputs_are_refused() -> None:
    bad = rec.StatementLine("x", END, "x", D("1.00"), D("1.00"))
    with pytest.raises(rec.ReconciliationInvalid):
        rec.reconcile(_inputs(statement_lines=(bad,)))
    with pytest.raises(rec.ReconciliationInvalid):
        rec.reconcile(_inputs(register_lines=(*_register(), _register()[0])))


def test_statement_lines_from_an_extracted_table_keep_the_row_box_and_lowest_confidence() -> None:
    def cell(r: int, c: int, text: str, conf: str = "0.99") -> rec.TableCell:
        x = D(c) / 10
        y = D(r) / 40
        return rec.TableCell(r, c, text, (x, y, x + D("0.09"), y + D("0.02")), D(conf))

    cells = [
        cell(0, 0, "Date"), cell(0, 1, "Description"),
        cell(0, 2, "Withdrawals"), cell(0, 3, "Deposits"),
        cell(1, 0, "08/27"), cell(1, 1, "ROCKY RIDGE DAIRY CO REFUND"),
        cell(1, 3, "380.00", "0.91"),
        cell(2, 0, "08/28"), cell(2, 1, "CHECK 2287"), cell(2, 2, "3,615.75"),
        cell(3, 0, ""), cell(3, 1, "Ending balance"), cell(3, 3, "184,236.18"),
    ]  # fmt: skip
    cols = rec.Columns(date=0, description=1, withdrawal=2, deposit=3)
    refund, check = rec.statement_lines_from_table("t1", 2, cells, cols, END)
    assert refund.id == "t1:1" and refund.deposit == D("380.00") and refund.withdrawal is None
    assert refund.txn_date == date(2026, 8, 27)
    assert refund.confidence == D("0.91")
    assert refund.bbox[0] == D(0) and refund.bbox[2] == D("0.39")
    assert check.withdrawal == D("3615.75") and check.number == "2287"

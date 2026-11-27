"""Q-03-T367 (TASK-8959): the bank reconciliation engine's edges (C-01-T22; CLS-05; ADR-050).

The quarterly mutation sweep found the engine's parsing, refusals, boundaries and carry-forward
held only by the ••4410 fixture's happy path. Each case below is one rule from the module
docstring, written with its exact expected value.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest

from abacus.modules.closes.compute import reconciliation as rec

END = date(2026, 8, 31)
BOX = (D("0.10"), D("0.20"), D("0.30"), D("0.25"))


def _cell(
    row: int, col: int, text: str, *, conf: str = "0.99", box: tuple[D, ...] = BOX
) -> rec.TableCell:
    return rec.TableCell(row, col, text, box, D(conf))  # type: ignore[arg-type]  # a 4-tuple box


# --- statement lines from an extracted table ----------------------------------------------------

ONE_COLUMN = rec.Columns(date=0, description=1, amount=2, check_number=3)
TWO_COLUMNS = rec.Columns(date=0, description=1, withdrawal=2, deposit=3)


@pytest.mark.parametrize(
    ("text", "deposit", "withdrawal"),
    [
        ("$1,234.50", D("1234.50"), None),
        ("$ 1 234.50", D("1234.50"), None),  # spaces and the dollar sign drop
        ("(1,234.50)", None, D("1234.50")),  # parentheses are a withdrawal
        ("-12.00", None, D("12.00")),
        ("12", D("12.00"), None),
    ],
)
def test_one_signed_amount_column_reads_as_printed(
    text: str, deposit: D | None, withdrawal: D | None
) -> None:
    (line,) = rec.statement_lines_from_table(
        "t1", 3, [_cell(1, 0, "08/12"), _cell(1, 1, " ACH "), _cell(1, 2, text)], ONE_COLUMN, END
    )
    assert (line.deposit, line.withdrawal) == (deposit, withdrawal)
    assert (line.id, line.page_no, line.description) == ("t1:1", 3, "ACH")
    assert line.check_number is None  # no number cell in the row


def test_rows_without_a_readable_date_or_amount_are_skipped() -> None:
    cells = [
        _cell(0, 0, "Date"),
        _cell(0, 1, "Description"),
        _cell(0, 2, "Amount"),  # the header
        _cell(1, 0, "13/40"),
        _cell(1, 2, "5.00"),  # no such date
        _cell(2, 0, "08/03"),
        _cell(2, 2, "0.00"),  # a zero amount
        _cell(3, 0, "08/04"),
        _cell(3, 2, "abc"),  # not an amount
        _cell(4, 1, "no date"),
        _cell(4, 2, "9.00"),
        _cell(5, 0, "08/05"),  # no amount cell at all
        _cell(6, 0, "08/06"),
        _cell(6, 2, "7.00"),  # the one transaction
    ]
    lines = rec.statement_lines_from_table("t", 1, cells, ONE_COLUMN, END)
    assert [(ln.id, ln.txn_date, ln.deposit) for ln in lines] == [
        ("t:6", date(2026, 8, 6), D("7.00"))
    ]
    assert lines[0].description == ""  # no description cell


def test_two_columns_and_the_dates_year() -> None:
    cells = [
        _cell(1, 0, "12/28"),
        _cell(1, 1, "Dec fee"),
        _cell(1, 2, "25.00"),  # before January
        _cell(2, 0, "1/3/27"),
        _cell(2, 3, "100.00"),  # a two-digit year
        _cell(3, 0, "01-04-2027"),
        _cell(3, 2, "(5.00)"),  # dashes, four digits, a negative
        _cell(4, 0, "01/05"),
        _cell(4, 2, "3.00"),
        _cell(4, 3, "4.00"),  # both: ambiguous
    ]
    lines = rec.statement_lines_from_table("t", 1, cells, TWO_COLUMNS, date(2027, 1, 31))
    assert [(ln.txn_date, ln.withdrawal, ln.deposit) for ln in lines] == [
        (date(2026, 12, 28), D("25.00"), None),
        (date(2027, 1, 3), None, D("100.00")),
        (date(2027, 1, 4), D("5.00"), None),  # a withdrawal column's value is its size
    ]


def test_a_row_keeps_its_box_its_lowest_confidence_and_its_check_number() -> None:
    cells = [
        _cell(7, 0, "08/12", conf="0.95", box=(D("0.10"), D("0.40"), D("0.20"), D("0.42"))),
        _cell(7, 1, "x" * 600, conf="0.99", box=(D("0.25"), D("0.39"), D("0.70"), D("0.43"))),
        _cell(7, 2, "-410.00", conf="0.97", box=(D("0.75"), D("0.41"), D("0.85"), D("0.42"))),
        _cell(7, 3, "  2281 ", conf="0.81", box=(D("0.90"), D("0.40"), D("0.95"), D("0.44"))),
        _cell(8, 0, "08/13"),
        _cell(8, 2, "1.00"),
        _cell(8, 3, "   "),  # a blank number cell
    ]
    first, second = rec.statement_lines_from_table("t", 2, cells, ONE_COLUMN, END)
    assert first.bbox == (D("0.10"), D("0.39"), D("0.95"), D("0.44"))
    assert first.confidence == D("0.81")  # the number cell counts
    assert first.check_number == "2281"
    assert first.description == "x" * 500
    assert first.number == "2281"
    assert second.check_number is None


# --- refusals ------------------------------------------------------------------------------------

_DEP = rec.StatementLine("s1", date(2026, 8, 3), "Deposit", None, D("10.00"))
_BASE = rec.Inputs(period_end=END, book_balance=D("0"), balance_per_bank=D("0"))


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        (
            replace(_BASE, statement_lines=(_DEP, _DEP)),
            "duplicate statement line id or register line ref",
        ),
        (
            replace(_BASE, register_lines=(rec.RegisterLine("r", END, D("1")),) * 2),
            "duplicate statement line id or register line ref",
        ),
        (
            replace(_BASE, statement_lines=(replace(_DEP, withdrawal=D("1.00")),)),
            "statement line s1: one of withdrawal, deposit",
        ),
        (
            replace(_BASE, statement_lines=(replace(_DEP, deposit=D("0")),)),
            "statement line s1: amounts are positive",
        ),
        (
            replace(_BASE, register_lines=(rec.RegisterLine("r9", END, D("0")),)),
            "register line r9: zero amount",
        ),
        (
            replace(
                _BASE, prior_items=(rec.PriorItem("p9", "bank", "outstanding_check", END, D("0")),)
            ),
            "prior item p9: amounts are positive",
        ),
        (replace(_BASE, date_window_days=-1), "negative window"),
        (replace(_BASE, stale_after_days=-1), "negative window"),
    ],
)
def test_each_refusal_names_what_is_wrong(inputs: rec.Inputs, message: str) -> None:
    with pytest.raises(rec.ReconciliationInvalid) as refused:
        rec.reconcile(inputs)
    assert str(refused.value) == message


def test_the_boundaries_that_are_allowed() -> None:
    allowed = replace(
        _BASE,
        register_lines=(rec.RegisterLine("r1", END, D("1.00")),),
        date_window_days=0,
        stale_after_days=0,
    )
    assert rec.reconcile(allowed).tally == "off"  # a $1 deposit in transit, nothing refused


# --- aging, staleness and the carried items ------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "bucket", "stale"),
    [
        (0, "0-30", False),
        (30, "0-30", False),
        (31, "31-60", False),
        (60, "31-60", False),
        (61, "61-90", False),
        (90, "61-90", False),
        (91, "over_90", True),
    ],
)
def test_an_items_age_bucket_and_staleness(days: int, bucket: str, stale: bool) -> None:
    when = date.fromordinal(END.toordinal() - days)
    inputs = replace(_BASE, register_lines=(rec.RegisterLine("r1", when, D("-50.00"), "101"),))
    (item,) = rec.reconcile(inputs).items
    assert (item.days_at_period_end, item.aging, item.stale) == (days, bucket, stale)
    assert (item.kind, item.ref, item.amount, item.register_line_ref) == (
        "outstanding_check",
        "#101",
        D("50.00"),
        "r1",
    )


def test_prior_items_carry_clear_and_keep_their_kind() -> None:
    prior = (
        rec.PriorItem(
            "p-dit",
            "bank",
            "deposit_in_transit",
            date(2026, 7, 30),
            D("300.00"),
            register_line_ref="r-old",
        ),
        rec.PriorItem(
            "p-chk", "bank", "outstanding_check", date(2026, 7, 20), D("120.00"), ref="#000123"
        ),
        rec.PriorItem("p-wd", "book", "unrecorded_withdrawal", date(2026, 7, 31), D("15.00")),
        rec.PriorItem("p-dep", "book", "unrecorded_deposit", date(2026, 7, 31), D("40.00")),
    )
    statement = (
        rec.StatementLine("s1", date(2026, 8, 2), "Deposit", None, D("300.00")),
        rec.StatementLine("s2", date(2026, 8, 9), "CHECK 123", D("120.00"), None),
    )
    register = (
        rec.RegisterLine("r-wd", date(2026, 8, 1), D("-15.00")),  # books the prior withdrawal
        rec.RegisterLine(
            "r-other", date(2026, 8, 1), D("-40.00")
        ),  # not the deposit: opposite sign
    )
    result = rec.reconcile(
        replace(_BASE, statement_lines=statement, register_lines=register, prior_items=prior)
    )
    assert [(m.statement_line_id, m.register_line_ref, m.match_rule) for m in result.matches] == [
        ("s1", "r-old", "carried_amount_date"),
        ("s2", "prior:p-chk", "carried_reference"),
    ]
    assert result.cleared_prior == ("p-chk", "p-dit", "p-wd")
    carried = [(i.side, i.kind, i.carried_from, i.amount) for i in result.items if i.carried_from]
    assert carried == [("book", "unrecorded_deposit", "p-dep", D("40.00"))]
    # The register's -40 is not the prior deposit (the opposite sign): it is an outstanding check.
    (check,) = [i for i in result.items if i.register_line_ref == "r-other"]
    assert (check.side, check.kind, check.ref) == ("bank", "outstanding_check", None)


# --- the two matching passes ---------------------------------------------------------------------


def _reconcile(
    statement: tuple[rec.StatementLine, ...], register: tuple[rec.RegisterLine, ...], **kw: object
) -> rec.Result:
    return rec.reconcile(replace(_BASE, statement_lines=statement, register_lines=register, **kw))


def test_reference_needs_the_number_the_amount_and_a_statement_date_on_or_after_issue() -> None:
    statement = (
        rec.StatementLine(
            "a", date(2026, 8, 5), "Transfer", None, D("9.00")
        ),  # no number: skipped
        rec.StatementLine("b", date(2026, 8, 10), "CHECK 501", D("75.00"), None),
        rec.StatementLine("c", date(2026, 8, 10), "CHECK 502", D("80.00"), None),
    )
    register = (
        rec.RegisterLine("r501", date(2026, 8, 10), D("-75.00"), "501"),  # issued the same day
        rec.RegisterLine("r502", date(2026, 8, 11), D("-80.00"), "502"),  # issued after it cleared
        rec.RegisterLine("r9", date(2026, 8, 5), D("9.00")),
    )
    rules = {
        m.statement_line_id: (m.register_line_ref, m.match_rule)
        for m in _reconcile(statement, register).matches
    }
    # 502 cleared a day before its register date: never by reference, but the amount-and-date
    # pass takes the gap either way, so it still matches there (a register dated late).
    assert rules == {
        "a": ("r9", "amount_date"),
        "b": ("r501", "reference"),
        "c": ("r502", "amount_date"),
    }


def test_amount_date_takes_the_nearest_date_within_the_window_then_the_lowest_key() -> None:
    line = rec.StatementLine("s", date(2026, 8, 10), "ACH", D("20.00"), None)
    register = (
        rec.RegisterLine("r-far", date(2026, 8, 3), D("-20.00")),  # 7 days: the window's edge
        rec.RegisterLine("r-b", date(2026, 8, 12), D("-20.00")),  # 2 days
        rec.RegisterLine("r-a", date(2026, 8, 8), D("-20.00")),  # 2 days, the lower key
    )
    (match,) = _reconcile((line,), register).matches
    assert (match.register_line_ref, match.match_rule) == ("r-a", "amount_date")
    edge = _reconcile((line,), register[:1]).matches
    assert [m.register_line_ref for m in edge] == ["r-far"]  # 7 days is within a 7-day window
    out = _reconcile((line,), register[:1], date_window_days=6).matches
    assert out == ()  # 7 days is outside a 6-day window


def test_a_numbered_check_never_matches_another_number_by_amount() -> None:
    line = rec.StatementLine("s", date(2026, 8, 10), "CHECK 700", D("20.00"), None)
    other = rec.RegisterLine("r", date(2026, 8, 10), D("-20.00"), "701")
    assert _reconcile((line,), (other,)).matches == ()
    blank = rec.RegisterLine("r", date(2026, 8, 10), D("-20.00"))
    (m,) = _reconcile((line,), (blank,)).matches
    assert m.match_rule == "amount_date"  # an unnumbered register line may still match


def test_the_confidence_floor_is_inclusive() -> None:
    at = rec.StatementLine("s", date(2026, 8, 10), "ACH", D("20.00"), None, confidence=D("0.800"))
    below = replace(at, id="t", confidence=D("0.799"))
    register = (
        rec.RegisterLine("r1", date(2026, 8, 10), D("-20.00")),
        rec.RegisterLine("r2", date(2026, 8, 10), D("-20.00")),
    )
    result = _reconcile((at, below), register)
    assert [m.statement_line_id for m in result.matches] == ["s"]
    assert result.needs_review == ("t",)
    assert all(i.statement_line_id != "t" for i in result.items)  # a person matches it


# --- one period, whole ---------------------------------------------------------------------------
#
# Book 1,000.00; bank 1,500.00.
# Bank side: the Aug 30 deposit in transit 400.00; outstanding checks #77 (carried, 20.00) and
# #99 (75.00): adjusted bank = 1,500 + 400 - 95 = 1,805.00.
# Book side: unrecorded deposits 55.00 (the interest) + 12.00 (carried), the unrecorded check #42
# (30.00) and a carried book error (5.00, reduces the book): adjusted book = 1,000 + 67 - 30 - 5 =
# 1,032.00. Off by 773.00.

_WHOLE = rec.Inputs(
    period_end=END,
    book_balance=D("1000"),
    balance_per_bank=D("1500"),
    statement_lines=(
        rec.StatementLine("s1", date(2026, 8, 5), "Deposit", None, D("200.00")),
        rec.StatementLine("s2", END, "CHECK 0042", D("30.00"), None),
        rec.StatementLine("s3", date(2026, 8, 20), "Interest", None, D("55.00")),
    ),
    register_lines=(
        rec.RegisterLine("r1", date(2026, 8, 5), D("200.00")),
        rec.RegisterLine("r2", date(2026, 8, 30), D("400.00")),
        rec.RegisterLine("r3", date(2026, 6, 2), D("-75.00"), "0099"),
        rec.RegisterLine("r4", date(2026, 9, 2), D("10.00")),  # after the period: not in it
    ),
    prior_items=(
        rec.PriorItem("pb1", "bank", "outstanding_check", date(2026, 5, 1), D("20.00"), "#77"),
        rec.PriorItem("pk1", "book", "book_error", date(2026, 8, 1), D("5.00")),
        rec.PriorItem("pk2", "book", "unrecorded_deposit", date(2026, 7, 31), D("12.00")),
    ),
)


def _row(i: rec.Item) -> tuple[object, ...]:
    return (
        i.side,
        i.kind,
        i.txn_date,
        i.amount,
        i.days_at_period_end,
        i.stale,
        i.aging,
        i.ref,
        i.statement_line_id,
        i.register_line_ref,
        i.carried_from,
    )


def test_one_period_whole() -> None:
    r = rec.reconcile(_WHOLE)
    assert [_row(i) for i in r.items] == [
        (
            "bank",
            "deposit_in_transit",
            date(2026, 8, 30),
            D("400.00"),
            1,
            False,
            "0-30",
            None,
            None,
            "r2",
            None,
        ),
        (
            "bank",
            "outstanding_check",
            date(2026, 5, 1),
            D("20.00"),
            122,
            True,
            "over_90",
            "#77",
            None,
            None,
            "pb1",
        ),
        (
            "bank",
            "outstanding_check",
            date(2026, 6, 2),
            D("75.00"),
            90,
            False,
            "61-90",
            "#99",
            None,
            "r3",
            None,
        ),
        (
            "book",
            "book_error",
            date(2026, 8, 1),
            D("5.00"),
            30,
            False,
            "0-30",
            None,
            None,
            None,
            "pk1",
        ),
        (
            "book",
            "unrecorded_deposit",
            date(2026, 7, 31),
            D("12.00"),
            31,
            False,
            "31-60",
            None,
            None,
            None,
            "pk2",
        ),
        (
            "book",
            "unrecorded_deposit",
            date(2026, 8, 20),
            D("55.00"),
            11,
            False,
            "0-30",
            None,
            "s3",
            None,
            None,
        ),
        (
            "book",
            "unrecorded_withdrawal",
            END,
            D("30.00"),
            0,
            False,
            "0-30",
            "#42",
            "s2",
            None,
            None,
        ),
    ]
    assert (r.deposits_in_transit, r.outstanding_checks) == (D("400.00"), D("95.00"))
    assert (r.unrecorded_deposits, r.unrecorded_withdrawals) == (D("67.00"), D("30.00"))
    assert (r.balance_per_bank, r.adjusted_bank) == (D("1500.00"), D("1805.00"))
    assert (r.book_balance, r.adjusted_book) == (D("1000.00"), D("1032.00"))
    assert (r.difference, r.tally) == (D("773.00"), "off")
    assert r.matches == (rec.Pairing("s1", "r1", "amount_date"),)
    assert (r.cleared_prior, r.needs_review) == ((), ())
    assert r.aging == {
        "0-30": D("490.00"),
        "31-60": D("12.00"),
        "61-90": D("75.00"),
        "over_90": D("20.00"),
    }
    assert (r.period_end, r.stale_count) == (END, 1)
    assert r.content_hash == "f4527e642cc3382817ed7d3565e291cd265f86a5d7c0ae9b82a04ff1cc90a57c"


def test_the_same_period_before_its_statement() -> None:
    r = rec.reconcile(replace(_WHOLE, balance_per_bank=None))
    assert (r.tally, r.balance_per_bank, r.adjusted_bank, r.difference) == (
        "pending",
        None,
        None,
        None,
    )
    # The register's bank-side items wait for the statement; a carried one stays.
    assert [(i.side, i.kind, i.carried_from) for i in r.items if i.side == "bank"] == [
        ("bank", "outstanding_check", "pb1")
    ]
    assert r.adjusted_book == D("1032.00")

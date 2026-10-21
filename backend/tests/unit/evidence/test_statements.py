"""SPEC-312 phase 2-3 (TASK-324): statement lines read from PDF text, CSV and OFX in one sign
convention, reconciled by code; the reviewer's decisions applied without trusting the client."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from abacus.modules.evidence.extraction import PDF, extract
from abacus.modules.evidence.statement_review import (
    BalancePrinted,
    Decisions,
    ReviewInvalid,
    apply,
    read_statement,
)
from abacus.modules.evidence.statements import amount_of, date_of, from_pages, from_text_file
from abacus_tools.synthetic.documents import card_statement_pdf

D = Decimal
NONE = Decisions({}, False, None, None)


@pytest.mark.parametrize("pages", [1, 2])
def test_ac1_a_card_statement_reads_and_reconciles(pages: int) -> None:
    parsed = from_pages(extract(card_statement_pdf(pages=pages), PDF).pages)
    assert (parsed.account_kind, parsed.last4) == ("credit_card", "4471")
    assert (parsed.period_start, parsed.period_end) == (date(2026, 11, 22), date(2026, 12, 21))
    assert (parsed.opening, parsed.closing) == (D("1250.00"), D("1209.58"))
    amounts = sorted(line.amount for line in parsed.lines)
    assert amounts == [D("-1250.00"), D("-24.99"), D("184.37"), D("438.20"), D("612.00")]
    view = apply(parsed, NONE)
    assert view.reconciliation.reconciled and view.reconciliation.difference == D("0.00")


def test_ac1_a_statement_that_does_not_add_up_shows_the_difference() -> None:
    parsed = from_pages(extract(card_statement_pdf(new_balance=D("1300.00")), PDF).pages)
    rec = apply(parsed, NONE).reconciliation
    assert not rec.reconciled and rec.difference == D("90.42")


def test_ac1_dates_and_amounts_as_printed() -> None:
    assert date_of("12/09", date(2026, 12, 21)) == date(2026, 12, 9)
    assert date_of("12/28", date(2027, 1, 21)) == date(2026, 12, 28)  # December on January's
    assert date_of("Dec 9", date(2026, 12, 21)) == date(2026, 12, 9)
    assert date_of("02/30", date(2026, 3, 1)) is None
    assert amount_of("($1,250.00)") == D("-1250.00")
    assert amount_of("-24.99") == D("-24.99")


def test_ac2_csv_exports_with_one_or_two_amount_columns() -> None:
    chase = (
        b"Transaction Date,Post Date,Description,Category,Type,Amount\n"
        b"12/02/2026,12/03/2026,CLOUD HOSTING INC,Services,Sale,-612.00\n"
        b"11/28/2026,11/29/2026,OFFICE SUPPLY,Shopping,Sale,-184.37\n"
        b"11/24/2026,11/24/2026,PAYMENT THANK YOU,,Payment,1250.00\n"
    )
    parsed = from_text_file(chase)
    assert parsed is not None and parsed.signs_inferred
    assert [line.amount for line in parsed.lines] == [D("612.00"), D("184.37"), D("-1250.00")]
    split = (
        b"Date,Description,Debit,Credit\n2026-12-02,HOSTING,612.00,\n2026-11-24,PAYMENT,,1250.00\n"
    )
    two = from_text_file(split)
    assert two is not None and not two.signs_inferred
    assert [line.amount for line in two.lines] == [D("612.00"), D("-1250.00")]


def test_ac2_ofx_card_amounts_become_effects_on_the_balance_owed() -> None:
    ofx = (
        b"OFXHEADER:100\n<OFX><CREDITCARDMSGSRSV1><CCSTMTTRNRS><CCSTMTRS><CCACCTFROM>"
        b"<ACCTID>4111111111114471</CCACCTFROM><BANKTRANLIST><DTSTART>20261122<DTEND>20261221"
        b"<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261202<TRNAMT>-612.00<NAME>CLOUD HOSTING</STMTTRN>"
        b"<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261124<TRNAMT>100.00<NAME>PAYMENT</STMTTRN>"
        b"</BANKTRANLIST><LEDGERBAL><BALAMT>-512.00</LEDGERBAL></CCSTMTRS></CCSTMTTRNRS>"
        b"</CREDITCARDMSGSRSV1></OFX>"
    )
    parsed = from_text_file(ofx)
    assert parsed is not None and parsed.account_kind == "credit_card" and parsed.last4 == "4471"
    assert [line.amount for line in parsed.lines] == [D("612.00"), D("-100.00")]
    assert (parsed.opening, parsed.closing) == (None, D("512.00"))
    view = apply(parsed, Decisions({}, False, D("0.00"), None))  # the person enters the opening
    assert view.reconciliation.reconciled and view.opening_source == "entered"


def test_ac3_decisions_exclude_with_reasons_and_never_replace_a_printed_balance() -> None:
    parsed = from_pages(extract(card_statement_pdf(new_balance=D("1234.57")), PDF).pages)
    return_line = next(line for line in parsed.lines if "RETURN" in line.description)
    view = apply(parsed, Decisions({return_line.position: "Counted twice"}, False, None, None))
    assert view.reconciliation.reconciled  # without the -24.99 return
    with pytest.raises(ReviewInvalid):
        apply(parsed, Decisions({return_line.position: "  "}, False, None, None))
    with pytest.raises(BalancePrinted):
        apply(parsed, Decisions({}, False, D("1.00"), None))
    with pytest.raises(ReviewInvalid):
        apply(parsed, Decisions({}, True, None, None))  # signs were printed, not inferred


def test_read_statement_takes_pdf_and_text_files_only() -> None:
    assert read_statement(card_statement_pdf(), PDF) is not None
    assert read_statement(b"\x89PNG", "image/png") is None


def test_task334_lines_and_summary_values_keep_where_they_were_printed() -> None:
    parsed = read_statement(card_statement_pdf(pages=2), PDF)
    assert parsed is not None and parsed.sources is not None
    assert set(parsed.sources) == {"opening", "closing", "period", "last4"}
    opening = parsed.sources["opening"]
    assert opening.page == 1 and 0 < opening.box[0] < opening.box[2] <= 1
    assert all(line.box is not None and line.page in (1, 2) for line in parsed.lines)
    # A second-page line points at page 2, below the page's top edge.
    second = next(line for line in parsed.lines if line.page == 2)
    assert second.box is not None and second.box[1] > 0
    view = apply(parsed, NONE)
    assert view.sources == parsed.sources
    assert all(line.box is not None for line in view.lines)

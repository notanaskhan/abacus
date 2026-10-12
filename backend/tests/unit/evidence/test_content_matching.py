"""SPEC-033 AC-1, AC-2 (TASK-064): suggestions from what's in an inbox file, by code."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from abacus.modules.evidence.matching import (
    ContentFacts,
    EngagementFacts,
    Reason,
    facts_of,
    suggest,
)
from abacus.modules.evidence.models import UploadExtraction
from abacus.modules.requests.api import RequestItemView

YEAR_END = date(2026, 12, 31)
E = uuid4()


def _item(description: str, kind: str | None, area: str = "Cash") -> RequestItemView:
    return RequestItemView(
        uuid4(), E, description, area, "open", datetime.now(UTC), document_kind=kind
    )


STATEMENT = ContentFacts(
    "bank_statement", date(2026, 12, 1), YEAR_END, last4="4471", holder="Northwind Ltd."
)


def _context(needed: dict[UUID, frozenset[str]] | None = None) -> EngagementFacts:
    return EngagementFacts(YEAR_END, "Northwind Ltd", needed or {})


def test_ac1_a_meaningless_name_still_finds_the_statement_request() -> None:
    bank = _item("Bank statements for December", "bank_statement")
    aging = _item("AR aging at year end", "ar_aging", "Receivables")
    (top,) = suggest("scan0042.pdf", [bank, aging], STATEMENT, _context())
    assert top.request_item_id == bank.id
    assert top.source == "content"
    assert [r.code for r in top.reasons] == ["kind", "date", "holder"]
    assert Reason("date", "2026-12-31") in top.reasons


def test_ac2_the_needed_account_decides_between_two_statement_requests() -> None:
    operating = _item("Bank statement - operating account", "bank_statement")
    payroll = _item("Bank statement - payroll account", "bank_statement")
    found = suggest(
        "statement (1).pdf",
        [operating, payroll],
        STATEMENT,
        _context({operating.id: frozenset({"2290"}), payroll.id: frozenset({"4471"})}),
    )
    assert found[0].request_item_id == payroll.id
    assert Reason("account", "4471") in found[0].reasons


def test_ac1_digits_in_the_description_count_too() -> None:
    ending = _item("Statement for account ending 4471", "bank_statement")
    other = _item("Statement for account ending 2290", "bank_statement")
    found = suggest("x.pdf", [other, ending], STATEMENT, _context())
    assert found[0].request_item_id == ending.id


def test_ac1_a_misleading_name_loses_to_the_contents() -> None:
    bank = _item("Bank statements for December", "bank_statement")
    aging = _item("AR aging at year end", "ar_aging", "Receivables")
    facts = ContentFacts("aging", as_of=YEAR_END)
    found = suggest("bank statement december.pdf", [bank, aging], facts, _context())
    assert found[0].request_item_id == aging.id


def test_ac1_without_facts_the_file_name_decides_as_before() -> None:
    bank = _item("Bank statements for December", "bank_statement")
    (only,) = suggest("bank statements december.pdf", [bank])
    assert only.source == "file_name"
    assert only.reasons == (Reason("file_name", "bank, december, statement"),)
    assert suggest("scan0042.pdf", [bank]) == []


def test_ac1_facts_come_from_the_extraction_columns() -> None:
    def row(**over: object) -> UploadExtraction:
        values: dict[str, object] = {"status": "extracted", "period_start": None}
        values |= {"period_end": None, "as_of": None, "account_last4": None}
        values |= {"entity_name": None, "closing": None, "grand_total": None}
        return UploadExtraction(**(values | over))

    statement = facts_of(row(period_end=YEAR_END, closing=Decimal("1.00"), account_last4="4471"))
    assert statement is not None and statement.kind == "bank_statement"
    aging = facts_of(row(as_of=YEAR_END, grand_total=Decimal("10")))
    assert aging is not None and aging.kind == "aging"
    assert facts_of(row(status="unreadable")) is None
    assert facts_of(None) is None

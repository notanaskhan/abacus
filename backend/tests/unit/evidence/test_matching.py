"""SPEC-023 AC-3 (TASK-039): suggestions from the file name only, best first, at most three."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from abacus.modules.evidence.matching import suggest, words
from abacus.modules.requests.api import RequestItemView

E = uuid.uuid4()


def _item(description: str, area: str = "Area", status: str = "open") -> RequestItemView:
    return RequestItemView(
        uuid.uuid4(), E, description, area, status, datetime(2026, 10, 1, tzinfo=UTC)
    )


def test_ac3_file_name_words_drop_noise() -> None:
    assert words("BankStatements_Dec-2026 (final) v2.pdf") == {"bank", "statements", "dec"}
    assert words("scan0001.pdf") == {"scan0001"}


def test_ac3_suggestions_rank_by_matched_words_with_their_score() -> None:
    bank = _item("Bank statements for December")
    payroll = _item("Payroll summary")
    found = suggest("Bank_Statements_Dec.pdf", [payroll, bank])
    assert [s.request_item_id for s in found] == [bank.id]
    assert found[0].matched == ("bank", "statement")
    assert found[0].score == 67  # two of "bank", "statement", "december" ("for" is a stop word)


def test_ac3_a_shared_rule_lifts_an_abbreviation() -> None:
    tb = _item("Trial balance at year end")
    found = suggest("TB FY26.xlsx", [tb])
    assert [s.request_item_id for s in found] == [tb.id]
    assert found[0].score >= 40


def test_ac3_closed_items_and_weak_matches_are_never_suggested() -> None:
    closed = _item("Bank statements", status="accepted")
    weak = _item("Bank reconciliation working papers and supporting schedules")
    assert suggest("bank.pdf", [closed, weak]) == []


def test_ac3_at_most_three_suggestions() -> None:
    items = [_item(f"Invoice batch {n}") for n in range(5)]
    assert len(suggest("invoice batch.pdf", items)) == 3

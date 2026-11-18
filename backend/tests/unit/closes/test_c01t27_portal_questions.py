"""C-01-T27 (SPEC-656; DEC-5633): what POR-11 shows a client about a transaction question, from
code facts only; the answer text from the sheet's choice and the client's note."""

from __future__ import annotations

from abacus.modules.closes import portal_questions as pq


def test_context_line_uses_code_facts_only() -> None:
    line = pq.context_line(
        {
            "account_label": "Front Range Bank ••4410",
            "register_line_label": "check #2285",
            "issue_class": "unmatched",
        }
    )
    assert line == "Front Range Bank ••4410 · check #2285"
    assert pq.context_line({"issue_class": "unmatched"}) == ""


def test_answer_text_from_choice_and_note() -> None:
    assert pq.answer_text("lost_reissue", None) == "Lost — please reissue it"
    assert pq.answer_text("something_else", " Paid by card ") == "Something else — Paid by card"
    assert pq.answer_text(None, "See invoice") == "See invoice"

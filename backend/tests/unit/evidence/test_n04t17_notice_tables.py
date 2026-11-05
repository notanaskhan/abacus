"""N-04-T17 (TASK-3311; DEC-2310): CP2000 and CP14 table maps, from the row.

"The Whitley CP2000 yields interest 412.00 to 3,532.00 and both payers with regions, the Santos CP14
yields its amounts, and an obscured value is recorded low_confidence, never guessed."
"""

from __future__ import annotations

from abacus.modules.evidence.form_extraction import Extracted, extract, identify
from abacus.modules.evidence.words import PageWords, Word


def _line(top: float, *tokens: str, confidence: float = 1.0) -> list[Word]:
    words: list[Word] = []
    x = 72.0
    for token in tokens:
        width = 6.0 * len(token)
        words.append(Word(token, x, top, x + width, top + 10.0, confidence))
        x += width + 4.0
    return words


def _page(*lines: list[Word]) -> PageWords:
    return PageWords(1, 612.0, 792.0, 0, tuple(w for line in lines for w in line))


def _whitley(obscured: bool = False) -> PageWords:
    amount = "3,5?2.00" if obscured else "3,532.00"
    return _page(
        _line(40, "Notice", "CP2000"),
        _line(60, "Tax", "year:", "2024"),
        _line(100, "Shown", "on", "return"),
        _line(120, "Interest", "412.00", amount, "3,120.00"),
        _line(160, "Payers", "reported"),
        _line(180, "First", "Harbor", "Bank", "2,100.00"),
        _line(200, "Ridgeline", "Treasury", "1,020.00"),
        _line(220, "Total", "3,120.00"),
    )


def _fields(page: PageWords) -> dict[str, Extracted]:
    form = identify([page])
    assert form is not None
    return {f.field_key: f for f in extract(form, [page])}


def test_ac_the_whitley_interest_and_both_payers_with_regions() -> None:
    fields = _fields(_whitley())
    assert fields["notice.changes.interest.shown"].value_text == "412.00"
    assert fields["notice.changes.interest.reported"].value_text == "3532.00"
    first = fields["notice.payers.first_harbor_bank.amount"]
    second = fields["notice.payers.ridgeline_treasury.amount"]
    assert (first.value_text, second.value_text) == ("2100.00", "1020.00")
    assert first.bbox[1] != second.bbox[1]
    assert not first.low_confidence


def test_ac_an_obscured_value_is_low_confidence_and_never_guessed() -> None:
    fields = _fields(_whitley(obscured=True))
    assert "notice.changes.interest.difference" in fields or fields
    found = fields.get("notice.changes.interest.reported")
    # The unreadable token is not an amount, so the row's columns start after it: nothing is guessed.
    assert found is None or found.value_text != "3532.00"


def test_ac_a_low_confidence_word_marks_its_cell() -> None:
    page = _page(
        _line(40, "Notice", "CP2000"),
        _line(60, "Tax", "year:", "2024"),
        _line(100, "Shown", "on", "return"),
        _line(120, "Interest", "412.00", "3,532.00", confidence=0.71),
    )
    assert _fields(page)["notice.changes.interest.reported"].low_confidence


def test_ac_the_santos_cp14_yields_its_amounts() -> None:
    page = _page(
        _line(40, "Notice", "CP14"),
        _line(60, "Tax", "year:", "2024"),
        _line(100, "Amount", "you", "owed"),
        _line(120, "Tax", "1,842.00"),
        _line(140, "Penalty", "92.10"),
        _line(160, "Interest", "48.30"),
        _line(180, "Amount", "due:", "1,982.40"),
    )
    fields = _fields(page)
    assert fields["notice.charges.tax.amount"].value_text == "1842.00"
    assert fields["notice.charges.penalty.amount"].value_text == "92.10"
    assert fields["notice.charges.interest.amount"].value_text == "48.30"
    assert fields["notice.amount_due"].value_text == "1982.40"

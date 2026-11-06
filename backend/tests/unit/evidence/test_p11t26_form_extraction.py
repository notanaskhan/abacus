"""P-11-T26 (TASK-3309; DEC-2308): form identification and box maps, from the row and AC8.

"The Whitley CP2000 yields CP2000, TY2024, 753.01 and respond by Sep 23, 2026, the Santos CP14
photo
fixture yields its eight header fields, and an obscured date is recorded low_confidence, never
guessed." Whitley's and Santos's own golden faces land with P-11-T28's corpus.
"""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.evidence.form_extraction import (
    Extracted,
    covers,
    extract,
    identify,
    load_maps,
)
from abacus.modules.evidence.words import PageWords, Word


def _line(top: float, *tokens: str, x: float = 72.0, confidence: float = 1.0) -> list[Word]:
    words: list[Word] = []
    for token in tokens:
        width = 6.0 * len(token)
        words.append(Word(token, x, top, x + width, top + 10.0, confidence))
        x += width + 4.0
    return words


def _page(*lines: list[Word]) -> PageWords:
    return PageWords(1, 612.0, 792.0, 0, tuple(w for line in lines for w in line))


def _whitley(
    date_confidence: float = 1.0, date: tuple[str, ...] = ("September", "23,", "2026")
) -> PageWords:
    return _page(
        _line(40, "Notice", "CP2000"),
        _line(60, "Notice", "number:", "CP2000"),
        _line(80, "Tax", "year:", "2024"),
        _line(100, "Notice", "date:", "August", "24,", "2026"),
        _line(120, "Respond", "by:", *date, confidence=date_confidence),
        _line(140, "Amount", "due:", "$753.01"),
        _line(160, "Social", "Security", "number:", "6081"),
        _line(180, "Increase", "in", "tax:", "$686.40"),
        _line(200, "Interest:", "$66.61"),
    )


def _by_key(page: PageWords) -> dict[str, Extracted]:
    form = identify([page])
    assert form is not None
    return {f.field_key: f for f in extract(form, [page])}


def test_ac_the_whitley_cp2000_header() -> None:
    form = identify([_whitley()])
    assert form is not None
    assert (form.form_type, form.tax_year) == ("cp2000", 2024)
    fields = _by_key(_whitley())
    assert fields["notice.amount_due"].value_text == "753.01"
    assert fields["notice.respond_by"].value_text == "2026-09-23"
    assert fields["notice.proposed_tax"].value_text == "686.40"
    assert fields["notice.amount_due"].confidence == Decimal("1.000")
    assert not fields["notice.amount_due"].low_confidence


def test_ac_an_obscured_date_is_low_confidence_and_never_guessed() -> None:
    fields = _by_key(_whitley(date=("Sept", "2?,", "2026")))
    respond = fields["notice.respond_by"]
    assert respond.value_text == "Sept 2?, 2026"
    assert respond.low_confidence


def test_ac_confidence_is_the_minimum_of_its_words() -> None:
    fields = _by_key(_whitley(date_confidence=0.72))
    respond = fields["notice.respond_by"]
    assert respond.confidence == Decimal("0.720")
    assert respond.low_confidence
    assert respond.value_text == "2026-09-23"


def test_ac_another_years_map_is_never_used() -> None:
    page = _page(_line(40, "Notice", "CP2000"), _line(80, "Tax", "year:", "2019"))
    assert identify([page]) is None


def test_ac_an_unknown_form_writes_nothing() -> None:
    assert (
        identify([_page(_line(40, "Invoice", "4471"), _line(80, "Tax", "year:", "2024"))]) is None
    )


def test_ac_the_five_notice_headers_are_mapped() -> None:
    assert {m.form_type for m in load_maps()} >= {"cp2000", "cp14", "cp501", "cp503", "cp504"}
    cp14 = next(m for m in load_maps() if m.form_type == "cp14")
    assert len(cp14.fields) == 8


def test_ac_a_flag_family_covers_only_its_forms() -> None:
    assert covers("notices", "notices")
    assert not covers("off", "notices")
    assert not covers("notices", "tax_forms")
    assert covers("all", "tax_forms")


def test_ac_a_text_layer_word_keeps_its_object_byte_for_byte() -> None:
    from abacus.modules.evidence.words import layer_document, parse_layer

    page = _whitley()
    raw = layer_document(page)
    assert b"confidence" not in raw
    assert parse_layer(raw).words == page.words
    ocr = _whitley(date_confidence=0.72)
    assert parse_layer(layer_document(ocr)).words == ocr.words

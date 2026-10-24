"""P-03-T13 (SPEC-322 AC4.1; P-03 §4.4): PII detection by code over the word layer.

The seeded corpus (W-2 box a 000-00-6081, a K-1 EIN, a 1099 recipient TIN, a direct-deposit
form) is found at recall 1.0; label-anchored values are masked even when they fail validity;
unlabelled ones only when they pass it."""

from __future__ import annotations

import pytest

from abacus.modules.evidence.pii import detect, lines_of
from abacus.modules.evidence.words import Word, extract_words
from abacus_tools.synthetic.documents import PiiDocument, pii_corpus

CORPUS = pii_corpus()


@pytest.mark.parametrize("doc", CORPUS, ids=[d.name for d in CORPUS])
def test_ac4_1_the_seeded_corpus_is_found_at_recall_one(doc: PiiDocument) -> None:
    layer = extract_words(doc.content, "application/pdf")
    found = [f for page in layer.pages for f in detect(page.page, page.words)]
    assert sorted((f.page, f.kind, f.last4) for f in found) == sorted(doc.expected)
    assert all(f.label_anchored for f in found)


def test_ac4_1_the_w2_box_a_ssn_is_found_where_it_is_printed() -> None:
    layer = extract_words(CORPUS[0].content, "application/pdf")
    [ssn] = [f for f in detect(1, layer.pages[0].words) if f.kind == "ssn"]
    word = next(w for w in layer.pages[0].words if w.text == "000-00-6081")
    assert ssn.box == (
        round(word.x0, 2),
        round(word.top, 2),
        round(word.x1, 2),
        round(word.bottom, 2),
    )
    assert (ssn.value, ssn.last4) == ("000006081", "6081")


def _line(*texts: str, top: float = 100.0) -> list[Word]:
    words: list[Word] = []
    x = 36.0
    for text in texts:
        words.append(Word(text, x, top, x + 6 * len(text), top + 10))
        x += 6 * len(text) + 4
    return words


def test_an_unlabelled_number_counts_only_when_it_passes_its_rules() -> None:
    found = detect(1, _line("Ref", "912-70-1234", "and", "000-00-1111", "and", "00-1234567"))
    # A valid ITIN is masked unlabelled; an SSN-shaped 000 area and an EIN with the
    # unassigned 00 prefix are not, without a label.
    assert [(f.kind, f.last4, f.label_anchored) for f in found] == [("itin", "1234", False)]


def test_nine_bare_digits_are_a_routing_number_only_with_the_aba_checksum() -> None:
    assert [f.kind for f in detect(1, _line("Wire", "000000000"))] == ["routing_number"]
    assert detect(1, _line("Wire", "000000001")) == []
    labelled = detect(1, [*_line("Routing", "number", top=80.0), *_line("000000001")])
    assert [(f.kind, f.label_anchored) for f in labelled] == [("routing_number", True)]


def test_a_label_left_of_the_value_on_its_line_anchors_it() -> None:
    found = detect(1, _line("SSN:", "000-00-6081"))
    assert [(f.kind, f.label_anchored) for f in found] == [("ssn", True)]
    ein = detect(1, _line("EIN", "00-1230287"))
    assert [(f.kind, f.last4) for f in ein] == [("ein", "0287")]


def test_a_tin_written_as_three_runs_is_one_region() -> None:
    [found] = detect(1, _line("Social", "security", "number", "000", "00", "6081"))
    assert (found.kind, found.last4) == ("ssn", "6081")
    assert found.box[0] < found.box[2]


def test_a_date_counts_only_beside_a_birth_date_label() -> None:
    assert detect(1, _line("Statement", "date", "01/31/2026")) == []
    [dob] = detect(1, _line("Date", "of", "birth", "01/01/1980"))
    assert (dob.kind, dob.last4) == ("dob", None)


def test_amounts_and_invoice_numbers_are_never_pii() -> None:
    assert (
        detect(1, _line("Total", "4,210.55", "Invoice", "12345", "Balance", "16,500,000.00")) == []
    )


def test_lines_group_words_by_their_vertical_centre() -> None:
    words = [*_line("a", "b", top=100.0), *_line("c", top=130.0)]
    assert [[w.text for w in line.words] for line in lines_of(words)] == [["a", "b"], ["c"]]

"""P-03-T05 (SPEC-322 AC-1, AC-3; ADR-166, ADR-110; DEC-217): the word layer. Every text page of
a PDF gets its words with boxes in page points, top-left origin, in the rendered page's space; a
scan gets an empty page, never a guess; hostile or locked files are `unreadable`, in the child."""

from __future__ import annotations

import pytest

from abacus.modules.evidence import words
from abacus.modules.evidence.words import (
    PDF,
    extract_words,
    extract_words_isolated,
    layer_document,
    parse_layer,
)
from abacus_tools.synthetic.documents import encrypted_pdf, positioned_pdf, scanned_pdf

LINE = [(72.0, 700.0, "Total investments 16,500,000.00")]


def _rotated(content: bytes, turn: int) -> bytes:
    return content.replace(
        b"/MediaBox [0 0 612 792]", b"/MediaBox [0 0 612 792] /Rotate %d" % turn
    )


def test_p03t05_ac1_every_word_has_a_box_in_page_points_from_the_top_left() -> None:
    layer = extract_words(positioned_pdf([LINE]), PDF)
    assert layer.status == "extracted"
    [page] = layer.pages
    assert (page.page, page.width, page.height, page.rotation) == (1, 612.0, 792.0, 0)
    assert [w.text for w in page.words] == ["Total", "investments", "16,500,000.00"]
    first = page.words[0]
    assert first.x0 == pytest.approx(72.0, abs=0.01)
    # Baseline 700 from the bottom of a 792 pt page: the word sits about 84 pt from the top.
    assert 80 < first.top < first.bottom < 100
    assert all(w.x0 < w.x1 for w in page.words)


def test_p03t05_dec217_a_rotated_page_shares_the_rendered_images_space() -> None:
    layer = extract_words(_rotated(positioned_pdf([LINE]), 90), PDF)
    [page] = layer.pages
    assert (page.width, page.height, page.rotation) == (792.0, 612.0, 90)
    assert all(0 <= w.x0 <= w.x1 <= page.width for w in page.words)
    assert all(0 <= w.top <= w.bottom <= page.height for w in page.words)


def test_p03t05_a_scanned_page_has_geometry_and_no_words() -> None:
    layer = extract_words(scanned_pdf(pages=2), PDF)
    assert layer.status == "extracted"
    assert [(p.page, p.words) for p in layer.pages] == [(1, ()), (2, ())]


def test_p03t05_every_page_of_a_multi_page_file() -> None:
    layer = extract_words(positioned_pdf([LINE, [(72.0, 500.0, "Page two")]]), PDF)
    assert [[w.text for w in p.words] for p in layer.pages] == [
        ["Total", "investments", "16,500,000.00"],
        ["Page", "two"],
    ]


def test_p03t05_a_password_protected_file_is_unreadable() -> None:
    assert (
        extract_words(encrypted_pdf(), PDF).status,
        extract_words(encrypted_pdf(), PDF).reason,
    ) == (
        "unreadable",
        "encrypted",
    )


def test_p03t05_a_damaged_file_is_unreadable() -> None:
    assert extract_words(b"%PDF-1.4 not really", PDF).status == "unreadable"


def test_p03t05_only_pdfs_have_a_word_layer() -> None:
    assert extract_words(b"a,b\n1,2\n", "text/csv").status == "not_applicable"


def test_p03t05_control_and_format_characters_are_dropped() -> None:
    clean = words._clean  # pyright: ignore[reportPrivateUsage] -- the sanitiser itself
    assert clean("Tot\x07al\u200b") == "Total"
    assert clean("\u202e" + "x" * 500) == "x" * words.MAX_WORD


def test_p03t05_pages_past_the_cap_are_left_out_and_say_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(words, "MAX_PAGES", 1)
    layer = extract_words(positioned_pdf([LINE, LINE]), PDF)
    assert (len(layer.pages), layer.truncated) == (1, True)


def test_p03t05_words_past_the_page_cap_are_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(words, "MAX_PAGE_WORDS", 2)
    assert len(extract_words(positioned_pdf([LINE]), PDF).pages[0].words) == 2


def test_p03t05_the_layer_object_round_trips_and_is_stable() -> None:
    [page] = extract_words(positioned_pdf([LINE]), PDF).pages
    document = layer_document(page)
    assert parse_layer(document) == page
    assert layer_document(parse_layer(document)) == document


def test_p03t05_adr110_words_are_read_in_the_isolated_child() -> None:
    layer = extract_words_isolated(positioned_pdf([LINE]), PDF)
    assert [w.text for w in layer.pages[0].words][-1] == "16,500,000.00"


def test_p03t05_adr110_a_child_that_fails_is_crashed_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_args: object) -> object:
        raise words.IsolationFailed

    monkeypatch.setattr(words, "run_isolated", boom)
    assert (extract_words_isolated(b"", PDF).status, extract_words_isolated(b"", PDF).reason) == (
        "unreadable",
        "crashed",
    )

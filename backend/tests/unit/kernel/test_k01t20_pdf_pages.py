"""K-01-T20: PDF words with boxes and page images in the isolated child (kernel.pdf_pages).

Row acceptance (first half): "A 96-page synthetic PDF yields words and boxes for every page inside
the isolated child." Plus the problem codes (encrypted, damaged, too many pages) and a page image.
"""

from __future__ import annotations

import pytest

from abacus.kernel import pdf_pages
from abacus_tools.synthetic.documents import encrypted_pdf, positioned_pdf

PAGES = 96


def _manual(pages: int = PAGES) -> bytes:
    return positioned_pdf(
        [
            [
                (72, 720, f"BH-EBP-110 step {n}"),
                (72, 700, f"Perform procedure {n} on page {n}"),
            ]
            for n in range(1, pages + 1)
        ]
    )


def test_ac_96_pages_yield_words_and_boxes_for_every_page_in_the_child() -> None:
    found = pdf_pages.read_words_isolated(_manual())
    assert found.problem is None
    assert found.page_count == PAGES
    assert [p.page for p in found.pages] == list(range(1, PAGES + 1))
    for page in found.pages:
        assert f"page {page.page}" in page.text
        assert page.words, page.page
        for word in page.words:
            x0, top, x1, bottom = word.box
            assert 0.0 <= x0 < x1 <= 1.0
            assert 0.0 <= top < bottom <= 1.0


def test_a_box_is_a_fraction_of_the_page() -> None:
    [page] = pdf_pages.read_words(positioned_pdf([[(306, 396, "Middle")]])).pages
    [word] = page.words
    assert word.text == "Middle"
    assert word.box[0] == pytest.approx(0.5, abs=0.01)
    assert 0.48 < word.box[1] < 0.5


def test_an_encrypted_file_is_a_problem_code_not_a_raise() -> None:
    assert pdf_pages.read_words_isolated(encrypted_pdf()).problem == "encrypted"


@pytest.mark.parametrize("content", [b"not a pdf", b"%PDF-1.4\n1 0 obj <<", b""])
def test_a_malformed_file_is_damaged(content: bytes) -> None:
    assert pdf_pages.read_words_isolated(content).problem == "damaged"
    assert pdf_pages.render_page_isolated(content, 1).problem == "damaged"


def test_more_pages_than_the_cap_reads_nothing() -> None:
    found = pdf_pages.read_words(_manual(3), max_pages=2)
    assert (found.problem, found.page_count, found.pages) == ("too_many_pages", 3, ())


def test_a_page_image_and_the_page_range() -> None:
    content = _manual(3)
    page = pdf_pages.render_page_isolated(content, 2, width_px=600)
    assert page.problem is None
    assert (page.page, page.page_count, page.width) == (2, 3, 600)
    assert page.png.startswith(b"\x89PNG")
    assert pdf_pages.render_page_isolated(content, 4).problem == "page_out_of_range"


def test_words_drop_control_and_format_characters() -> None:
    assert pdf_pages.clean("step​ 4\u0007") == "step 4"

"""P-11-T07 (TASK-2304; SPEC-520 AC-6 to AC-12; P-11 §4.4): the renderer core end to end, through
WeasyPrint.

Image-bound like `test_ac30_render_golden.py`: `make golden-render` runs this file inside the
backend image (no network) after the two-container check. Each test renders DocBlocks through
`render.core.render`, the function the isolated child runs.
"""

from __future__ import annotations

import io
from dataclasses import replace
from datetime import UTC, datetime
from typing import Final

import pdfplumber
import pytest

from abacus.modules.reporting.render.core import RenderInput, render
from abacus.modules.reporting.render.fetcher import AssetFetcher, AssetNotAllowed
from abacus.modules.reporting.render.head import RenderRefused
from abacus_tools.synthetic.scenarios.brightwater_hale import render_letter as letter

AS_OF = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)


def _letter(mode: str = "draft", **values: str) -> RenderInput:
    """The golden letter's wording as DocBlocks, one variable per section."""
    blocks: list[object] = [{"type": "heading", "level": 1, "text": letter.TITLE}]
    for i, (heading, paragraphs) in enumerate(letter.SECTIONS):
        if i > 0:
            blocks.append({"type": "page_break"})
        blocks.append({"type": "heading", "level": 2, "text": heading})
        blocks.extend(
            {"type": "paragraph", "runs": [{"type": "text", "text": p}]} for p in paragraphs
        )
    blocks.append(
        {
            "type": "paragraph",
            "runs": [{"type": "text", "text": "Client: "}, {"type": "var", "key": "client.name"}],
        }
    )
    return RenderInput(
        layout_key="letter",
        blocks=blocks,
        values={"client.name": "Copperleaf Coffee Roasters, Inc.", **values},
        title=letter.TITLE,
        as_of=AS_OF,
        mode=mode,  # type: ignore[arg-type]  # the three modes, from the tests' parameters
        content_hash="d" * 64,
    )


def _texts(pdf: bytes) -> list[str]:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        return [page.extract_text() or "" for page in document.pages]


def test_ac6_the_same_input_renders_the_same_bytes() -> None:
    first, second = render(_letter()), render(_letter())
    assert first.pdf == second.pdf and first.render_hash == second.render_hash
    assert first.page_count == 3


MARK_SIZE: Final = 36.0  # points; the watermark is ~64 pt, body text and headings far smaller


def _marks(pdf: bytes) -> list[str]:
    """Each page's diagonal mark: its display-size characters (the mark is set far above any
    heading), left to right. Text extraction splits the diagonal word across lines (its order
    depends on the fonts installed), so the mark is read from the characters, not the text."""
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        return [
            "".join(
                str(c["text"])
                for c in sorted(page.chars, key=lambda c: float(c["x0"]))
                if float(c["size"]) >= MARK_SIZE
            )
            for page in document.pages
        ]


def test_ac7_every_draft_page_carries_the_watermark_and_a_final_none() -> None:
    draft = _marks(render(_letter("draft")).pdf)
    assert draft and all(mark == "DRAFT" for mark in draft)
    final = _marks(render(_letter("final")).pdf)
    assert final and all(mark == "" for mark in final)
    assert all(mark == "SAMPLE" for mark in _marks(render(_letter("sample")).pdf))


def test_ac8_hostile_text_is_extracted_as_its_characters() -> None:
    hostile = '<script>x</script> =HYPERLINK("u") {{ y }}'
    text = " ".join(_texts(render(_letter(**{"client.name": hostile})).pdf))
    assert "<script>x</script>" in text and '=HYPERLINK("u")' in text and "{{ y }}" in text


def test_ac9_an_image_that_is_not_in_the_asset_map_refuses() -> None:
    request = _letter()
    blocks: list[object] = [
        *request.blocks,
        {"type": "image", "asset_id": "5c4e0b3c-0a0d-4c5c-9f9a-0e6c0d1d7a11"},
    ]
    with pytest.raises(RenderRefused) as refused:
        render(replace(request, blocks=blocks))
    assert refused.value.code == "asset_not_allowed"


def test_ac11_a_legend_prints_on_every_page_of_a_package() -> None:
    request = _letter("final")
    blocks: list[object] = [
        {"type": "legend", "text": "Restricted to the use of management"},
        *request.blocks,
    ]
    out = render(replace(request, layout_key="package", blocks=blocks))
    pages = _texts(out.pdf)
    assert len(pages) >= 2 and all("Restricted to the use of management" in p for p in pages)


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "https://example.com/logo.png",
        "file:///etc/passwd",
        "data:image/png;base64,AAAA",
        "asset:font/not-a-face.ttf",
    ],
)
def test_ac9_the_fetcher_refuses_anything_but_a_known_asset(url: str) -> None:
    fetcher = AssetFetcher({"font/known.ttf": b"x"})
    with pytest.raises(AssetNotAllowed):
        fetcher.fetch(url)
    assert fetcher.refused == [url[:80]]
    assert fetcher.fetch("asset:font/known.ttf") is not None

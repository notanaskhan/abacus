# ac-test-author: ayushkbhatia
"""P-11-T14 (ADR-078; TASK-2526; SPEC-520 AC-6 to AC-9, AC-20): the renderer's independent suite,
image-bound half, written from the SPEC and C11 v1 rather than the code. `make golden-render`
runs it inside the backend image with no network, after the two-container byte check (AC-6's
"two containers").

- AC-9: a URL in an asset reference, including the instance-metadata address, is refused
  `asset_not_allowed`; a URL in a value is text, never fetched.
- AC-8: hostile variable text prints as its characters.
- AC-6, AC-20: the same input gives the same PDF and the same DOCX bytes.
- AC-7: every page of a draft carries DRAFT; a final carries no mark.
"""

from __future__ import annotations

import io
from dataclasses import replace
from datetime import UTC, datetime

import pdfplumber
import pytest

from abacus.modules.reporting.render.core import RenderInput, render, render_docx
from abacus.modules.reporting.render.head import RenderRefused

AS_OF = datetime(2027, 7, 28, 15, 0, tzinfo=UTC)
METADATA = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"


def _input(mode: str = "draft", value: str = "Ridgeline Property Partners, LP") -> RenderInput:
    blocks: list[object] = [{"type": "heading", "level": 1, "text": "Engagement letter"}]
    for n in range(3):
        if n:
            blocks.append({"type": "page_break"})
        blocks.append(
            {
                "type": "paragraph",
                "runs": [
                    {"type": "text", "text": f"Section {n + 1} for "},
                    {"type": "var", "key": "client.name"},
                ],
            }
        )
    return RenderInput(
        layout_key="letter",
        blocks=blocks,
        values={"client.name": value},
        title="Engagement letter",
        as_of=AS_OF,
        mode=mode,  # type: ignore[arg-type]  # the modes under test
        content_hash="e" * 64,
    )


def _pages(pdf: bytes) -> list[str]:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        return [page.extract_text() or "" for page in document.pages]


def _big(pdf: bytes) -> list[str]:
    """Each page's display-size characters (the diagonal mark), left to right."""
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        return [
            "".join(
                str(c["text"])
                for c in sorted(page.chars, key=lambda c: float(c["x0"]))
                if float(c["size"]) >= 36.0
            )
            for page in document.pages
        ]


@pytest.mark.parametrize(
    "asset",
    [
        METADATA,
        "https://cdn.example.com/logo.png",
        "file:///etc/passwd",
        "data:image/png;base64,AA",
    ],
)
def test_ac9_a_url_as_an_asset_is_refused(asset: str) -> None:
    request = _input()
    blocks = [*request.blocks, {"type": "image", "asset_id": asset}]
    with pytest.raises(RenderRefused) as refused:
        render(replace(request, blocks=blocks))
    assert refused.value.code == "asset_not_allowed"


def test_ac9_a_url_in_a_value_is_text_and_is_never_fetched() -> None:
    hostile = f'<img src="{METADATA}"> url({METADATA})'
    out = render(_input(value=hostile))  # no network in the container: a fetch would fail it
    text = " ".join(_pages(out.pdf)).replace("\n", " ")
    assert "169.254.169.254" in text and "<img" in text


def test_ac8_hostile_variable_text_prints_as_its_characters() -> None:
    hostile = '<script>alert(1)</script> =HYPERLINK("http://x") {{ secret }}'
    text = " ".join(_pages(render(_input(value=hostile)).pdf))
    for literal in ("<script>alert(1)</script>", '=HYPERLINK("http://x")', "{{ secret }}"):
        assert literal in text, literal


def test_ac6_ac20_the_same_input_gives_the_same_pdf_and_docx_bytes() -> None:
    a, b = render(_input()), render(_input())
    assert a.pdf == b.pdf and a.render_hash == b.render_hash
    da, db = render_docx(_input()), render_docx(_input())
    assert da.docx == db.docx and da.render_hash == db.render_hash


def test_ac7_every_draft_page_is_marked_and_a_final_is_not() -> None:
    draft = _big(render(_input("draft")).pdf)
    assert len(draft) == 3 and draft == ["DRAFT"] * 3
    assert _big(render(_input("final")).pdf) == [""] * 3

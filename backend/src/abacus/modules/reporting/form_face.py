"""A `tax_form_face` drawn as a PDF (T-06-T44; TASK-8913; C11 v1.2; ADR-320 §3; DEC-5915).

A form face has no blocks: each page is a US Letter sheet on which every manifest field's value is
placed in its box (fractions of the page from the top left), under a diagonal "Draft — not for
filing" watermark and a header naming the form, the tax year and the page. Values arrive already
formatted and masked by the owner (a TIN prints as its last four only); this module escapes them
and draws. The same inputs give the same bytes: the PDF's dates are the checkpoint's recorded
time and its identifier the content hash (`render.pdf`'s byte stability).
"""

from __future__ import annotations

import html as _html
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from abacus.modules.reporting.render.head import dated_head

WATERMARK: Final = "Draft — not for filing"
_CSS: Final = """
@page { size: 8.5in 11in; margin: 0; }
body { margin: 0; font-family: 'Geist', sans-serif; color: #1b1b1b; }
.page { position: relative; width: 8.5in; height: 11in; page-break-after: always; }
.page:last-child { page-break-after: auto; }
.head { position: absolute; left: 0.5in; top: 0.3in; font-size: 9pt; }
.mark { position: absolute; left: 1.2in; top: 4.6in; font-size: 48pt; color: #d6d6d6;
        transform: rotate(-35deg); white-space: nowrap; }
.f { position: absolute; font-size: 7.5pt; overflow: hidden; white-space: nowrap; }
.f .l { color: #6a6a6a; font-size: 5.5pt; display: block; }
.f .v { text-align: right; display: block; }
"""


@dataclass(frozen=True)
class FacePage:
    page_key: str
    title: str


@dataclass(frozen=True)
class FaceField:
    page_key: str
    label: str
    box: tuple[float, float, float, float]
    value: str  # formatted and masked by the owner


def face_html(
    title: str, pages: Sequence[FacePage], fields: Sequence[FaceField], *, as_of: datetime
) -> str:
    out: list[str] = [f"<html><head>{dated_head(_html.escape(title), as_of)}</head><body>"]
    for page in pages:
        out.append("<div class='page'>")
        out.append(
            f"<div class='head'>{_html.escape(title)} · {_html.escape(page.title)}</div>"
            f"<div class='mark'>{WATERMARK}</div>"
        )
        for f in (x for x in fields if x.page_key == page.page_key):
            x0, y0, x1, y1 = f.box
            style = (
                f"left:{x0 * 100:.3f}%;top:{y0 * 100:.3f}%;"
                f"width:{(x1 - x0) * 100:.3f}%;height:{(y1 - y0) * 100:.3f}%"
            )
            out.append(
                f"<div class='f' style='{style}'><span class='l'>{_html.escape(f.label)}</span>"
                f"<span class='v'>{_html.escape(f.value)}</span></div>"
            )
        out.append("</div>")
    out.append("</body></html>")
    return "".join(out)


def render_face(
    title: str,
    pages: Sequence[FacePage],
    fields: Sequence[FaceField],
    *,
    as_of: datetime,
    content_hash: str,
) -> bytes:
    """The face's PDF: one page per manifest page, byte-stable for the same inputs (WeasyPrint is
    loaded here, not at import: the system library is the renderer host's)."""
    from abacus.modules.reporting.render.pdf import render_pdf

    return render_pdf(
        face_html(title, pages, fields, as_of=as_of), _CSS, content_hash=content_hash
    )


def render_face_isolated(
    title: str,
    pages: Sequence[FacePage],
    fields: Sequence[FaceField],
    *,
    as_of: datetime,
    content_hash: str,
) -> bytes:
    """`render_face` in a fresh child with the renderer's limits (C11's isolation, as
    `render.core.render_isolated`); a crash or limit is `renderer_unavailable` (503)."""
    from abacus.kernel.isolation import IsolationFailed, run_isolated_with
    from abacus.modules.reporting.render.core import RENDER_LIMITS
    from abacus.modules.reporting.render.head import RenderRefused

    try:
        return run_isolated_with(
            RENDER_LIMITS, render_face, title, tuple(pages), tuple(fields), as_of=as_of,
            content_hash=content_hash,
        )  # fmt: skip
    except IsolationFailed as error:
        raise RenderRefused("renderer_unavailable") from error


__all__ = [
    "WATERMARK",
    "FaceField",
    "FacePage",
    "face_html",
    "render_face",
    "render_face_isolated",
]

"""Render the golden letter once and print its hashes (P-11-T02; ADR-320; SPEC-520 AC-30).

Run inside the backend image (`--target test`), where the pinned Pango, HarfBuzz and fontconfig
are: `python tests/golden_render/render_letter.py`. Prints `pdf <sha256> <pages>` and
`docx <sha256>`; `two_containers.sh` runs it in two fresh containers and compares.
"""

from __future__ import annotations

import hashlib
import io
import sys

import pdfplumber

from abacus.modules.reporting.render.docx import render_docx
from abacus.modules.reporting.render.pdf import dated_head, render_pdf
from abacus_tools.synthetic.scenarios.brightwater_hale import render_letter as letter


def render() -> tuple[bytes, bytes]:
    pdf = render_pdf(
        letter.html(dated_head(letter.TITLE, letter.AS_OF)),
        letter.CSS,
        content_hash=letter.CONTENT_HASH,
    )
    docx = render_docx(letter.blocks(), title=letter.TITLE, as_of=letter.AS_OF)
    return pdf, docx


def pages(pdf: bytes) -> int:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        return len(document.pages)


def main() -> int:
    pdf, docx = render()
    sys.stdout.write(f"pdf {hashlib.sha256(pdf).hexdigest()} {pages(pdf)}\n")
    sys.stdout.write(f"docx {hashlib.sha256(docx).hexdigest()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

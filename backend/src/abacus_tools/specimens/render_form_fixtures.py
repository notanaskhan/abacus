"""Render TPL-17's form-page fixtures (F-07-T15; F-07 §H, §6; DEC-4731).

    make form-fixtures       # inside the backend image, twice, then writes the files
    python -m abacus_tools.specimens.render_form_fixtures --out DIR [--check]

Renders `form_faces` once through the C11 renderer's pure in-process pipeline (`render_located`:
WeasyPrint, the deny-all fetcher, the vendored fonts; draft mode, so the page carries the DRAFT
mark), rasterises the PDF with the evidence preview path (`evidence.previews.render`, called and
never edited), and writes `page-<n>.png` and `manifest.json` (fields with rect, label, value,
match_id and diagnostic) to `--out`, the specimen's `packages/ui/src/specimens/fixtures/tpl-17/`.
It prints one `sha256 <name>` line per file, so two runs can be compared byte for byte.

Image-bound like `make golden-render`: Pango, HarfBuzz and fontconfig are the backend image's,
never a developer's. It reads no tenant, writes no database and needs no network (the
containers run with `--network none`). `--check` compares with the files already in `--out`.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from abacus_tools.specimens import form_faces

PDF: Final = "application/pdf"


def render() -> dict[str, bytes]:
    """Every output file by name, in memory."""
    from abacus.modules.evidence.previews import render as rasterise
    from abacus.modules.reporting.render.core import RenderInput, render_located

    located = render_located(
        RenderInput(
            layout_key=form_faces.LAYOUT,
            blocks=form_faces.blocks(),
            values=form_faces.values(),
            title=form_faces.TITLE,
            as_of=form_faces.AS_OF,
            mode="draft",
            content_hash=form_faces.content_hash(),
        )
    )
    pages = rasterise(located.output.pdf, PDF)
    if pages.kind != "pages" or len(pages.pages) != len(form_faces.FACES):
        raise RuntimeError(f"expected {len(form_faces.FACES)} pages, got {pages.kind}")
    images = [f"page-{n}.png" for n in range(1, len(pages.pages) + 1)]
    document = form_faces.manifest(
        [form_faces.Located(r.field_key, r.page, r.rect_pt) for r in located.regions],
        [(s.width_pt, s.height_pt) for s in located.page_sizes],
        images,
    )
    files = {name: page.png for name, page in zip(images, pages.pages, strict=True)}
    files["manifest.json"] = form_faces.manifest_json(document).encode()
    return files


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="abacus_tools.specimens.render_form_fixtures")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    files = render()
    differ: list[str] = []
    for name in sorted(files):
        data = files[name]
        print(f"sha256 {hashlib.sha256(data).hexdigest()} {name}")
        target = args.out / name
        if args.check:
            if not target.is_file() or target.read_bytes() != data:
                differ.append(name)
        else:
            args.out.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    if differ:
        print(f"differs from the committed fixtures: {', '.join(differ)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""DOCX from the same blocks through python-docx (ADR-320 §3; SPEC-520 AC-20; P-11-T02 spike).

Byte stability as `evidence/render.py` does it for XLSX: fixed core properties (dates from the
snapshot's `as_of`, a fixed author and revision), then the ZIP rebuilt with its entries sorted, a
fixed timestamp and fixed compression.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from docx import Document

_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
AUTHOR = "abacus-reporting"


@dataclass(frozen=True)
class DocxBlock:
    """The spike's subset of the DocBlock vocabulary: a heading or a paragraph of text."""

    kind: str  # "heading" | "paragraph" | "page_break"
    text: str = ""
    level: int = 1


def _rebuild(raw: bytes) -> bytes:
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(raw)) as source,
        zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for name in sorted(source.namelist()):
            entry = zipfile.ZipInfo(name, date_time=_ZIP_TIME)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            entry.create_system = 3  # the same on every platform
            target.writestr(entry, source.read(name))
    return out.getvalue()


def render_docx(blocks: Sequence[DocxBlock], *, title: str, as_of: datetime) -> bytes:
    document = Document()
    props = document.core_properties
    props.author = AUTHOR
    props.last_modified_by = AUTHOR
    props.title = title
    props.created = as_of
    props.modified = as_of
    props.revision = 1
    for block in blocks:
        if block.kind == "heading":
            document.add_heading(block.text, level=block.level)
        elif block.kind == "page_break":
            document.add_page_break()
        else:
            document.add_paragraph(block.text)
    raw = io.BytesIO()
    document.save(raw)
    return _rebuild(raw.getvalue())

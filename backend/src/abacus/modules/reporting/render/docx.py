"""DOCX from the same blocks through python-docx (ADR-320 §3; SPEC-520 AC-20; P-11-T02 spike,
P-11-T10 writer).

Byte stability as `evidence/render.py` does it for XLSX: fixed core properties (dates from the
snapshot's `as_of`, a fixed author and revision), fixed app properties, then the ZIP rebuilt with
its entries sorted, a fixed timestamp and fixed compression.

`write_docx` (P-11-T10) walks the closed DocBlock union exactly as `html.py` does: the same
clause states and library standards, the same variable values (the caller ran `build_html`
first, so a missing variable or an uncovered character has already refused), the letterhead,
the DRAFT or SAMPLE mark in every page header, a legend in every page footer, tables with
right-aligned figures (nothing sums, ADR-050), signature lines, enclosures, page breaks, and
`fixed` layouts starting each top-level section on a new page. The layout tokens are the
stylesheet's (Arimo 12 pt at 1.55, headings 16 and 13.5 pt, ink #2b1f17, Letter with 1 in
margins). The strings it places are returned in the order `html.py` collects them, so a test
can hold the two outputs' text equal. `render_docx` is the T02 spike's subset, kept for the
golden harness.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final

from docx import Document
from docx.document import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Inches, Pt, RGBColor
from docx.table import _Cell  # pyright: ignore[reportPrivateUsage] -- python-docx's cell type
from docx.text.paragraph import Paragraph

from abacus.modules.reporting.contract import (
    ClauseBlock,
    DocBlock,
    EnclosuresBlock,
    HeadingBlock,
    ImageBlock,
    KvBlock,
    LegendBlock,
    ListBlock,
    PageBreakBlock,
    ParagraphBlock,
    Run,
    SectionBlock,
    SignatureBlock,
    TableBlock,
    TextRun,
    VarRun,
)
from abacus.modules.reporting.render.head import RenderRefused
from abacus.modules.reporting.render.html import Letterhead
from abacus.modules.reporting.render.html import (
    _numeric as numeric,  # pyright: ignore[reportPrivateUsage]
)
from abacus.modules.reporting.render.layouts import Layout, Mark
from abacus.modules.reporting.render.text import clean

_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
AUTHOR = "abacus-reporting"


@dataclass(frozen=True)
class DocxBlock:
    """The spike's subset of the DocBlock vocabulary: a heading or a paragraph of text."""

    kind: str  # "heading" | "paragraph" | "page_break"
    text: str = ""
    level: int = 1


# docProps/app.xml as python-docx's template ships it names an application and version: fixed
# here instead, with nothing that names a product (client documents are the firm's, DEC-01).
_APP_XML: Final = (
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    b'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"'
    b' xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
    b"<Template>Normal.dotm</Template><TotalTime>0</TotalTime><DocSecurity>0</DocSecurity>"
    b"<ScaleCrop>false</ScaleCrop><LinksUpToDate>false</LinksUpToDate>"
    b"<SharedDoc>false</SharedDoc><HyperlinksChanged>false</HyperlinksChanged>"
    b"</Properties>"
)


def _rebuild(raw: bytes, *, app_xml: bytes | None = None) -> bytes:
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
            data = source.read(name)
            if app_xml is not None and name == "docProps/app.xml":
                data = app_xml
            target.writestr(entry, data)
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


# --- P-11-T10: the writer ------------------------------------------------------------------

INK: Final = RGBColor(0x2B, 0x1F, 0x17)
MUTED: Final = RGBColor(0x7A, 0x6F, 0x66)
# The 6% ink watermark over white paper, as an opaque colour (DOCX text has no alpha).
STAMP: Final = RGBColor(0xF0, 0xEF, 0xEE)
BODY_FONT: Final = "Arimo"
LETTERHEAD_FONT: Final = "Gelasio"
_SIZES: Final = {1: 16.0, 2: 13.5, 3: 12.0, 4: 12.0}
SIGNATURE_LINE: Final = "_" * 36


@dataclass
class _W:
    values: Mapping[str, str]
    clause_states: Mapping[str, bool]
    library: Mapping[str, Sequence[DocBlock]]
    assets: Mapping[str, bytes]
    texts: list[str] = field(default_factory=list[str])
    legends: list[str] = field(default_factory=list[str])
    citations: dict[str, int] = field(default_factory=dict[str, int])


@dataclass(frozen=True)
class DocxOutput:
    docx: bytes
    texts: tuple[str, ...]


def _font(run_font: object, *, size: float | None = None, family: str = BODY_FONT) -> None:
    from docx.text.font import Font

    font = run_font if isinstance(run_font, Font) else None
    if font is None:
        return
    font.name = family
    font.color.rgb = INK
    if size is not None:
        font.size = Pt(size)


def _styles(document: DocxDocument, layout: Layout) -> None:
    normal = document.styles["Normal"]
    _font(getattr(normal, "font", None), size=12.0)
    fmt = getattr(normal, "paragraph_format", None)
    if fmt is not None:
        fmt.line_spacing = 1.55
        fmt.space_after = Pt(8)
    for level, size in _SIZES.items():
        style = document.styles[f"Heading {level}"]
        font = getattr(style, "font", None)
        _font(font, size=size)
        if font is not None:
            font.bold = False
            font.italic = False
    for section in document.sections:
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
        section.top_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)
        section.bottom_margin = Inches(1.1)
    del layout  # every layout shares the base tokens; consent's floor is the body size


def _rule_below(paragraph: Paragraph) -> None:
    """A hair rule under the letterhead (`pBdr/bottom`, 0.5 pt)."""
    ppr = paragraph._p.get_or_add_pPr()  # pyright: ignore[reportPrivateUsage]
    ppr.append(  # pyright: ignore[reportUnknownMemberType] -- lxml's element API
        parse_xml(
            f"<w:pBdr {nsdecls('w')}><w:bottom w:val='single' w:sz='4' w:space='4' "
            "w:color='D9D6D1'/></w:pBdr>"
        )
    )


def _add_text(w: _W, paragraph: Paragraph, value: str, **font: float) -> None:
    w.texts.append(value)
    run = paragraph.add_run(clean(value))
    _font(run.font, size=font.get("size"))


def _add_runs(w: _W, paragraph: Paragraph, runs: Sequence[Run]) -> None:
    for item in runs:
        if isinstance(item, TextRun):
            _add_text(w, paragraph, item.text)
        elif isinstance(item, VarRun):
            value = w.values.get(item.key)
            if value is None:  # build_html refused first; a direct caller gets the same refusal
                raise RenderRefused("missing_variable")
            _add_text(w, paragraph, value)
        else:
            n = w.citations.setdefault(str(item.citation_id), len(w.citations) + 1)
            run = paragraph.add_run(f"[{n}]")
            run.font.superscript = True
            _font(run.font, size=9.0)


def _cell(w: _W, cell: _Cell, value: str, *, right: bool = False) -> None:
    paragraph = cell.paragraphs[0]
    _add_text(w, paragraph, value, size=11.0)
    if right:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT


def _write(
    document: DocxDocument, w: _W, blocks: Sequence[DocBlock], *, top: bool, fixed: bool
) -> None:
    for index, block in enumerate(blocks):
        if fixed and top and index > 0 and isinstance(block, SectionBlock):
            document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        _one(document, w, block, fixed=fixed)


def _one(document: DocxDocument, w: _W, block: DocBlock, *, fixed: bool) -> None:
    match block:
        case SectionBlock():
            if block.title:
                heading = document.add_heading(level=2)
                _add_text(w, heading, block.title, size=_SIZES[2])
            _write(document, w, block.blocks, top=False, fixed=fixed)
        case HeadingBlock():
            level = min(block.level + 1, 4) if block.level > 1 else 1
            heading = document.add_heading(level=level)
            _add_text(w, heading, block.text, size=_SIZES[level])
        case ParagraphBlock():
            _add_runs(w, document.add_paragraph(), block.runs)
        case ClauseBlock():
            if not w.clause_states.get(block.clause_id, block.enabled):
                return
            inner = block.blocks or list(w.library.get(block.clause_id, ()))
            _write(document, w, inner, top=False, fixed=fixed)
        case ListBlock():
            style = "List Number" if block.ordered else "List Bullet"
            for item in block.items:
                _add_runs(w, document.add_paragraph(style=style), item)
        case TableBlock():
            table = document.add_table(rows=1 + len(block.rows), cols=max(len(block.columns), 1))
            for i, column in enumerate(block.columns):
                _cell(w, table.rows[0].cells[i], column)
            for r, row in enumerate(block.rows, start=1):
                for i, value in enumerate(row[: len(table.columns)]):
                    _cell(w, table.rows[r].cells[i], value, right=numeric(value))
        case KvBlock():
            table = document.add_table(rows=len(block.rows), cols=2)
            for r, row in enumerate(block.rows):
                _cell(w, table.rows[r].cells[0], row.key)
                value = table.rows[r].cells[1].paragraphs[0]
                _add_runs(w, value, row.value)
                value.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        case SignatureBlock():
            for signer in block.signers:
                line = document.add_paragraph()
                line.paragraph_format.space_before = Pt(28)
                line.add_run(SIGNATURE_LINE)
                who = document.add_paragraph()
                _add_runs(w, who, signer.name)
                for run in who.runs:
                    run.font.name = LETTERHEAD_FONT
                _add_text(w, document.add_paragraph(), signer.label)
        case LegendBlock():
            w.legends.append(block.text)
            w.texts.append(block.text)
        case ImageBlock():
            asset = w.assets.get(f"firm/{block.asset_id}.png")
            if asset is None:
                raise RenderRefused("asset_not_allowed")
            document.add_picture(io.BytesIO(asset), width=Inches(1.5))
        case EnclosuresBlock():
            label = document.add_paragraph()
            label.paragraph_format.space_before = Pt(16)
            run = label.add_run("Enclosures")
            _font(run.font, size=11.5)
            for item in block.items:
                _add_text(w, document.add_paragraph(style="List Bullet"), item, size=11.5)
        case PageBreakBlock():
            document.add_page_break()


def _header_and_footer(document: DocxDocument, mark: Mark | None, legends: Sequence[str]) -> None:
    section = document.sections[0]
    if mark is not None:
        stamp = section.header.paragraphs[0]
        stamp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = stamp.add_run(mark)
        run.font.name = BODY_FONT
        run.font.bold = True
        run.font.size = Pt(54)
        run.font.color.rgb = STAMP
    if legends:
        footer = section.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer.add_run(" ".join(clean(t) for t in legends))
        run.font.name = BODY_FONT
        run.font.size = Pt(9)
        run.font.color.rgb = MUTED


def _letterhead(document: DocxDocument, w: _W, letterhead: Letterhead) -> list[str]:
    """Written first in the document; its strings join the texts after the body's, as in
    `html.py`."""
    if letterhead.mark_asset is not None:
        asset = w.assets.get(letterhead.mark_asset)
        if asset is None:
            raise RenderRefused("asset_not_allowed")
        document.add_picture(io.BytesIO(asset), width=Inches(0.3))
    firm = document.add_paragraph()
    run = firm.add_run(clean(letterhead.firm))
    _font(run.font, size=13.5, family=LETTERHEAD_FONT)
    last = firm
    for line in letterhead.address:
        last = document.add_paragraph()
        address = last.add_run(clean(line))
        address.font.name = BODY_FONT
        address.font.size = Pt(11.5)
        address.font.color.rgb = MUTED
    _rule_below(last)
    return [letterhead.firm, *letterhead.address]


def write_docx(
    layout: Layout,
    blocks: Sequence[DocBlock],
    values: Mapping[str, str],
    *,
    title: str,
    as_of: datetime,
    mark: Mark | None,
    content_hash: str,
    clause_states: Mapping[str, bool] | None = None,
    library: Mapping[str, Sequence[DocBlock]] | None = None,
    letterhead: Letterhead | None = None,
    assets: Mapping[str, bytes] | None = None,
) -> DocxOutput:
    """The DOCX for the same input as `document_html`: same input, same bytes."""
    document = Document()
    _styles(document, layout)
    props = document.core_properties
    props.author = ""
    props.last_modified_by = ""
    props.title = clean(title)
    props.identifier = content_hash
    props.created = as_of
    props.modified = as_of
    props.revision = 1
    w = _W(values, clause_states or {}, library or {}, assets or {})
    head: list[str] = []
    if layout.letterhead and letterhead is not None:
        head = _letterhead(document, w, letterhead)
    _write(document, w, blocks, top=True, fixed=layout.flow == "fixed")
    _header_and_footer(document, mark, w.legends)
    raw = io.BytesIO()
    document.save(raw)
    return DocxOutput(_rebuild(raw.getvalue(), app_xml=_APP_XML), (*w.texts, *head))


def docx_texts(docx: bytes) -> list[str]:
    """The non-empty paragraph texts of a DOCX's body, tables included, in document order; for
    tests holding a DOCX's text to the PDF's block text."""
    out: list[str] = []
    for item in Document(io.BytesIO(docx)).iter_inner_content():
        paragraphs = (
            [item]
            if isinstance(item, Paragraph)
            else [p for row in item.rows for cell in row.cells for p in cell.paragraphs]
        )
        out.extend(p.text for p in paragraphs if p.text.strip())
    return out

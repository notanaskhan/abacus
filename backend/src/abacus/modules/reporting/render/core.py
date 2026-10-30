"""The renderer core (P-11-T07; P-11 §4.4; ADR-320; SPEC-520 AC-6 to AC-12).

`render(RenderInput) -> RenderOutput` is the whole pipeline, and runs only inside the isolated
child (`render_isolated`, renderer limits, `worker-batch`): the DocBlocks are re-validated
against C11's closed union, every character is checked against the vendored faces
(`missing_glyph`), the layout builds the HTML (`missing_variable` if a declared value is absent),
WeasyPrint writes the PDF with the deny-all fetcher and the in-memory asset map
(`asset_not_allowed`), and the page count is read back. Same input, same bytes (AC-6): no clock,
no locale, no randomness, no system font.

`RenderInput` is plain data (picklable): blocks as JSON, values as strings already formatted by
code (`format.py`, P-11-T08), the mode's mark and the content hash that names the PDF.
RenderWorkflow (P-11-T08) owns everything around it: snapshots, versions, evidence, events.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from typing import Final, Literal

from pydantic import TypeAdapter, ValidationError

from abacus.kernel.isolation import IsolationFailed, Limits, run_isolated_with
from abacus.modules.reporting.contract import DocBlock
from abacus.modules.reporting.render.assets import fonts_manifest_sha256
from abacus.modules.reporting.render.head import RenderRefused
from abacus.modules.reporting.render.html import Letterhead, document_html
from abacus.modules.reporting.render.layouts import LAYOUT_VERSION, LAYOUTS, Mark, stylesheet
from abacus.modules.reporting.render.text import uncovered

Mode = Literal["draft", "final", "sample"]
_BLOCKS: Final = TypeAdapter(list[DocBlock])
# P-11 §4.4 (inferred there): a renderer child gets more than an upload parse does.
RENDER_LIMITS: Final = Limits(timeout_seconds=60, cpu_seconds=45, memory_bytes=1024**3)
_MARKS: Final[dict[str, Mark | None]] = {"draft": "DRAFT", "sample": "SAMPLE", "final": None}
_PACKAGES: Final = ("weasyprint", "pydyf", "tinycss2", "python-docx")


class MissingGlyph(RenderRefused):
    def __init__(self, characters: Sequence[str]) -> None:
        super().__init__("missing_glyph")
        self.characters = tuple(characters)


@dataclass(frozen=True)
class RenderInput:
    layout_key: str
    blocks: list[object]
    values: Mapping[str, str]
    title: str
    as_of: datetime
    mode: Mode
    content_hash: str
    clause_states: Mapping[str, bool] = field(default_factory=dict[str, bool])
    library: Mapping[str, list[object]] = field(default_factory=dict[str, list[object]])
    letterhead: Letterhead | None = None
    assets: Mapping[str, bytes] = field(default_factory=dict[str, bytes])


@dataclass(frozen=True)
class RenderOutput:
    pdf: bytes
    page_count: int
    render_hash: str
    citations: tuple[str, ...]


def mark_for(mode: Mode) -> Mark | None:
    """AC-7: DRAFT on a draft, SAMPLE on a template preview, nothing on a final render."""
    return _MARKS[mode]


def engine_version() -> str:
    """Every input to the bytes that is not the document itself (P-11 §4.2 `engine_version`):
    the PDF and DOCX packages, the layouts' version and the fonts manifest. An engine upgrade
    changes it, never a document's `content_hash` (AC-17: it never marks a document out of
    date)."""
    parts: list[str] = []
    for name in _PACKAGES:
        try:
            parts.append(f"{name}={package_version(name)}")
        except PackageNotFoundError:
            parts.append(f"{name}=absent")
    parts.append(f"layouts={LAYOUT_VERSION}")
    parts.append(f"fonts={fonts_manifest_sha256()[:16]}")
    return ";".join(parts)


def _blocks(raw: list[object]) -> list[DocBlock]:
    try:
        return _BLOCKS.validate_python(raw)
    except ValidationError as error:
        raise RenderRefused("unknown_block") from error


def build_html(request: RenderInput) -> tuple[str, str, tuple[str, ...]]:
    """The document and its stylesheet, refusals raised before any engine runs. Pure: no Pango."""
    layout = LAYOUTS.get(request.layout_key)
    if layout is None:
        raise RenderRefused("unknown_layout")
    library = {k: _blocks(v) for k, v in request.library.items()}
    built = document_html(
        layout,
        _blocks(request.blocks),
        request.values,
        title=request.title,
        as_of=request.as_of,
        mark=mark_for(request.mode),
        clause_states=request.clause_states,
        library=library,
        letterhead=request.letterhead,
    )
    missing = uncovered([request.title, *built.texts])
    if missing:
        raise MissingGlyph(missing)
    return built.document, stylesheet(layout, mark_for(request.mode)), built.citations


def _pages(pdf: bytes) -> int:
    import pdfplumber  # the isolated child only

    with pdfplumber.open(io.BytesIO(pdf)) as document:
        return len(document.pages)


def render(request: RenderInput) -> RenderOutput:
    """The pipeline, in the current process (the isolated child calls this)."""
    document, css, citations = build_html(request)
    from abacus.modules.reporting.render.pdf import render_pdf  # Pango: the child only

    pdf = render_pdf(document, css, content_hash=request.content_hash, assets=dict(request.assets))
    return RenderOutput(pdf, _pages(pdf), hashlib.sha256(pdf).hexdigest(), citations)


def render_isolated(request: RenderInput) -> RenderOutput:
    """`render` in a fresh child with the renderer's limits; a crash or limit is
    `renderer_unavailable` (503), a refusal comes back as itself."""
    try:
        return run_isolated_with(RENDER_LIMITS, render, request)
    except IsolationFailed as error:
        raise RenderRefused("renderer_unavailable") from error

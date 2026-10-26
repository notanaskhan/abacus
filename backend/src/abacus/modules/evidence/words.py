"""The word layer: every word of a PDF page and its box (P-03-T05; SPEC-322; ADR-166, ADR-110,
ADR-104). PROTECTED.

`upload_processing` v4 (`patched("words")`) runs `words_upload` for each upload. The file is
hostile (ADR-052): `extract_words_isolated` runs pdfplumber's `extract_words` in a short-lived
child (`kernel.isolation`), so a crash, a hang or a limit hit is `unreadable`, never a worker
failure. Each page with words becomes one sealed object in storage (the tenant's key, content
addressed; ADR-104) `{page, w, h, rotation, words: [{text, x0, top, x1, bottom}]}`, and every page
becomes one `evidence_pages` row with its geometry. A page with no words (a scan) gets a row with
`has_text_layer=false` and no object, so "no text" is recorded, never inferred (T13 reads it as
`not_scannable`).

Coordinates are render space (`w2`, P-03-T15 security review; DEC-369): page points with a
top-left origin on the page's visible box (MediaBox ∩ CropBox) with `/Rotate` applied, exactly
what PDFium renders, so the client and the masker only scale (`image_w / width_pt`). Words are
read from the file with its annotations flattened in, from an unrotated copy (so text reads in
order), and mapped into render space (`pdf_layout`). A page whose words can't be reconciled with
PDFium's own text, that reads as a scan or drawn text, or that passes `MAX_PAGE_WORDS` is
recorded without a text layer: `not_scannable`, never part-scanned. `rotation` records the
`/Rotate` value (DEC-217).

The layer is a derived record: it never alters the evidence or its fingerprint and can be rebuilt.
Idempotent on (source, `WORDS_VERSION`). Words are client text (Restricted); they are never
logged and never cross a workflow payload.
"""

from __future__ import annotations

import asyncio
import io
import json
import math
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Final, Literal, cast
from uuid import UUID

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch
from abacus.kernel.errors import NotFound
from abacus.kernel.isolation import IsolationFailed, run_isolated
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.evidence import storage
from abacus.modules.evidence.active_content import is_active
from abacus.modules.evidence.models import EvidencePage
from abacus.modules.evidence.object_keys import under_key
from abacus.modules.evidence.pdf_layout import (
    RenderSpace,
    drawn_glyphs,
    flattened,
    image_content,
    reconciled,
    render_space,
    sideways_digits,
    text_boxes,
    upright,
)
from abacus.modules.evidence.repository import (
    get_inbox_file,
    get_version,
    insert_pages,
    is_withdrawn,
    pages_of,
    sources_without_words,
)
from abacus.modules.evidence.workflow_types import INBOX, VERSION, BackfillInput, UploadInput
from abacus.modules.evidence.workflows import BACKFILL_BATCH, TrustLayerBackfill

if TYPE_CHECKING:
    from pdfplumber.page import Page as PlumberPage
    from pypdfium2 import PdfPage

_log = get_logger(__name__)

# w2 (P-03-T15 security review, DEC-369): flattened annotations, render-space boxes, and pages
# that can't be reconciled, read as scans or pass the word cap recorded without a text layer.
WORDS_VERSION: Final = "w2"
MAX_PAGES: Final = 200  # the extractor's cap (extraction.MAX_PAGES)
MAX_PAGE_WORDS: Final = 5000
MAX_WORD: Final = 200
# PDF's largest page side (ISO 32000, 200 in at 72 pt); `evidence_pages` is numeric(8, 2) > 0.
MAX_PAGE_PT: Final = 14_400.0
PDF: Final = "application/pdf"
_REFUSED: Final = frozenset({"Cc", "Cf", "Cs", "Co"})

Status = Literal["extracted", "unreadable", "not_applicable"]


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    top: float
    x1: float
    bottom: float


@dataclass(frozen=True)
class PageWords:
    page: int  # from 1
    width: float  # page points, after /Rotate
    height: float
    rotation: int  # the page's /Rotate: 0, 90, 180 or 270
    words: tuple[Word, ...]
    # Reviews N1, R1 to R3: the page shows content no scan reads before OCR (a picture, glyph-sized
    # vector shapes, a sideways digit): its upright text is masked, the rest is not.
    unread: bool = False


@dataclass(frozen=True)
class WordLayer:
    status: Status
    reason: str | None = None  # encrypted, damaged, crashed
    pages: tuple[PageWords, ...] = ()
    truncated: bool = False


def _clean(value: object) -> str:
    """Plain text: control, format and private-use characters dropped, length capped."""
    text = "" if value is None else str(value)
    return "".join(c for c in text if unicodedata.category(c) not in _REFUSED)[:MAX_WORD].strip()


def _pt(value: object) -> float:
    try:
        found = round(float(cast(float, value)), 2)
    except (TypeError, ValueError, OverflowError):
        return float("nan")
    return found if math.isfinite(found) else float("nan")


def _side(value: float) -> bool:
    """A page side a reader could see and the table can hold."""
    return math.isfinite(value) and 0 < value <= MAX_PAGE_PT


def _clamped(value: float) -> float:
    return min(max(value, 1.0), MAX_PAGE_PT) if math.isfinite(value) else 1.0


def _unscannable(number: int, width: float, height: float, rotation: int) -> PageWords:
    """A page recorded without a text layer, so it reads `not_scannable` (fail closed)."""
    return PageWords(number, _clamped(width), _clamped(height), rotation, ())


def _placed(
    found: list[dict[str, object]], space: RenderSpace, width: float, height: float
) -> list[Word] | None:
    """pdfplumber's words in render space, those outside the visible page dropped; None past
    `MAX_PAGE_WORDS` (L2: never part-scanned)."""
    words: list[Word] = []
    for raw in found:
        text = _clean(raw.get("text"))
        if not text:
            continue
        box = (_pt(raw.get("x0")), _pt(raw.get("top")), _pt(raw.get("x1")), _pt(raw.get("bottom")))
        if not all(math.isfinite(v) for v in box):
            continue
        x0, top, x1, bottom = space.plumber_box(*box)
        if not (0 <= (x0 + x1) / 2 <= width and 0 <= (top + bottom) / 2 <= height):
            continue  # outside the visible page box: nothing a reader could see
        x0, top = _pt(max(0.0, x0)), _pt(max(0.0, top))
        x1, bottom = _pt(min(width, x1)), _pt(min(height, bottom))
        if x1 < x0 or bottom < top:
            continue
        words.append(Word(text, x0, top, x1, bottom))
        if len(words) >= MAX_PAGE_WORDS:
            return None
    return words


def _is_upright(obj: dict[str, object]) -> bool:
    return obj.get("object_type") != "char" or upright(obj)


def _page_words(number: int, page: PlumberPage, shown: PdfPage) -> PageWords:
    """One page's words in render space (`pdf_layout`; DEC-369): what PDFium draws, where it
    draws it. Unscannable when the two parsers can't be reconciled or the words pass
    `MAX_PAGE_WORDS` (H1, H2, L2). Only upright words are kept; a page with a picture, glyph-sized
    vector shapes or a sideways digit is marked `unread` (N1, R1 to R3)."""
    rendered = render_space(shown)
    width = _pt(getattr(rendered, "width", float("nan")))
    height = _pt(getattr(rendered, "height", float("nan")))
    rotation = rendered.rotation if rendered is not None else 0
    space = (
        render_space(shown, page)
        if rendered is not None and _side(width) and _side(height)
        else None
    )
    if space is None:
        # A hostile or broken page box (zero, negative, tiny, past PDF's limit) or geometry the
        # parsers disagree on: recorded without a text layer, with sides the table can hold.
        return _unscannable(number, width, height, rotation)
    every = _placed(
        cast(list[dict[str, object]], page.extract_words(keep_blank_chars=False)),
        space,
        width,
        height,
    )
    if every is None:
        return _unscannable(number, width, height, rotation)
    drawn = text_boxes(shown, space)
    if not reconciled([(w.x0, w.top, w.x1, w.bottom) for w in every], drawn):
        return _unscannable(number, width, height, rotation)
    chars = cast(list[dict[str, object]], page.chars)
    sideways = not all(_is_upright(c) for c in chars)
    words = every
    if sideways:
        # Words set sideways, upside down or mirrored are read out of order: left out of the
        # layer, so no agent or search ever reads them (review R3).
        upright_only = page.filter(_is_upright)
        kept = _placed(
            cast(list[dict[str, object]], upright_only.extract_words(keep_blank_chars=False)),
            space,
            width,
            height,
        )
        if kept is None:
            return _unscannable(number, width, height, rotation)
        words = kept
    unread = sideways_digits(chars) or image_content(shown, space) or drawn_glyphs(shown, space)
    return PageWords(number, width, height, rotation, tuple(words), unread)


def _reason(exc: BaseException) -> str:
    from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect

    causes = (exc, *exc.args, exc.__cause__)
    if any(isinstance(c, (PDFPasswordIncorrect, PDFEncryptionError)) for c in causes):
        return "encrypted"
    return "damaged"


def extract_words(content: bytes, media_type: str) -> WordLayer:
    """In-process (tests, and inside the isolated child): a PDF's words page by page, read from
    the flattened file (`pdf_layout.flattened`) in render space."""
    if media_type != PDF:
        return WordLayer("not_applicable")
    if is_active(content):  # DEC-296 (ED-021): kept, never read for words
        return WordLayer("not_applicable", "active_content")
    import pdfplumber
    import pypdfium2 as pdfium

    try:
        flat = flattened(content)
        upright_copy = flattened(content, unrotated=True)
        shown = pdfium.PdfDocument(flat)
    except Exception as exc:  # a damaged, encrypted or hostile file: PDFium raises several kinds
        return WordLayer(
            "unreadable", "encrypted" if "password" in str(exc).casefold() else "damaged"
        )
    try:
        try:
            pdf = pdfplumber.open(io.BytesIO(upright_copy))
        except Exception as exc:  # a damaged or hostile file: pdfminer raises many kinds
            return WordLayer("unreadable", _reason(exc))
        with pdf:
            try:
                if getattr(pdf.doc, "encryption", None) is not None:
                    return WordLayer("unreadable", "encrypted")
                count = len(pdf.pages)
                if count != len(shown):
                    return WordLayer("unreadable", "damaged")  # the parsers disagree on pages
                pages = tuple(
                    _page_words(n, page, shown[n - 1])
                    for n, page in enumerate(pdf.pages[:MAX_PAGES], start=1)
                )
            except Exception as exc:
                return WordLayer("unreadable", _reason(exc))
    finally:
        shown.close()
    if not pages:
        return WordLayer("unreadable", "empty")
    return WordLayer("extracted", pages=pages, truncated=count > MAX_PAGES)


def extract_words_isolated(content: bytes, media_type: str) -> WordLayer:
    """`extract_words` in a short-lived child with limits; a crash or a hang is `crashed`."""
    try:
        return run_isolated(extract_words, content, media_type)
    except IsolationFailed:
        return WordLayer("unreadable", "crashed")
    except Exception:  # anything the child didn't turn into a result
        return WordLayer("unreadable", "crashed")


def layer_document(page: PageWords) -> bytes:
    """The sealed object for one page: compact, sorted, so the same page is the same object."""
    body = {
        "page": page.page,
        "w": page.width,
        "h": page.height,
        "rotation": page.rotation,
        "unread": page.unread,
        "words": [
            {"text": w.text, "x0": w.x0, "top": w.top, "x1": w.x1, "bottom": w.bottom}
            for w in page.words
        ],
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def parse_layer(raw: bytes) -> PageWords:
    """A stored layer object back into words (written by `layer_document`)."""
    body = cast(dict[str, object], json.loads(raw))
    words = tuple(
        Word(
            str(w["text"]),
            float(cast(float, w["x0"])),
            float(cast(float, w["top"])),
            float(cast(float, w["x1"])),
            float(cast(float, w["bottom"])),
        )
        for w in cast(list[dict[str, object]], body["words"])
    )
    return PageWords(
        int(cast(int, body["page"])),
        float(cast(float, body["w"])),
        float(cast(float, body["h"])),
        int(cast(int, body["rotation"])),
        words,
        bool(body.get("unread", False)),
    )


async def read_page_layer(tenant_id: UUID, page: EvidencePage) -> PageWords:
    """One page's words; a page without a text layer has none (its geometry still holds)."""
    if (
        page.text_layer_key is None
        or page.text_layer_version_id is None
        or page.text_layer_fingerprint is None
        or page.text_layer_size is None
    ):
        return PageWords(
            page.page_no, float(page.width_pt), float(page.height_pt), page.rotation, ()
        )
    stored = storage.StoredObject(
        page.text_layer_key,
        page.text_layer_version_id,
        page.text_layer_fingerprint,
        page.text_layer_size,
    )
    return parse_layer(await storage.get(tenant_id, stored))


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "evidence.upload_processing")


async def words_upload(given: UploadInput) -> int:
    """The `upload.words` activity's body: one upload's word layer; returns its page count (0
    when it isn't a PDF or can't be read). Idempotent."""
    tenant_id, source_id = UUID(given.tenant_id), UUID(given.source_id)
    tenant = _system(tenant_id)
    version_id = source_id if given.kind == VERSION else None
    inbox_id = source_id if given.kind == INBOX else None
    async with tenant_session(tenant) as session:
        done = await pages_of(
            session,
            evidence_version_id=version_id,
            inbox_file_id=inbox_id,
            extractor_version=WORDS_VERSION,
        )
        if done:
            return len(done)
        source = (
            await get_version(session, source_id)
            if version_id is not None
            else await get_inbox_file(session, source_id)
        )
    if source is None:
        if version_id is not None:
            async with tenant_session(tenant) as session:
                if await is_withdrawn(session, version_id):
                    return 0  # P-06-T19: no word layer for a withdrawn version
        raise NotFound("upload")
    if source.media_type != PDF:
        return 0
    stored = storage.StoredObject(
        source.storage_key, source.storage_version_id, source.fingerprint, source.size_bytes
    )
    content = await storage.get(tenant_id, stored)
    layer = await asyncio.to_thread(extract_words_isolated, content, source.media_type)
    under = under_key(source)
    if layer.status != "extracted":
        _log.info("upload.words_skipped", kind=given.kind, reason=layer.reason)
        return 0
    objects = [
        await storage.put(tenant_id, layer_document(page), under=under) if page.words else None
        for page in layer.pages
    ]
    rows: list[dict[str, object]] = [
        {
            "tenant_id": tenant_id,
            "evidence_version_id": version_id,
            "inbox_file_id": inbox_id,
            "derivation_id": None,
            "page_no": page.page,
            "width_pt": Decimal(str(page.width)),
            "height_pt": Decimal(str(page.height)),
            "rotation": page.rotation,
            "has_text_layer": bool(page.words),
            "word_count": len(page.words),
            "text_layer_key": put.key if put else None,
            "text_layer_version_id": put.version_id if put else None,
            "text_layer_fingerprint": put.fingerprint if put else None,
            "text_layer_size": put.size if put else None,
            "ocr_used": False,
            "extractor_version": WORDS_VERSION,
        }
        for page, put in zip(layer.pages, objects, strict=True)
    ]
    async with uow(tenant) as tx:
        added = await insert_pages(tx.session, rows)
        # A concurrent run that got there first adds nothing: still one audited write.
        tx.record(
            "upload.words_extracted" if added else "upload.words_exist",
            target=Target("evidence_version" if version_id else "inbox_file", source_id),
            after=Ref(pages=added, words=sum(len(p.words) for p in layer.pages)),
        )
    _log.info("upload.words_extracted", kind=given.kind, pages=len(rows))
    return len(rows)


# --- The backfill (P-03 §4.5) -------------------------------------------------------------------


def backfill_workflow_id(tenant_id: UUID) -> str:
    return f"trust_layer_backfill:{tenant_id}"


async def pending_words(given: BackfillInput) -> list[UploadInput]:
    """The `trust_layer.pending_words` activity's body: the next PDFs (versions, then inbox
    files, by id after the cursors) with no word layer and a readable extraction."""
    tenant_id = UUID(given.tenant_id)
    async with tenant_session(_system(tenant_id)) as session:
        found = await sources_without_words(
            session,
            WORDS_VERSION,
            after_version=UUID(given.after_version) if given.after_version else None,
            after_inbox=UUID(given.after_inbox) if given.after_inbox else None,
            limit=BACKFILL_BATCH,
        )
    return [
        UploadInput(given.tenant_id, VERSION if kind == "version" else INBOX, str(source))
        for kind, source in found
    ]


async def start_trust_layer_backfill(tenant_id: UUID) -> str:
    """Start (or join) the tenant's backfill; an operator command runs this (never a person's
    request). Returns the workflow id."""
    workflow_id = backfill_workflow_id(tenant_id)
    await dispatch(
        TrustLayerBackfill,
        BackfillInput(str(tenant_id)),
        id=workflow_id,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return workflow_id

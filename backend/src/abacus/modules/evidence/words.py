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

Coordinates are page points with a top-left origin, in the same space as the server-rendered page
image: pdfplumber and PDFium both apply the page's `/Rotate`, so the client only scales
(`image_w / width_pt`). `rotation` records the `/Rotate` value (DEC-217).

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
from typing import Final, Literal, cast
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
from abacus.modules.evidence.repository import (
    get_inbox_file,
    get_version,
    insert_pages,
    pages_of,
    sources_without_words,
)
from abacus.modules.evidence.workflow_types import INBOX, VERSION, BackfillInput, UploadInput
from abacus.modules.evidence.workflows import BACKFILL_BATCH, TrustLayerBackfill

_log = get_logger(__name__)

WORDS_VERSION: Final = "w1"
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


def _rotation(value: object) -> int:
    turned = int(cast(int, value or 0)) % 360
    return turned if turned in (0, 90, 180, 270) else 0


def _page_words(number: int, page: object) -> PageWords:
    width, height = _pt(getattr(page, "width", 0)), _pt(getattr(page, "height", 0))
    rotation = _rotation(getattr(page, "rotation", 0))
    if not (_side(width) and _side(height)):
        # A hostile or broken MediaBox (zero, negative, tiny or past PDF's limit): unreadable,
        # recorded without a text layer, with geometry the table can hold (security review).
        return PageWords(number, _clamped(width), _clamped(height), rotation, ())
    found = cast(list[dict[str, object]], page.extract_words(keep_blank_chars=False))  # type: ignore[attr-defined]  # pdfplumber Page
    words: list[Word] = []
    for raw in found:
        text = _clean(raw.get("text"))
        if not text:
            continue
        box = (_pt(raw.get("x0")), _pt(raw.get("top")), _pt(raw.get("x1")), _pt(raw.get("bottom")))
        if not all(math.isfinite(v) for v in box):
            continue
        x0, top = max(0.0, box[0]), max(0.0, box[1])
        x1, bottom = min(width, box[2]), min(height, box[3])
        if x1 < x0 or bottom < top:
            continue  # a box outside the page: nothing a reader could see
        words.append(Word(text, x0, top, x1, bottom))
        if len(words) >= MAX_PAGE_WORDS:
            break
    return PageWords(number, width, height, rotation, tuple(words))


def _reason(exc: BaseException) -> str:
    from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect

    causes = (exc, *exc.args, exc.__cause__)
    if any(isinstance(c, (PDFPasswordIncorrect, PDFEncryptionError)) for c in causes):
        return "encrypted"
    return "damaged"


def extract_words(content: bytes, media_type: str) -> WordLayer:
    """In-process (tests, and inside the isolated child): a PDF's words page by page."""
    if media_type != PDF:
        return WordLayer("not_applicable")
    if is_active(content):  # DEC-296 (ED-021): kept, never read for words
        return WordLayer("not_applicable", "active_content")
    import pdfplumber

    try:
        pdf = pdfplumber.open(io.BytesIO(content))
    except Exception as exc:  # a damaged or hostile file: pdfminer raises many kinds
        return WordLayer("unreadable", _reason(exc))
    with pdf:
        try:
            if getattr(pdf.doc, "encryption", None) is not None:
                return WordLayer("unreadable", "encrypted")
            count = len(pdf.pages)
            pages = tuple(
                _page_words(n, page) for n, page in enumerate(pdf.pages[:MAX_PAGES], start=1)
            )
        except Exception as exc:
            return WordLayer("unreadable", _reason(exc))
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
        raise NotFound("upload")
    if source.media_type != PDF:
        return 0
    stored = storage.StoredObject(
        source.storage_key, source.storage_version_id, source.fingerprint, source.size_bytes
    )
    content = await storage.get(tenant_id, stored)
    layer = await asyncio.to_thread(extract_words_isolated, content, source.media_type)
    if layer.status != "extracted":
        _log.info("upload.words_skipped", kind=given.kind, reason=layer.reason)
        return 0
    objects = [
        await storage.put(tenant_id, layer_document(page)) if page.words else None
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

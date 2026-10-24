"""Evidence's built-in citation verifiers: `document_text`, `sheet_cell` and `request_item`
(P-03-T06; ADR-166 §§2-5, ADR-066; DEC-218, DEC-219). PROTECTED.

Every verifier first authorises the actor on the anchor's engagement (`evidence.read`, or
`request_item.read`): an anchor with no engagement, or an actor refused there, is
`source_not_visible` before any source is read; a source that isn't in that engagement is
`source_not_found`, exactly as if it didn't exist (security review).

- **`document_text`** `{evidence_version_id, page, bbox?, annotation_id?}`: the page and its
  words come from the word layer (P-03-T05); a version with no layer, or a page the layer has no
  words for, is read from the extraction's page text, where a quote can still be verified but no
  region resolved (`verify_on_layer`). A claim with nothing to check (no box, quote or value) is
  `locator_invalid`. `annotation_id` is reserved (K-03) and must be null.
- **`sheet_cell`** `{evidence_version_id, sheet?, cell, value?}`: the extraction's table (a single
  sheet may be named or not); the quote must be in the cell contiguously on word boundaries, the
  value must equal its amount.
- **`request_item`** `{request_item_id}`: the item exists in the anchor's engagement.

Each derives the `match_id` (C4 §3.1) and renders `title` and `loc` by code. Verification reads
the words as stored; once P-03-T13 records PII regions, it reads the masked projection instead.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from abacus.kernel.classification import classified
from abacus.kernel.db import transaction_context
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import UnitOfWork
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.citations.matching import (
    Box,
    Reason,
    amount,
    cell_reason,
    cell_text,
    verify_on_layer,
)
from abacus.modules.evidence.citations.registry import (
    Anchor,
    CitationClaim,
    Display,
    Verdict,
    register_citable,
    unverifiable,
)
from abacus.modules.evidence.models import EvidenceVersion
from abacus.modules.evidence.processing import document_text
from abacus.modules.evidence.repository import get_item, get_version, newest_extraction, pages_of
from abacus.modules.evidence.words import WORDS_VERSION, read_page_layer
from abacus.modules.identity.api import Actor, Forbidden, authorise
from abacus.modules.requests.api import item_ref

VERIFIER_VERSION: Final = "v1"
_CELL = r"^[A-Z]{1,3}[1-9][0-9]{0,6}$"
Rect = Annotated[list[float], Field(min_length=4, max_length=4)]


class DocumentTextLocator(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_version_id: Annotated[UUID, classified("internal")]
    page: Annotated[int, Field(ge=1, le=5000), classified("internal")]
    bbox: Annotated[Rect | None, classified("internal")] = None
    annotation_id: Annotated[None, classified("internal")] = None  # reserved for K-03


class SheetCellLocator(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_version_id: Annotated[UUID, classified("internal")]
    sheet: Annotated[str | None, Field(max_length=120), classified("confidential")] = None
    cell: Annotated[str, Field(pattern=_CELL), classified("internal")]
    value: Annotated[str | None, Field(max_length=200), classified("confidential")] = None


class RequestItemLocator(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request_item_id: Annotated[UUID, classified("internal")]


def _pt(value: float) -> str:
    """A coordinate in a match id: one decimal, no trailing zeros (`72`, `84.3`)."""
    return f"{round(value, 1):g}"


def document_match_id(version_id: UUID, page: int, box: Box | None) -> str:
    """`ev:<version>#p<page>:<x0>,<top>,<x1>,<bottom>` (C4 §3.1), without the box when the
    region didn't resolve."""
    base = f"ev:{version_id}#p{page}"
    return base if box is None else f"{base}:{','.join(_pt(v) for v in box)}"


def sheet_match_id(version_id: UUID, sheet_index: int, cell: str) -> str:
    """`<file>!<cell>` (C4 §3.1); a workbook's later sheets are told apart by index."""
    return f"{version_id}!{cell}" if sheet_index == 0 else f"{version_id}.s{sheet_index}!{cell}"


def _value(raw: str | None) -> Decimal | str | None:
    """A cited value as a number; the claim's text when it isn't one (it can't match)."""
    if raw is None:
        return None
    found = amount(raw)
    return found if found is not None else raw


async def _authorised(actor: Actor, anchor: Anchor, action: str) -> Reason | None:
    """The actor may `action` on the anchor's engagement, or `source_not_visible` (an anchor
    with no engagement, an engagement outside the actor's reach, a wall). Checked before any
    source is read, so a refused actor learns nothing about it (security review)."""
    if anchor.engagement_id is None:
        return "source_not_visible"
    try:
        engagement = await get_ref(actor, anchor.engagement_id)
        await authorise(actor, action, engagement.resource())
    except (NotFound, Forbidden):
        return "source_not_visible"
    return None


async def _version(
    tx: UnitOfWork, actor: Actor, version_id: UUID, anchor: Anchor
) -> tuple[EvidenceVersion | None, Reason | None]:
    """The cited version, read only after the actor is allowed `evidence.read` on the anchor's
    engagement; a version that isn't in that engagement is `source_not_found`, as if absent."""
    refused = await _authorised(actor, anchor, "evidence.read")
    if refused is not None:
        return None, refused
    version = await get_version(tx.session, version_id)
    if version is None or version.engagement_id != anchor.engagement_id:
        return None, "source_not_found"
    return version, None


async def _extracted_text(
    tx: UnitOfWork, version_id: UUID
) -> tuple[dict[int, str], dict[str, tuple[tuple[str, ...], ...]]]:
    row = await newest_extraction(tx.session, evidence_version_id=version_id)
    if row is None:
        return {}, {}
    tenant = await transaction_context(tx.session)
    return await document_text(tenant.tenant_id, row)


def _round(box: Box) -> list[float]:
    return [round(v, 2) for v in box]


async def verify_document_text(
    tx: UnitOfWork, actor: Actor, claim: CitationClaim, anchor: Anchor
) -> Verdict:
    try:
        locator = DocumentTextLocator.model_validate(dict(claim.locator))
    except ValidationError:
        return unverifiable(claim)
    source = ("evidence_version", locator.evidence_version_id)
    kept = locator.model_dump(mode="json")
    version, refused = await _version(tx, actor, locator.evidence_version_id, anchor)
    if version is None:
        return Verdict(refused, *source, kept)
    number = str(version.version_no)
    found = _value(claim.value)
    if isinstance(found, str):
        return Verdict("value_mismatch", *source, kept, number)
    box: Box | None = None
    if locator.bbox is not None:
        box = (locator.bbox[0], locator.bbox[1], locator.bbox[2], locator.bbox[3])
    tenant = await transaction_context(tx.session)
    pages = await pages_of(
        tx.session, evidence_version_id=version.id, extractor_version=WORDS_VERSION
    )
    page = next((p for p in pages if p.page_no == locator.page), None)
    if pages and page is None:
        return Verdict("page_not_found", *source, kept, number)
    words = (await read_page_layer(tenant.tenant_id, page)).words if page is not None else ()
    if words:
        text = " ".join(w.text for w in words)
    else:
        # No words for this page in the layer (no layer yet, or text only PDFium reads): the
        # extraction's page text verifies the quote; no region resolves (AC-3).
        text_pages, _ = await _extracted_text(tx, version.id)
        if page is None and locator.page not in text_pages:
            return Verdict("page_not_found", *source, kept, number)
        if page is not None and box is not None:
            return Verdict("bbox_mismatch", *source, kept, number)  # a box on a wordless page
        text, box = text_pages.get(locator.page, ""), None
    verdict = verify_on_layer(words, text, box=box, quote=claim.quote, value=found)
    if verdict.reason is not None:
        return Verdict(verdict.reason, *source, kept, number)
    kept["bbox"] = _round(verdict.box) if verdict.box is not None else None
    return Verdict(
        None,
        *source,
        kept,
        number,
        document_match_id(version.id, locator.page, verdict.box),
        verdict.sha256,
        verdict.value_text,
    )


async def verify_sheet_cell(
    tx: UnitOfWork, actor: Actor, claim: CitationClaim, anchor: Anchor
) -> Verdict:
    try:
        locator = SheetCellLocator.model_validate(dict(claim.locator))
    except ValidationError:
        return unverifiable(claim)
    source = ("evidence_version", locator.evidence_version_id)
    kept = locator.model_dump(mode="json")
    version, refused = await _version(tx, actor, locator.evidence_version_id, anchor)
    if version is None:
        return Verdict(refused, *source, kept)
    found = _value(claim.value if claim.value is not None else locator.value)
    _, sheets = await _extracted_text(tx, version.id)
    names = list(sheets)
    name = locator.sheet or ""
    if name not in sheets and locator.sheet is None and len(sheets) == 1:
        name = names[0]  # one sheet: its name may be left out
    rows = sheets.get(name)
    text = cell_text(rows, locator.cell) if rows is not None else None
    if isinstance(found, str):
        reason: Reason | None = "cell_not_found" if text is None else "value_mismatch"
    else:
        reason = cell_reason(
            text,
            amount(text) if text is not None else None,
            claim.quote,
            found,
            quote_rule="contiguous",
        )
    if reason is not None:
        return Verdict(reason, *source, kept, str(version.version_no))
    return Verdict(
        None,
        *source,
        kept,
        str(version.version_no),
        sheet_match_id(version.id, names.index(name), locator.cell),
        None,
        text[:200] if found is not None and text else None,
    )


async def verify_request_item(
    tx: UnitOfWork, actor: Actor, claim: CitationClaim, anchor: Anchor
) -> Verdict:
    try:
        locator = RequestItemLocator.model_validate(dict(claim.locator))
    except ValidationError:
        return unverifiable(claim)
    source = ("request_item", locator.request_item_id)
    kept = locator.model_dump(mode="json")
    refused = await _authorised(actor, anchor, "request_item.read")
    if refused is not None:
        return Verdict(refused, *source, kept)
    try:
        item = await item_ref(tx, locator.request_item_id)
    except NotFound:
        return Verdict("source_not_found", *source, kept)
    if item.engagement_id != anchor.engagement_id:
        return Verdict("source_not_found", *source, kept)
    return Verdict(None, *source, kept, None, f"req:{item.id}")


# --- Display: rendered by code from the locator (INV-2) ----------------------------------------


async def _file_title(tx: UnitOfWork, version_id: object) -> str:
    try:
        version = await get_version(tx.session, UUID(str(version_id)))
    except ValueError:
        version = None
    item = await get_item(tx.session, version.evidence_item_id) if version is not None else None
    return item.title if item is not None else "Document"


async def display_document_text(tx: UnitOfWork, locator: Mapping[str, object]) -> Display:
    return Display(
        await _file_title(tx, locator.get("evidence_version_id")), f"p. {locator.get('page')}"
    )


async def display_sheet_cell(tx: UnitOfWork, locator: Mapping[str, object]) -> Display:
    sheet, cell = locator.get("sheet"), locator.get("cell")
    loc = f"{sheet} · {cell}" if sheet else str(cell)
    return Display(await _file_title(tx, locator.get("evidence_version_id")), loc)


async def display_request_item(tx: UnitOfWork, locator: Mapping[str, object]) -> Display:
    return Display("Request item", "")


register_citable(
    "document_text", verify_document_text, display_document_text, version=VERIFIER_VERSION
)
register_citable("sheet_cell", verify_sheet_cell, display_sheet_cell, version=VERIFIER_VERSION)
register_citable(
    "request_item", verify_request_item, display_request_item, version=VERIFIER_VERSION
)

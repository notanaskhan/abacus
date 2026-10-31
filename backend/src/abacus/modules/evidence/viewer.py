"""The source viewer's reads: manifest, masked pages, regions and in-document search (P-03-T09;
C4 §3.3, §3.4; SPEC-322 AC-16, AC-21, AC-22, AC-24; ADR-110, ADR-052; DEC-266). PROTECTED.

- **Who:** a client principal is refused before anything is read (INV-4: 403). The version is
  read through `visible(evidence.read)` on its engagement, so an invisible, walled or other-firm
  version answers 404 with no count (AC-22, DEC-43); then `evidence.read` is authorised on its
  request item with the item's client facts, as every evidence content read is.
- **Geometry and mask tokens only, never text:** the manifest carries page sizes from the word
  layer and the rendition, which pages were scanned for PII, and each detected region as a box
  and its token. Search returns page rects, never words, and the query is never logged or kept.
- **Fail closed on unscanned pages (`projection`):** a page no PII scan covers is never searched;
  with no scanned text page at all, search answers 409 `preview_outdated`, as the pages do.
  Search needs 3 characters, reads at most 50 pages and counts at most 1,000 hits a call.
- **Masked renditions only (AC-24; P-03-T15):** a page is served only from a preview with
  `mask_version` set, which `masked_previews` burns in the isolated child. A version with only a
  pre-masking preview reads `processing` with reason `preview_outdated` and its pages answer 409
  `preview_outdated` until the backfill re-renders it. Pages without a PII scan read
  `not_scannable` (fail closed), never clean, and are refused to a reader who may not read
  unmasked content (an offshore member or a run acting for one; AC-30, DEC-52): 403.
- **Unlocked files (P-03-T19):** a password-protected version that a person unlocked has an
  `evidence_derivations` row; its manifest, pages, text and search read that derivation's word
  layer, PII scan and masked rendition (made by the same code as any upload's) and carry its
  `derivation_id`. A `password_protected` manifest offers `evidence.unlock` to a person who holds
  it while `evidence.viewer_unlock` is on.
- **Access logging:** a page image is content, and search hits are positions of content (an
  oracle for it): each read leaves an `evidence_content.read` access event (who, which version;
  never the query) before it is answered, and nothing is answered if logging fails (Q-02-T20).
  The manifest and regions carry geometry only and log nothing beyond the route's check.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final, cast
from uuid import UUID

from sqlalchemy import select

from abacus.kernel._flags import EVIDENCE_PII_REVEAL, EVIDENCE_VIEWER_UNLOCK
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence import storage
from abacus.modules.evidence.access import record_content_read
from abacus.modules.evidence.citations.matching import Box, line_rects, normalised, quote_spans
from abacus.modules.evidence.extraction import ACTIVE_CONTENT
from abacus.modules.evidence.masked_previews import PreviewOutdated
from abacus.modules.evidence.masked_text import masked_pages
from abacus.modules.evidence.masking import mask_token
from abacus.modules.evidence.models import EvidencePage, EvidenceVersion, PiiRegion
from abacus.modules.evidence.pii import DETECTOR_VERSION, masked_rows
from abacus.modules.evidence.previews import MASKED_RENDERER_VERSION, PAGE_WIDTH, RENDERER_VERSION
from abacus.modules.evidence.processing import document_text
from abacus.modules.evidence.projection import projection_of
from abacus.modules.evidence.repository import (
    current_derivation,
    get_item,
    masked_preview_for,
    newest_extraction,
    not_withdrawn,
    pages_of,
    pii_regions_of,
    preview_for,
    preview_page,
    preview_pages_of,
    verified_citations_into,
)
from abacus.modules.evidence.uploads import (
    _authorised_any_version,  # pyright: ignore[reportPrivateUsage] -- the module's own check
)
from abacus.modules.evidence.words import WORDS_VERSION, read_page_layer
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    allowed_actions,
    may_read_unmasked,
    visible,
)

READ: Final = "evidence.read"
REVEAL: Final = "pii.reveal"
UNLOCK: Final = "evidence.unlock"
MAX_HITS: Final = 200
# Search costs (security review #4): every searched page is a sealed object decrypted per call.
MIN_QUERY: Final = 3  # characters, after normalising
MAX_SEARCH_PAGES: Final = 50  # the rendition's page cap (previews.MAX_PAGES)
MAX_COUNTED: Final = 1000  # hits counted for `total`; more is `truncated`
MAX_REGIONS: Final = 200
PDF: Final = "application/pdf"
# A preview made without masks: every reason a kind-`none` preview can carry, by C4 status.
_PASSWORD: Final = frozenset({"encrypted"})
_NOT_PREVIEWABLE: Final = frozenset({"not_previewable"})


class ActiveContent(DomainConflict):
    """A PDF with active content is kept but never shown (DEC-296, ED-021): every viewer read
    refuses it, whatever was derived before the rule existed."""

    code = "active_content"


@dataclass(frozen=True)
class ViewerPage:
    n: int
    width_pt: float
    height_pt: float
    rotation: int
    image_w: int
    image_h: int
    text_layer: bool
    pii_scan: str  # done | not_scannable


@dataclass(frozen=True)
class ViewerMask:
    id: UUID
    page: int
    rect: list[float]
    kind: str
    display: str


@dataclass(frozen=True)
class ViewerManifest:
    evidence_version_id: UUID
    file_name: str
    media_type: str
    status: str
    reason: str | None
    kind: str
    page_count: int
    truncated: bool
    pages: list[ViewerPage] = field(default_factory=list[ViewerPage])
    pii_masks: list[ViewerMask] = field(default_factory=list[ViewerMask])
    derivation_id: UUID | None = None
    allowed_actions: list[str] = field(default_factory=list[str])
    # How this reader sees the pages (Ayush, 2026-10-26; DEC-369): `images`, or `text` (the
    # masked text projection, `viewer_text`) for a reader who may not read unmasked content.
    view: str = "images"


@dataclass(frozen=True)
class ViewerRegion:
    match_id: str
    page: int | None
    rects: list[list[float]]
    sheet: str | None
    cell: str | None
    citation_id: UUID | None
    label: str | None


@dataclass(frozen=True)
class SearchHit:
    page: int
    rects: list[list[float]]


@dataclass(frozen=True)
class SearchResult:
    items: list[SearchHit]
    total: int
    truncated: bool


async def visible_version(ctx: AuthContext, version_id: UUID) -> EvidenceVersion:
    """The version, for a person who may read its content (404 when invisible or walled, 403
    for a client principal or a role without `evidence.read`)."""
    if ctx.client:
        raise Forbidden(READ, "role")  # INV-4: clients hold no C4 action
    engagement = EvidenceVersion.engagement_id.expression
    async with tenant_session(ctx.tenant) as session:
        version = (
            await session.execute(
                select(EvidenceVersion).where(
                    EvidenceVersion.id == version_id,
                    visible(ctx, READ, engagement),
                    not_withdrawn(),  # P-06-T19: a withdrawn upload is as if it never arrived
                )
            )
        ).scalar_one_or_none()
    if version is None:
        raise NotFound("evidence_version")
    await _authorised_any_version(ctx, version.engagement_id, version.id)
    if version.media_type == PDF:
        async with tenant_session(ctx.tenant) as session:
            extracted = await newest_extraction(session, evidence_version_id=version.id)
        if extracted is not None and extracted.reason == ACTIVE_CONTENT:
            raise ActiveContent
    return version


def _box(region: PiiRegion) -> Box:
    b = region.bbox
    return (float(b[0]), float(b[1]), float(b[2]), float(b[3]))


def _status(
    kind: str, reason: str | None, *, layered: bool, masked: bool, media_type: str
) -> tuple[str, str | None]:
    """The manifest's status from the preview, the word layer and the masked rendition."""
    if kind == "none":
        if reason in _PASSWORD:
            return "password_protected", reason
        if reason in _NOT_PREVIEWABLE:
            return "not_previewable", reason
        return "unreadable", reason
    if kind == "table":
        return "ready", None
    if media_type == PDF and not layered:
        return "processing", "words_pending"
    if not masked:
        return "processing", "preview_outdated"  # only a pre-masking preview (DEC-266)
    return "ready", None


async def _offered(
    ctx: AuthContext, version: EvidenceVersion, *, masked: bool, locked: bool
) -> list[str]:
    """`pii.reveal` when the version has a masked value, the reveal flag is on and every layer
    but fresh MFA allows it (P-03-T16; AC-28: an offshore member, a client principal or a role
    without it gets no chip); MFA is stepped up when the person acts. `evidence.unlock` when the
    version is password-protected, the unlock flag is on and the person holds it (P-03-T19)."""
    wanted: list[str] = []
    if masked and await flag_enabled(ctx.tenant, EVIDENCE_PII_REVEAL):
        wanted.append(REVEAL)
    if locked and not ctx.client and await flag_enabled(ctx.tenant, EVIDENCE_VIEWER_UNLOCK):
        wanted.append(UNLOCK)
    if not wanted:
        return []
    engagement = await get_ref(ctx, version.engagement_id)
    held = set(await allowed_actions(ctx, engagement.resource(), tuple(wanted)))
    return [a for a in wanted if a in held]


async def _derivation_of(ctx: AuthContext, version_id: UUID) -> UUID | None:
    """The version's current unlock derivation (P-03-T19): what the viewer reads in its place."""
    async with tenant_session(ctx.tenant) as session:
        found = await current_derivation(session, version_id)
    return found.id if found is not None else None


async def viewer_manifest(ctx: AuthContext, version_id: UUID) -> ViewerManifest:
    """SHL-08's manifest: geometry and mask tokens only (AC-16)."""
    version = await visible_version(ctx, version_id)
    derived = await _derivation_of(ctx, version.id)
    async with tenant_session(ctx.tenant) as session:
        item = await get_item(session, version.evidence_item_id)
        preview = await preview_for(
            session, evidence_version_id=version.id, renderer_version=RENDERER_VERSION
        )
        masked = await masked_preview_for(
            session, version.id, renderer_version=MASKED_RENDERER_VERSION, derivation_id=derived
        )
        layer: Sequence[EvidencePage] = await pages_of(
            session,
            evidence_version_id=version.id,
            extractor_version=WORDS_VERSION,
            derivation_id=derived,
        )
        regions = await pii_regions_of(
            session,
            evidence_version_id=version.id,
            detector_version=DETECTOR_VERSION,
            derivation_id=derived,
        )
        projection = await projection_of(
            session, evidence_version_id=version.id, derivation_id=derived
        )
        rendered = masked or preview
        images = (
            {p.page_no: p for p in await preview_pages_of(session, rendered.id)}
            if rendered is not None
            else {}
        )
    file_name = item.title if item is not None else "Document"
    source = masked or preview
    if source is None:
        return ViewerManifest(
            version.id,
            file_name,
            version.media_type,
            "processing",
            None,
            "none",
            0,
            False,
            view="images" if await may_read_unmasked(ctx) else "text",
        )
    status, reason = _status(
        source.kind,
        source.reason,
        layered=bool(layer),
        masked=masked is not None,
        media_type=version.media_type,
    )
    pages: list[ViewerPage] = []
    for page in layer:
        width, height = float(page.width_pt), float(page.height_pt)
        image = images.get(page.page_no)
        pages.append(
            ViewerPage(
                n=page.page_no,
                width_pt=width,
                height_pt=height,
                rotation=page.rotation,
                image_w=image.width if image else PAGE_WIDTH,
                image_h=image.height if image else round(height * PAGE_WIDTH / width),
                text_layer=page.has_text_layer,
                pii_scan=projection.scan_state(page.page_no),
            )
        )
    if not layer and source.kind == "image":
        image = images.get(1)
        if image is not None:  # an image has no points: its pixels are its geometry
            pages.append(
                ViewerPage(
                    1,
                    float(image.width),
                    float(image.height),
                    0,
                    image.width,
                    image.height,
                    False,
                    projection.scan_state(1),
                )
            )
    masks = [
        ViewerMask(r.id, r.page_no, list(_box(r)), r.kind, mask_token(r.kind, r.last4))
        for r in regions
    ]
    return ViewerManifest(
        evidence_version_id=version.id,
        file_name=file_name,
        media_type=version.media_type,
        status=status,
        reason=reason,
        kind=source.kind,
        page_count=source.page_count,
        truncated=source.truncated,
        pages=pages,
        pii_masks=masks,
        derivation_id=derived,
        allowed_actions=await _offered(
            ctx, version, masked=bool(masks), locked=status == "password_protected"
        ),
        view="images" if await may_read_unmasked(ctx) else "text",
    )


async def viewer_page(ctx: AuthContext, version_id: UUID, page_no: int) -> bytes:
    """One masked page image (AC-24): 409 `preview_outdated` while only a pre-masking preview
    exists, 404 when nothing is rendered; the read is logged before the bytes leave. A reader who
    may not read unmasked content (an offshore member) gets no page image at all, whatever the
    scan found (Ayush, 2026-10-26: masked text only until OCR, P-11; DEC-369): 403 before
    anything is read. They read `viewer_text` instead."""
    version = await visible_version(ctx, version_id)
    if not await may_read_unmasked(ctx):
        raise Forbidden(READ, "condition")
    return await _masked_page(ctx, version, page_no)


async def signer_page(ctx: AuthContext, version_id: UUID, page_no: int) -> bytes:
    """N-02-T23 (DEC-1283): one masked page of a document a client is asked to sign, for POR-06's
    review. Called only by signatures' portal, which has already proved the person is the
    envelope's named signer under `portal_envelopes.read` (`scope_only`); a firm principal is
    refused here. The masked rendition only, the read logged before the bytes leave, as above."""
    if not ctx.client:
        raise Forbidden(READ, "role")
    async with tenant_session(ctx.tenant) as session:
        version = (
            await session.execute(
                select(EvidenceVersion).where(EvidenceVersion.id == version_id, not_withdrawn())
            )
        ).scalar_one_or_none()
    if version is None:
        raise NotFound("evidence_version")
    return await _masked_page(ctx, version, page_no)


async def _masked_page(ctx: AuthContext, version: EvidenceVersion, page_no: int) -> bytes:
    derived = await _derivation_of(ctx, version.id)
    async with tenant_session(ctx.tenant) as session:
        masked = await masked_preview_for(
            session, version.id, renderer_version=MASKED_RENDERER_VERSION, derivation_id=derived
        )
        if masked is None:
            legacy = await preview_for(
                session, evidence_version_id=version.id, renderer_version=RENDERER_VERSION
            )
            if legacy is not None and legacy.kind in ("pages", "image"):
                raise PreviewOutdated
            raise NotFound("preview_page")
        page = await preview_page(session, masked.id, page_no)
    if page is None:
        raise NotFound("preview_page")
    await record_content_read(ctx, version.engagement_id, "evidence_version", version.id)
    stored = storage.StoredObject(
        page.storage_key, page.storage_version_id, page.fingerprint, page.size_bytes
    )
    return await storage.get(ctx.tenant_id, stored)


@dataclass(frozen=True)
class TextPage:
    page: int
    text: str  # masked, then the kernel TIN scrub
    unread: bool  # the page shows content no scan read (no text layer, pictures, shapes)


@dataclass(frozen=True)
class TextSheet:
    name: str
    rows: list[list[str]]
    withheld: bool = False  # review M-A: the sheet exists but its cells aren't shown


@dataclass(frozen=True)
class ViewerText:
    items: list[TextPage]
    sheets: list[TextSheet]
    truncated: bool


async def viewer_text(ctx: AuthContext, version_id: UUID) -> ViewerText:
    """The masked text projection, page by page (Ayush, 2026-10-26: what an offshore reader sees
    until OCR, P-11; DEC-369): each page's upright words with every detected region replaced by
    its token and the kernel TIN scrub applied (as agents read it); a page no scan covers has no
    text; `unread` marks a page that shows content no scan read. A workbook's cells are masked
    by `pii.masked_rows` as onshore agent material is; to a reader who may not read unmasked
    content a sheet is `withheld` (its name only), as their agents get no sheet (review M-A). At
    most `MAX_SEARCH_PAGES` pages; a PDF with text pages and no PII scan yet answers 409
    `preview_outdated` (fail closed). Logged as a content read before it is answered."""
    version = await visible_version(ctx, version_id)
    derived = await _derivation_of(ctx, version.id)
    async with tenant_session(ctx.tenant) as session:
        layer = await pages_of(
            session,
            evidence_version_id=version.id,
            extractor_version=WORDS_VERSION,
            derivation_id=derived,
        )
        projection = await projection_of(
            session, evidence_version_id=version.id, derivation_id=derived
        )
        extracted = await newest_extraction(session, evidence_version_id=version.id)
    texts = [p for p in layer if p.has_text_layer]
    if texts and not any(projection.readable(p.page_no) for p in texts):
        raise PreviewOutdated  # not scanned for PII yet: never read raw
    # The same masked text agents read (`masked_text.masked_pages`), so the two never drift.
    masked = (
        await masked_pages(ctx.tenant, evidence_version_id=version.id, derivation_id=derived) or {}
    )
    items = [
        TextPage(p.page_no, masked.get(p.page_no, ""), not projection.complete(p.page_no))
        for p in layer[:MAX_SEARCH_PAGES]
    ]
    if not layer and version.media_type != PDF and version.media_type.startswith("image/"):
        items.append(TextPage(1, "", True))  # a picture: nothing a scan read
    sheets: list[TextSheet] = []
    if extracted is not None:
        _pages, raw = await document_text(ctx.tenant_id, extracted)
        if await may_read_unmasked(ctx):
            sheets = [
                TextSheet(name, [list(row) for row in masked_rows(rows)])
                for name, rows in raw.items()
            ]
        else:
            # Review M-A: cells are masked by heuristic, so a reader who may not read unmasked
            # content gets a sheet's name only, as agents acting for them get no sheet at all.
            sheets = [TextSheet(name, [], withheld=True) for name in raw]
    await record_content_read(ctx, version.engagement_id, "evidence_version", version.id)
    return ViewerText(items, sheets, len(layer) > MAX_SEARCH_PAGES)


def _rect(raw: object) -> list[float] | None:
    if not isinstance(raw, list) or len(cast(list[object], raw)) != 4:
        return None
    try:
        return [float(cast(float, v)) for v in cast(list[object], raw)]
    except (TypeError, ValueError):
        return None


async def viewer_regions(
    ctx: AuthContext, version_id: UUID, match_ids: Sequence[str] | None
) -> list[ViewerRegion]:
    """Where the version's verified citations sit, in page points (AC3.1, AC3.6): one region a
    match, from its first citation; a sheet cell as `{sheet, cell}`. Every verified region the
    reader may see when no matches are named (auto-highlight)."""
    version = await visible_version(ctx, version_id)
    async with tenant_session(ctx.tenant) as session:
        rows = await verified_citations_into(session, ctx, version.id, match_ids)
    values_shown = await may_read_unmasked(ctx)  # a printed value is raw (DEC-52; TASK-1207)
    regions: dict[str, ViewerRegion] = {}
    for row in rows:
        match = row.match_id
        if match is None or match in regions or len(regions) >= MAX_REGIONS:
            continue
        locator = row.locator
        if row.kind == "sheet_cell":
            sheet, cell = locator.get("sheet"), locator.get("cell")
            regions[match] = ViewerRegion(
                match,
                None,
                [],
                sheet if isinstance(sheet, str) else None,
                cell if isinstance(cell, str) else None,
                row.id,
                row.value_text if values_shown else None,
            )
            continue
        page = locator.get("page")
        rect = _rect(locator.get("bbox"))
        regions[match] = ViewerRegion(
            match,
            page if isinstance(page, int) and not isinstance(page, bool) else None,
            [rect] if rect is not None else [],  # no box: highlighted by quote search (AC-3)
            None,
            None,
            row.id,
            row.value_text if values_shown else None,
        )
    return list(regions.values())


async def viewer_search(ctx: AuthContext, version_id: UUID, query: str) -> SearchResult:
    """Hits of `query` in the version's masked word layer, as page rects (AC-21): whole words,
    contiguous, at most `MAX_HITS` returned and `MAX_COUNTED` counted, over at most
    `MAX_SEARCH_PAGES` pages. Only pages a PII scan covers are searched (fail closed): when the
    version has text pages and none is scanned, 409 `preview_outdated`, as its pages answer; a
    skipped page marks the result `truncated`. A query under `MIN_QUERY` characters reads
    nothing. The search is logged as a content read (who, which version), never the query."""
    version = await visible_version(ctx, version_id)
    if len(normalised(query)) < MIN_QUERY:
        return SearchResult([], 0, False)
    derived = await _derivation_of(ctx, version.id)
    async with tenant_session(ctx.tenant) as session:
        layer = await pages_of(
            session,
            evidence_version_id=version.id,
            extractor_version=WORDS_VERSION,
            derivation_id=derived,
        )
        projection = await projection_of(
            session, evidence_version_id=version.id, derivation_id=derived
        )
    texts = [p for p in layer if p.has_text_layer]
    readable = [p for p in texts if projection.readable(p.page_no)]
    if texts and not readable:
        raise PreviewOutdated  # nothing scanned for PII yet: never searched raw
    searched = readable[:MAX_SEARCH_PAGES]
    skipped = len(texts) > len(searched)
    hits: list[SearchHit] = []
    total = 0
    for page in searched:
        words = projection.words((await read_page_layer(ctx.tenant_id, page)).words, page.page_no)
        if words is None:  # unreachable: `searched` holds readable pages only
            continue
        runs = quote_spans(words, query, limit=MAX_COUNTED - total + 1)
        total += len(runs)
        for run in runs:
            if len(hits) < MAX_HITS:
                hits.append(SearchHit(page.page_no, [list(r) for r in line_rects(run)]))
        if total > MAX_COUNTED:
            skipped, total = True, MAX_COUNTED
            break
    if searched:
        # Hit positions are content: the read is logged first (who, which version; no query).
        await record_content_read(ctx, version.engagement_id, "evidence_version", version.id)
    return SearchResult(hits, total, skipped or total > len(hits))


__all__ = [
    "MAX_HITS",
    "PreviewOutdated",
    "SearchHit",
    "SearchResult",
    "ViewerManifest",
    "ViewerMask",
    "ViewerPage",
    "ViewerRegion",
    "viewer_manifest",
    "viewer_page",
    "viewer_regions",
    "viewer_search",
    "viewer_text",
    "visible_version",
]


async def readable_version(ctx: AuthContext, version_id: UUID) -> bool:
    """For a screening record's evidence link (P-07-T36 review, DEC-375): the version exists and
    the person may read its content. A PDF with active content is still a readable record."""
    try:
        await visible_version(ctx, version_id)
    except ActiveContent:
        return True
    except (NotFound, Forbidden):
        return False
    return True

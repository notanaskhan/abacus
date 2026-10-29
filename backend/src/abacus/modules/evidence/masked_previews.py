"""Masked renditions: the only page images any route serves (P-03-T15; SPEC-322 AC-24, AC-30;
P-03 §4.4, §4.5; ADR-110, DEC-52, DEC-369). PROTECTED.

`upload_processing` v7 (`patched("masked_preview")`) runs `masked_preview_upload` after the PII
scan, in place of the unmasked `upload.preview` for new runs; the trust-layer backfill runs it for
uploads made before masking existed. The file is rendered in the isolated child with every
detected region burned in opaque (`previews.render_masked_isolated`), and one `upload_previews`
row with `mask_version` set records the PNGs. The unmasked bitmap never leaves the child.

Fail closed:
- a PDF rendition with pages but no PII scan run (by `DETECTOR_VERSION`) is never stored: its
  text might hold an identifier no box covers (`unscanned`; the backfill tries again);
- a page the scan could not read (no text layer) is rendered without boxes and reads
  `not_scannable` in the viewer, which an offshore reader is refused (AC-30);
- an image (no text layer until P-11's OCR), a table or a `none` result is stored with no boxes;
- nothing is derived from a withdrawn version (DEC-298) or an active-content PDF (DEC-296).

Idempotent on (source, `MASKED_RENDERER_VERSION`). Identifiers in, a kind out; region values are
never read here (only their boxes), and nothing about a page's content is logged.
"""

from __future__ import annotations

import asyncio
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.evidence import storage
from abacus.modules.evidence.intake_sources import source_of, target_type
from abacus.modules.evidence.object_keys import under_key
from abacus.modules.evidence.pii import DETECTOR_VERSION
from abacus.modules.evidence.previews import (
    MASK_VERSION,
    MASKED_RENDERER_VERSION,
    PDF,
    Box,
    render_masked_isolated,
)
from abacus.modules.evidence.repository import (
    insert_preview,
    insert_preview_pages,
    is_withdrawn,
    newest_extraction,
    pages_of,
    pii_regions_of,
    preview_for,
    scan_run_for,
    sources_without_masks,
)
from abacus.modules.evidence.words import WORDS_VERSION
from abacus.modules.evidence.workflow_types import (
    INBOX,
    INTAKE,
    VERSION,
    BackfillInput,
    UploadInput,
)
from abacus.modules.evidence.workflows import BACKFILL_BATCH

_log = get_logger(__name__)

UNSCANNED: Final = "unscanned"
WITHDRAWN: Final = "withdrawn"
ACTIVE_CONTENT: Final = "active_content"


class PreviewOutdated(DomainConflict):
    """The page was rendered before masking existed: it is never served (SPEC-322 AC-24) until
    the backfill re-renders it."""

    code = "preview_outdated"


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "evidence.upload_processing")


async def masked_preview_upload(given: UploadInput) -> str:
    """The `upload.masked_preview` activity's body: one upload's masked rendition; returns its
    kind, or `unscanned` when a PDF's pages can't be masked yet. Idempotent."""
    tenant_id, source_id = UUID(given.tenant_id), UUID(given.source_id)
    tenant = _system(tenant_id)
    version_id = source_id if given.kind == VERSION else None
    inbox_id = source_id if given.kind == INBOX else None
    attachment_id = source_id if given.kind == INTAKE else None
    async with tenant_session(tenant) as session:
        done = await preview_for(
            session,
            evidence_version_id=version_id,
            inbox_file_id=inbox_id,
            inbox_attachment_id=attachment_id,
            renderer_version=MASKED_RENDERER_VERSION,
        )
        if done is not None:
            return done.kind
        source = await source_of(session, tenant, given.kind, source_id)
        if source is None:
            if version_id is not None and await is_withdrawn(session, version_id):
                return WITHDRAWN  # DEC-298: nothing is derived from a withdrawn version
            raise NotFound("upload")
        extraction = await newest_extraction(
            session,
            evidence_version_id=version_id,
            inbox_file_id=inbox_id,
            inbox_attachment_id=attachment_id,
        )
        if extraction is not None and extraction.reason == ACTIVE_CONTENT:
            return "none"  # DEC-296: kept, never rendered
        run = await scan_run_for(
            session,
            evidence_version_id=version_id,
            inbox_file_id=inbox_id,
            inbox_attachment_id=attachment_id,
            detector_version=DETECTOR_VERSION,
        )
        layer = await pages_of(
            session,
            evidence_version_id=version_id,
            inbox_file_id=inbox_id,
            inbox_attachment_id=attachment_id,
            extractor_version=WORDS_VERSION,
        )
        regions = await pii_regions_of(
            session,
            evidence_version_id=version_id,
            inbox_file_id=inbox_id,
            inbox_attachment_id=attachment_id,
            detector_version=DETECTOR_VERSION,
        )
    masks: dict[int, list[Box]] = {}
    for region in regions:
        b = region.bbox
        masks.setdefault(region.page_no, []).append(
            (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
        )
    sizes = {p.page_no: (float(p.width_pt), float(p.height_pt)) for p in layer}
    stored = storage.StoredObject(
        source.storage_key, source.storage_version_id, source.fingerprint, source.size_bytes
    )
    rendered = await asyncio.to_thread(
        render_masked_isolated,
        await storage.get(tenant_id, stored),
        source.media_type,
        masks,
        sizes,
    )
    if rendered.pages and source.media_type == PDF and run is None:
        # A PDF's pages may hold text no scan has read: never stored, never served.
        _log.info("upload.masked_preview_unscanned", kind=given.kind)
        return UNSCANNED
    under = under_key(source)
    pages = [await storage.put(tenant_id, page.png, under=under) for page in rendered.pages]
    async with uow(tenant) as tx:
        row = await insert_preview(
            tx.session,
            tenant_id=tenant_id,
            engagement_id=source.engagement_id,
            evidence_version_id=version_id,
            inbox_file_id=inbox_id,
            inbox_attachment_id=attachment_id,
            renderer_version=MASKED_RENDERER_VERSION,
            mask_version=MASK_VERSION,
            kind=rendered.kind,
            reason=rendered.reason,
            page_count=len(pages),
            truncated=rendered.truncated,
        )
        if row is not None:
            await insert_preview_pages(
                tx.session,
                [
                    {
                        "tenant_id": tenant_id,
                        "preview_id": row.id,
                        "page_no": n,
                        "storage_key": put.key,
                        "storage_version_id": put.version_id,
                        "fingerprint": put.fingerprint,
                        "size_bytes": put.size,
                        "width": page.width,
                        "height": page.height,
                    }
                    for n, (put, page) in enumerate(zip(pages, rendered.pages, strict=True), 1)
                ],
            )
        # A concurrent run that got there first adds nothing: still one audited write.
        tx.record(
            "upload.masked_previewed" if row is not None else "upload.masked_preview_exists",
            target=Target(target_type(given.kind), source_id),
            after=Ref(pages=len(pages), masks=sum(len(b) for b in masks.values())),
        )
    _log.info("upload.masked_previewed", kind=given.kind, pages=len(pages))
    return rendered.kind


async def pending_masks(given: BackfillInput) -> list[UploadInput]:
    """The `trust_layer.pending_masks` activity's body: the backfill's next batch, versions then
    inbox files by id after the cursors, extracted and without a masked rendition."""
    tenant_id = UUID(given.tenant_id)
    async with tenant_session(_system(tenant_id)) as session:
        found = await sources_without_masks(
            session,
            MASKED_RENDERER_VERSION,
            after_version=UUID(given.after_version) if given.after_version else None,
            after_inbox=UUID(given.after_inbox) if given.after_inbox else None,
            limit=BACKFILL_BATCH,
        )
    return [
        UploadInput(
            given.tenant_id, VERSION if kind == "version" else INBOX, str(source), announce=False
        )
        for kind, source in found
    ]


__all__ = ["UNSCANNED", "PreviewOutdated", "masked_preview_upload", "pending_masks"]


async def intake_masked_pages(tenant: TenantContext, attachment_id: UUID) -> int | None:
    """N-01-T13: the page count of an intake attachment's masked rendition; None until
    AttachmentTriage has made it (the viewer then shows nothing, never an unmasked page)."""
    async with tenant_session(tenant) as session:
        found = await preview_for(
            session, inbox_attachment_id=attachment_id, renderer_version=MASKED_RENDERER_VERSION
        )
    return None if found is None else found.page_count

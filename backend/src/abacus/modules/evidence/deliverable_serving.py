"""C10's serving (R-02-T07; R-02 §3.15 AC-38 to AC-41; ADR-104, DEC-509; red zone).

Three calls, each for a client person `reporting.api.reader_version` already admitted (an
audience grant on a published, unwithdrawn version; `NotFound` for every other principal), handed
over as a `ServableVersion`:

- `deliverable_page`: one stored page as a PNG, rendered from the version's own bytes (the C11
  render, sealed in evidence). A draft is served only when it is a C11 draft-mode render, which
  C11 always draws with the DRAFT mark on every page: no code path returns an unwatermarked draft
  byte (AC-38). Each page writes one `access_events` row (`deliverable.page_view`).
- `issue_deliverable_download`: a single-use link valid 60 seconds, bound to the tenant (RLS), the
  person (0712's CHECK), the deliverable version and its evidence version. ADR-104 keeps object
  keys and presigned URLs out of every answer, so the URL is the API's own file route carrying
  the link id (DEC-509's pattern). One `access_events` row (`deliverable.download`) per issue.
- `open_deliverable_download`: the link's bytes, once, before expiry, for the person it was
  issued to; `deliverable.downloaded` is audited in the same unit of work that uses the link.

K-1s and tax deliverables are marked `tri` on their access rows (C19). URLs never appear in a log
line, notification or email: callers return them in the response body only.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.access import AccessSubject, record_reads, register_access_kind
from abacus.kernel.errors import NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.pdf_pages import PagePng, render_page_isolated
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.evidence import storage
from abacus.modules.evidence.item_detail import Download, download_name
from abacus.modules.evidence.service import version_view
from abacus.modules.identity.api import AuthContext

PAGE_VIEW: Final = "deliverable.page_view"
DOWNLOAD: Final = "deliverable.download"
FILE_ROUTE: Final = "/v1/portal/deliverable-files/{link_id}"
register_access_kind(PAGE_VIEW)
register_access_kind(DOWNLOAD)
_log = get_logger(__name__)


@dataclass(frozen=True)
class ServableVersion:
    """What reporting's reader check hands over for one admitted version (evidence never reads
    reporting's tables; `reporting.api.ReaderVersion.servable()` builds this)."""

    version_id: UUID
    version_no: int
    evidence_version_id: UUID
    is_draft: bool
    watermarked: bool
    page_count: int
    title: str
    client_id: UUID
    engagement_id: UUID | None
    work_item_id: UUID | None
    tri: bool
    contact_id: UUID


@dataclass(frozen=True)
class PageImage:
    content: bytes
    media_type: str
    page: int
    page_count: int


@dataclass(frozen=True)
class IssuedDownload:
    link_id: UUID
    url: str
    expires_at: datetime


def _servable(reader: ServableVersion) -> None:
    """A draft that is not a C11 draft-mode render is never served, page or file (AC-18, AC-38)."""
    if reader.is_draft and not reader.watermarked:
        _log.error("deliverable.draft_without_watermark", version_id=str(reader.version_id))
        raise NotFound("deliverable")


def _subject(reader: ServableVersion) -> AccessSubject:
    return AccessSubject(
        subject_type="deliverable_version",
        subject_id=reader.version_id,
        client_id=reader.client_id,
        engagement_id=reader.engagement_id,
        work_item_id=reader.work_item_id,
    )


def _flags(reader: ServableVersion) -> tuple[str, ...]:
    return ("tri",) if reader.tri else ()


async def _bytes(ctx: AuthContext, evidence_version_id: UUID) -> tuple[bytes, str]:
    view = await version_view(ctx.tenant, evidence_version_id)
    try:
        content = await storage.get(ctx.tenant_id, view.stored)
    except storage.IntegrityError:
        _log.error("deliverable.integrity_failed", evidence_version_id=str(evidence_version_id))
        raise NotFound("deliverable") from None
    return content, view.media_type


async def deliverable_page(
    ctx: AuthContext, reader: ServableVersion, page: int, *, request_id: UUID | None = None
) -> PageImage:
    _servable(reader)
    if not 1 <= page <= reader.page_count:
        raise NotFound("deliverable_page")
    content, media_type = await _bytes(ctx, reader.evidence_version_id)
    if media_type != "application/pdf":
        raise NotFound("deliverable_page")
    found: PagePng = await asyncio.to_thread(render_page_isolated, content, page)
    if found.problem is not None or not found.png:
        raise NotFound("deliverable_page")
    await record_reads(
        ctx.tenant, PAGE_VIEW, [_subject(reader)], request_id=request_id, flags=_flags(reader)
    )
    return PageImage(found.png, "image/png", page, found.page_count)


_ISSUE = text(
    """
    INSERT INTO deliverable_download_links
        (tenant_id, deliverable_version_id, evidence_version_id, contact_id, user_id, request_id)
    VALUES (:tenant, :version, :evidence, :contact, :user, :request)
    RETURNING id, expires_at
    """
)
_USE = text(
    """
    UPDATE deliverable_download_links SET used_at = clock_timestamp()
     WHERE id = :id AND user_id = :user AND used_at IS NULL AND expires_at > clock_timestamp()
    RETURNING deliverable_version_id, evidence_version_id, contact_id
    """
)


async def issue_deliverable_download(
    ctx: AuthContext, reader: ServableVersion, *, request_id: UUID | None = None
) -> IssuedDownload:
    _servable(reader)
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                _ISSUE,
                {
                    "tenant": ctx.tenant_id,
                    "version": reader.version_id,
                    "evidence": reader.evidence_version_id,
                    "contact": reader.contact_id,
                    "user": ctx.user_id,
                    "request": request_id,
                },
            )
        ).one()
        tx.record(
            "deliverable.download_issued",
            target=Target("deliverable_version", reader.version_id),
            after=Ref(link=row.id),
            scope=_scope(reader),
        )
    await record_reads(
        ctx.tenant, DOWNLOAD, [_subject(reader)], request_id=request_id, flags=_flags(reader)
    )
    return IssuedDownload(row.id, FILE_ROUTE.format(link_id=row.id), row.expires_at)


def _scope(reader: ServableVersion) -> Scope | None:
    if reader.engagement_id is None:
        return Scope(client_id=reader.client_id)
    return Scope(engagement_id=reader.engagement_id, work_item_id=reader.work_item_id)


async def open_deliverable_download(
    ctx: AuthContext, link_id: UUID, reader: ServableVersion
) -> Download:
    """The bytes for a link issued to this person, once, inside its 60 seconds. `reader` is
    re-checked by the caller at use (an audience grant revoked since the issue answers 404)."""
    _servable(reader)
    async with uow(ctx.tenant) as tx:
        row = (await tx.session.execute(_USE, {"id": link_id, "user": ctx.user_id})).first()
        if row is None or row.deliverable_version_id != reader.version_id:
            raise NotFound("deliverable_download")
        tx.record(
            "deliverable.downloaded",
            target=Target("deliverable_version", reader.version_id),
            after=Ref(link=link_id),
            scope=_scope(reader),
        )
    content, media_type = await _bytes(ctx, row.evidence_version_id)
    return Download(
        content, media_type, download_name(reader.title, reader.version_no, None, media_type)
    )

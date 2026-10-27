"""Engagement export download (A-01-T22; SPEC-344 AC-14, AC-15; A-01 §3.6 Story 6.1, 6.4;
DEC-536, DEC-537). PROTECTED (evidence, red). Contract: `docs/contracts/engagement-export-v1.md`.

    plan = await prepare(ctx, export_id, range_header, if_range)   # authorise, decide, audit
    async for chunk in plan.stream(): ...                           # decrypted bytes, in order

- **Who, every request:** a person (never an agent, the system, support or a client: INV-1,
  INV-4), `export.download` on the export's engagement: engagement partner or manager, fresh MFA,
  independence, onshore, walls (404 behind one, before anything else is read); the
  `audits.binder_export` flag; and the requester or someone who holds `export.create` there. There
  is no presigned link and no object key in any answer (ADR-104): the API opens the sealed
  segments itself under the export's own tenant and streams the ZIP, so nothing outlives the
  request's authorisation.
- **When:** only a `ready` export (409 `export_not_ready` before); 410 `export_expired` once
  `expires_at` has passed on the business clock (whether or not the sweep has run yet), once it
  is `expired` (the 7 days, or voided by withdrawn content), and whenever any version it holds was
  withdrawn since, even before the withdrawal's subscriber has voided it (DEC-537).
- **Range (DEC-536):** one `bytes=` range: `a-b`, `a-` or the suffix `-n`. An end past the
  bundle is clamped, a suffix longer than it is the whole bundle. Several ranges, a malformed
  header, numbers longer than 19 digits, a start at or past the end or an empty suffix answer
  416 with `Content-Range: bytes */<size>` and nothing else. An `If-Range` that is not the
  bundle's ETag serves the whole bundle (200). A range of the whole bundle is still a 206.
- **Audit:** `engagement_export.downloaded` (human, with the bytes and range planned) and an
  `engagement_export_downloads` row, in one unit of work, before the first byte is sent. Each
  resumed range is its own row.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import insert, select

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.export_models import (
    EngagementExport,
    EngagementExportContent,
    EngagementExportDownload,
)
from abacus.modules.evidence.export_storage import SEGMENT_BYTES, get_segment
from abacus.modules.evidence.exports import SUBJECT, flag_on, human
from abacus.modules.evidence.withdrawals import withdrawn_among
from abacus.modules.identity.api import AuthContext, Forbidden, allowed_actions, authorise

_DOWNLOAD: Final = "export.download"
_CREATE: Final = "export.create"
# One range only, digits bounded: `bytes=a-b`, `bytes=a-`, `bytes=-n` (whitespace tolerated).
_RANGE: Final = re.compile(r"\s*bytes\s*=\s*(\d{0,19})\s*-\s*(\d{0,19})\s*")


class ExportNotReady(DomainConflict):
    """The export is not `ready` yet (queued, packaging), or never will be (undone, failed)."""

    code = "export_not_ready"


class ExportExpired(Exception):
    """410 `export_expired`: past its 7 days, voided, or holding withdrawn content."""


class RangeNotSatisfiable(Exception):
    """416: a range this API does not serve; `size` goes into `Content-Range: bytes */size`."""

    def __init__(self, size: int) -> None:
        super().__init__("range_not_satisfiable")
        self.size = size


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int  # inclusive

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def parse_range(header: str | None, size: int) -> ByteRange | None:
    """The one range asked for, within a bundle of `size` bytes; None for no `Range` header.
    Raises `RangeNotSatisfiable` for anything else (DEC-536)."""
    if header is None:
        return None
    found = _RANGE.fullmatch(header)
    if found is None or size <= 0:
        raise RangeNotSatisfiable(size)
    first, last = found.group(1), found.group(2)
    if not first and not last:
        raise RangeNotSatisfiable(size)
    if not first:  # a suffix: the last n bytes
        n = int(last)
        if n == 0:
            raise RangeNotSatisfiable(size)
        return ByteRange(max(0, size - n), size - 1)
    start = int(first)
    end = int(last) if last else size - 1
    if start >= size or end < start:
        raise RangeNotSatisfiable(size)
    return ByteRange(start, min(end, size - 1))


def etag_of(bundle_sha256: str) -> str:
    return f'"{bundle_sha256}"'


def file_name(export_id: UUID) -> str:
    """ASCII only, from the export's id: never a client's or an engagement's name."""
    return f"accrued-binder-{export_id}.zip"


@dataclass(frozen=True)
class DownloadPlan:
    tenant_id: UUID
    export_id: UUID
    size: int
    segment_count: int
    etag: str
    range: ByteRange | None

    @property
    def length(self) -> int:
        return self.range.length if self.range is not None else self.size

    def stream(self) -> AsyncIterator[bytes]:
        start = self.range.start if self.range is not None else 0
        return stream_bytes(
            self.tenant_id, self.export_id, self.size, self.segment_count, start, self.length
        )


def _geometry(size: int, segment_count: int) -> int | None:
    """The segment size when the bundle was cut at `SEGMENT_BYTES`; None otherwise (read in
    order from the first segment)."""
    expected = max(1, -(-size // SEGMENT_BYTES))
    return SEGMENT_BYTES if expected == segment_count else None


async def stream_bytes(
    tenant_id: UUID, export_id: UUID, size: int, segment_count: int, start: int, length: int
) -> AsyncIterator[bytes]:
    """`length` bytes from `start`, decrypted segment by segment (one in memory at a time). A
    segment that opens to the wrong length stops the stream (the seal already binds each one to
    its export and position)."""
    segment_size = _geometry(size, segment_count)
    first, offset = (start // segment_size, start % segment_size) if segment_size else (0, start)
    left = length
    for n in range(first, segment_count):
        if left <= 0:
            return
        chunk = await get_segment(tenant_id, export_id, n)
        if segment_size is not None:
            want = segment_size if n < segment_count - 1 else size - segment_size * n
            if len(chunk) != want:
                raise RuntimeError("an export segment opened to an unexpected length")
        if offset >= len(chunk):
            offset -= len(chunk)
            continue
        part = chunk[offset : offset + left]
        offset = 0
        left -= len(part)
        yield part
    if left > 0:
        raise RuntimeError("an export bundle ended before its recorded size")


async def _holds_withdrawn(tenant: TenantContext, export_id: UUID) -> bool:
    async with tenant_session(tenant) as session:
        versions = list(
            (
                await session.execute(
                    select(EngagementExportContent.evidence_version_id).where(
                        EngagementExportContent.export_id == export_id
                    )
                )
            )
            .scalars()
            .all()
        )
    return bool(await withdrawn_among(tenant, versions))


async def prepare(
    ctx: AuthContext, export_id: UUID, range_header: str | None, if_range: str | None
) -> DownloadPlan:
    """Authorise, decide what is served and audit it; the bytes follow from `plan.stream()`."""
    human(ctx, _DOWNLOAD)
    async with tenant_session(ctx.tenant) as session:
        row = await session.get(EngagementExport, export_id)
    if row is None:
        raise NotFound(SUBJECT)
    ref = await get_ref(ctx, row.engagement_id)  # 404 behind a wall, before anything else
    resource = replace(ref.resource(), work_item_id=row.work_item_id)
    await authorise(ctx, _DOWNLOAD, resource)
    await flag_on(ctx)
    if row.requested_by != ctx.user_id and _CREATE not in await allowed_actions(
        ctx, resource, [_CREATE]
    ):
        raise Forbidden(_DOWNLOAD, "role")
    if row.status == "expired":
        raise ExportExpired
    if row.status != "ready":
        raise ExportNotReady
    now = await clock.now(ctx.tenant)
    expires_at: datetime | None = row.expires_at
    if expires_at is None or now >= expires_at or await _holds_withdrawn(ctx.tenant, row.id):
        raise ExportExpired
    size, segments, digest = row.bytes, row.segment_count, row.bundle_sha256
    if size is None or segments is None or digest is None:
        raise ExportNotReady  # the CHECK makes a ready row carry these; fail closed regardless
    etag = etag_of(digest)
    wanted = range_header if if_range is None or if_range.strip() == etag else None
    byte_range = parse_range(wanted, size)
    if ctx.mfa_at is None:  # authorise demanded a fresh factor; the row records when
        raise Forbidden(_DOWNLOAD, "condition")
    sent = byte_range.length if byte_range is not None else size
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            insert(EngagementExportDownload).values(
                tenant_id=ctx.tenant_id,
                export_id=row.id,
                user_id=ctx.user_id,
                bytes_sent=sent,
                range_start=byte_range.start if byte_range is not None else None,
                range_end=byte_range.end if byte_range is not None else None,
                mfa_at=ctx.mfa_at,
            )
        )
        tx.record(
            "engagement_export.downloaded",
            target=Target(SUBJECT, row.id),
            after=(
                Ref(bytes=sent, range_start=byte_range.start, range_end=byte_range.end)
                if byte_range is not None
                else Ref(bytes=sent)
            ),
            scope=Scope(engagement_id=row.engagement_id, work_item_id=row.work_item_id),
        )
    return DownloadPlan(ctx.tenant_id, row.id, size, segments, etag, byte_range)


__all__ = [
    "ByteRange",
    "DownloadPlan",
    "ExportExpired",
    "ExportNotReady",
    "RangeNotSatisfiable",
    "etag_of",
    "file_name",
    "parse_range",
    "prepare",
    "stream_bytes",
]

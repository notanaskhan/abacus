"""Firm exports with dual approval: request, decide, history, link and download (Q-02-T43;
DEC-72, conflict C-11; DEC-508, DEC-509). PROTECTED (evidence, red). Contract:
`docs/contracts/compliance-kernel.md` §2 to §7.

- **Request** (`firm_export.request`, a security admin with a fresh second factor, an
  `Idempotency-Key`): the export of everything the firm holds, `awaiting_approval`, naming the
  approver, who must be someone else holding `firm_export.approve` now (a security admin or a
  partner-level member): 422 `approver_invalid` otherwise. The database refuses the same again:
  the requester-insert trigger binds the row to the person acting and checks both memberships,
  and a CHECK keeps the two people apart.
- **Decide** (`firm_export.approve`, fresh MFA): only the named approver approves (`building`,
  the outbox starts `FirmExportWorkflow`) or declines. The requester answers 409
  `approver_must_differ` and anyone else 403, both before the status is read; a decided export is
  409 `export_not_awaiting_approval`; a requester who is no longer an active security admin is 409
  `requester_not_active` (two current people stand behind every approval). The guard trigger
  binds the decision to the named approver as the session's person, and re-checks both
  memberships.
- **Link** (`firm_export.download`, fresh MFA, not offshore; the requester or the approver): a
  15-minute link inside the 7-day window (`available_until`; 410 `export_expired` from then on,
  on whichever of the business and system clocks is later; 409 `export_not_ready` before the
  archive is built). The link is a path, not a presigned URL (ADR-104, DEC-509): it opens only for
  the signed-in person it was issued to, who is re-authorised when it is opened. The first link
  marks the export `downloaded`; every link is audited `firm_export.downloaded` and recorded in
  `firm_export_links` (at most `LINK_LIMIT` an hour per person, 429).
- **Download** (`prepare`): the archive streamed from its sealed segments with the engagement
  export's machinery (one `Range`, 1 MiB slices, a re-check before every segment after the
  first, at most `MAX_STREAMS` open streams per person in a process and `DOWNLOAD_LIMIT` requests
  per person a minute across processes, counted over `firm_export_downloads`), audited
  `firm_export.streamed` with a `firm_export_downloads` row. An expired link answers 410
  `link_expired`. Neither audit event carries the link's id: the link rows hold it.

Every route refuses a non-person first (INV-1), then authorises on the firm, then the flag.
Nothing here logs a link (Restricted) or a decline reason.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel import clock
from abacus.kernel._flags import COMPLIANCE_FIRM_EXPORT
from abacus.kernel.clock import system_now
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, uow
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.evidence.export_download import (
    DOWNLOAD_LIMIT,
    DOWNLOAD_WINDOW_SECONDS,
    MAX_STREAMS,
    DownloadPlan,
    DownloadRateLimited,
    DownloadRevoked,
    ExportExpired,
    ExportNotReady,
    etag_of,
    parse_range,
    streams_open,
)
from abacus.modules.evidence.exports import authorise_fresh, human
from abacus.modules.evidence.firm_export_events import FirmExportApproved, FirmExportRequested
from abacus.modules.evidence.firm_export_models import (
    FirmExport,
    FirmExportDownload,
    FirmExportLink,
)
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    member_could,
    names_of,
)

SUBJECT: Final = "firm_export"
HISTORY_LIMIT: Final = 12
WINDOW: Final = timedelta(days=7)  # `firm_export_link_days`: links can be made for 7 days
LINK_LIFETIME: Final = timedelta(minutes=15)
LINK_LIMIT: Final = 20  # links per person per hour
LINK_WINDOW_SECONDS: Final = 3600
LINKABLE: Final = ("ready", "downloaded")
_READ: Final = "firm_export.read"
_REQUEST: Final = "firm_export.request"
_APPROVE: Final = "firm_export.approve"
_DOWNLOAD: Final = "firm_export.download"
_LOCK_PERSON = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))")
_RECENT_LINKS = text(
    "SELECT count(*) AS n, min(issued_at) AS oldest, clock_timestamp() AS now "
    "FROM firm_export_links WHERE user_id = :user "
    "AND issued_at > clock_timestamp() - make_interval(secs => :window)"
)
_RECENT_DOWNLOADS = text(
    "SELECT count(*) AS n, min(at) AS oldest, clock_timestamp() AS now "
    "FROM firm_export_downloads WHERE user_id = :user "
    "AND at > clock_timestamp() - make_interval(secs => :window)"
)


class ApproverInvalid(DomainInvalid):
    """The approver is the requester, or holds no security-admin or partner-level membership."""

    code = "approver_invalid"


class ApproverMustDiffer(DomainConflict):
    """The person who approves is never the person who asked (AC-37, DEC-50; DEC-72)."""

    code = "approver_must_differ"


class ExportNotAwaitingApproval(DomainConflict):
    """The export was already approved or declined."""

    code = "export_not_awaiting_approval"


class RequesterNotActive(DomainConflict):
    """The requester is no longer an active security admin: the export can't be approved."""

    code = "requester_not_active"


class LinkExpired(Exception):
    """410 `link_expired`: the 15 minutes passed; ask for a new link."""


@dataclass(frozen=True)
class NamedUser:
    user_id: UUID
    display_name: str


@dataclass(frozen=True)
class FirmExportView:
    id: UUID
    status: str
    scope: str
    origin: str
    requested_by: NamedUser
    requested_at: datetime
    approver: NamedUser
    decided_at: datetime | None
    ready_at: datetime | None
    available_until: datetime | None
    size_bytes: int | None
    manifest_sha256: str | None


@dataclass(frozen=True)
class FirmExportLinkView:
    url: str  # Restricted: never logged
    expires_at: datetime
    manifest_sha256: str


def _firm(ctx: AuthContext) -> Resource:
    return Resource.firm(ctx.tenant_id)


async def _flag_on(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, COMPLIANCE_FIRM_EXPORT):
        raise NotFound(COMPLIANCE_FIRM_EXPORT.name)


async def _may(ctx: AuthContext, action: str) -> None:
    """INV-1, then the action on the firm (fresh MFA where the matrix asks), then the flag."""
    human(ctx, action)
    await authorise_fresh(ctx, action, _firm(ctx))
    await _flag_on(ctx)


def past_window(available_until: datetime | None, business_now: datetime) -> bool:
    """Past the 7 days once either clock has passed `available_until` (as DEC-546 for binders):
    a business clock held behind never keeps an archive available past the real window."""
    return available_until is None or max(business_now, system_now()) >= available_until


def link_url(export_id: UUID, link_id: UUID) -> str:
    return f"/v1/firm/data-exports/{export_id}/links/{link_id}"


def file_name(export_id: UUID) -> str:
    """ASCII only, from the export's id: never the firm's name."""
    return f"accrued-firm-export-{export_id}.zip"


async def _locked(session: AsyncSession, export_id: UUID) -> FirmExport | None:
    return await session.scalar(
        select(FirmExport)
        .where(FirmExport.id == export_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _refused(exc: DBAPIError) -> Exception | None:
    """The database's own refusals, as the service's answers."""
    said = str(exc.orig)
    if "approver_must_differ" in said:
        return ApproverMustDiffer()
    if "approver_invalid" in said:
        return ApproverInvalid(facts={"field": "approver_user_id"})
    if "requester_not_active" in said:
        return RequesterNotActive()
    return None


# --- request ---------------------------------------------------------------------------------


async def request(
    ctx: AuthContext, approver_user_id: UUID, *, idempotency_key: str
) -> FirmExportView:
    """ADM-06 b and g: `awaiting_approval`, naming a second, distinct person; a retried key
    returns the same export."""
    await _may(ctx, _REQUEST)
    if approver_user_id == ctx.user_id or not await member_could(
        ctx.tenant_id, approver_user_id, _APPROVE, _firm(ctx), waive_fresh_mfa=True
    ):
        raise ApproverInvalid(facts={"field": "approver_user_id"})

    async def run() -> tuple[int, dict[str, object]]:
        export_id = await _write(ctx, approver_user_id)
        return 202, {"export_id": str(export_id)}

    stored = await idempotent(
        ctx.tenant,
        route="firm_export.request",
        key=idempotency_key,
        body={"approver_user_id": str(approver_user_id), "scope": "all"},
        run=run,
    )
    return await read(ctx, UUID(str(stored.body["export_id"])))


async def _write(ctx: AuthContext, approver_user_id: UUID) -> UUID:
    if ctx.mfa_at is None:  # authorise demanded a fresh factor; the row records when
        raise Forbidden(_REQUEST, "condition")
    export_id = uuid4()
    try:
        async with uow(ctx.tenant) as tx:
            await tx.session.execute(
                insert(FirmExport).values(
                    id=export_id,
                    tenant_id=ctx.tenant_id,
                    scope="all",
                    origin="on_demand",
                    requested_by=ctx.user_id,
                    requested_by_kind="human",
                    request_mfa_at=ctx.mfa_at,
                    approver_id=approver_user_id,
                )
            )
            tx.record(
                "firm_export.requested",
                target=Target(SUBJECT, export_id),
                after=Ref(approver=approver_user_id),
            )
            tx.emit(
                FirmExportRequested(
                    export_id=export_id,
                    requested_by=ctx.user_id,
                    approver_user_id=approver_user_id,
                )
            )
    except DBAPIError as exc:
        refused = _refused(exc)
        if refused is not None:
            raise refused from None
        raise
    return export_id


# --- decide ----------------------------------------------------------------------------------


async def respond(
    ctx: AuthContext, export_id: UUID, *, approve: bool, reason: str | None = None
) -> FirmExportView:
    """ADM-06 f: the named approver approves (`building`) or declines (`declined`)."""
    await _may(ctx, _APPROVE)
    if ctx.mfa_at is None:
        raise Forbidden(_APPROVE, "condition")
    try:
        async with uow(ctx.tenant) as tx:
            row = await _locked(tx.session, export_id)
            if row is None:
                raise NotFound(SUBJECT)
            if row.requested_by == ctx.user_id:
                raise ApproverMustDiffer
            if row.approver_id != ctx.user_id:
                raise Forbidden(_APPROVE, "role")
            if row.status != "awaiting_approval":
                raise ExportNotAwaitingApproval
            if approve and not await member_could(
                ctx.tenant_id, row.requested_by, _REQUEST, _firm(ctx), waive_fresh_mfa=True
            ):
                raise RequesterNotActive
            values: dict[str, object] = {
                "status": "building" if approve else "declined",
                "decided_by": ctx.user_id,
                "decided_at": await clock.now(ctx.tenant),
                "decided_mfa_at": ctx.mfa_at,
            }
            if not approve and reason:
                values["decline_reason"] = reason
            await tx.session.execute(
                update(FirmExport)
                .where(FirmExport.id == row.id, FirmExport.status == "awaiting_approval")
                .values(**values)
            )
            fields = {
                "export_id": row.id,
                "requested_by": row.requested_by,
                "approver_user_id": row.approver_id,
            }
            if approve:
                tx.record(
                    "firm_export.approved",
                    target=Target(SUBJECT, row.id),
                    after=Ref(requested_by=row.requested_by),
                )
                tx.emit(FirmExportApproved(**fields))
            else:
                tx.record(
                    "firm_export.declined",
                    target=Target(SUBJECT, row.id),
                    after=Ref(requested_by=row.requested_by),
                )
    except DBAPIError as exc:
        refused = _refused(exc)
        if refused is not None:
            raise refused from None
        raise
    return await read(ctx, export_id)


# --- reads -----------------------------------------------------------------------------------


async def _views(rows: list[FirmExport]) -> list[FirmExportView]:
    if not rows:
        return []
    names = await names_of(sorted({r.requested_by for r in rows} | {r.approver_id for r in rows}))
    return [
        FirmExportView(
            id=r.id,
            status=r.status,
            scope=r.scope,
            origin=r.origin,
            requested_by=NamedUser(r.requested_by, names.get(r.requested_by, "")),
            requested_at=r.requested_at,
            approver=NamedUser(r.approver_id, names.get(r.approver_id, "")),
            decided_at=r.decided_at,
            ready_at=r.ready_at,
            available_until=r.available_until,
            size_bytes=r.bytes,
            manifest_sha256=r.manifest_sha256,
        )
        for r in rows
    ]


async def read(ctx: AuthContext, export_id: UUID) -> FirmExportView:
    await _may(ctx, _READ)
    async with tenant_session(ctx.tenant) as session:
        row = await session.get(FirmExport, export_id, populate_existing=True)
    if row is None:
        raise NotFound(SUBJECT)
    [view] = await _views([row])
    return view


async def recent_exports(ctx: AuthContext) -> list[FirmExportView]:
    """ADM-06 a and c: the last 12, newest first."""
    await _may(ctx, _READ)
    async with tenant_session(ctx.tenant) as session:
        rows = list(
            (
                await session.execute(
                    select(FirmExport)
                    .order_by(FirmExport.requested_at.desc(), FirmExport.id.desc())
                    .limit(HISTORY_LIMIT)
                )
            )
            .scalars()
            .all()
        )
    return await _views(rows)


# --- link ------------------------------------------------------------------------------------


async def issue_link(ctx: AuthContext, export_id: UUID) -> FirmExportLinkView:
    """A 15-minute link for the requester or the approver inside the 7 days."""
    await _may(ctx, _DOWNLOAD)
    if ctx.mfa_at is None:
        raise Forbidden(_DOWNLOAD, "condition")
    link_id = uuid4()
    async with uow(ctx.tenant) as tx:
        row = await _locked(tx.session, export_id)
        if row is None:
            raise NotFound(SUBJECT)
        if ctx.user_id not in (row.requested_by, row.approver_id):
            raise Forbidden(_DOWNLOAD, "role")
        business_now = await clock.now(ctx.tenant)
        if row.status == "expired" or (
            row.status in LINKABLE and past_window(row.available_until, business_now)
        ):
            raise ExportExpired
        manifest, available_until = row.manifest_sha256, row.available_until
        if row.status not in LINKABLE or manifest is None or available_until is None:
            raise ExportNotReady  # a linkable row carries both (CHECK); fail closed regardless
        await tx.session.execute(
            _LOCK_PERSON, {"key": f"firm_export_link:{ctx.tenant_id}:{ctx.user_id}"}
        )
        recent = (
            await tx.session.execute(
                _RECENT_LINKS, {"user": ctx.user_id, "window": LINK_WINDOW_SECONDS}
            )
        ).one()
        if int(recent.n) >= LINK_LIMIT:
            elapsed = (recent.now - recent.oldest).total_seconds()
            raise DownloadRateLimited(
                facts={
                    "limit": LINK_LIMIT,
                    "retry_after": max(1, math.ceil(LINK_WINDOW_SECONDS - elapsed)),
                }
            )
        # The link's 15 minutes run on the database's clock, from the transaction's instant (the
        # row's `issued_at`), as its CHECK and its use do.
        expires_at = await tx.session.scalar(
            insert(FirmExportLink)
            .values(
                id=link_id,
                tenant_id=ctx.tenant_id,
                export_id=row.id,
                user_id=ctx.user_id,
                expires_at=func.least(func.now() + LINK_LIFETIME, available_until),
                mfa_at=ctx.mfa_at,
            )
            .returning(FirmExportLink.expires_at)
        )
        if expires_at is None:  # RETURNING always answers; fail closed regardless
            raise ExportNotReady
        if row.status == "ready":
            await tx.session.execute(
                update(FirmExport)
                .where(FirmExport.id == row.id, FirmExport.status == "ready")
                .values(status="downloaded", downloaded_at=business_now)
            )
        tx.record("firm_export.downloaded", target=Target(SUBJECT, row.id))
    return FirmExportLinkView(link_url(export_id, link_id), expires_at, manifest)


# --- download --------------------------------------------------------------------------------


async def prepare(
    ctx: AuthContext,
    export_id: UUID,
    link_id: UUID,
    range_header: str | None,
    if_range: str | None,
) -> DownloadPlan:
    """Authorise the person and the link, decide what is served and audit it; the bytes follow
    from `plan.stream()`."""
    await _may(ctx, _DOWNLOAD)
    async with tenant_session(ctx.tenant) as session:
        link = await session.get(FirmExportLink, link_id)
        row = await session.get(FirmExport, export_id, populate_existing=True)
        db_now = await session.scalar(select(func.clock_timestamp()))
    if (
        link is None
        or row is None
        or link.export_id != row.id
        or link.user_id != ctx.user_id
        or ctx.user_id not in (row.requested_by, row.approver_id)
    ):
        raise NotFound("firm_export_link")
    if row.status == "expired" or (
        row.status in LINKABLE and past_window(row.available_until, await clock.now(ctx.tenant))
    ):
        raise ExportExpired
    if db_now is None or db_now >= link.expires_at:  # the database's clock, as at issue
        raise LinkExpired
    if row.status not in LINKABLE:
        raise ExportNotReady
    if streams_open(ctx.tenant_id, ctx.user_id) >= MAX_STREAMS:
        raise DownloadRateLimited(facts={"limit": MAX_STREAMS, "retry_after": 30})
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
        # One person's archive requests are counted one at a time, across processes (as M2).
        await tx.session.execute(
            _LOCK_PERSON, {"key": f"firm_export_download:{ctx.tenant_id}:{ctx.user_id}"}
        )
        recent = (
            await tx.session.execute(
                _RECENT_DOWNLOADS, {"user": ctx.user_id, "window": DOWNLOAD_WINDOW_SECONDS}
            )
        ).one()
        if int(recent.n) >= DOWNLOAD_LIMIT:
            elapsed = (recent.now - recent.oldest).total_seconds()
            raise DownloadRateLimited(
                facts={
                    "limit": DOWNLOAD_LIMIT,
                    "retry_after": max(1, math.ceil(DOWNLOAD_WINDOW_SECONDS - elapsed)),
                }
            )
        await tx.session.execute(
            insert(FirmExportDownload).values(
                tenant_id=ctx.tenant_id,
                export_id=row.id,
                link_id=link.id,
                user_id=ctx.user_id,
                bytes_sent=sent,
                range_start=byte_range.start if byte_range is not None else None,
                range_end=byte_range.end if byte_range is not None else None,
                mfa_at=ctx.mfa_at,
            )
        )
        tx.record(
            "firm_export.streamed",
            target=Target(SUBJECT, row.id),
            after=(
                Ref(bytes=sent, range_start=byte_range.start, range_end=byte_range.end)
                if byte_range is not None
                else Ref(bytes=sent)
            ),
        )
    firm = _firm(ctx)

    async def guard() -> None:
        """Still within the window, still built, and the person still holds the download."""
        async with tenant_session(ctx.tenant) as session:
            now_row = await session.get(FirmExport, export_id, populate_existing=True)
        if (
            now_row is None
            or now_row.status not in LINKABLE
            or past_window(now_row.available_until, await clock.now(ctx.tenant))
            or _DOWNLOAD not in await allowed_actions(ctx, firm, [_DOWNLOAD])
        ):
            raise DownloadRevoked("no longer downloadable")

    return DownloadPlan(
        ctx.tenant_id,
        row.id,
        size,
        segments,
        etag,
        byte_range,
        ctx.user_id,
        guard,
        kind="firm_export",
    )


__all__ = [
    "HISTORY_LIMIT",
    "LINK_LIFETIME",
    "WINDOW",
    "ApproverInvalid",
    "ApproverMustDiffer",
    "ExportNotAwaitingApproval",
    "FirmExportLinkView",
    "FirmExportView",
    "LinkExpired",
    "RequesterNotActive",
    "file_name",
    "issue_link",
    "past_window",
    "prepare",
    "read",
    "recent_exports",
    "request",
    "respond",
]

"""Firm export with dual approval: the routes (Q-02-T38 contract; Q-02-T43 live; compliance-kernel
v1.3; DEC-72, conflict C-11). Contract: `docs/contracts/compliance-kernel.md` §2 to §4. The
service is `firm_exports.py`, the build `firm_export_activities.py`.

For G-02's ADM-06 (b, c, f, g). Behind `compliance.firm_export` (off: 404):

- `GET /v1/firm/data-exports` (`firm_export.read`): the last 12, newest first (the export card
  and the history tray).
- `POST /v1/firm/data-exports` (`firm_export.request`, fresh MFA, `Idempotency-Key`): a security
  admin asks for an export and names the partner-level approver, who must be someone else (422
  `approver_invalid`). 202, `awaiting_approval`.
- `POST /v1/firm/data-exports/{export_id}/approve` and `/decline` (`firm_export.approve`, fresh
  MFA): the named approver decides; the requester can't (409 `approver_must_differ`), a decided
  export answers 409 `export_not_awaiting_approval`.
- `POST /v1/firm/data-exports/{export_id}/link` (`firm_export.download`, fresh MFA): a 15-minute
  link while the 7-day window holds (410 `export_expired` after it); requester or approver only.
- `GET /v1/firm/data-exports/{export_id}/links/{link_id}` (`firm_export.download`): the link
  itself: the archive streamed from its sealed segments for the person it was issued to (no
  presigned URL, ADR-104, DEC-509), resumable with one `Range`; 410 `link_expired` after its 15
  minutes, `export_expired` after the 7 days.

Status codes are this contract's (`FirmExportStatus`); their words ("Waiting for approval ·
Margaret Okonkwo") are G-02's screen copy. Sizes are bytes; a size or a link exists only once
the archive is built.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Header
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.text import SingleLineText
from abacus.modules.evidence import export_download, firm_exports
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
# ADR-139: a request starts a workflow and notifies the approver, so it carries a key.
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]

FirmExportStatus = Literal[
    "awaiting_approval", "declined", "building", "ready", "downloaded", "expired", "failed"
]
# v1 exports everything the firm holds (ADM-06 b "Export all firm data?"): one A-01 package per
# engagement plus a firm index. Narrower scopes are additive later.
FirmExportScope = Literal["all"]
FirmExportOrigin = Literal["on_demand", "scheduled"]

router = AbacusRouter(prefix="/v1/firm/data-exports", tags=["firm export"])


class FirmExportRequestIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    approver_user_id: Annotated[UUID, classified("internal")]
    scope: Annotated[FirmExportScope, classified("internal")] = "all"


class FirmExportDeclineIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    reason: Annotated[
        SingleLineText | None, Field(default=None, max_length=500), classified("confidential")
    ]


class FirmExportPersonOut(BaseModel):
    """A person named on the export, for the card's line ("Waiting for approval · Margaret
    Okonkwo"); the id links to ADM-02."""

    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]


class FirmExportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    status: Annotated[FirmExportStatus, classified("internal")]
    scope: Annotated[FirmExportScope, classified("internal")]
    origin: Annotated[FirmExportOrigin, classified("internal")]
    requested_by: Annotated[FirmExportPersonOut, classified("internal")]
    requested_at: Annotated[datetime, classified("internal")]
    approver: Annotated[FirmExportPersonOut, classified("internal")]
    decided_at: Annotated[datetime | None, classified("internal")] = None
    ready_at: Annotated[datetime | None, classified("internal")] = None
    # The 7-day window in which links can be made (`firm_export_link_days`).
    available_until: Annotated[datetime | None, classified("internal")] = None
    size_bytes: Annotated[int | None, Field(ge=0), classified("internal")] = None
    manifest_sha256: Annotated[
        str | None, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")
    ] = None


class FirmExportPageOut(BaseModel):
    """The last 12 exports, newest first."""

    model_config = ConfigDict(frozen=True)

    items: Annotated[list[FirmExportOut], Field(max_length=12), classified("internal")]


class FirmExportLinkOut(BaseModel):
    """A download link for 15 minutes: the API path of the archive for the signed-in person it
    was issued to (DEC-509: no presigned URL). Restricted (it opens the firm's whole archive) and
    never logged."""

    model_config = ConfigDict(frozen=True)

    url: Annotated[str, classified("restricted")]
    expires_at: Annotated[datetime, classified("internal")]
    manifest_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]


def _person(p: firm_exports.NamedUser) -> FirmExportPersonOut:
    return FirmExportPersonOut(user_id=p.user_id, display_name=p.display_name)


def _out(v: firm_exports.FirmExportView) -> FirmExportOut:
    return FirmExportOut(
        id=v.id,
        status=cast(FirmExportStatus, v.status),
        scope=cast(FirmExportScope, v.scope),
        origin=cast(FirmExportOrigin, v.origin),
        requested_by=_person(v.requested_by),
        requested_at=v.requested_at,
        approver=_person(v.approver),
        decided_at=v.decided_at,
        ready_at=v.ready_at,
        available_until=v.available_until,
        size_bytes=v.size_bytes,
        manifest_sha256=v.manifest_sha256,
    )


def _no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _gone(detail: str) -> Response:
    return _no_store(JSONResponse({"detail": detail}, status_code=410))


@router.get("", action="firm_export.read", response_model=FirmExportPageOut)
async def list_firm_exports_route(ctx: Ctx) -> FirmExportPageOut:
    """ADM-06 a and c: the export card and the history tray."""
    return FirmExportPageOut(items=[_out(v) for v in await firm_exports.recent_exports(ctx)])


@router.post(
    "",
    action="firm_export.request",
    response_model=FirmExportOut,
    status_code=202,
)
async def request_firm_export_route(
    body: FirmExportRequestIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FirmExportOut:
    """ADM-06 b and g: `awaiting_approval`; 422 `approver_invalid` when the approver is the
    requester or holds no partner-level membership. Audited `firm_export.requested`."""
    return _out(
        await firm_exports.request(ctx, body.approver_user_id, idempotency_key=idempotency_key)
    )


@router.post(
    "/{export_id}/approve",
    action="firm_export.approve",
    response_model=FirmExportOut,
    errors=(409,),
)
async def approve_firm_export_route(export_id: UUID, ctx: Ctx) -> FirmExportOut:
    """ADM-06 f: the named approver starts the build (`building`). 409 `approver_must_differ` for
    the requester, `export_not_awaiting_approval` once decided. Audited `firm_export.approved`."""
    return _out(await firm_exports.respond(ctx, export_id, approve=True))


@router.post(
    "/{export_id}/decline",
    action="firm_export.approve",
    response_model=FirmExportOut,
    errors=(409,),
)
async def decline_firm_export_route(
    export_id: UUID, body: FirmExportDeclineIn, ctx: Ctx
) -> FirmExportOut:
    """The named approver declines (`declined`); the same 409s as approve. Audited
    `firm_export.declined`."""
    return _out(await firm_exports.respond(ctx, export_id, approve=False, reason=body.reason))


@router.post(
    "/{export_id}/link",
    action="firm_export.download",
    response_model=FirmExportLinkOut,
    errors=(409, 410, 429),
)
async def link_firm_export_route(export_id: UUID, ctx: Ctx) -> FirmExportLinkOut | Response:
    """A 15-minute link for the requester or the approver while the archive is `ready` or
    `downloaded` (409 `export_not_ready` before); 410 `export_expired` after the 7 days. Audited
    `firm_export.downloaded`."""
    try:
        link = await firm_exports.issue_link(ctx, export_id)
    except export_download.ExportExpired:
        return _gone("export_expired")
    return FirmExportLinkOut(
        url=link.url, expires_at=link.expires_at, manifest_sha256=link.manifest_sha256
    )


@router.get(
    "/{export_id}/links/{link_id}",
    action="firm_export.download",
    response_model=bytes,
    errors=(409, 410, 416, 429),
)
async def firm_export_archive_route(
    export_id: UUID,
    link_id: UUID,
    ctx: Ctx,
    range_header: Annotated[str | None, Header(alias="Range", max_length=100)] = None,
    if_range: Annotated[str | None, Header(alias="If-Range", max_length=100)] = None,
) -> Response:
    """The archive (`application/zip`, `Cache-Control: no-store`, a safe `Content-Disposition`)
    for the person the link was issued to, streamed by the API from the sealed segments,
    resumable with one `Range` (206). 410 `link_expired` after the link's 15 minutes,
    `export_expired` after the 7 days; 416 for a range not served. Audited
    `firm_export.streamed`."""
    try:
        plan = await firm_exports.prepare(ctx, export_id, link_id, range_header, if_range)
    except export_download.ExportExpired:
        return _gone("export_expired")
    except firm_exports.LinkExpired:
        return _gone("link_expired")
    except export_download.RangeNotSatisfiable as unsatisfiable:
        response = _no_store(JSONResponse({"detail": "range_not_satisfiable"}, status_code=416))
        response.headers["Content-Range"] = f"bytes */{unsatisfiable.size}"
        return response
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'attachment; filename="{firm_exports.file_name(plan.export_id)}"',
        "Content-Length": str(plan.length),
        "ETag": plan.etag,
    }
    status = 200
    if plan.range is not None:
        status = 206
        headers["Content-Range"] = f"bytes {plan.range.start}-{plan.range.end}/{plan.size}"
    return _no_store(
        StreamingResponse(
            plan.stream(), status_code=status, media_type="application/zip", headers=headers
        )
    )

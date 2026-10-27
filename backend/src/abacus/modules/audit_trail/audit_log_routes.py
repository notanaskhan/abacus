"""ADM-07's live routes (G-02-T08, G-02-T17; SPEC-349 §4; `docs/contracts/audit-log.md` v1): the
list, the detail and the export family, on the contract's router.

Each route checks the principal first (security review L1: a client principal 404, the agent and
the system 403), then `audit_log.explorer` (404 while off), then narrows every event to what the
reader may see (`explorer.shown_to`)."""

from __future__ import annotations

from datetime import date
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated
from uuid import UUID

from fastapi import Path, Query
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import AfterValidator

from abacus.modules.audit_trail import explorer, exports
from abacus.modules.audit_trail.audit_log_contract import (
    ActorKind,
    AuditEventDetail,
    AuditEventPageOut,
    AuditExport,
    AuditExportLinkOut,
    AuditExportRequestIn,
    Ctx,
    IdempotencyKey,
    authorised,
    gate,
    router,
)

Text = Annotated[str | None, Query(max_length=200)]


def _no_zone(ip: IPv4Address | IPv6Address | None) -> IPv4Address | IPv6Address | None:
    """L7: an IPv6 zone (`fe80::1%eth0`) is no host `inet` holds: 422, never a 500."""
    if isinstance(ip, IPv6Address) and ip.scope_id is not None:
        raise ValueError("an IP address filter names a host, without a zone")
    return ip


Ip = Annotated[IPv4Address | IPv6Address | None, Query(), AfterValidator(_no_zone)]


@router.get("/exports/{export_id}", action="audit_export.read", response_model=AuditExport)
async def audit_export_route(export_id: UUID, ctx: Ctx) -> AuditExport:
    """ADM-07 g: the requester's export; anyone else's answers 404. A status read needs no fresh
    second factor (L5); the request, the link and the download do."""
    await authorised(ctx, "audit_export.read")
    await gate(ctx)
    return await exports.read(ctx, export_id)


@router.post(
    "/exports",
    action="audit_event.export",
    response_model=AuditExport,
    status_code=202,
)
async def request_audit_export_route(
    body: AuditExportRequestIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AuditExport:
    """ADM-07 e (AC-12): one person with a fresh second factor (DEC-415 Q8); 202 `requested`,
    the same job again for a repeated `Idempotency-Key`. 422 `export_range_invalid` past 92 days.
    Where no export-signing key or exports bucket is configured the job fails
    (`signing_unavailable`, `exports_unavailable`), never signing or storing elsewhere. Audited
    `audit_export.requested`; values only as the requester may see them on screen (AC-14)."""
    await authorised(ctx, "audit_event.export")
    await gate(ctx)
    return await exports.request(ctx, body, idempotency_key)


@router.post(
    "/exports/{export_id}/link",
    action="audit_event.export",
    response_model=AuditExportLinkOut,
    errors=(409, 410),
)
async def link_audit_export_route(export_id: UUID, ctx: Ctx) -> AuditExportLinkOut | Response:
    """ADM-07 g: where the ZIP downloads (the API's own download route, ADR-104), valid while
    the second factor stays fresh and never past the export's 7 days. 409 `export_not_ready`
    before it is ready, 410 `export_expired` after."""
    await authorised(ctx, "audit_event.export")
    await gate(ctx)
    try:
        return await exports.download_link(ctx, export_id)
    except exports.AuditExportExpired:
        return _no_store(JSONResponse({"detail": "export_expired"}, status_code=410))


@router.get(
    "/exports/{export_id}/download",
    action="audit_event.export",
    response_model=bytes,
    errors=(409, 410),
)
async def download_audit_export_route(export_id: UUID, ctx: Ctx) -> Response:
    """ADM-07 g (AC-12, AC-13): the ZIP of `audit-log-<from>-<to>.csv`, `manifest.json` and
    `manifest.sig`, streamed by the API from the sealed bundle (`application/zip`,
    `Cache-Control: no-store`). The requester only, with a fresh second factor. Audited
    `audit_export.downloaded` naming the person before the first byte."""
    await authorised(ctx, "audit_event.export")
    await gate(ctx)
    try:
        plan = await exports.download(ctx, export_id)
    except exports.AuditExportExpired:
        return _no_store(JSONResponse({"detail": "export_expired"}, status_code=410))
    headers = {
        "Content-Disposition": f'attachment; filename="{plan.file_name}"',
        "Content-Length": str(plan.size),
    }
    return _no_store(
        StreamingResponse(plan.stream(), media_type="application/zip", headers=headers)
    )


def _no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.get("", action="audit_event.read", response_model=AuditEventPageOut)
async def list_audit_events_route(
    ctx: Ctx,
    actor_kind: Annotated[ActorKind | None, Query()] = None,
    actor_id: Annotated[UUID | None, Query()] = None,
    object_type: Annotated[str | None, Query(max_length=64)] = None,
    action: Annotated[str | None, Query(max_length=80)] = None,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
    office_id: Annotated[UUID | None, Query()] = None,
    ip: Ip = None,
    q: Text = None,
    since_seq: Annotated[int | None, Query(ge=0)] = None,
    cursor: Annotated[str | None, Query(max_length=1024)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AuditEventPageOut:
    """ADM-07 a, b, f: newest first by `seq` (oldest first after `since_seq`). Dates filter on
    `effective_at` in the firm's time zone; `office_id` is the object's office (DEC-415 Q9);
    `q` searches actor, target and fact labels only, never a value (M4); `ip` filters only for
    the readers who see request context (DEC-420)."""
    await authorised(ctx, "audit_event.read")
    await gate(ctx)
    where = explorer.EventFilter(
        actor_kind=actor_kind,
        actor_id=actor_id,
        object_type=object_type,
        action=action,
        from_date=from_,
        to_date=to,
        office_id=office_id,
        ip=str(ip) if ip is not None else None,
        q=q,
        since_seq=since_seq,
    )
    page = await explorer.list_events(ctx, where, cursor, limit)
    return AuditEventPageOut.model_validate(page.model_dump())


@router.get("/{seq}", action="audit_event.read", response_model=AuditEventDetail)
async def audit_event_route(seq: Annotated[int, Path(ge=1)], ctx: Ctx) -> AuditEventDetail:
    """ADM-07 c: one event; a walled or invisible one answers 404 (DEC-43)."""
    await authorised(ctx, "audit_event.read")
    await gate(ctx)
    return await explorer.get_event(ctx, seq)

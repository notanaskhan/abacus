"""Engagement exports: create, Undo, history and status (A-01-T18; SPEC-344 AC-6 to AC-8;
DEC-376, DEC-379, DEC-435). PROTECTED (evidence, red). Contract:
`docs/contracts/engagement-export-v1.md`.

A person (never an agent, the system or support: INV-1; the database agrees) with a fresh second
factor, onshore and independent asks for a binder export of an audit work item. The request is
written at once, `queued`, and held by a single-use approval grant whose `not_before` is ten
seconds on (P-35, ADR-161): Undo inside that window voids the grant and leaves an `undone` row
and no package; after it, `EngagementExportWorkflow` consumes the grant and builds (A-01-T19).

Every route authorises first, so a wall answers 404 before the flag or any read (DEC-379 L3);
then the `audits.binder_export` flag. A work item with no assurance row (a tax return, any
non-audit item) is 422 `export_kind_unsupported` (fail closed until C19); a scope binder id that
is not one of the work item's asked PBC binders, as the requester reads them, is 422
`binder_not_in_work_item` (DEC-379 M4).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Final, cast
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, insert, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel import clock
from abacus.kernel._flags import AUDITS_BINDER_EXPORT
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import (
    Position,
    decode_cursor,
    encode_cursor,
    keyset,
    page_of,
    query_hash,
)
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.engagements.api import assurance_item, get_ref, work_item_engagement
from abacus.modules.evidence.export_events import (
    EngagementExportRequested,
    EngagementExportUndone,
)
from abacus.modules.evidence.export_manifest import FORMAT_VERSION
from abacus.modules.evidence.export_models import EngagementExport
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    issue_grant,
    names_of,
    visible,
    void_grant,
)
from abacus.modules.requests.api import pbc_binders

UNDO_WINDOW: Final = timedelta(seconds=10)
GRANT_LIFETIME: Final = timedelta(days=7)
HISTORY_LIMIT: Final = 50
SUBJECT: Final = "engagement_export"
_CREATE: Final = "export.create"
_READ: Final = "export.read"
_DOWNLOAD: Final = "export.download"


class ExportKindUnsupported(DomainInvalid):
    """Only an audit work item exports a binder (fail closed until C19 and a tax-export
    review)."""

    code = "export_kind_unsupported"


class BinderNotInWorkItem(DomainInvalid):
    """A scope binder id is not one of the work item's asked PBC binders (DEC-379), or the work
    item has none to export."""

    code = "binder_not_in_work_item"


class ExportUndoClosed(DomainConflict):
    """Undo is possible for 10 seconds after the request, by the person who asked."""

    code = "undo_window_closed"


class ExportEffectStarted(DomainConflict):
    """The build has started (its grant was consumed): the export can no longer be undone."""

    code = "effect_started"


@dataclass(frozen=True)
class ExportScope:
    binder_ids: tuple[UUID, ...]
    include_unaccepted: bool
    include_audit_trail: bool

    def as_json(self) -> dict[str, object]:
        return {
            "binder_ids": [str(b) for b in self.binder_ids],
            "include_unaccepted": self.include_unaccepted,
            "include_audit_trail": self.include_audit_trail,
        }

    @classmethod
    def of(cls, stored: dict[str, object]) -> ExportScope:
        return cls(
            tuple(UUID(str(b)) for b in cast(list[object], stored["binder_ids"])),
            bool(stored["include_unaccepted"]),
            bool(stored["include_audit_trail"]),
        )


@dataclass(frozen=True)
class ExportView:
    id: UUID
    engagement_id: UUID
    work_item_id: UUID
    kind: str
    scope: ExportScope
    format_version: str
    status: str
    requested_by: UUID
    requested_by_name: str
    requested_at: datetime
    not_before: datetime
    ready_at: datetime | None
    expires_at: datetime | None
    request_count: int | None
    file_count: int | None
    size_bytes: int | None
    manifest_sha256: str | None
    bundle_sha256: str | None
    failure_code: str | None
    void_reason: str | None
    allowed_actions: list[str]


@dataclass(frozen=True)
class ExportPage:
    items: list[ExportView]
    next_cursor: str | None


def grant_digest(export_id: UUID, work_item_id: UUID, kind: str, scope: dict[str, object]) -> str:
    """What the export's grant is bound to: the export, its work item, kind and scope. The
    workflow recomputes it from the row when it consumes the grant."""
    canonical = json.dumps(
        {"export_id": str(export_id), "work_item_id": str(work_item_id), "kind": kind}
        | {"scope": scope},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _human(ctx: AuthContext, action: str) -> None:
    """INV-1: a person's own act, never an agent, the platform, support or a client."""
    if ctx.client or ctx.is_support or ctx.tenant.actor_kind != "human":
        raise Forbidden(action, "role")


async def _flag_on(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, AUDITS_BINDER_EXPORT):
        raise NotFound(AUDITS_BINDER_EXPORT.name)


async def _on_work_item(ctx: AuthContext, action: str, work_item_id: UUID) -> Resource:
    """The action on the work item's engagement: 404 outside the tenant or behind a wall, 403 by
    role, independence, offshore or stale MFA."""
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    ref = await get_ref(ctx, engagement_id)
    resource = replace(ref.resource(), work_item_id=work_item_id)
    await authorise(ctx, action, resource)
    return resource


async def _on_export(ctx: AuthContext, action: str, row: EngagementExport) -> Resource:
    ref = await get_ref(ctx, row.engagement_id)
    resource = replace(ref.resource(), work_item_id=row.work_item_id)
    await authorise(ctx, action, resource)
    return resource


# --- create ----------------------------------------------------------------------------------


async def create(
    ctx: AuthContext,
    work_item_id: UUID,
    *,
    kind: str,
    binder_ids: Sequence[UUID],
    include_unaccepted: bool,
    include_audit_trail: bool,
    idempotency_key: str,
) -> ExportView:
    """AC-6: one `queued` export behind a 10-second grant; a retried key returns the same one."""
    _human(ctx, _CREATE)
    resource = await _on_work_item(ctx, _CREATE, work_item_id)
    await _flag_on(ctx)
    try:
        await assurance_item(ctx.tenant, work_item_id)
    except NotFound:
        raise ExportKindUnsupported from None
    binders = await pbc_binders(ctx, work_item_id)
    asked = list(dict.fromkeys(binder_ids)) or binders
    if not asked or any(b not in binders for b in asked):
        raise BinderNotInWorkItem
    scope = ExportScope(tuple(asked), include_unaccepted, include_audit_trail)

    async def run() -> tuple[int, dict[str, object]]:
        export_id = await _write(ctx, resource, work_item_id, kind, scope)
        return 202, {"export_id": str(export_id)}

    stored = await idempotent(
        ctx.tenant,
        route="engagement_export.create",
        key=idempotency_key,
        body={"work_item_id": str(work_item_id), "kind": kind}
        | {"scope": {**scope.as_json(), "asked": [str(b) for b in binder_ids]}},
        run=run,
    )
    return await read(ctx, UUID(str(stored.body["export_id"])))


async def _write(
    ctx: AuthContext, resource: Resource, work_item_id: UUID, kind: str, scope: ExportScope
) -> UUID:
    if ctx.mfa_at is None:  # authorise demanded a fresh factor; the row records when
        raise Forbidden(_CREATE, "condition")
    engagement_id = cast(UUID, resource.engagement_id)
    ref = await get_ref(ctx, engagement_id)
    export_id = uuid4()
    not_before = await clock.now(ctx.tenant) + UNDO_WINDOW
    stored_scope = scope.as_json()
    async with uow(ctx.tenant) as tx:
        grant = await issue_grant(
            tx,
            ctx,
            action=_CREATE,
            resource=resource,
            subject=Target(SUBJECT, export_id),
            payload_sha256=grant_digest(export_id, work_item_id, kind, stored_scope),
            not_before=not_before,
            expires_at=not_before + GRANT_LIFETIME,
        )
        await tx.session.execute(
            insert(EngagementExport).values(
                id=export_id,
                tenant_id=ctx.tenant_id,
                engagement_id=engagement_id,
                work_item_id=work_item_id,
                client_id=ref.client_id,
                kind=kind,
                scope=stored_scope,
                format_version=FORMAT_VERSION,
                requested_by=ctx.user_id,
                requested_by_kind="human",
                mfa_at=ctx.mfa_at,
                grant_id=grant,
                not_before=not_before,
            )
        )
        tx.record(
            "engagement_export.requested",
            target=Target(SUBJECT, export_id),
            after=Ref(work_item=work_item_id, grant=grant, binders=len(scope.binder_ids)),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
        tx.emit(
            EngagementExportRequested(
                export_id=export_id,
                engagement_id=engagement_id,
                work_item_id=work_item_id,
                requested_by=ctx.user_id,
            )
        )
    return export_id


# --- undo ------------------------------------------------------------------------------------


async def _locked(session: AsyncSession, export_id: UUID) -> EngagementExport | None:
    return await session.scalar(
        select(EngagementExport)
        .where(EngagementExport.id == export_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def undo(ctx: AuthContext, export_id: UUID) -> ExportView:
    """AC-7: inside the window, by the requester: the grant is voided, the export `undone`, no
    package is built. Later (or anyone else), 409 `undo_window_closed`; once the build consumed
    the grant, 409 `effect_started`."""
    _human(ctx, _CREATE)
    async with uow(ctx.tenant) as tx:
        row = await _locked(tx.session, export_id)
        if row is None:
            raise NotFound(SUBJECT)
        await _on_export(ctx, _CREATE, row)
        await _flag_on(ctx)
        now = await clock.now(ctx.tenant)
        if row.status != "queued" or row.requested_by != ctx.user_id or now >= row.not_before:
            raise ExportUndoClosed
        if not await void_grant(tx, row.grant_id):
            raise ExportEffectStarted
        await _undone(tx, row, ctx.user_id, now)
    return await read(ctx, export_id)


async def _undone(tx: UnitOfWork, row: EngagementExport, user_id: UUID, now: datetime) -> None:
    try:
        await tx.session.execute(
            update(EngagementExport)
            .where(EngagementExport.id == row.id)
            .values(status="undone", undone_at=now, undone_by=user_id)
        )
    except DBAPIError as exc:  # the guard's own window check, on the database's clock
        if "undo_window_closed" in str(exc.orig):
            raise ExportUndoClosed from None
        raise
    tx.record(
        "engagement_export.undone",
        target=Target(SUBJECT, row.id),
        after=Ref(grant=row.grant_id),
        scope=Scope(engagement_id=row.engagement_id, work_item_id=row.work_item_id),
    )
    tx.emit(
        EngagementExportUndone(
            export_id=row.id,
            engagement_id=row.engagement_id,
            work_item_id=row.work_item_id,
            requested_by=row.requested_by,
        )
    )


# --- reads -----------------------------------------------------------------------------------


async def _views(
    ctx: AuthContext, rows: Sequence[EngagementExport], resource: Resource
) -> list[ExportView]:
    if not rows:
        return []
    names = await names_of(sorted({r.requested_by for r in rows}))
    may = set(await allowed_actions(ctx, resource, [_CREATE, _DOWNLOAD]))
    now = await clock.now(ctx.tenant)
    out: list[ExportView] = []
    for row in rows:
        actions: list[str] = []
        if (
            row.status == "queued"
            and row.requested_by == ctx.user_id
            and now < row.not_before
            and _CREATE in may
        ):
            actions.append("undo")
        if row.status == "ready" and _DOWNLOAD in may:
            actions.append("download")
        out.append(
            ExportView(
                id=row.id,
                engagement_id=row.engagement_id,
                work_item_id=row.work_item_id,
                kind=row.kind,
                scope=ExportScope.of(row.scope),
                format_version=row.format_version,
                status=row.status,
                requested_by=row.requested_by,
                requested_by_name=names.get(row.requested_by, ""),
                requested_at=row.requested_at,
                not_before=row.not_before,
                ready_at=row.ready_at,
                expires_at=row.expires_at,
                request_count=row.request_count,
                file_count=row.file_count,
                size_bytes=row.bytes,
                manifest_sha256=row.manifest_sha256,
                bundle_sha256=row.bundle_sha256,
                failure_code=row.failure_code,
                void_reason=row.void_reason,
                allowed_actions=actions,
            )
        )
    return out


async def read(ctx: AuthContext, export_id: UUID) -> ExportView:
    """The sheet's poll (`export.read` on the export's engagement)."""
    _human(ctx, _READ)
    async with tenant_session(ctx.tenant) as session:
        row = await session.get(EngagementExport, export_id)
    if row is None:
        raise NotFound(SUBJECT)
    resource = await _on_export(ctx, _READ, row)
    await _flag_on(ctx)
    [view] = await _views(ctx, [row], resource)
    return view


async def work_item_exports(
    ctx: AuthContext, work_item_id: UUID, cursor: str | None
) -> ExportPage:
    """The work item's exports, newest first, 50 a page (`export.read`)."""
    _human(ctx, _READ)
    resource = await _on_work_item(ctx, _READ, work_item_id)
    await _flag_on(ctx)
    query = query_hash(work_item_id=str(work_item_id))
    after: Position | None = None
    if cursor is not None:
        after = decode_cursor(
            cursor, tenant_id=ctx.tenant_id, resource="engagement_exports", query=query
        )
    stmt = keyset(
        select(EngagementExport).where(
            EngagementExport.work_item_id == work_item_id,
            visible(ctx, "export.read", EngagementExport.engagement_id),
        ),
        sort=cast(ColumnElement[object], EngagementExport.requested_at.expression),
        id_column=cast(ColumnElement[object], EngagementExport.id.expression),
        after=after,
        descending=True,
        limit=HISTORY_LIMIT,
    )
    async with tenant_session(ctx.tenant) as session:
        rows = list((await session.execute(stmt)).scalars().all())
    page, last = page_of(
        rows, limit=HISTORY_LIMIT, key=lambda r: r.requested_at, id_of=lambda r: r.id
    )
    next_cursor = (
        encode_cursor(last, tenant_id=ctx.tenant_id, resource="engagement_exports", query=query)
        if last is not None
        else None
    )
    return ExportPage(await _views(ctx, page, resource), next_cursor)

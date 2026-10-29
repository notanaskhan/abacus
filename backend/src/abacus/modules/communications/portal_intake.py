"""Portal intake: POR-03 "Upload something else" (N-01-T14; N-01 §3.5; ADR-137, ADR-162,
ADR-210; DEC-1060).

- **Who:** a portal principal, on one of its own grants (`scope_ref`) with an uploading role;
  the scope is checked against the principal's grants here (`scope_only`, INV-4), since the
  matrix's condition resolves engagement scopes only. A firm principal never reaches these (404).
- **Batch:** one batch is one thread with one message (the client's note its sealed body,
  DEC-702), matched to the scope's client; files follow one request each, scanned before storage
  and stored under a key of their own (detached-key mode, ADR-162 §5), New or Waiting. The intake
  scope learns of it through `inbox_attachment.received` (AttachmentTriage, the Inbox).
- **Own uploads:** the principal lists only what it sent under that scope, in client words:
  Sent, Received by {firm} (filed), Withdrawn.
- **Withdraw:** only while every file is New or Waiting (409 `attachment_filed` otherwise): the
  files become Withdrawn at once and leave every firm read and agent; 30 days later the purge
  destroys each file's key unless a hold covers it, so nothing of it can be read again.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import text
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel._flags import PORTAL_INTAKE_UPLOAD
from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import Position, decode_cursor, page_of, query_hash
from abacus.kernel.uow import OutboxEvent, Ref, Target, uow
from abacus.modules.communications import intake
from abacus.modules.communications.events import PortalIntakeWithdrawn
from abacus.modules.communications.intake_purge_workflow import (
    IntakePurgeInput,
    IntakeWithdrawalPurgeWorkflow,
    intake_purge_id,
)
from abacus.modules.evidence.api import destroy_intake_key, held_intake_objects, live_intake_keys
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    authorise_with_scope,
    portal_scopes,
    scope_facts,
)

UPLOAD: Final = "portal_intake.upload"
READ_OWN: Final = "portal_intake.read_own"
WITHDRAW: Final = "portal_intake.withdraw"
# The grant roles the matrix calls `client_admin` (owner) and `client_contributor` (DEC-1060).
UPLOADING_ROLES: Final = frozenset({"owner", "contributor"})
PURGE_AFTER: Final = timedelta(days=30)
LIST_RESOURCE: Final = "portal_intake_uploads"
_OPEN: Final = ("new", "waiting")


class AttachmentFiled(DomainConflict):
    """The firm already filed a file of this upload: it can no longer be withdrawn."""

    code = "attachment_filed"


@dataclass(frozen=True)
class Scope:
    kind: str
    id: UUID
    client_id: UUID


async def _scope(ctx: AuthContext, kind: str, scope_id: UUID, action: str) -> Scope:
    """The principal's own grant on this scope, with an uploading role; anything else is 404."""
    if not ctx.client:
        raise NotFound("portal intake")
    if not await flag_enabled(ctx.tenant, PORTAL_INTAKE_UPLOAD):
        raise NotFound(PORTAL_INTAKE_UPLOAD.name)
    held = await portal_scopes(ctx)
    granted = any(
        g.scope_kind == kind and g.scope_id == scope_id and g.role in UPLOADING_ROLES
        for g in held.scopes
    )
    facts = await scope_facts(ctx.tenant, kind, scope_id) if granted else None
    if facts is None:
        raise NotFound("portal_scope")
    await authorise_with_scope(
        ctx, action, Resource.client(ctx.tenant_id, facts.client_id), in_scope=True
    )
    return Scope(kind, scope_id, facts.client_id)


@dataclass(frozen=True)
class BatchFile:
    id: UUID
    file_name: str
    size_bytes: int
    status: str  # client words: sent | received | withdrawn


@dataclass(frozen=True)
class IntakeBatch:
    id: UUID
    scope_kind: str
    scope_id: UUID
    status: str
    sent_at: datetime
    files: list[BatchFile]
    can_withdraw: bool


def _word(status: str) -> str:
    if status == "withdrawn":
        return "withdrawn"
    if status == "filed":
        return "received"
    return "sent"


async def create_upload(
    ctx: AuthContext, scope_kind: str, scope_id: UUID, note: str | None
) -> IntakeBatch:
    """The batch: one thread, one message, matched to the scope's client."""
    scope = await _scope(ctx, scope_kind, scope_id, UPLOAD)
    made = await intake.record_inbound_message(
        ctx.tenant,
        intake.Inbound(
            channel="portal_upload",
            sender_display="Client portal",
            subject="Documents from the portal",
            received_at=system_now(),
            body=note,
            client_id=scope.client_id,
            principal_id=ctx.user_id,
            portal_scope_kind=scope.kind,
            portal_scope_id=scope.id,
        ),
    )
    return IntakeBatch(made.message_id, scope.kind, scope.id, "sent", system_now(), [], True)


async def _own_upload(ctx: AuthContext, upload_id: UUID, action: str) -> Scope:
    """The principal's own batch (by message), with its scope re-checked; else 404."""
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT portal_scope_kind, portal_scope_id FROM inbound_messages "
                    "WHERE id = :id AND sender_principal_id = :user AND channel = 'portal_upload'"
                ),
                {"id": upload_id, "user": ctx.user_id},
            )
        ).one_or_none()
    if row is None or row.portal_scope_kind is None:
        raise NotFound("portal_intake_upload")
    return await _scope(ctx, row.portal_scope_kind, row.portal_scope_id, action)


async def add_file(ctx: AuthContext, upload_id: UUID, file_name: str, content: bytes) -> BatchFile:
    """One file of the batch: scanned, stored under its own key, New or Waiting."""
    await _own_upload(ctx, upload_id, UPLOAD)
    got = await intake.add_attachment(ctx.tenant, upload_id, file_name=file_name, content=content)
    return BatchFile(got.attachment_id, got.file_name, len(content), "sent")


async def _files(tenant: TenantContext, message_ids: list[UUID]) -> dict[UUID, list[BatchFile]]:
    if not message_ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, message_id, file_name, size_bytes, status FROM inbox_attachments "
                    "WHERE message_id = ANY(:ids) ORDER BY created_at, id"
                ),
                {"ids": message_ids},
            )
        ).all()
    out: dict[UUID, list[BatchFile]] = {}
    for r in rows:
        out.setdefault(r.message_id, []).append(
            BatchFile(r.id, r.file_name, int(r.size_bytes), _word(r.status))
        )
    return out


def _upload(
    message_id: UUID, scope: Scope, sent_at: datetime, files: list[BatchFile]
) -> IntakeBatch:
    words = {f.status for f in files}
    status = (
        "withdrawn" if words == {"withdrawn"} else "received" if "received" in words else "sent"
    )
    return IntakeBatch(
        message_id,
        scope.kind,
        scope.id,
        status,
        sent_at,
        files,
        can_withdraw=bool(files) and words == {"sent"},
    )


@dataclass(frozen=True)
class BatchPage:
    uploads: list[IntakeBatch]
    next_position: Position | None
    query: str
    total: int


async def list_uploads(
    ctx: AuthContext, scope_kind: str, scope_id: UUID, cursor: str | None, limit: int
) -> BatchPage:
    """The principal's own uploads under this scope, newest first."""
    scope = await _scope(ctx, scope_kind, scope_id, READ_OWN)
    query = query_hash(scope_kind=scope_kind, scope_id=str(scope_id))
    after = (
        None
        if cursor is None
        else decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=LIST_RESOURCE, query=query)
    )
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, received_at FROM inbound_messages WHERE sender_principal_id = "
                    ":user AND channel = 'portal_upload' AND portal_scope_kind = :kind AND "
                    "portal_scope_id = :scope AND (CAST(:after_at AS timestamptz) IS NULL OR "
                    "(received_at, id) < "
                    "(CAST(:after_at AS timestamptz), CAST(:after_id AS uuid))) "
                    "ORDER BY received_at DESC, id DESC LIMIT :n"
                ),
                {
                    "user": ctx.user_id,
                    "kind": scope_kind,
                    "scope": scope_id,
                    "after_at": None if after is None else after.key,
                    "after_id": None if after is None else after.id,
                    "n": limit + 1,
                },
            )
        ).all()
        total = int(
            (
                await session.execute(
                    text(
                        "SELECT count(*) FROM inbound_messages WHERE sender_principal_id = :user "
                        "AND channel = 'portal_upload' AND portal_scope_kind = :kind "
                        "AND portal_scope_id = :scope"
                    ),
                    {"user": ctx.user_id, "kind": scope_kind, "scope": scope_id},
                )
            ).scalar_one()
        )
    page, last = page_of(rows, limit=limit, key=lambda r: r.received_at, id_of=lambda r: r.id)
    files = await _files(ctx.tenant, [r.id for r in page])
    return BatchPage(
        [_upload(r.id, scope, r.received_at, files.get(r.id, [])) for r in page],
        last,
        query,
        total,
    )


async def withdraw(ctx: AuthContext, upload_id: UUID) -> IntakeBatch:
    """Every file Withdrawn at once, only while none is filed (ADR-162)."""
    scope = await _own_upload(ctx, upload_id, WITHDRAW)
    now = system_now()
    async with uow(ctx.tenant) as tx:
        states = (
            await tx.session.execute(
                text("SELECT id, status FROM inbox_attachments WHERE message_id = :id FOR UPDATE"),
                {"id": upload_id},
            )
        ).all()
        if any(s.status not in (*_OPEN, "withdrawn") for s in states):
            raise AttachmentFiled
        await tx.session.execute(
            text(
                "UPDATE inbox_attachments SET status = 'withdrawn', withdrawn_at = :now "
                "WHERE message_id = :id AND status IN ('new', 'waiting')"
            ),
            {"now": now, "id": upload_id},
        )
        tx.record(
            "portal_intake.withdrawn",
            target=Target("inbound_message", upload_id),
            after=Ref(files=len(states)),
        )
        tx.emit(PortalIntakeWithdrawn(upload_id=upload_id))
    async with tenant_session(ctx.tenant) as session:
        sent_at = (
            await session.execute(
                text("SELECT received_at FROM inbound_messages WHERE id = :id"), {"id": upload_id}
            )
        ).scalar_one()
    files = await _files(ctx.tenant, [upload_id])
    return _upload(upload_id, scope, sent_at, files.get(upload_id, []))


# --- The purge (P-06's withdrawal purge, for intake) ---------------------------------------------

WORKFLOWS: dict[type, WorkClass] = {IntakeWithdrawalPurgeWorkflow: "batch"}
register_work_classes(WORKFLOWS)
_HELD_RETRY_SECONDS: Final = 24 * 3600


async def on_withdrawn(event: OutboxEvent) -> None:
    """`portal_intake.withdrawn` starts the upload's purge once (reuse rejected)."""
    upload = str(event.payload["upload_id"])
    await dispatch(
        IntakeWithdrawalPurgeWorkflow,
        IntakePurgeInput(str(event.tenant_id), upload),
        id=intake_purge_id(str(event.tenant_id), upload),
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


@activity.defn(name="communications.erase_withdrawn_intake")
async def erase_withdrawn_intake(given: IntakePurgeInput) -> int:
    """Destroy the keys of the upload's withdrawn files whose 30 days have passed, unless a hold
    covers them; 0 when nothing is left, else the seconds to wait."""
    tenant = TenantContext(UUID(given.tenant_id), "system", "communications.intake_purge")
    now = system_now()
    async with tenant_session(tenant) as session:
        withdrawn = (
            await session.execute(
                text(
                    "SELECT id, client_id, withdrawn_at FROM inbox_attachments "
                    "WHERE message_id = :upload AND status = 'withdrawn'"
                ),
                {"upload": UUID(given.upload_id)},
            )
        ).all()
    live = await live_intake_keys(tenant, [r.id for r in withdrawn])
    rows = [r for r in withdrawn if r.id in live]
    if not rows:
        return 0
    due = [r for r in rows if r.withdrawn_at + PURGE_AFTER <= now]
    if not due:
        first = min(r.withdrawn_at for r in rows)
        return max(1, int((first + PURGE_AFTER - now).total_seconds()))
    # Unfiled, so no evidence version: the version hold check would call every id held.
    held = await held_intake_objects(tenant, [(r.id, r.client_id) for r in due])
    erasable = [r.id for r in due if r.id not in held]
    for attachment in erasable:
        async with uow(tenant) as tx:
            await destroy_intake_key(tx, attachment)
    return 0 if len(erasable) == len(rows) else _HELD_RETRY_SECONDS


ACTIVITIES: Final = (erase_withdrawn_intake,)

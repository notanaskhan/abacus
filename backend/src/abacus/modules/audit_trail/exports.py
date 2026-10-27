"""Audit-log exports (G-02-T17; SPEC-349 AC-12 to AC-14; G-02 §4.5; DEC-620 to DEC-622).
Contract: `docs/contracts/audit-log.md` §Exports.

    POST /v1/audit-events/exports              request (fresh MFA): 202 `requested`
    GET  /v1/audit-events/exports/{id}          the requester's job
    POST /v1/audit-events/exports/{id}/link     where to download it (fresh MFA)
    GET  /v1/audit-events/exports/{id}/download the ZIP, streamed by the API (fresh MFA)

- **Who:** a person holding `audit_event.export` (the matrix: `security_admin`, in-scope quality
  partners and practice leaders), with a fresh second factor for the request, the link and the
  download; a job is its requester's alone (anyone else's answers 404, as unknown).
- **What:** `AuditExportWorkflow` reads the range as the requester reads it on screen
  (`identity.api.member_context`: their current membership, no MFA time, reads only), through the
  explorer's narrowing (walls, `visible()`, firm-level readers, request context only for its
  readers) and, with "Include before/after values", the detail drawer's value resolution, masked
  by classification (AC-14). A requester who is no longer a member gets nothing: the job fails.
- **The bundle** (`audit-log-<from>-<to>.zip`): `audit-log-<from>-<to>.csv`, `manifest.json`
  (format `accrued.audit-log-export` v1: the CSV's SHA-256, the seq range, the firm's latest
  P-43 checkpoint, the filter, the requester, the row count) and `manifest.sig` (ECDSA P-256 over
  the manifest by the environment's export-signing key, `kernel.crypto.signing`). Sealed under
  the tenant key in the exports bucket (`kernel.export_bundles`); no presigned link (ADR-104).
- **Expiry:** 7 days from `ready`; expired once either the business clock or the system clock
  has passed `expires_at` (DEC-546's rule), 410 `export_expired`; the bucket's lifecycle rule
  removes the objects.
- **Audit:** `audit_export.requested` and `audit_export.downloaded` name the person;
  `audit_export.ready` and `audit_export.failed` are the system's.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
import zipfile
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import IO, Final, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import ApplicationError, WorkflowAlreadyStartedError

from abacus.kernel import clock
from abacus.kernel import export_bundles as export_store
from abacus.kernel.crypto.signing import SigningUnavailable, export_signer
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.export_bundles import BundleKind
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Handler, OutboxEvent, Ref, Target, uow
from abacus.kernel.uow.chain import latest_checkpoint
from abacus.modules.audit_trail.audit_log_contract import (
    ActorKind,
    AuditEventRow,
    AuditExport,
    AuditExportFilterIn,
    AuditExportLinkOut,
    AuditExportRequestIn,
    AuditPersonOut,
    AuditValuesOut,
    ExportStatus,
    Fact,
)
from abacus.modules.audit_trail.events import AuditExportReady, AuditExportRequested
from abacus.modules.audit_trail.explorer import EventFilter, export_batch, reader_of
from abacus.modules.audit_trail.workflows import (
    AuditExportFacts,
    AuditExportFailure,
    AuditExportInput,
    AuditExportWorkflow,
    audit_export_workflow_id,
)
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    member_context,
    names_of,
)

SUBJECT: Final = "audit_export"
_KIND: Final[BundleKind] = "audit-log"
FORMAT: Final = "accrued.audit-log-export"
FORMAT_VERSION: Final = "1"
MAX_DAYS: Final = 92
EXPIRY: Final = timedelta(days=7)
LINK_LIFETIME: Final = timedelta(minutes=15)  # the fresh window the download needs
PAGE: Final = 500
_FORMULA_LEADS: Final = ("=", "+", "-", "@", "\t", "\r")
# 1980-01-01, the ZIP epoch: the bundle's bytes depend on its content only.
_ZIP_TIME: Final = (1980, 1, 1, 0, 0, 0)
CSV_COLUMNS: Final = (
    "seq",
    "effective_at",
    "action",
    "category",
    "actor_kind",
    "actor_user_id",
    "actor_name",
    "on_behalf_of_user_id",
    "on_behalf_of_name",
    "agent_id",
    "policy_ref",
    "target_type",
    "target_id",
    "target_label",
    "engagement_id",
    "client_id",
    "office_id",
    "ip",
    "detail_facts",
)
VALUE_COLUMNS: Final = ("values_status", "values")
_log = get_logger(__name__)


class _Unchanged(Exception):
    """A repeated stamp found nothing to change: the unit of work rolls back (it records no
    event, so it may not commit)."""


class ExportRangeInvalid(DomainInvalid):
    """`to_date` is before `from_date`, or the range is longer than 92 days."""

    code = "export_range_invalid"


class AuditExportNotReady(DomainConflict):
    """The export is not `ready` yet, or never will be (failed)."""

    code = "export_not_ready"


class AuditExportExpired(Exception):
    """410 `export_expired`: past its 7 days."""


@dataclass(frozen=True)
class _Row:
    id: UUID
    requested_by: UUID
    filter: dict[str, Fact]
    from_date: date
    to_date: date
    include_values: bool
    status: ExportStatus
    seq_from: int | None
    seq_to: int | None
    row_count: int | None
    manifest_sha256: str | None
    expires_at: datetime | None
    created_at: datetime
    segment_count: int | None
    bundle_bytes: int | None


_BY_ID = text(
    "SELECT id, requested_by, filter, from_date, to_date, include_values, status, seq_from, "
    "seq_to, row_count, manifest_sha256, expires_at, created_at, segment_count, bundle_bytes "
    "FROM audit_exports WHERE id = :id"
)
_BY_KEY = text(
    "SELECT id, requested_by, filter, from_date, to_date, include_values, status, seq_from, "
    "seq_to, row_count, manifest_sha256, expires_at, created_at, segment_count, bundle_bytes "
    "FROM audit_exports WHERE requested_by = :by AND idempotency_key = :key"
)
_INSERT = text(
    "INSERT INTO audit_exports (id, tenant_id, requested_by, requested_by_kind, filter, "
    "from_date, to_date, include_values, idempotency_key) VALUES (:id, :tenant, :by, 'human', "
    "CAST(:filter AS jsonb), :from_date, :to_date, :values, :key) "
    "ON CONFLICT (tenant_id, requested_by, idempotency_key) DO NOTHING RETURNING id"
)


def _row(found: object) -> _Row:
    m = cast(dict[str, object], found)
    return _Row(
        id=cast(UUID, m["id"]),
        requested_by=cast(UUID, m["requested_by"]),
        filter=cast(dict[str, Fact], m["filter"] or {}),
        from_date=cast(date, m["from_date"]),
        to_date=cast(date, m["to_date"]),
        include_values=bool(m["include_values"]),
        status=cast(ExportStatus, m["status"]),
        seq_from=cast(int | None, m["seq_from"]),
        seq_to=cast(int | None, m["seq_to"]),
        row_count=cast(int | None, m["row_count"]),
        manifest_sha256=cast(str | None, m["manifest_sha256"]),
        expires_at=cast(datetime | None, m["expires_at"]),
        created_at=cast(datetime, m["created_at"]),
        segment_count=cast(int | None, m["segment_count"]),
        bundle_bytes=cast(int | None, m["bundle_bytes"]),
    )


def file_stem(from_date: date, to_date: date) -> str:
    """`audit-log-2026-09-08-2026-09-14` (AC-12)."""
    return f"audit-log-{from_date.isoformat()}-{to_date.isoformat()}"


async def _expired(tenant: TenantContext, expires_at: datetime | None) -> bool:
    if expires_at is None:
        return False
    return max(await clock.now(tenant), clock.system_now()) >= expires_at


async def _out(tenant: TenantContext, row: _Row) -> AuditExport:
    names = await names_of([row.requested_by])
    status: ExportStatus = row.status
    if status in ("ready", "downloaded") and await _expired(tenant, row.expires_at):
        status = "expired"
    done = row.status in ("ready", "downloaded")
    return AuditExport(
        id=row.id,
        status=status,
        from_date=row.from_date,
        to_date=row.to_date,
        filter=row.filter,
        include_values=row.include_values,
        requested_by=AuditPersonOut(
            user_id=row.requested_by, display_name=names.get(row.requested_by, "")
        ),
        requested_at=row.created_at,
        file_name=f"{file_stem(row.from_date, row.to_date)}.zip" if done else None,
        row_count=row.row_count,
        seq_from=row.seq_from,
        seq_to=row.seq_to,
        manifest_sha256=row.manifest_sha256,
        expires_at=row.expires_at,
    )


def _human(ctx: AuthContext, action: str) -> None:
    """INV-1: a person, never the agent, the system or support (the matrix refuses them too)."""
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden(action, "role")


async def _mine(ctx: AuthContext, export_id: UUID) -> _Row:
    async with tenant_session(ctx.tenant) as session:
        found = (await session.execute(_BY_ID, {"id": export_id})).mappings().one_or_none()
    if found is None or found["requested_by"] != ctx.user_id:
        raise NotFound(SUBJECT)
    return _row(dict(found))


# --- request -------------------------------------------------------------------------------------


def _filter_json(given: AuditExportFilterIn) -> dict[str, Fact]:
    return {
        k: (str(v) if isinstance(v, UUID) else v)
        for k, v in given.model_dump(mode="python").items()
        if v is not None
    }


async def request(
    ctx: AuthContext, body: AuditExportRequestIn, idempotency_key: str
) -> AuditExport:
    """AC-12: one job per `Idempotency-Key` (a retry returns the same job), `requested`, audited
    `audit_export.requested` naming the person; the workflow starts from the outbox."""
    _human(ctx, "audit_event.export")
    if body.to_date < body.from_date or (body.to_date - body.from_date).days > MAX_DAYS:
        raise ExportRangeInvalid(facts={"max_days": MAX_DAYS})
    filter_json = _filter_json(body.filter)
    async with tenant_session(ctx.tenant) as session:
        found = (
            (await session.execute(_BY_KEY, {"by": ctx.user_id, "key": idempotency_key}))
            .mappings()
            .one_or_none()
        )
    if found is not None:
        return await _out(ctx.tenant, _row(dict(found)))
    export_id = uuid4()
    with suppress(_Unchanged):
        await _insert_request(ctx, body, filter_json, idempotency_key, export_id)
    async with tenant_session(ctx.tenant) as session:
        again = (
            (await session.execute(_BY_KEY, {"by": ctx.user_id, "key": idempotency_key}))
            .mappings()
            .one()
        )
    return await _out(ctx.tenant, _row(dict(again)))


async def _insert_request(
    ctx: AuthContext,
    body: AuditExportRequestIn,
    filter_json: dict[str, Fact],
    idempotency_key: str,
    export_id: UUID,
) -> None:
    async with uow(ctx.tenant) as tx:
        written = await tx.session.scalar(
            _INSERT,
            {
                "id": export_id,
                "tenant": ctx.tenant_id,
                "by": ctx.user_id,
                "filter": json.dumps(filter_json, sort_keys=True),
                "from_date": body.from_date,
                "to_date": body.to_date,
                "values": body.include_values,
                "key": idempotency_key,
            },
        )
        if written is None:
            raise _Unchanged  # the same key raced in: the first request stands
        tx.record(
            "audit_export.requested",
            target=Target(SUBJECT, export_id),
            after=Ref(days=(body.to_date - body.from_date).days + 1),
        )
        tx.emit(AuditExportRequested(export_id=export_id, requested_by=ctx.user_id))


async def read(ctx: AuthContext, export_id: UUID) -> AuditExport:
    """ADM-07 g: the requester's job; anyone else's answers 404."""
    _human(ctx, "audit_export.read")
    return await _out(ctx.tenant, await _mine(ctx, export_id))


async def _downloadable(ctx: AuthContext, export_id: UUID) -> _Row:
    row = await _mine(ctx, export_id)
    if row.status not in ("ready", "downloaded"):
        raise AuditExportNotReady
    if await _expired(ctx.tenant, row.expires_at):
        raise AuditExportExpired
    return row


def download_path(export_id: UUID) -> str:
    return f"/v1/audit-events/exports/{export_id}/download"


async def download_link(ctx: AuthContext, export_id: UUID) -> AuditExportLinkOut:
    """ADM-07 g: where the ZIP downloads while the second factor stays fresh (at most 15
    minutes, never past the export's expiry). The URL is the API's own route (ADR-104): it opens
    only with this person's session, so it is useless to anyone it is passed to."""
    _human(ctx, "audit_event.export")
    row = await _downloadable(ctx, export_id)
    if ctx.mfa_at is None:  # the matrix demanded a fresh factor
        raise Forbidden("audit_event.export", "condition")
    until = ctx.mfa_at + LINK_LIFETIME
    if row.expires_at is not None:
        until = min(until, row.expires_at)
    return AuditExportLinkOut(
        url=download_path(export_id),
        expires_at=until,
        manifest_sha256=cast(str, row.manifest_sha256),
    )


@dataclass(frozen=True)
class Download:
    file_name: str
    size: int
    tenant_id: UUID
    export_id: UUID
    segments: int

    async def stream(self) -> AsyncIterator[bytes]:
        for n in range(self.segments):
            yield await export_store.get_segment(_KIND, self.tenant_id, self.export_id, n)


_DOWNLOADED = text(
    "UPDATE audit_exports SET status = 'downloaded', updated_at = clock_timestamp() "
    "WHERE id = :id AND status = 'ready'"
)


async def download(ctx: AuthContext, export_id: UUID) -> Download:
    """AC-12: the requester's ZIP while it is ready; audited `audit_export.downloaded` naming
    them, before the first byte. 409 `export_not_ready`, 410 `export_expired`."""
    _human(ctx, "audit_event.export")
    row = await _downloadable(ctx, export_id)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(_DOWNLOADED, {"id": export_id})
        tx.record(
            "audit_export.downloaded",
            target=Target(SUBJECT, export_id),
            after=Ref(bytes=int(row.bundle_bytes or 0)),
        )
    return Download(
        file_name=f"{file_stem(row.from_date, row.to_date)}.zip",
        size=int(row.bundle_bytes or 0),
        tenant_id=ctx.tenant_id,
        export_id=export_id,
        segments=int(row.segment_count or 0),
    )


# --- the workflow's start (outbox) -------------------------------------------------------------


def _system(tenant_id: UUID, export_id: UUID | str) -> TenantContext:
    return TenantContext(tenant_id, "system", f"audit_export:{export_id}")


async def on_requested(event: OutboxEvent) -> None:
    """`audit_export.requested` starts the build, once per export (reuse rejected)."""
    export_id = UUID(str(event.payload["export_id"]))
    async with tenant_session(_system(event.tenant_id, export_id)) as session:
        found = (await session.execute(_BY_ID, {"id": export_id})).mappings().one_or_none()
    if found is None or found["status"] != "requested":
        return
    try:
        await dispatch(
            AuditExportWorkflow,
            AuditExportInput(str(event.tenant_id), str(export_id)),
            id=audit_export_workflow_id(str(event.tenant_id), str(export_id)),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
    except WorkflowAlreadyStartedError:
        return


SUBSCRIPTIONS: dict[str, Handler] = {AuditExportRequested.event_type: on_requested}


# --- the build ---------------------------------------------------------------------------------


def _cell(value: object) -> str:
    """A cell always read as text: formula leads neutralised (ADR-052)."""
    if value is None:
        return ""
    found = value if isinstance(value, str) else str(value)
    return f"'{found}" if found.startswith(_FORMULA_LEADS) else found


def _json_cell(value: object) -> str:
    if value in (None, {}, []):
        return ""
    return _cell(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def csv_line(row: AuditEventRow, values: AuditValuesOut | None, include_values: bool) -> list[str]:
    actor = row.actor
    cells: list[object] = [
        row.seq,
        row.effective_at.astimezone(UTC).isoformat(),
        row.action,
        row.category,
        actor.kind,
        actor.person.user_id if actor.person else None,
        actor.person.display_name if actor.person else None,
        actor.on_behalf_of.user_id if actor.on_behalf_of else None,
        actor.on_behalf_of.display_name if actor.on_behalf_of else None,
        actor.agent_id,
        actor.policy_ref,
        row.target.type,
        row.target.id,
        row.target.label,
        row.target.engagement_id,
        row.target.client_id,
        row.office_id,
        row.ip,
    ]
    out = [_cell(c) for c in cells]
    out.append(_json_cell(row.detail_facts))
    if include_values:
        out.append(values.status if values is not None else "unavailable")
        out.append(
            _json_cell(
                [r.model_dump(mode="json") for r in values.rows] if values is not None else None
            )
        )
    return out


def _beat(progress: int) -> None:
    """Heartbeat inside the activity; the same build called directly (tests, tooling) has none."""
    if activity.in_activity():
        activity.heartbeat(progress)


async def _still_allowed(ctx: AuthContext) -> None:
    """Security review: the requester still holds the export family's rights at build time, not
    only at the request. `audit_export.read` grants the same roles as `audit_event.export`
    without the fresh second factor a worker cannot have."""
    try:
        await authorise(ctx, "audit_export.read", Resource.firm(ctx.tenant_id))
    except Forbidden:
        raise _decided("requester_not_member") from None


def _decided(code: str) -> ApplicationError:
    return ApplicationError(code, type=code, non_retryable=True)


def _where(row: _Row) -> EventFilter:
    f = row.filter
    office = f.get("office_id")
    actor_kind = f.get("actor_kind")
    return EventFilter(
        actor_kind=cast(ActorKind, actor_kind) if isinstance(actor_kind, str) else None,
        object_type=cast(str | None, f.get("object_type")),
        action=cast(str | None, f.get("action")),
        office_id=UUID(str(office)) if office else None,
        from_date=row.from_date,
        to_date=row.to_date,
    )


def manifest_bytes(manifest: dict[str, object]) -> bytes:
    return json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False).encode() + b"\n"


def _zip(into: IO[bytes], files: list[tuple[str, IO[bytes] | bytes]]) -> None:
    with zipfile.ZipFile(into, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files:
            info = zipfile.ZipInfo(name, date_time=_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            if isinstance(content, bytes):
                archive.writestr(info, content)
                continue
            content.seek(0)
            with archive.open(info, "w") as target:
                while chunk := content.read(1024 * 1024):
                    target.write(chunk)


async def build(given: AuditExportInput) -> AuditExportFacts:
    """The bundle, read as the requester (AC-14), stored sealed; facts only come back."""
    tenant_id, export_id = UUID(given.tenant_id), UUID(given.export_id)
    async with tenant_session(_system(tenant_id, export_id)) as session:
        found = (await session.execute(_BY_ID, {"id": export_id})).mappings().one_or_none()
    if found is None:
        raise _decided("requester_not_member")  # not this tenant's: nothing to build
    row = _row(dict(found))
    ctx = await member_context(tenant_id, row.requested_by)
    if ctx is None:
        raise _decided("requester_not_member")
    await _still_allowed(ctx)
    try:
        signer = export_signer()
    except SigningUnavailable:
        raise _decided("signing_unavailable") from None
    if not export_store.configured():
        raise _decided("exports_unavailable")
    reader = await reader_of(ctx)
    where = _where(row)
    stem = file_stem(row.from_date, row.to_date)
    header = [*CSV_COLUMNS, *(VALUE_COLUMNS if row.include_values else ())]
    digest = hashlib.sha256()
    count, seq_from, seq_to, after = 0, None, None, 0
    with tempfile.TemporaryFile() as csv_file, tempfile.TemporaryFile() as bundle:
        text_out = io.StringIO()
        writer = csv.writer(text_out, lineterminator="\r\n")

        def flush() -> None:
            data = text_out.getvalue().encode("utf-8")
            digest.update(data)
            csv_file.write(data)
            text_out.seek(0)
            text_out.truncate(0)

        writer.writerow(header)
        flush()
        while True:
            batch = await export_batch(
                reader, where, after, PAGE, include_values=row.include_values
            )
            for event, values in batch:
                writer.writerow(csv_line(event, values, row.include_values))
                seq_from = event.seq if seq_from is None else seq_from
                seq_to = event.seq
                count += 1
            flush()
            _beat(count)
            if len(batch) < PAGE:
                break
            after = batch[-1][0].seq
        csv_sha256 = digest.hexdigest()
        checkpoint = await latest_checkpoint(tenant_id)
        try:
            key_id = await signer.resolve_key_id()
        except SigningUnavailable:
            raise _decided("signing_unavailable") from None
        manifest: dict[str, object] = {
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "export_id": str(export_id),
            "tenant_id": str(tenant_id),
            "requested_by": {"user_id": str(row.requested_by), "display_name": ""},
            "requested_at": row.created_at.astimezone(UTC).isoformat(),
            "range": {"from": row.from_date.isoformat(), "to": row.to_date.isoformat()},
            "filter": row.filter,
            "include_values": row.include_values,
            "files": [{"name": f"{stem}.csv", "sha256": csv_sha256, "rows": count}],
            "columns": header,
            "seq_from": seq_from,
            "seq_to": seq_to,
            "row_count": count,
            "checkpoint": (
                None
                if checkpoint is None
                else {
                    "checkpoint_no": checkpoint.checkpoint_no,
                    "seq_from": checkpoint.seq_from,
                    "seq_to": checkpoint.seq_to,
                    "chain_hash": checkpoint.chain_hash.hex(),
                    "merkle_root": checkpoint.merkle_root.hex(),
                    "covers_range": seq_to is None or checkpoint.seq_to >= seq_to,
                }
            ),
            "signature": {
                "file": "manifest.sig",
                "algorithm": "ECDSA_P256_SHA256",
                "encoding": "DER",
                "key_ref": signer.key_ref,
                "key_id": key_id,
            },
        }
        names = await names_of([row.requested_by])
        cast(dict[str, str], manifest["requested_by"])["display_name"] = names.get(
            row.requested_by, ""
        )
        body = manifest_bytes(manifest)
        try:
            signed = await signer.sign_digest(hashlib.sha256(body).digest())
        except SigningUnavailable:
            raise _decided("signing_unavailable") from None
        if signed.key_id != key_id:  # the alias moved mid-build: the manifest names another key
            raise _decided("signing_unavailable")
        signature = signed.signature
        _zip(
            bundle,
            [(f"{stem}.csv", csv_file), ("manifest.json", body), ("manifest.sig", signature)],
        )
        size = bundle.tell()
        bundle.seek(0)
        segments = await export_store.put_bundle(_KIND, tenant_id, export_id, bundle)
    return AuditExportFacts(
        tenant_id=given.tenant_id,
        export_id=given.export_id,
        row_count=count,
        seq_from=seq_from,
        seq_to=seq_to,
        csv_sha256=csv_sha256,
        manifest_sha256=hashlib.sha256(body).hexdigest(),
        bundle_bytes=size,
        segment_count=segments,
        signature_key_ref=signer.key_ref,
        signature_key_id=key_id,
    )


_READY = text(
    "UPDATE audit_exports SET status = 'ready', seq_from = :seq_from, seq_to = :seq_to, "
    "row_count = :rows, csv_key = :prefix, manifest_key = 'manifest.json', "
    "manifest_sha256 = :manifest, signature_key_ref = :key_ref, signature_key_id = :key_id, "
    "expires_at = :expires, "
    "segment_count = :segments, bundle_bytes = :bytes, updated_at = clock_timestamp() "
    "WHERE id = :id AND status = 'requested' RETURNING requested_by"
)
_FAILED = text(
    "UPDATE audit_exports SET status = 'failed', failure_code = :code, "
    "updated_at = clock_timestamp() WHERE id = :id AND status = 'requested' RETURNING id"
)


async def mark_ready(facts: AuditExportFacts) -> str:
    try:
        return await _mark_ready(facts)
    except _Unchanged:
        return "unchanged"  # a retried stamp: already ready


async def _mark_ready(facts: AuditExportFacts) -> str:
    tenant_id, export_id = UUID(facts.tenant_id), UUID(facts.export_id)
    system = _system(tenant_id, export_id)
    expires = max(await clock.now(system), clock.system_now()) + EXPIRY
    async with uow(system) as tx:
        by = await tx.session.scalar(
            _READY,
            {
                "id": export_id,
                "seq_from": facts.seq_from,
                "seq_to": facts.seq_to,
                "rows": facts.row_count,
                "prefix": export_store.bundle_prefix(_KIND, tenant_id, export_id),
                "manifest": facts.manifest_sha256,
                "key_ref": facts.signature_key_ref,
                "key_id": facts.signature_key_id or None,
                "expires": expires,
                "segments": facts.segment_count,
                "bytes": facts.bundle_bytes,
            },
        )
        if by is None:
            raise _Unchanged
        tx.record(
            "audit_export.ready",
            target=Target(SUBJECT, export_id),
            after=Ref(rows=facts.row_count, manifest=facts.manifest_sha256),
        )
        tx.emit(AuditExportReady(export_id=export_id, requested_by=cast(UUID, by)))
    return "ready"


async def mark_failed(failure: AuditExportFailure) -> str:
    tenant_id, export_id = UUID(failure.tenant_id), UUID(failure.export_id)
    try:
        async with uow(_system(tenant_id, export_id)) as tx:
            changed = await tx.session.scalar(_FAILED, {"id": export_id, "code": failure.code})
            if changed is None:
                raise _Unchanged
            tx.record("audit_export.failed", target=Target(SUBJECT, export_id))
    except _Unchanged:
        return "unchanged"
    _log.warning("audit_export.failed", tenant_id=str(tenant_id), code=failure.code)
    return "failed"


@activity.defn(name="audit_export.build")
async def build_activity(given: AuditExportInput) -> AuditExportFacts:
    return await build(given)


@activity.defn(name="audit_export.mark_ready")
async def mark_ready_activity(facts: AuditExportFacts) -> str:
    return await mark_ready(facts)


@activity.defn(name="audit_export.mark_failed")
async def mark_failed_activity(failure: AuditExportFailure) -> str:
    return await mark_failed(failure)


ACTIVITIES: tuple[object, ...] = (build_activity, mark_ready_activity, mark_failed_activity)

__all__ = [
    "ACTIVITIES",
    "CSV_COLUMNS",
    "FORMAT",
    "SUBSCRIPTIONS",
    "AuditExportExpired",
    "AuditExportNotReady",
    "Download",
    "ExportRangeInvalid",
    "build",
    "download",
    "download_link",
    "download_path",
    "file_stem",
    "manifest_bytes",
    "mark_failed",
    "mark_ready",
    "read",
    "request",
]

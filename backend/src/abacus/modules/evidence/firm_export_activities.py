"""The firm export's workflow start, its activities, expiry and clean-up (Q-02-T43;
compliance-kernel §7; DEC-508). PROTECTED (evidence, red).

Identifiers in, identifiers and digests out. The workflow input is never proof: each activity
reads the export row under the tenant and acts as the system on behalf of the approver (INV-5).

- `on_approved` (the `firm_export.approved` subscriber): starts `FirmExportWorkflow` once per
  export (reuse rejected), only while the row is `building` and decided by its named approver.
- `package`: the v1 skeleton archive (DEC-508): a ZIP with `index.json` (format 0.1: the export,
  the firm, the two people, when it was built, and `packages`, empty until Q-02-T47 adds one A-01
  package per engagement) and `manifest.json` (each other file's path, size and SHA-256). Built in
  worker scratch, off the event loop, and stored sealed under the tenant's key in 64 MiB segments
  (`export_storage`, `kind="firm_export"`). `manifest_sha256` is the manifest file's digest,
  `bundle_sha256` the archive's.
- `mark_ready` / `mark_failed`: the stamps (`available_until` = the approval + 7 days, SPEC-341
  AC-41: links can be minted for 7 days from approval), the audit event and, for ready, the
  outbox event that tells both people. A build finishing after its window is failed instead.
- Expiry (`expire_due`, run by the daily `export_expiry:platform` sweep's activity): every ready
  or downloaded export past `available_until` becomes `expired`, audited, and its
  `firm_export.expired` subscriber deletes the segments. A link already answers 410 from
  `available_until` itself.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
import zipfile
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
from typing import IO, Final
from uuid import UUID

from sqlalchemy import select, update
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel import clock
from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Handler, OutboxEvent, Ref, Target, uow
from abacus.modules.evidence.export_storage import delete_segments, export_prefix, put_segments
from abacus.modules.evidence.firm_export_events import (
    FirmExportApproved,
    FirmExportExpired,
    FirmExportReady,
)
from abacus.modules.evidence.firm_export_models import FirmExport
from abacus.modules.evidence.firm_exports import SUBJECT, WINDOW
from abacus.modules.evidence.workflow_types import BUILD_ERROR, FirmExportFacts, FirmExportInput
from abacus.modules.evidence.workflows import FirmExportWorkflow

FORMAT_VERSION: Final = "0.1"
SWEEP_BATCH: Final = 200
_ZIP_TIME: Final = (1980, 1, 1, 0, 0, 0)  # fixed entry times: the same rows give the same bytes
_log = get_logger(__name__)

WORKFLOWS: dict[type, WorkClass] = {FirmExportWorkflow: "batch"}
register_work_classes(WORKFLOWS)


class _Nothing(Exception):
    """Nothing to write: leave the unit of work without a commit (and without an audit row)."""


class _TooLate(Exception):
    """The archive was built after the 7 days from its approval: it is failed, never ready."""


class FirmExportNotBuilding(Exception):
    """The row is not an approved export waiting for its archive: nothing is built."""


def workflow_id(tenant_id: UUID, export_id: UUID) -> str:
    return f"firm_export:{tenant_id}:{export_id}"


def _system(row: FirmExport, purpose: str = "build") -> TenantContext:
    return TenantContext(
        row.tenant_id,
        "system",
        f"firm_export:{purpose}:{row.id}",
        on_behalf_of_user_id=row.decided_by or row.approver_id,
    )


def _fields(row: FirmExport) -> dict[str, UUID]:
    return {
        "export_id": row.id,
        "requested_by": row.requested_by,
        "approver_user_id": row.approver_id,
    }


def _approved(row: FirmExport | None) -> bool:
    """An export two distinct people agreed to: the row's own word, never the event's."""
    return (
        row is not None
        and row.decided_by is not None
        and row.decided_by == row.approver_id
        and row.decided_by != row.requested_by
    )


async def _row(tenant_id: UUID, export_id: UUID) -> FirmExport | None:
    reader = TenantContext(tenant_id, "system", f"firm_export:{export_id}")
    async with tenant_session(reader) as session:
        return await session.get(FirmExport, export_id, populate_existing=True)


# --- the start ---------------------------------------------------------------------------------


async def on_approved(event: OutboxEvent) -> None:
    """`firm_export.approved` starts the build's workflow, once per export (reuse rejected)."""
    export_id = UUID(str(event.payload["export_id"]))
    row = await _row(event.tenant_id, export_id)
    if row is None or row.status != "building" or not _approved(row):
        return
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            FirmExportWorkflow,
            FirmExportInput(str(event.tenant_id), str(export_id)),
            id=workflow_id(event.tenant_id, export_id),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )


# --- package -----------------------------------------------------------------------------------


def _json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


def _entry(archive: zipfile.ZipFile, path: str, data: bytes) -> None:
    info = zipfile.ZipInfo(path, date_time=_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)


def _iso(at: datetime) -> str:
    return at.isoformat().replace("+00:00", "Z")


def write_archive(out: IO[bytes], row: FirmExport, built_at: datetime) -> str:
    """The v1 skeleton archive into `out`; the manifest's SHA-256. Files: `index.json`, then
    `manifest.json` naming every other file with its size and digest (DEC-508)."""
    index = _json(
        {
            "format": "accrued-firm-export",
            "format_version": FORMAT_VERSION,
            "export_id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "scope": row.scope,
            "requested_by": str(row.requested_by),
            "approved_by": str(row.decided_by),
            "requested_at": _iso(row.requested_at),
            "built_at": _iso(built_at),
            # Q-02-T47: one A-01 engagement export package per engagement.
            "packages": [],
        }
    )
    files = [("index.json", index)]
    manifest = _json(
        {
            "format_version": FORMAT_VERSION,
            "export_id": str(row.id),
            "files": [
                {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                for path, data in files
            ],
        }
    )
    with zipfile.ZipFile(out, "w") as archive:
        for path, data in files:
            _entry(archive, path, data)
        _entry(archive, "manifest.json", manifest)
    return hashlib.sha256(manifest).hexdigest()


def _digest(handle: IO[bytes]) -> tuple[str, int]:
    handle.seek(0)
    digest = hashlib.sha256()
    size = 0
    while chunk := handle.read(1024 * 1024):
        digest.update(chunk)
        size += len(chunk)
    handle.seek(0)
    return digest.hexdigest(), size


def _quiet(*_details: object) -> None:
    return None


async def package_export(
    tenant_id: UUID,
    export_id: UUID,
    *,
    segment_bytes: int | None = None,
    heartbeat: Callable[..., None] = _quiet,
) -> FirmExportFacts:
    """Build and store the archive of an approved `building` export, reporting progress through
    `heartbeat` between its steps (the activity's)."""
    row = await _row(tenant_id, export_id)
    if row is None or row.status != "building" or not _approved(row):
        raise FirmExportNotBuilding(str(export_id))
    built_at = await clock.now(_system(row))
    with tempfile.TemporaryFile() as scratch:
        manifest_sha256 = await asyncio.to_thread(write_archive, scratch, row, built_at)
        bundle_sha256, size = await asyncio.to_thread(_digest, scratch)
        heartbeat("written")
        if segment_bytes is None:
            segments = await put_segments(
                tenant_id, export_id, scratch, kind="firm_export", progress=heartbeat
            )
        else:
            segments = await put_segments(
                tenant_id,
                export_id,
                scratch,
                segment_bytes=segment_bytes,
                kind="firm_export",
                progress=heartbeat,
            )
    heartbeat("stored")
    return FirmExportFacts(
        tenant_id=str(tenant_id),
        export_id=str(export_id),
        bundle_sha256=bundle_sha256,
        manifest_sha256=manifest_sha256,
        bytes=size,
        segment_count=segments,
        object_prefix=export_prefix(tenant_id, export_id, kind="firm_export"),
    )


# --- ready or failed ---------------------------------------------------------------------------


async def ready_export(facts: FirmExportFacts) -> str:
    """`ready` with its stamps and its 7-day window, under a lock on the row."""
    tenant_id, export_id = UUID(facts.tenant_id), UUID(facts.export_id)
    row = await _row(tenant_id, export_id)
    if row is None:
        return "missing"
    if row.status != "building":
        return row.status
    system = _system(row)
    now = await clock.now(system)
    try:
        async with uow(system) as tx:
            locked = await tx.session.scalar(
                select(FirmExport)
                .where(FirmExport.id == export_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if locked is None or locked.status != "building":
                raise _Nothing
            # A decision stamped after now (a clock moved back) is failed too, never wedged on the
            # window CHECK.
            decided = locked.decided_at
            if decided is None or decided > now or decided + WINDOW <= now:
                raise _TooLate
            await tx.session.execute(
                update(FirmExport)
                .where(FirmExport.id == export_id, FirmExport.status == "building")
                .values(
                    status="ready",
                    bundle_sha256=facts.bundle_sha256,
                    manifest_sha256=facts.manifest_sha256,
                    bytes=facts.bytes,
                    segment_count=facts.segment_count,
                    object_prefix=facts.object_prefix,
                    ready_at=now,
                    available_until=decided + WINDOW,
                )
            )
            tx.record(
                "firm_export.ready",
                target=Target(SUBJECT, export_id),
                after=Ref(
                    bytes=facts.bytes,
                    bundle=facts.bundle_sha256,
                    manifest=facts.manifest_sha256,
                ),
            )
            tx.emit(FirmExportReady(**_fields(locked)))
    except _Nothing:
        again = await _row(tenant_id, export_id)
        return again.status if again is not None else "missing"
    except _TooLate:
        return await fail_export(tenant_id, export_id)
    return "ready"


async def fail_export(tenant_id: UUID, export_id: UUID) -> str:
    """`failed`, audited; any segments an attempt stored are deleted (idempotent, so a retried
    activity finishes the clean-up)."""
    row = await _row(tenant_id, export_id)
    if row is None:
        return "missing"
    if row.status == "failed":
        await delete_segments(tenant_id, export_id, kind="firm_export")
        return "failed"
    if row.status != "building":
        return row.status
    try:
        async with uow(_system(row)) as tx:
            locked = await tx.session.scalar(
                select(FirmExport)
                .where(FirmExport.id == export_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if locked is None or locked.status != "building":
                raise _Nothing  # settled meanwhile (ready): nothing is failed or deleted
            await tx.session.execute(
                update(FirmExport)
                .where(FirmExport.id == export_id, FirmExport.status == "building")
                .values(status="failed", failure_code=BUILD_ERROR)
            )
            tx.record("firm_export.failed", target=Target(SUBJECT, export_id))
    except _Nothing:
        again = await _row(tenant_id, export_id)
        return again.status if again is not None else "missing"
    await delete_segments(tenant_id, export_id, kind="firm_export")
    return "failed"


# --- expiry and segments -----------------------------------------------------------------------


async def expire_due(tenant_id: UUID) -> int:
    """One firm: every ready or downloaded export past `available_until` becomes `expired`, in
    batches; how many."""
    sweeper = TenantContext(tenant_id, "system", "firm_export:sweep")
    expired = 0
    while True:
        now: datetime = max(await clock.now(sweeper), system_now())
        try:
            async with uow(sweeper) as tx:
                rows = list(
                    (
                        await tx.session.execute(
                            select(FirmExport)
                            .where(
                                FirmExport.status.in_(("ready", "downloaded")),
                                FirmExport.available_until <= now,
                            )
                            .order_by(FirmExport.available_until, FirmExport.id)
                            .limit(SWEEP_BATCH)
                            .with_for_update(skip_locked=True)
                        )
                    )
                    .scalars()
                    .all()
                )
                if not rows:
                    raise _Nothing
                for row in rows:
                    await tx.session.execute(
                        update(FirmExport)
                        .where(
                            FirmExport.id == row.id,
                            FirmExport.status.in_(("ready", "downloaded")),
                        )
                        .values(status="expired")
                    )
                    tx.record("firm_export.expired", target=Target(SUBJECT, row.id))
                    tx.emit(FirmExportExpired(**_fields(row)))
        except _Nothing:
            return expired
        expired += len(rows)
        if len(rows) < SWEEP_BATCH:
            return expired


async def on_expired(event: OutboxEvent) -> None:
    """`firm_export.expired`: delete the segments once the row (read under the event's tenant,
    never the payload's word) says `expired`."""
    row = await _row(event.tenant_id, UUID(str(event.payload["export_id"])))
    if row is None or row.status != "expired":
        return
    deleted = await delete_segments(row.tenant_id, row.id, kind="firm_export")
    _log.info("firm_export_segments.deleted", export_id=str(row.id), deleted=deleted)


# --- activities --------------------------------------------------------------------------------


@activity.defn(name="firm_export.package")
async def package_activity(given: FirmExportInput) -> FirmExportFacts:
    return await package_export(
        UUID(given.tenant_id), UUID(given.export_id), heartbeat=activity.heartbeat
    )


@activity.defn(name="firm_export.mark_ready")
async def mark_ready_activity(given: FirmExportFacts) -> str:
    return await ready_export(given)


@activity.defn(name="firm_export.mark_failed")
async def mark_failed_activity(given: FirmExportInput) -> str:
    return await fail_export(UUID(given.tenant_id), UUID(given.export_id))


ACTIVITIES = (package_activity, mark_ready_activity, mark_failed_activity)
SUBSCRIPTIONS: dict[str, Handler] = {
    FirmExportApproved.event_type: on_approved,
    FirmExportExpired.event_type: on_expired,
}

__all__ = [
    "ACTIVITIES",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "expire_due",
    "fail_export",
    "on_approved",
    "on_expired",
    "package_export",
    "ready_export",
    "workflow_id",
    "write_archive",
]

"""The engagement export workflow's activities and its start (A-01-T19; A-01 §4.5; SPEC-344
AC-9 to AC-13; DEC-433). PROTECTED.

Identifiers in, identifiers and digests out. The workflow input is never proof: each activity
reads the export row under the tenant and acts as the system on behalf of the requester (INV-5).

- `consume_grant`: the single gate (P-04-T10). Voided (an Undo) or refused: the run ends; not
  yet due: `GrantNotYetDue`, retried. Consumed: `packaging`.
- `snapshot`: the tenant's newest audit sequence becomes `as_of_seq`, and the versions the
  requester's selection holds now are written to `engagement_export_contents` (once).
- `package`: the selection (restricted to the snapshot), every registered section, the audit
  trail, every evidence file read through `evidence.storage.get` only when its ZIP entry is
  written (one original in memory at a time) and hashed as it is written against its
  fingerprint; the ZIP built in worker scratch, off the event loop, and stored sealed in 64 MiB
  segments.
  A swapped object fails `integrity_mismatch`, a core section without a provider
  `export_section_missing` (both decided, never retried); nothing is published either way.
- `mark_ready` / `mark_failed`: the stamps, the audit event and the outbox event.
"""

from __future__ import annotations

import asyncio
import math
import tempfile
from collections.abc import Callable
from contextlib import suppress
from datetime import timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import ApplicationError, WorkflowAlreadyStartedError

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import (
    AuditFilter,
    Handler,
    OutboxEvent,
    Ref,
    Scope,
    Target,
    audit_page,
    uow,
)
from abacus.modules.engagements.api import engagement_metadata
from abacus.modules.evidence import storage
from abacus.modules.evidence.export_builder import (
    PackageFacts,
    PackageFile,
    PackageIntegrityError,
    PackageInvalid,
    StreamedFile,
    build_package,
)
from abacus.modules.evidence.export_events import (
    EngagementExportFailed,
    EngagementExportRequested,
)
from abacus.modules.evidence.export_lifecycle import ReadyStamps, settle_ready
from abacus.modules.evidence.export_manifest import (
    AUDIT_TRAIL,
    ManifestClient,
    ManifestEngagement,
    ManifestEvidence,
    ManifestPerson,
    ManifestScope,
    ManifestSection,
)
from abacus.modules.evidence.export_models import EngagementExport, EngagementExportContent
from abacus.modules.evidence.export_package import (
    CORE_SECTIONS,
    ExportSectionInvalid,
    SectionRequest,
    missing_core_sections,
    registered_sections,
    section_path,
)
from abacus.modules.evidence.export_sections import (
    acting_person,
    audit_trail_lines,
    audit_trail_registered,
)
from abacus.modules.evidence.export_selection import Plan, plan_in_use, plan_selection
from abacus.modules.evidence.export_storage import SEGMENT_BYTES, export_prefix, put_segments
from abacus.modules.evidence.exports import ExportScope, grant_digest
from abacus.modules.evidence.workflow_types import (
    BUILD_ERROR,
    INTEGRITY_MISMATCH,
    SECTION_MISSING,
    EngagementExportInput,
    ExportFailure,
    ExportPackageFacts,
)
from abacus.modules.evidence.workflows import EngagementExportWorkflow
from abacus.modules.identity.api import consume_grant, firm_name, names_of

READY_FOR: Final = timedelta(days=7)
SUBJECT: Final = "engagement_export"
_log = get_logger(__name__)

WORKFLOWS: dict[type, WorkClass] = {EngagementExportWorkflow: "batch"}
register_work_classes(WORKFLOWS)


class _Settled(Exception):
    def __init__(self, status: str) -> None:
        super().__init__(status)
        self.status = status


class ExportBuildFailed(Exception):
    """A decided build failure: the export is marked failed with `code`, never retried."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def workflow_id(tenant_id: UUID, export_id: UUID) -> str:
    return f"engagement_export:{tenant_id}:{export_id}"


def _system(row: EngagementExport) -> TenantContext:
    return TenantContext(
        row.tenant_id,
        "system",
        f"engagement_export:{row.id}",
        on_behalf_of_user_id=row.requested_by,
    )


def _scope(row: EngagementExport) -> Scope:
    return Scope(engagement_id=row.engagement_id, work_item_id=row.work_item_id)


def _event_fields(row: EngagementExport) -> dict[str, UUID]:
    return {
        "export_id": row.id,
        "engagement_id": row.engagement_id,
        "work_item_id": row.work_item_id,
        "requested_by": row.requested_by,
    }


async def _row(tenant_id: UUID, export_id: UUID) -> EngagementExport:
    reader = TenantContext(tenant_id, "system", f"engagement_export:{export_id}")
    async with tenant_session(reader) as session:
        row = await session.get(EngagementExport, export_id)
    if row is None:
        raise ExportBuildFailed(BUILD_ERROR)  # not in this tenant: nothing to build
    return row


# --- the start ---------------------------------------------------------------------------------


async def on_requested(event: OutboxEvent) -> None:
    """`engagement_export.requested` starts the build's workflow, once per export (reuse
    rejected); it sleeps out the rest of the Undo window on the business clock."""
    export_id = UUID(str(event.payload["export_id"]))
    reader = TenantContext(event.tenant_id, "system", f"engagement_export:{export_id}")
    async with tenant_session(reader) as session:
        row = await session.get(EngagementExport, export_id)
    if row is None or row.status != "queued":
        return  # undone already, or not this tenant's
    left = (row.not_before - await clock.now(reader)).total_seconds()
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            EngagementExportWorkflow,
            EngagementExportInput(str(event.tenant_id), str(export_id), max(0, math.ceil(left))),
            id=workflow_id(event.tenant_id, export_id),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )


SUBSCRIPTIONS: dict[str, Handler] = {EngagementExportRequested.event_type: on_requested}


# --- consume the grant -------------------------------------------------------------------------


async def start_export(tenant_id: UUID, export_id: UUID) -> str:
    """`packaging` once the grant is consumed; `undone` when an Undo voided it; `failed` when it
    was refused (expired, or the requester lost `export.create`). Raises `GrantNotYetDue`."""
    row = await _row(tenant_id, export_id)
    if row.status != "queued":
        return row.status  # a retried activity: the decision is already made
    digest = grant_digest(row.id, row.work_item_id, row.kind, row.scope)
    if not await consume_grant(tenant_id, row.grant_id, row.id, digest):
        again = await _row(tenant_id, export_id)
        if again.status == "queued":
            return await fail_export(tenant_id, export_id, BUILD_ERROR)
        return again.status
    async with uow(_system(row)) as tx:
        await tx.session.execute(
            update(EngagementExport)
            .where(EngagementExport.id == row.id, EngagementExport.status == "queued")
            .values(status="packaging")
        )
        tx.record(
            "engagement_export.started",
            target=Target(SUBJECT, row.id),
            after=Ref(grant=row.grant_id),
            scope=_scope(row),
        )
    return "packaging"


# --- snapshot ----------------------------------------------------------------------------------


def _section_request(row: EngagementExport, membership_id: UUID, as_of_seq: int) -> SectionRequest:
    scope = ExportScope.of(row.scope)
    return SectionRequest(
        export_id=row.id,
        engagement_id=row.engagement_id,
        work_item_id=row.work_item_id,
        binder_ids=scope.binder_ids,
        as_of_seq=as_of_seq,
        include_unaccepted=scope.include_unaccepted,
        requested_by_user_id=row.requested_by,
        membership_id=membership_id,
    )


async def snapshot_export(tenant_id: UUID, export_id: UUID) -> int:
    """One audit sequence for the whole selection; the selected versions recorded once."""
    row = await _row(tenant_id, export_id)
    if row.as_of_seq is not None:
        return row.as_of_seq
    system = _system(row)
    async with tenant_session(system) as session:
        newest = await audit_page(session, AuditFilter(), None, 1)  # the trail's own reader
    as_of_seq = newest[0].seq if newest else 0
    try:
        ctx = await acting_person(system, row.requested_by)
        plan = await plan_selection(ctx, _section_request(row, ctx.membership_id, as_of_seq))
    except ExportSectionInvalid:
        raise ExportBuildFailed(BUILD_ERROR) from None
    async with uow(system) as tx:
        versions = sorted(plan.version_ids)
        if versions:
            await tx.session.execute(
                insert(EngagementExportContent)
                .values(
                    [
                        {"tenant_id": tenant_id, "export_id": export_id, "evidence_version_id": v}
                        for v in versions
                    ]
                )
                .on_conflict_do_nothing()
            )
        await tx.session.execute(
            update(EngagementExport)
            .where(EngagementExport.id == export_id)
            .values(as_of_seq=as_of_seq)
        )
        tx.record(
            "engagement_export.snapshotted",
            target=Target(SUBJECT, export_id),
            after=Ref(as_of_seq=as_of_seq, files=len(versions), requests=len(plan.requests)),
            scope=_scope(row),
        )
    return as_of_seq


# --- package -----------------------------------------------------------------------------------


async def _contents(tenant: TenantContext, export_id: UUID) -> frozenset[UUID]:
    async with tenant_session(tenant) as session:
        found = await session.execute(
            select(EngagementExportContent.evidence_version_id).where(
                EngagementExportContent.export_id == export_id
            )
        )
        return frozenset(found.scalars().all())


def _evidence_files(
    tenant_id: UUID,
    plan: Plan,
    loop: asyncio.AbstractEventLoop,
    heartbeat: Callable[[], None],
) -> list[StreamedFile]:
    """Each file named by its fingerprint and read only when the builder writes its entry, from
    the builder's thread through the event loop; storage verifies it, and the builder hashes it
    again as it writes."""

    def reader(stored: storage.StoredObject, path: str) -> Callable[[], bytes]:
        async def fetch() -> bytes:
            try:
                return await storage.get(tenant_id, stored)
            except storage.IntegrityError:
                raise PackageIntegrityError(path) from None
            finally:
                heartbeat()

        return lambda: asyncio.run_coroutine_threadsafe(fetch(), loop).result()

    return [
        StreamedFile(
            f.path,
            f.fingerprint,
            f.size_bytes,
            "evidence",
            reader(
                storage.StoredObject(
                    f.storage_key, f.storage_version_id, f.fingerprint, f.size_bytes
                ),
                f.path,
            ),
            evidence=ManifestEvidence(
                evidence_version_id=f.evidence_version_id,
                request_item_id=f.request_item_id,
                binder_id=f.binder_id,
                version_no=f.version_no,
                review_state=f.review_state,
                media_type=f.media_type,
            ),
        )
        for f in plan.files
    ]


# Q-02-T47: the firm export builds its per-engagement packages with the same file reader.
evidence_files = _evidence_files


async def section_files(
    tenant: TenantContext, request: SectionRequest
) -> tuple[list[PackageFile], list[ManifestSection]]:
    if missing_core_sections():
        raise ExportBuildFailed(SECTION_MISSING)
    files: list[PackageFile] = []
    sections: list[ManifestSection] = []
    for section in registered_sections():
        produced = list(await section.provider(tenant, request))
        if section.name in CORE_SECTIONS:
            if len(produced) != 1:
                raise ExportBuildFailed(BUILD_ERROR)
            role = "index" if section.name == "index" else "provenance"
            files.append(PackageFile(section_path(section.name, ""), produced[0].content, role))
            continue
        for made in produced:
            files.append(
                PackageFile(
                    section_path(section.name, made.name),
                    made.content,
                    "section",
                    section=section.name,
                )
            )
        if produced:
            sections.append(
                ManifestSection(
                    name=section.name,
                    section_version=section.section_version,
                    file_count=len(produced),
                )
            )
    return files, sections


async def package_export(
    tenant_id: UUID,
    export_id: UUID,
    *,
    heartbeat: Callable[[], None] = lambda: None,
    segment_bytes: int | None = None,
) -> ExportPackageFacts:
    """Build, verify and store the package; nothing is published here (`mark_ready` does)."""
    row = await _row(tenant_id, export_id)
    if row.status != "packaging" or row.as_of_seq is None:
        raise ExportBuildFailed(BUILD_ERROR)
    system = _system(row)
    scope = ExportScope.of(row.scope)
    if scope.include_audit_trail and not audit_trail_registered():
        raise ExportBuildFailed(SECTION_MISSING)
    try:
        ctx = await acting_person(system, row.requested_by)
        request = _section_request(row, ctx.membership_id, row.as_of_seq)
        only = await _contents(system, export_id)
        plan = await plan_selection(ctx, request, only=only)
        with plan_in_use(plan):
            sections, extra = await section_files(system, request)
        if scope.include_audit_trail:
            sections.append(
                PackageFile(AUDIT_TRAIL, await audit_trail_lines(ctx, request), "audit_trail")
            )
        evidence = _evidence_files(tenant_id, plan, asyncio.get_running_loop(), heartbeat)
        meta = await engagement_metadata(ctx, row.engagement_id)
        names = await names_of([row.requested_by])
        facts = PackageFacts(
            export_id=row.id,
            kind=row.kind,
            generated_at=row.not_before,
            as_of_seq=row.as_of_seq,
            tenant_id=tenant_id,
            firm_name=await firm_name(tenant_id),
            client=ManifestClient(
                client_id=row.client_id, display_name=meta.engagement.client_name
            ),
            engagement=ManifestEngagement(
                engagement_id=row.engagement_id,
                work_item_id=row.work_item_id,
                display_name=meta.engagement.name,
                period_end=meta.engagement.fiscal_period_end,
            ),
            requested_by=ManifestPerson(
                user_id=row.requested_by,
                display_name=names.get(row.requested_by) or "Unknown person",
            ),
            requested_at=row.requested_at,
            scope=ManifestScope(
                binder_ids=list(scope.binder_ids),
                include_unaccepted=scope.include_unaccepted,
                include_audit_trail=scope.include_audit_trail,
            ),
            request_count=len(plan.requests),
            requests_without_file=sum(1 for r in plan.requests if not r.files),
            sections=tuple(extra),
        )
    except ExportSectionInvalid:
        raise ExportBuildFailed(BUILD_ERROR) from None
    with tempfile.TemporaryFile() as scratch:  # worker scratch, removed on close
        try:
            built = await asyncio.to_thread(build_package, facts, [*sections, *evidence], scratch)
        except PackageInvalid:
            raise ExportBuildFailed(BUILD_ERROR) from None
        except PackageIntegrityError as mismatch:
            failed_path = mismatch.path
            version_id = next(
                (f.evidence_version_id for f in plan.files if f.path == failed_path), None
            )
            # RB-29: the integrity alarm reads this event. Identifiers only.
            _log.error(
                "evidence.integrity_mismatch",
                tenant_id=tenant_id,
                evidence_version_id=version_id,
                export_id=plan.export_id,
            )
            raise ExportBuildFailed(INTEGRITY_MISMATCH) from None
        heartbeat()
        segments = await put_segments(
            tenant_id, export_id, scratch, segment_bytes=segment_bytes or SEGMENT_BYTES
        )
    return ExportPackageFacts(
        tenant_id=str(tenant_id),
        export_id=str(export_id),
        bundle_sha256=built.bundle_sha256,
        manifest_sha256=built.manifest_sha256,
        bytes=built.bytes,
        file_count=built.file_count,
        request_count=facts.request_count,
        segment_count=segments,
        object_prefix=export_prefix(tenant_id, export_id),
    )


# --- ready or failed ---------------------------------------------------------------------------


async def ready_export(facts: ExportPackageFacts) -> str:
    """`ready` with its stamps, under a lock on the row; voided at once when a version it holds
    was withdrawn while it was built (A-01-T22, `export_lifecycle.settle_ready`)."""
    tenant_id, export_id = UUID(facts.tenant_id), UUID(facts.export_id)
    row = await _row(tenant_id, export_id)
    if row.status != "packaging":
        return row.status
    system = _system(row)
    now = await clock.now(system)
    try:
        async with uow(system) as tx:
            locked = await tx.session.scalar(
                select(EngagementExport)
                .where(EngagementExport.id == export_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if locked is None or locked.status != "packaging":
                raise _Settled(locked.status if locked is not None else row.status)
            return await settle_ready(
                tx,
                system,
                locked,
                ReadyStamps(
                    bundle_sha256=facts.bundle_sha256,
                    manifest_sha256=facts.manifest_sha256,
                    bytes=facts.bytes,
                    file_count=facts.file_count,
                    request_count=facts.request_count,
                    segment_count=facts.segment_count,
                    object_prefix=facts.object_prefix,
                    ready_at=now,
                    expires_at=now + READY_FOR,
                ),
            )
    except _Settled as settled:  # another attempt settled it meanwhile: nothing is written
        return settled.status


async def fail_export(tenant_id: UUID, export_id: UUID, code: str) -> str:
    row = await _row(tenant_id, export_id)
    if row.status not in ("queued", "packaging"):
        return row.status
    async with uow(_system(row)) as tx:
        await tx.session.execute(
            update(EngagementExport)
            .where(
                EngagementExport.id == export_id,
                EngagementExport.status.in_(("queued", "packaging")),
            )
            .values(status="failed", failure_code=code)
        )
        tx.record("engagement_export.failed", target=Target(SUBJECT, export_id), scope=_scope(row))
        tx.emit(EngagementExportFailed(**_event_fields(row)))
    return "failed"


# --- activities --------------------------------------------------------------------------------


def _decided(error: ExportBuildFailed) -> ApplicationError:
    return ApplicationError(
        error.code,
        type=error.code,
        non_retryable=error.code in (INTEGRITY_MISMATCH, SECTION_MISSING),
    )


@activity.defn(name="engagement_export.consume_grant")
async def consume_grant_activity(given: EngagementExportInput) -> str:
    return await start_export(UUID(given.tenant_id), UUID(given.export_id))


@activity.defn(name="engagement_export.snapshot")
async def snapshot_activity(given: EngagementExportInput) -> int:
    try:
        return await snapshot_export(UUID(given.tenant_id), UUID(given.export_id))
    except ExportBuildFailed as error:
        raise _decided(error) from None


@activity.defn(name="engagement_export.package")
async def package_activity(given: EngagementExportInput) -> ExportPackageFacts:
    try:
        return await package_export(
            UUID(given.tenant_id), UUID(given.export_id), heartbeat=activity.heartbeat
        )
    except ExportBuildFailed as error:
        raise _decided(error) from None


@activity.defn(name="engagement_export.mark_ready")
async def mark_ready_activity(given: ExportPackageFacts) -> str:
    return await ready_export(given)


@activity.defn(name="engagement_export.mark_failed")
async def mark_failed_activity(given: ExportFailure) -> str:
    return await fail_export(UUID(given.tenant_id), UUID(given.export_id), given.failure_code)


ACTIVITIES = (
    consume_grant_activity,
    snapshot_activity,
    package_activity,
    mark_ready_activity,
    mark_failed_activity,
)

"""General ledger detail imports (SPEC-034; TASK-069). PROTECTED.

`receive_gl_export`: the flag, permission and client data gate before the body is read; then the
malware scan before anything parses it; the file is stored write-once and recorded as a
`gl_imports` row (`processing`), and `GlImportWorkflow` takes over (D1), so a large ledger never
holds a request open. The same file again returns its first import.

`process_gl_import` (the workflow's one activity, on one worker so the temporary file stays
local): without the period's trial balance snapshot it waits (`waiting_for_tb`, SPEC-034 Q4);
otherwise the file is parsed in an isolated child that writes the postings to a private temporary
file (D2, D3), checked by `ledger.validate_gl`, and, if complete, snapshotted with its entries in
one transaction (`reconciled`); else `failed` with code-computed details. The temporary directory
is removed whatever happens. `ledger_snapshot.recorded` restarts waiting imports.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from uuid import UUID, uuid4

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel import _flags
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.scanning import scan
from abacus.kernel.uow import OutboxEvent, Ref, Target, uow
from abacus.modules.connections.gl_formats import GL_FORMATS
from abacus.modules.connections.gl_parse import MAX_GL_BYTES, parse_gl_isolated, read_entries
from abacus.modules.connections.ledger_import import (
    EmptyFile,
    FileRefused,
    FileTooLarge,
    ImportOff,
    UnknownFormat,
)
from abacus.modules.connections.models import GlImport
from abacus.modules.connections.repository import (
    get_gl_import,
    gl_import_by_fingerprint,
    insert_gl_import,
    latest_gl_import,
    set_gl_import,
    waiting_gl_imports,
)
from abacus.modules.connections.workflow_types import GlImportInput
from abacus.modules.connections.workflows import GlImportWorkflow
from abacus.modules.engagements.api import engagement_metadata, gate_client_data, get_ref
from abacus.modules.evidence.api import ContentTooLarge, StoredObject, read_content, stage_content
from abacus.modules.identity.api import AuthContext, authorise, engagement_role_of
from abacus.modules.ledger.api import (
    NormaliseError,
    Unvalidated,
    record_gl_snapshot,
    validate_gl,
    year_end_trial_balance,
)

_log = get_logger(__name__)
_CLIENT_ROLES: Final = frozenset({"client_admin", "client_contributor"})
WORKFLOWS: dict[type, WorkClass] = {GlImportWorkflow: "batch"}
register_work_classes(WORKFLOWS)


def workflow_id(tenant_id: UUID, import_id: UUID) -> str:
    return f"gl_import:{tenant_id}:{import_id}"


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "connections.gl_import")


@dataclass(frozen=True)
class GlImportView:
    id: UUID
    format: str
    status: str  # processing | waiting_for_tb | reconciled | failed
    failure_code: str | None
    failure_details: dict[str, object] | None
    line_count: int | None
    gl_snapshot_id: UUID | None
    created_at: datetime
    duplicate: bool = False


def _view(row: GlImport, *, duplicate: bool = False) -> GlImportView:
    return GlImportView(
        row.id,
        row.format,
        row.status,
        row.failure_code,
        row.failure_details,
        row.line_count,
        row.gl_snapshot_id,
        row.created_at,
        duplicate,
    )


async def check_gl_receive(ctx: AuthContext, engagement_id: UUID) -> None:
    """Before the body is read: the flag, the permission and the client data gate."""
    if not await flag_enabled(ctx.tenant, _flags.LEDGER_GL_IMPORT):
        raise ImportOff(str(engagement_id))
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "ledger_import.upload", ref.resource())
    await gate_client_data(ctx, engagement_id, "ledger_import.upload")


async def dispatch_gl_import(tenant_id: UUID, import_id: UUID, *, again: str = "") -> None:
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            GlImportWorkflow,
            GlImportInput(str(tenant_id), str(import_id)),
            id=workflow_id(tenant_id, import_id) + (f":{again}" if again else ""),
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )


async def receive_gl_export(
    ctx: AuthContext, engagement_id: UUID, *, format_id: str, content: bytes
) -> GlImportView:
    """SPEC-034 AC-1, AC-2, AC-7: stored, recorded `processing`, and handed to the workflow."""
    await check_gl_receive(ctx, engagement_id)
    ref = await get_ref(ctx, engagement_id)
    fmt = GL_FORMATS.get(format_id)
    if fmt is None:
        raise UnknownFormat(format_id[:50])
    if not content:
        raise EmptyFile(str(engagement_id))
    if len(content) > MAX_GL_BYTES:
        raise FileTooLarge(str(engagement_id))
    result = await asyncio.to_thread(scan, content)  # ADR-110: before anything parses it
    if not result.clean:
        async with uow(ctx.tenant) as tx:
            tx.record(
                "gl_import.refused",
                target=Target("engagement", engagement_id),
                after=Ref(size=len(content)),
            )
        raise FileRefused(result.reason or "refused")
    metadata = await engagement_metadata(ctx, engagement_id)
    start = metadata.engagement.fiscal_period_start
    end = metadata.engagement.fiscal_period_end
    try:
        stored = await stage_content(ctx.tenant_id, content)
    except ContentTooLarge:  # the storage cap, should the two limits ever differ
        raise FileTooLarge(str(engagement_id)) from None
    role = await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id)
    import_id = uuid4()
    async with uow(ctx.tenant) as tx:
        row = await insert_gl_import(
            tx.session,
            id=import_id,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            client_entity_id=ref.client_entity_id,
            format=fmt.id,
            period_start=start,
            period_end=end,
            storage_key=stored.key,
            storage_version_id=stored.version_id,
            fingerprint=stored.fingerprint,
            size_bytes=stored.size,
            uploaded_by=ctx.user_id,
            on_behalf=role not in _CLIENT_ROLES,
        )
        if row is None:  # AC-7: the same file again
            found = await gl_import_by_fingerprint(
                tx.session, ref.client_entity_id, stored.fingerprint
            )
            if found is None:
                raise NotFound("gl_import")
            tx.record("gl_import.duplicate", target=Target("gl_import", found.id))
            return _view(found, duplicate=True)
        tx.record(
            "gl_import.received",
            target=Target("gl_import", import_id),
            after=Ref(engagement_id=engagement_id, fingerprint=stored.fingerprint),
        )
    await dispatch_gl_import(ctx.tenant_id, import_id)
    return _view(row)


async def latest_gl(ctx: AuthContext, engagement_id: UUID) -> GlImportView | None:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "connection.read_log", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        row = await latest_gl_import(session, ref.client_entity_id)
    return None if row is None else _view(row)


async def _set(tenant: TenantContext, import_id: UUID, action: str, **values: object) -> None:
    async with uow(tenant) as tx:
        await set_gl_import(tx.session, import_id, updated_at=datetime.now(UTC), **values)
        refs: dict[str, UUID | int | str] = {}
        snapshot, lines = values.get("gl_snapshot_id"), values.get("line_count")
        if isinstance(snapshot, UUID):
            refs["gl_snapshot_id"] = snapshot
        if isinstance(lines, int):
            refs["lines"] = lines
        tx.record(
            action, target=Target("gl_import", import_id), after=Ref(**refs) if refs else None
        )


def _details(
    accounts: tuple[tuple[str, object], ...], months: tuple[str, ...]
) -> dict[str, object]:
    """Codes and code-computed numbers only (AC-5)."""
    return {
        "accounts": [
            {"code": code, "difference": str(difference)} for code, difference in accounts
        ],
        "months": list(months),
    }


async def process_gl_import(tenant_id: UUID, import_id: UUID) -> str:
    """The workflow's activity: the import's status once done (SPEC-034 AC-3, AC-4)."""
    tenant = _system(tenant_id)
    async with tenant_session(tenant) as session:
        row = await get_gl_import(session, import_id)
    if row is None:
        raise NotFound("gl_import")
    if row.status in ("reconciled", "failed"):
        return row.status
    tb = await year_end_trial_balance(
        tenant, row.client_entity_id, row.period_start, row.period_end
    )
    if tb is None:
        if row.status != "waiting_for_tb":
            await _set(tenant, import_id, "gl_import.waiting", status="waiting_for_tb")
        return "waiting_for_tb"
    if row.status != "processing":
        await _set(tenant, import_id, "gl_import.resumed", status="processing")
    stored = StoredObject(row.storage_key, row.storage_version_id, row.fingerprint, row.size_bytes)
    content = await read_content(tenant, stored)
    workdir = Path(tempfile.mkdtemp(prefix="abacus-gl-"))  # private (0700), this worker only
    try:
        out = str(workdir / "entries.csv")
        try:
            summary = await asyncio.to_thread(
                parse_gl_isolated, content, row.format, row.period_start, row.period_end, out
            )
        except NormaliseError as exc:
            await _set(
                tenant, import_id, "gl_import.failed", status="failed", failure_code=exc.code
            )
            return "failed"
        check = validate_gl(
            summary, tb.accounts, period_start=row.period_start, period_end=row.period_end
        )
        if check.failure is not None:
            await _set(
                tenant,
                import_id,
                "gl_import.failed",
                status="failed",
                failure_code=check.failure,
                failure_details=_details(check.accounts, check.months),
                line_count=summary.line_count,
            )
            return "failed"
        fmt = GL_FORMATS[row.format]
        try:
            async with uow(tenant) as tx:
                recorded = await record_gl_snapshot(
                    tx,
                    client_entity_id=row.client_entity_id,
                    period_start=row.period_start,
                    period_end=row.period_end,
                    summary=summary,
                    entries=read_entries(out),
                    tb_snapshot_id=tb.snapshot_id,
                    raw_fingerprint=row.fingerprint,
                    source=fmt.source,
                )
        except Unvalidated as exc:  # the trial balance changed between the check and now
            await _set(
                tenant, import_id, "gl_import.failed", status="failed", failure_code=str(exc)
            )
            return "failed"
        await _set(
            tenant,
            import_id,
            "gl_import.reconciled",
            status="reconciled",
            gl_snapshot_id=recorded.id,
            line_count=summary.line_count,
        )
        return "reconciled"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def on_ledger_snapshot_recorded(event: OutboxEvent) -> None:
    """AC-4: a trial balance arrived; check the general ledgers waiting for it."""
    tenant = _system(event.tenant_id)
    entity = UUID(str(event.payload["client_entity_id"]))
    async with tenant_session(tenant) as session:
        waiting = await waiting_gl_imports(session, entity)
    for row in waiting:
        await dispatch_gl_import(event.tenant_id, row.id, again=str(event.event_id))

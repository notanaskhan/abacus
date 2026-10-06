"""The six retrieval stages (ADR-038; TASK-010 design §5). PROTECTED.

    extract → raw → normalise → validate → snapshot → render (+ fulfilment)

Each stage takes the system context and the run ID and nothing else, re-reads what it needs, and
is safe to repeat: TASK-010b runs each as a Temporal activity that may be retried after a crash.
Only identifiers cross stages; ledger data stays in storage and the database. A stage that finds
its work done returns the earlier result; a run that has failed raises `RunFailed`.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.connections.connector import ConnectorError, Period, RawPayload, Unavailable
from abacus.modules.connections.models import SyncRun
from abacus.modules.connections.repository import (
    finish,
    get_connection,
    get_run,
    lock_run,
    set_raw,
    set_snapshot,
)
from abacus.modules.connections.service import connector_for
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.evidence.api import (
    XLSX_MEDIA_TYPE,
    NewItem,
    Provenance,
    StoredObject,
    add_version,
    read_content,
    render_trial_balance,
    stage_content,
)
from abacus.modules.identity.api import SystemContext, authorise
from abacus.modules.ledger.api import (
    NormalisedTrialBalance,
    NormaliseError,
    normalise,
    record_snapshot,
    trial_balance_for,
    validate,
)
from abacus.modules.organisations.api import client_names
from abacus.modules.requests.api import fulfil_by_rule


class RunFailed(Exception):
    """The run has ended without evidence; `code` and `status` are on the sync run."""

    def __init__(self, status: str, code: str) -> None:
        super().__init__(f"{status}: {code}")
        self.status = status
        self.code = code


@dataclass(frozen=True)
class RunResult:
    run_id: UUID
    snapshot_id: UUID
    evidence_version_id: UUID


async def _run(sys: SystemContext, run_id: UUID) -> SyncRun:
    async with tenant_session(sys.tenant) as session:
        run = await get_run(session, run_id)
    if run is None or run.id != sys.run_id:
        raise NotFound("sync_run")
    if run.status in ("failed", "failed_validation"):
        raise RunFailed(run.status, run.failure_code or "unknown")
    return run


async def fail(sys: SystemContext, run_id: UUID, status: str, code: str) -> RunFailed:
    """Mark the run failed (once) and return the exception for the caller to raise."""
    async with uow(sys.tenant) as tx:
        run = await lock_run(tx.session, run_id)
        if run is not None and run.status == "running":
            await finish(tx.session, run_id, status=status, failure_code=code)
        tx.record("sync_run.failed", target=Target("sync_run", run_id))
    return RunFailed(status, code)


# 1. extract ------------------------------------------------------------------------------------
async def extract(sys: SystemContext, run_id: UUID) -> RawPayload:
    run = await _run(sys, run_id)
    engagement = await get_ref(sys, run.engagement_id)
    await authorise(sys, "connection.pull", engagement.resource())
    async with tenant_session(sys.tenant) as session:
        connection = await get_connection(session, run.connection_id)
    if connection is None or connection.status != "active":
        raise await fail(sys, run_id, "failed", "connection_inactive")
    try:
        return await connector_for(connection).pull(
            "trial_balance", Period(run.period_start, run.period_end), None
        )
    except Unavailable:
        raise  # retryable: the workflow retries the activity (TASK-010b)
    except ConnectorError as exc:
        raise await fail(sys, run_id, "failed", exc.code) from None


# 2. raw ----------------------------------------------------------------------------------------
async def store_raw(sys: SystemContext, run_id: UUID, raw: RawPayload) -> StoredObject:
    run = await _run(sys, run_id)
    if run.raw_fingerprint is not None:
        return _stored(run)  # a retry after the raw payload was already recorded
    stored = await stage_content(sys.tenant_id, raw.content)
    async with uow(sys.tenant) as tx:
        locked = await lock_run(tx.session, run_id)
        if locked is None:
            raise NotFound("sync_run")
        if locked.raw_fingerprint is None:
            await set_raw(
                tx.session,
                run_id,
                key=stored.key,
                version_id=stored.version_id,
                fingerprint=stored.fingerprint,
                size=stored.size,
                pulled_at=raw.pulled_at,
            )
        tx.record(
            "sync_run.raw_stored",
            target=Target("sync_run", run_id),
            after=Ref(raw_fingerprint=stored.fingerprint),
        )
    return stored


def _stored(run: SyncRun) -> StoredObject:
    if (
        run.raw_storage_key is None
        or run.raw_version_id is None
        or run.raw_fingerprint is None
        or run.raw_size_bytes is None
    ):
        raise NotFound("raw payload")
    return StoredObject(
        run.raw_storage_key, run.raw_version_id, run.raw_fingerprint, run.raw_size_bytes
    )


# 3. normalise ----------------------------------------------------------------------------------
async def _normalised(sys: SystemContext, run: SyncRun) -> NormalisedTrialBalance:
    content = await read_content(sys.tenant, _stored(run))
    try:
        return normalise(content)
    except NormaliseError as exc:
        raise await fail(sys, run.id, "failed", exc.code) from None


async def normalise_raw(sys: SystemContext, run_id: UUID) -> int:
    """Stage 3: the stored raw payload parses into the common model. Returns the line count."""
    return len((await _normalised(sys, await _run(sys, run_id))).lines)


# 4. validate -----------------------------------------------------------------------------------
async def validate_run(sys: SystemContext, run_id: UUID) -> None:
    """Stage 4: control totals (AC-11). A failure ends the run: no snapshot, no evidence."""
    run = await _run(sys, run_id)
    failure = validate(
        await _normalised(sys, run), period_start=run.period_start, period_end=run.period_end
    )
    if failure is not None:
        raise await fail(sys, run_id, "failed_validation", failure)


# 5. snapshot -----------------------------------------------------------------------------------
async def snapshot(sys: SystemContext, run_id: UUID) -> UUID:
    run = await _run(sys, run_id)
    if run.snapshot_id is not None:
        return run.snapshot_id
    tb = await _normalised(sys, run)
    failure = validate(tb, period_start=run.period_start, period_end=run.period_end)
    if failure is not None:  # validate_run ran first; never snapshot unvalidated data
        raise await fail(sys, run_id, "failed_validation", failure)
    engagement = await get_ref(sys, run.engagement_id)
    if run.raw_pulled_at is None or run.raw_fingerprint is None:
        raise NotFound("raw payload")
    async with uow(sys.tenant) as tx:
        locked = await lock_run(tx.session, run_id)
        if locked is None:
            raise NotFound("sync_run")
        if locked.snapshot_id is not None:
            snapshot_id = locked.snapshot_id
        else:
            recorded = await record_snapshot(
                tx,
                client_entity_id=engagement.client_entity_id,
                tb=tb,
                raw_fingerprint=run.raw_fingerprint,
                pulled_at=run.raw_pulled_at,
                source="fake",
            )
            snapshot_id = recorded.id
            await set_snapshot(tx.session, run_id, snapshot_id)
        tx.record(
            "sync_run.snapshot_linked",
            target=Target("sync_run", run_id),
            after=Ref(snapshot_id=snapshot_id),
        )
    return snapshot_id


# 6. render (+ fulfilment) ----------------------------------------------------------------------
async def render(sys: SystemContext, run_id: UUID) -> UUID:
    """Render the snapshot, add it as an evidence version, fulfil the request item by rule, and
    finish the run (AC-10). Idempotent: the evidence idempotency key is the snapshot and item."""
    run = await _run(sys, run_id)
    if run.snapshot_id is None:
        raise NotFound("ledger_snapshot")
    engagement = await get_ref(sys, run.engagement_id)
    async with tenant_session(sys.tenant) as session:
        names = await client_names(session, [engagement.client_entity_id])
    tb = await trial_balance_for(
        sys.tenant,
        run.snapshot_id,
        entity_name=names[engagement.client_entity_id].client_entity_name,
    )
    stored = await stage_content(sys.tenant_id, render_trial_balance(tb))
    async with uow(sys.tenant) as tx:
        locked_engagement = await lock_ref(tx, run.engagement_id)
        await authorise(sys, "evidence.upload", locked_engagement.resource())
        version = await add_version(
            tx,
            engagement_id=run.engagement_id,
            item=NewItem(
                f"Trial balance {tb.period_start.isoformat()} to {tb.period_end.isoformat()}"
            ),
            stored=stored,
            media_type=XLSX_MEDIA_TYPE,
            provenance=Provenance(
                source=tb.source,
                method="retrieved",
                pulled_at=tb.pulled_at,
                period_start=tb.period_start,
                period_end=tb.period_end,
                client_entity_id=tb.client_entity_id,
                snapshot_id=tb.snapshot_id,
            ),
            idempotency_key=f"snapshot:{run.snapshot_id}:item:{run.request_item_id}",
        )
        await fulfil_by_rule(
            tx, sys, request_item_id=run.request_item_id, evidence_version_id=version.id
        )
        locked = await lock_run(tx.session, run_id)
        if locked is not None and locked.status == "running":
            await finish(tx.session, run_id, status="succeeded")
        tx.record(
            "sync_run.succeeded",
            target=Target("sync_run", run_id),
            after=Ref(evidence_version_id=version.id),
        )
    return version.id


async def run_pipeline(sys: SystemContext, run_id: UUID) -> RunResult:
    """All six stages in order, in-process (TASK-010b runs them as Temporal activities)."""
    try:
        raw = await extract(sys, run_id)
    except Unavailable as exc:
        raise await fail(sys, run_id, "failed", exc.code) from None
    await store_raw(sys, run_id, raw)
    await normalise_raw(sys, run_id)
    await validate_run(sys, run_id)
    snapshot_id = await snapshot(sys, run_id)
    version_id = await render(sys, run_id)
    return RunResult(run_id, snapshot_id, version_id)

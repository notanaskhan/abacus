"""The retrieval stages (ADR-038; TASK-010 design §5, revision 1). PROTECTED.

    pull_raw (extract + raw) → normalise_raw → validate_run → snapshot → render (+ fulfilment)

Every stage takes only the system context, which `load_system_context` proved from the run row;
its run and engagement are the only ones it may touch. Each stage authorises its own action,
re-reads what it needs (only identifiers cross stages: the raw bytes never leave `pull_raw`), and
is safe to repeat: TASK-010b runs each as a Temporal activity that may be retried or delivered
twice. A repeat finds its work done and returns the recorded result without new audit events. A
finished run refuses further work (`RunFailed`), and only a running run is marked failed.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from abacus.kernel.crypto import DecryptionError
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.connections.connector import ConnectorError, Period, Unavailable
from abacus.modules.connections.fake_format import parse_trial_balance
from abacus.modules.connections.models import SyncRun
from abacus.modules.connections.repository import (
    finish,
    get_connection,
    get_run,
    lock_run,
    set_evidence,
    set_raw,
    set_snapshot,
)
from abacus.modules.connections.service import connector_for
from abacus.modules.engagements.api import EngagementRef, get_ref, lock_ref
from abacus.modules.evidence.api import (
    XLSX_MEDIA_TYPE,
    IntegrityError,
    NewItem,
    Provenance,
    StoredObject,
    TrialBalance,
    TrialBalanceLine,
    add_version,
    read_content,
    render_trial_balance,
    stage_content,
)
from abacus.modules.identity.api import Forbidden, SystemContext, authorise
from abacus.modules.ledger.api import (
    NormalisedTrialBalance,
    NormaliseError,
    Unvalidated,
    record_snapshot,
    snapshot_view,
    validate,
)
from abacus.modules.organisations.api import client_names
from abacus.modules.requests.api import ItemNotFulfillable, fulfil_by_rule


class RunFailed(Exception):
    """The run has ended without evidence; `status` and `code` are on the sync run."""

    retryable = False

    def __init__(self, status: str, code: str) -> None:
        super().__init__(f"{status}: {code}")
        self.status = status
        self.code = code


@dataclass(frozen=True)
class RunResult:
    run_id: UUID
    snapshot_id: UUID
    evidence_version_id: UUID


_TERMINAL = (RunFailed, NotFound, Forbidden, Unvalidated, NormaliseError, ItemNotFulfillable)


def is_retryable(exc: BaseException) -> bool:
    """For the workflow (TASK-010b): retry provider outages and infrastructure errors; never
    retry a decided outcome (failed run, missing or forbidden resource, invalid data)."""
    if isinstance(exc, ConnectorError):
        return exc.retryable
    return not isinstance(exc, _TERMINAL)


async def _run(sys: SystemContext) -> SyncRun:
    async with tenant_session(sys.tenant) as session:
        run = await get_run(session, sys.run_id)
    if run is None or run.engagement_id != sys.engagement_id:
        raise NotFound("sync_run")
    if run.status in ("failed", "failed_validation"):
        raise RunFailed(run.status, run.failure_code or "unknown")
    return run


async def _authorised(sys: SystemContext, action: str) -> EngagementRef:
    engagement = await get_ref(sys, sys.engagement_id)
    await authorise(sys, action, engagement.resource())
    return engagement


def _running(run: SyncRun) -> None:
    if run.status != "running":
        raise RunFailed(run.status, run.failure_code or "finished")


async def fail_run(sys: SystemContext, status: str, code: str) -> RunFailed:
    """End a running run as failed (`sync_run.failed`) and return the exception to raise. A run
    that has already finished is left as it is, with no new audit event. For the workflow's
    handler after retries are exhausted (TASK-010b)."""
    current = (status, code)
    try:
        async with uow(sys.tenant) as tx:
            locked = await lock_run(tx.session, sys.run_id)
            if locked is not None and locked.status != "running":
                current = (locked.status, locked.failure_code or code)
            elif locked is not None and await finish(
                tx.session, sys.run_id, status=status, failure_code=code
            ):
                tx.record("sync_run.failed", target=Target("sync_run", sys.run_id))
    except MissingAuditEvent:
        pass  # nothing changed: nothing to commit
    return RunFailed(*current)


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


# 1-2. extract and store the raw payload ----------------------------------------------------------
async def pull_raw(sys: SystemContext) -> StoredObject:
    """Pull from the provider and store the bytes write-once, in one step: the raw payload never
    crosses a stage boundary. Pulls at most once per run: a recorded payload is returned."""
    run = await _run(sys)
    if run.raw_fingerprint is not None:
        return _stored(run)
    _running(run)
    await _authorised(sys, "connection.pull")
    async with tenant_session(sys.tenant) as session:
        connection = await get_connection(session, run.connection_id)
    if (
        connection is None
        or connection.status != "active"
        or connection.client_entity_id != run.client_entity_id
    ):
        raise await fail_run(sys, "failed", "connection_inactive")
    try:
        raw = await connector_for(connection).pull(
            "trial_balance", Period(run.period_start, run.period_end), None
        )
    except Unavailable:
        raise  # retryable: the workflow retries, then calls fail_run (TASK-010b)
    except ConnectorError as exc:
        raise await fail_run(sys, "failed", exc.code) from None
    stored = await stage_content(sys.tenant_id, raw.content)
    result = stored
    try:
        async with uow(sys.tenant) as tx:
            locked = await lock_run(tx.session, sys.run_id)
            if locked is None:
                raise NotFound("sync_run")
            _running(locked)
            if locked.raw_fingerprint is not None:
                result = _stored(locked)  # a concurrent pull recorded first: keep its payload
            else:
                await set_raw(
                    tx.session,
                    sys.run_id,
                    key=stored.key,
                    version_id=stored.version_id,
                    fingerprint=stored.fingerprint,
                    size=stored.size,
                    pulled_at=raw.pulled_at,
                    source=raw.source,
                )
                tx.record(
                    "sync_run.raw_stored",
                    target=Target("sync_run", sys.run_id),
                    after=Ref(raw_fingerprint=stored.fingerprint, on_behalf_of=sys.on_behalf_of),
                )
    except MissingAuditEvent:
        pass
    return result


# 3. normalise ----------------------------------------------------------------------------------
async def _normalised(sys: SystemContext, run: SyncRun) -> NormalisedTrialBalance:
    try:
        content = await read_content(sys.tenant, _stored(run))
    except (IntegrityError, DecryptionError):
        raise await fail_run(sys, "failed", "unprocessable") from None
    try:
        return parse_trial_balance(content)
    except NormaliseError as exc:
        raise await fail_run(sys, "failed", exc.code) from None


async def normalise_raw(sys: SystemContext) -> int:
    """The stored raw payload parses into the common ledger model. Returns the line count."""
    run = await _run(sys)
    await _authorised(sys, "connection.pull")
    return len((await _normalised(sys, run)).lines)


# 4. validate -----------------------------------------------------------------------------------
async def validate_run(sys: SystemContext) -> None:
    """Control totals (AC-11). A failure ends the run: no snapshot, no evidence."""
    run = await _run(sys)
    if run.snapshot_id is not None:
        return  # validated before it was snapshotted
    await _authorised(sys, "connection.pull")
    failure = validate(
        await _normalised(sys, run), period_start=run.period_start, period_end=run.period_end
    )
    if failure is not None:
        raise await fail_run(sys, "failed_validation", failure)


# 5. snapshot -----------------------------------------------------------------------------------
async def snapshot(sys: SystemContext) -> UUID:
    run = await _run(sys)
    if run.snapshot_id is not None:
        return run.snapshot_id
    _running(run)
    await _authorised(sys, "connection.pull")
    tb = await _normalised(sys, run)
    failure = validate(tb, period_start=run.period_start, period_end=run.period_end)
    if failure is not None:  # validate_run ran first; never snapshot unvalidated data
        raise await fail_run(sys, "failed_validation", failure)
    if run.raw_pulled_at is None or run.raw_fingerprint is None or run.source is None:
        raise NotFound("raw payload")
    result: UUID | None = None
    try:
        async with uow(sys.tenant) as tx:
            locked = await lock_run(tx.session, sys.run_id)
            if locked is None:
                raise NotFound("sync_run")
            _running(locked)
            if locked.snapshot_id is not None:
                result = locked.snapshot_id
            else:
                recorded = await record_snapshot(
                    tx,
                    client_entity_id=run.client_entity_id,
                    period_start=run.period_start,
                    period_end=run.period_end,
                    tb=tb,
                    raw_fingerprint=run.raw_fingerprint,
                    pulled_at=run.raw_pulled_at,
                    source=run.source,
                )
                await set_snapshot(tx.session, sys.run_id, recorded.id)
                tx.record(
                    "sync_run.snapshot_linked",
                    target=Target("sync_run", sys.run_id),
                    after=Ref(snapshot_id=recorded.id, on_behalf_of=sys.on_behalf_of),
                )
                result = recorded.id
    except MissingAuditEvent:
        pass
    if result is None:
        raise NotFound("ledger_snapshot")
    return result


# 6. render (+ fulfilment) ----------------------------------------------------------------------
async def render(sys: SystemContext) -> UUID:
    """Render the snapshot, add it as an evidence version, fulfil the request item by rule, and
    finish the run (AC-10). Authorises before doing anything. Idempotent: a finished run returns
    its recorded version; the evidence idempotency key is the snapshot and the item."""
    run = await _run(sys)
    if run.evidence_version_id is not None:
        return run.evidence_version_id
    _running(run)
    if run.snapshot_id is None:
        raise NotFound("ledger_snapshot")
    engagement = await _authorised(sys, "evidence.upload")
    view = await snapshot_view(sys.tenant, run.snapshot_id)
    async with tenant_session(sys.tenant) as session:
        names = await client_names(session, [engagement.client_entity_id])
    tb = TrialBalance(
        client_entity_id=view.client_entity_id,
        entity_name=names[engagement.client_entity_id].client_entity_name,
        period_start=view.period_start,
        period_end=view.period_end,
        pulled_at=view.pulled_at,
        snapshot_id=view.id,
        source=view.source,
        source_fingerprint=view.raw_fingerprint,
        lines=tuple(
            TrialBalanceLine(line.account_code, line.account_name, line.debit, line.credit)
            for line in view.lines
        ),
    )
    stored = await stage_content(sys.tenant_id, render_trial_balance(tb))
    result: UUID | None = None
    try:
        async with uow(sys.tenant) as tx:
            locked = await lock_run(tx.session, sys.run_id)
            if locked is None:
                raise NotFound("sync_run")
            if locked.evidence_version_id is not None:
                result = locked.evidence_version_id
            else:
                _running(locked)
                locked_engagement = await lock_ref(tx, run.engagement_id)
                await authorise(sys, "evidence.upload", locked_engagement.resource())
                version = await add_version(
                    tx,
                    engagement_id=run.engagement_id,
                    item=NewItem(
                        f"Trial balance {view.period_start.isoformat()} "
                        f"to {view.period_end.isoformat()}"
                    ),
                    stored=stored,
                    media_type=XLSX_MEDIA_TYPE,
                    provenance=Provenance(
                        source=view.source,
                        method="retrieved",
                        pulled_at=view.pulled_at,
                        period_start=view.period_start,
                        period_end=view.period_end,
                        client_entity_id=view.client_entity_id,
                        snapshot_id=view.id,
                    ),
                    idempotency_key=f"snapshot:{view.id}:item:{run.request_item_id}",
                )
                await fulfil_by_rule(
                    tx, sys, request_item_id=run.request_item_id, evidence_version_id=version.id
                )
                await set_evidence(tx.session, sys.run_id, version.id)
                if await finish(tx.session, sys.run_id, status="succeeded"):
                    tx.record(
                        "sync_run.succeeded",
                        target=Target("sync_run", sys.run_id),
                        after=Ref(evidence_version_id=version.id, on_behalf_of=sys.on_behalf_of),
                    )
                result = version.id
    except MissingAuditEvent:
        pass
    if result is None:
        raise NotFound("evidence_version")
    return result


async def run_pipeline(sys: SystemContext) -> RunResult:
    """All stages in order, in-process (TASK-010b runs them as Temporal activities)."""
    try:
        await pull_raw(sys)
    except Unavailable as exc:
        raise await fail_run(sys, "failed", exc.code) from None
    await normalise_raw(sys)
    await validate_run(sys)
    snapshot_id = await snapshot(sys)
    version_id = await render(sys)
    return RunResult(sys.run_id, snapshot_id, version_id)

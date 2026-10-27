"""Connections data access: connections and sync runs only (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.clock import system_now
from abacus.modules.connections.models import (
    Connection,
    ConnectionConsent,
    ConnectionConsentLink,
    ConnectionSecret,
    ConnectionState,
    GlImport,
    LedgerImport,
    ReconnectRequest,
    SyncRun,
)
from abacus.modules.identity.api import AuthContext, visible


async def active_connection_for(
    session: AsyncSession, client_entity_id: UUID
) -> Connection | None:
    """The entity's active ledger connection, newest first (expired ones don't count). A-02-T16:
    retrievals pull a trial balance, so only the ledger serves them; a bank feed beside it does
    not."""
    now = system_now()
    return (
        await session.execute(
            select(Connection)
            .where(
                Connection.client_entity_id == client_entity_id,
                Connection.category == "ledger",
                Connection.status == "active",
                (Connection.expires_at.is_(None)) | (Connection.expires_at > now),
            )
            .order_by(Connection.created_at.desc(), Connection.id)
            .limit(1)
        )
    ).scalar_one_or_none()


async def get_connection(session: AsyncSession, connection_id: UUID) -> Connection | None:
    return (
        await session.execute(select(Connection).where(Connection.id == connection_id))
    ).scalar_one_or_none()


async def insert_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    client_entity_id: UUID,
    connection_id: UUID,
    engagement_id: UUID,
    request_item_id: UUID,
    period_start: date,
    period_end: date,
    started_by: str,
) -> SyncRun | None:
    """The new run, or None if a running or successful run exists for this item and period."""
    return (
        await session.execute(
            pg_insert(SyncRun)
            .values(
                id=uuid4(),
                tenant_id=tenant_id,
                client_entity_id=client_entity_id,
                connection_id=connection_id,
                engagement_id=engagement_id,
                request_item_id=request_item_id,
                dataset="trial_balance",
                period_start=period_start,
                period_end=period_end,
                started_by=started_by,
            )
            .on_conflict_do_nothing(
                index_elements=["tenant_id", "request_item_id", "period_start", "period_end"],
                # A literal predicate, never bound parameters: under a generic plan (after about
                # five executions on one pooled connection) Postgres can't prove bound values
                # imply the partial index's predicate, and the insert fails with "no unique or
                # exclusion constraint matching the ON CONFLICT specification".
                index_where=text("status IN ('running', 'succeeded')"),
            )
            .returning(SyncRun)
        )
    ).scalar_one_or_none()


async def active_run(
    session: AsyncSession, request_item_id: UUID, period_start: date, period_end: date
) -> SyncRun | None:
    return (
        await session.execute(
            select(SyncRun).where(
                SyncRun.request_item_id == request_item_id,
                SyncRun.period_start == period_start,
                SyncRun.period_end == period_end,
                SyncRun.status.in_(("running", "succeeded")),
            )
        )
    ).scalar_one_or_none()


async def runs_since(session: AsyncSession, engagement_id: UUID, since: datetime) -> int:
    """Retrieval runs started for the engagement since `since` (the action cap, SPEC-007)."""
    count = await session.scalar(
        select(func.count())
        .select_from(SyncRun)
        .where(SyncRun.engagement_id == engagement_id, SyncRun.started_at >= since)
    )
    return count or 0


async def get_run(session: AsyncSession, run_id: UUID) -> SyncRun | None:
    return (
        await session.execute(select(SyncRun).where(SyncRun.id == run_id))
    ).scalar_one_or_none()


async def lock_run(session: AsyncSession, run_id: UUID) -> SyncRun | None:
    """The run, row-locked until commit: stages of one run never interleave."""
    return (
        await session.execute(select(SyncRun).where(SyncRun.id == run_id).with_for_update())
    ).scalar_one_or_none()


async def set_raw(
    session: AsyncSession,
    run_id: UUID,
    *,
    key: str,
    version_id: str,
    fingerprint: str,
    size: int,
    pulled_at: datetime,
    source: str,
) -> None:
    await session.execute(
        update(SyncRun)
        .where(SyncRun.id == run_id)
        .values(
            raw_storage_key=key,
            raw_version_id=version_id,
            raw_fingerprint=fingerprint,
            raw_size_bytes=size,
            raw_pulled_at=pulled_at,
            source=source,
        )
    )


async def set_snapshot(session: AsyncSession, run_id: UUID, snapshot_id: UUID) -> None:
    await session.execute(
        update(SyncRun).where(SyncRun.id == run_id).values(snapshot_id=snapshot_id)
    )


async def set_evidence(session: AsyncSession, run_id: UUID, evidence_version_id: UUID) -> None:
    await session.execute(
        update(SyncRun).where(SyncRun.id == run_id).values(evidence_version_id=evidence_version_id)
    )


async def set_queued(
    session: AsyncSession, run_id: UUID, reason: str | None, estimated_start_at: datetime | None
) -> None:
    """Mark a running run as waiting for a work slot (`reason`), or running again (None)."""
    await session.execute(
        update(SyncRun)
        .where(SyncRun.id == run_id, SyncRun.status == "running")
        .values(queued_reason=reason, estimated_start_at=estimated_start_at)
    )


async def finish(
    session: AsyncSession, run_id: UUID, *, status: str, failure_code: str | None = None
) -> bool:
    """True if this call ended the run (it was running)."""
    result = await session.execute(
        update(SyncRun)
        .where(SyncRun.id == run_id, SyncRun.status == "running")
        .values(
            status=status,
            failure_code=failure_code,
            finished_at=system_now(),
            # A run that ends is no longer waiting (CHECK sync_runs_queued_running).
            queued_reason=None,
            estimated_start_at=None,
        )
        .returning(SyncRun.id)
    )
    return result.scalar_one_or_none() is not None


# --- The connection flow (SPEC-020; TASK-036) --------------------------------------------------

LIVE = ("active", "needs_attention")


async def live_connection_for(
    session: AsyncSession, client_entity_id: UUID, *, lock: bool = False
) -> Connection | None:
    """The entity's live ledger connection (active or needing attention), if any; at most one
    exists (`connections_one_live_ledger`). A-02-T16: the legacy engagement routes (SPEC-020)
    read the entity's ledger; bank, card and sales feeds may now sit beside it."""
    query = select(Connection).where(
        Connection.client_entity_id == client_entity_id,
        Connection.category == "ledger",
        Connection.status.in_(LIVE),
    )
    if lock:
        query = query.with_for_update()
    return (await session.execute(query)).scalar_one_or_none()


async def insert_connection(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    client_entity_id: UUID,
    provider: str,
    created_by: str,
) -> Connection:
    return (
        await session.execute(
            insert(Connection)
            .values(
                id=uuid4(),
                tenant_id=tenant_id,
                client_entity_id=client_entity_id,
                provider=provider,
                scopes=[],
                created_by=created_by,
            )
            .returning(Connection)
        )
    ).scalar_one()


async def set_connection(session: AsyncSession, connection_id: UUID, **values: object) -> None:
    """A-02-T16 (0215): a status change bumps the version (the portal's `seen_version`)."""
    if "status" in values:
        values["version"] = Connection.version + 1
    await session.execute(
        update(Connection).where(Connection.id == connection_id).values(**values)
    )


async def insert_secret(
    session: AsyncSession, *, tenant_id: UUID, connection_id: UUID, sealed: bytes
) -> None:
    await session.execute(
        insert(ConnectionSecret).values(
            connection_id=connection_id, tenant_id=tenant_id, sealed=sealed
        )
    )


async def secret_of(session: AsyncSession, connection_id: UUID) -> bytes | None:
    return (
        await session.execute(
            select(ConnectionSecret.sealed).where(ConnectionSecret.connection_id == connection_id)
        )
    ).scalar_one_or_none()


async def destroy_secret(session: AsyncSession, connection_id: UUID) -> bool:
    deleted = await session.execute(
        delete(ConnectionSecret)
        .where(ConnectionSecret.connection_id == connection_id)
        .returning(ConnectionSecret.connection_id)
    )
    return deleted.scalar_one_or_none() is not None


async def insert_state(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    client_entity_id: UUID,
    user_id: UUID,
    provider: str,
    state_hash: str,
    expires_at: datetime,
    consent_id: UUID | None = None,
    connection_id: UUID | None = None,
    category: str | None = None,
    verifier_sealed: bytes | None = None,
) -> UUID:
    return (
        await session.execute(
            insert(ConnectionState)
            .values(
                tenant_id=tenant_id,
                engagement_id=engagement_id,
                client_entity_id=client_entity_id,
                user_id=user_id,
                provider=provider,
                state_hash=state_hash,
                expires_at=expires_at,
                consent_id=consent_id,
                connection_id=connection_id,
                category=category,
                verifier_sealed=verifier_sealed,
            )
            .returning(ConnectionState.id)
        )
    ).scalar_one()


async def lock_state(session: AsyncSession, state_hash: str) -> ConnectionState | None:
    return (
        await session.execute(
            select(ConnectionState)
            .where(ConnectionState.state_hash == state_hash)
            .with_for_update()
        )
    ).scalar_one_or_none()


async def spend_state(session: AsyncSession, state_id: UUID) -> None:
    await session.execute(
        update(ConnectionState)
        .where(ConnectionState.id == state_id)
        .values(used_at=func.clock_timestamp())
    )


async def last_success(session: AsyncSession, connection_id: UUID) -> datetime | None:
    """When the connection last delivered a successful pull."""
    return await session.scalar(
        select(func.max(SyncRun.finished_at)).where(
            SyncRun.connection_id == connection_id, SyncRun.status == "succeeded"
        )
    )


async def list_access_log(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID, *, limit: int, offset: int
) -> list[SyncRun]:
    """The engagement's pulls, newest first (the client-visible access log, ADR-040)."""
    return list(
        (
            await session.execute(
                select(SyncRun)
                .where(
                    SyncRun.engagement_id == engagement_id,
                    visible(ctx, "connection.read_log", SyncRun.engagement_id),
                )
                .order_by(SyncRun.started_at.desc(), SyncRun.id)
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )


# --- Ledger imports (SPEC-028; TASK-052) ---------------------------------------------------------


async def insert_import(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    client_entity_id: UUID,
    format: str,
    period_start: date,
    period_end: date,
    storage_key: str,
    storage_version_id: str,
    fingerprint: str,
    size_bytes: int,
    failure_code: str | None,
    difference: Decimal | None,
    found_period_end: date | None,
    totals_from_lines: bool,
    uploaded_by: UUID,
    on_behalf: bool,
) -> LedgerImport | None:
    """The new import (scanned clean; failed when `failure_code`), or None when this entity
    already has this exact file as a good import."""
    return (
        await session.execute(
            pg_insert(LedgerImport)
            .values(
                tenant_id=tenant_id,
                engagement_id=engagement_id,
                client_entity_id=client_entity_id,
                format=format,
                period_start=period_start,
                period_end=period_end,
                storage_key=storage_key,
                storage_version_id=storage_version_id,
                fingerprint=fingerprint,
                size_bytes=size_bytes,
                scan_status="clean",
                status="failed" if failure_code else "received",
                failure_code=failure_code,
                difference=difference,
                found_period_end=found_period_end,
                totals_from_lines=totals_from_lines,
                uploaded_by=uploaded_by,
                on_behalf=on_behalf,
            )
            .on_conflict_do_nothing(
                index_elements=["tenant_id", "client_entity_id", "fingerprint"],
                index_where=LedgerImport.status != "failed",
            )
            .returning(LedgerImport)
        )
    ).scalar_one_or_none()


async def import_by_fingerprint(
    session: AsyncSession, client_entity_id: UUID, fingerprint: str
) -> LedgerImport | None:
    return (
        await session.execute(
            select(LedgerImport).where(
                LedgerImport.client_entity_id == client_entity_id,
                LedgerImport.fingerprint == fingerprint,
                LedgerImport.status != "failed",
            )
        )
    ).scalar_one_or_none()


async def latest_import(
    session: AsyncSession,
    client_entity_id: UUID,
    *,
    period_end: date | None = None,
    clean_only: bool = False,
) -> LedgerImport | None:
    query = select(LedgerImport).where(LedgerImport.client_entity_id == client_entity_id)
    if period_end is not None:
        query = query.where(LedgerImport.period_end == period_end)
    if clean_only:
        query = query.where(LedgerImport.scan_status == "clean", LedgerImport.status != "failed")
    return (
        await session.execute(
            query.order_by(LedgerImport.created_at.desc(), LedgerImport.id.desc()).limit(1)
        )
    ).scalar_one_or_none()


# --- General ledger imports (SPEC-034; TASK-069) ------------------------------------------------


async def insert_gl_import(session: AsyncSession, **values: object) -> GlImport | None:
    """The new import, or None when this entity already has this file (AC-7)."""
    return (
        await session.execute(
            pg_insert(GlImport)
            .values(**values)
            .on_conflict_do_nothing(constraint="gl_imports_once")
            .returning(GlImport)
        )
    ).scalar_one_or_none()


async def gl_import_by_fingerprint(
    session: AsyncSession, client_entity_id: UUID, fingerprint: str
) -> GlImport | None:
    return (
        await session.execute(
            select(GlImport).where(
                GlImport.client_entity_id == client_entity_id, GlImport.fingerprint == fingerprint
            )
        )
    ).scalar_one_or_none()


async def get_gl_import(session: AsyncSession, import_id: UUID) -> GlImport | None:
    return (
        await session.execute(select(GlImport).where(GlImport.id == import_id))
    ).scalar_one_or_none()


async def latest_gl_import(
    session: AsyncSession, client_entity_id: UUID, kind: str = "year"
) -> GlImport | None:
    return (
        await session.execute(
            select(GlImport)
            .where(GlImport.client_entity_id == client_entity_id, GlImport.kind == kind)
            .order_by(GlImport.created_at.desc(), GlImport.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def waiting_gl_imports(session: AsyncSession, client_entity_id: UUID) -> Sequence[GlImport]:
    """An entity's general ledgers waiting for a trial balance (the system's own read on a
    snapshot event; LIST_EXEMPT)."""
    return (
        (
            await session.execute(
                select(GlImport).where(
                    GlImport.client_entity_id == client_entity_id,
                    GlImport.status == "waiting_for_tb",
                )
            )
        )
        .scalars()
        .all()
    )


async def set_gl_import(session: AsyncSession, import_id: UUID, **values: object) -> None:
    await session.execute(update(GlImport).where(GlImport.id == import_id).values(**values))


# --- Entity-scoped connections (A-02-T16; POR-16) ------------------------------------------------


async def live_connections_of(
    session: AsyncSession, client_entity_id: UUID
) -> Sequence[Connection]:
    """The entity's live connections, oldest first (LIST_EXEMPT: the caller authorised
    `connection.read` on an engagement of this entity)."""
    return (
        (
            await session.execute(
                select(Connection)
                .where(
                    Connection.client_entity_id == client_entity_id,
                    Connection.status.in_(LIVE),
                )
                .order_by(Connection.created_at, Connection.id)
            )
        )
        .scalars()
        .all()
    )


async def lock_connection(session: AsyncSession, connection_id: UUID) -> Connection | None:
    return (
        await session.execute(
            select(Connection).where(Connection.id == connection_id).with_for_update()
        )
    ).scalar_one_or_none()


async def last_failures(
    session: AsyncSession, connection_ids: Sequence[UUID], engagement_ids: Sequence[UUID]
) -> dict[UUID, datetime]:
    """Per connection, when its newest run failed, if its newest finished run failed; only runs
    of the engagements the caller may read (review L7: walls hold across an entity)."""
    if not connection_ids or not engagement_ids:
        return {}
    rows = await session.execute(
        select(SyncRun.connection_id, SyncRun.status, SyncRun.finished_at)
        .where(
            SyncRun.connection_id.in_(list(connection_ids)),
            SyncRun.engagement_id.in_(list(engagement_ids)),
            SyncRun.finished_at.is_not(None),
        )
        .distinct(SyncRun.connection_id)
        .order_by(SyncRun.connection_id, SyncRun.finished_at.desc())
    )
    return {
        cid: at
        for cid, status, at in rows.all()
        if status in ("failed", "failed_validation") and at is not None
    }


async def recent_runs(
    session: AsyncSession, connection_id: UUID, engagement_ids: Sequence[UUID], limit: int
) -> Sequence[SyncRun]:
    """The connection's newest runs on the engagements the caller may read (LIST_EXEMPT: the
    caller authorised `connection.read` on each of `engagement_ids`; review L7)."""
    if not engagement_ids:
        return []
    return (
        (
            await session.execute(
                select(SyncRun)
                .where(
                    SyncRun.connection_id == connection_id,
                    SyncRun.engagement_id.in_(list(engagement_ids)),
                )
                .order_by(SyncRun.started_at.desc(), SyncRun.id)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def running_run_of(
    session: AsyncSession, connection_id: UUID, engagement_ids: Sequence[UUID]
) -> SyncRun | None:
    """The connection's live run on engagements the caller may retry on (review round 2 L6)."""
    if not engagement_ids:
        return None
    return (
        await session.execute(
            select(SyncRun)
            .where(
                SyncRun.connection_id == connection_id,
                SyncRun.engagement_id.in_(list(engagement_ids)),
                SyncRun.status == "running",
            )
            .order_by(SyncRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def latest_failed_run(
    session: AsyncSession, connection_id: UUID, engagement_ids: Sequence[UUID]
) -> SyncRun | None:
    """The newest failed run on the engagements the caller may retry on (review L7)."""
    if not engagement_ids:
        return None
    return (
        await session.execute(
            select(SyncRun)
            .where(
                SyncRun.connection_id == connection_id,
                SyncRun.engagement_id.in_(list(engagement_ids)),
                SyncRun.status.in_(("failed", "failed_validation")),
            )
            .order_by(SyncRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def open_reconnect_requests(
    session: AsyncSession, connection_ids: Sequence[UUID]
) -> dict[UUID, datetime]:
    if not connection_ids:
        return {}
    rows = await session.execute(
        select(ReconnectRequest.connection_id, ReconnectRequest.created_at).where(
            ReconnectRequest.connection_id.in_(list(connection_ids)),
            ReconnectRequest.fulfilled_at.is_(None),
        )
    )
    return {cid: at for cid, at in rows.all()}


async def fulfil_reconnect_requests(session: AsyncSession, connection_id: UUID) -> int:
    done = await session.execute(
        update(ReconnectRequest)
        .where(
            ReconnectRequest.connection_id == connection_id,
            ReconnectRequest.fulfilled_at.is_(None),
        )
        .values(fulfilled_at=func.abacus_now())
        .returning(ReconnectRequest.id)
    )
    return len(done.all())


async def insert_consent(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(
            insert(ConnectionConsent).values(**values).returning(ConnectionConsent.id)
        )
    ).scalar_one()


async def insert_consent_link(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(ConnectionConsentLink).values(**values))


async def insert_entity_connection(session: AsyncSession, **values: object) -> Connection:
    return (
        await session.execute(
            insert(Connection).values(id=uuid4(), scopes=[], **values).returning(Connection)
        )
    ).scalar_one()


async def insert_retry_run(session: AsyncSession, **values: object) -> SyncRun | None:
    """A retried run; None when a running or successful run exists for its item and period
    (the request-item runs' unique index)."""
    return (
        await session.execute(
            pg_insert(SyncRun)
            .values(id=uuid4(), **values)
            .on_conflict_do_nothing(
                index_elements=["tenant_id", "request_item_id", "period_start", "period_end"],
                index_where=text("status IN ('running', 'succeeded')"),
            )
            .returning(SyncRun)
        )
    ).scalar_one_or_none()


async def has_consent_link(session: AsyncSession, connection_id: UUID) -> bool:
    """Whether a client's consent produced (or re-authorised) this connection (POR-16)."""
    found = await session.scalar(
        select(ConnectionConsentLink.consent_id)
        .where(ConnectionConsentLink.connection_id == connection_id)
        .limit(1)
    )
    return found is not None


async def last_success_on(
    session: AsyncSession, connection_id: UUID, engagement_ids: Sequence[UUID]
) -> datetime | None:
    """When the connection last delivered on one of these engagements (review L7)."""
    if not engagement_ids:
        return None
    return await session.scalar(
        select(func.max(SyncRun.finished_at)).where(
            SyncRun.connection_id == connection_id,
            SyncRun.engagement_id.in_(list(engagement_ids)),
            SyncRun.status == "succeeded",
        )
    )

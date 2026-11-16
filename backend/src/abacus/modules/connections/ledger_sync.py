"""The hourly ledger sync for closes (C-01-T17; C-01 §4.5, F5; SPEC-655 US-5.1, US-5.2; red).

`LedgerSyncWorkflow` (`ledger_sync:<tenant>`, `ledger_sync_workflow.py`) asks two activities here
what to do; this module holds every rule, so the workflow stays a loop of identifiers.

**What is due.** The closes module registers a scope (`register_sync_scope`): the entities with
an unlocked close and the close months to keep fresh. An entity is due when it has a live ledger
connection, its schedule is not paused, its `next_run_at` has passed and the firm's clock reads
inside the schedule's business hours (07:00-19:00 firm time by default, QC-5).

**One entity's sync.** In order, each refusal leaves before any provider call:
1. `connections.ledger_sync` and the live-ledger kill switch (`connections.live_ledger`, A-02-T33)
   are read past the cache: either off, nothing leaves Accrued (`connector_paused`).
2. A connection that needs its client to sign in again (`token_expired`, `invalid_grant`) pauses
   the entity's sync (`needs_reauth`) without a pull; A-02's health path owns the reconnect.
3. The firm's monthly Intuit call budget (`connection_meter_usage`): a scheduled tick at the
   budget pauses scheduled syncs (`meter_budget_exhausted`) and tells the firm admin once; Sync
   now still runs (a Senior's decision).
4. Change-data-capture since the schedule's cursor names the changed datasets (the first sync
   pulls all three); only those are pulled, a month at a time. The rest is carried forward from
   the month's newest set (`ledger.api.record_month_snapshot`): a new immutable snapshot, never an
   update (ADR-004). An unchanged month records nothing.
5. Each pulled dataset is a `sync_runs` row (`trigger` `schedule` or `on_demand`) with its raw
   bytes stored write-once (ADR-038). A new set emits `ledger_snapshot.recorded` and
   `change_event.detected` (ADR-041); the calls made are added to the meter.

**Failures.** A throttle (`rate_limited`, `circuit_open`) records `retry_at` from Intuit's
Retry-After and the next tick waits for it; a grant problem pauses the entity; anything else is
recorded as the schedule's `last_failure_code` and the next hour tries again. Codes only, never
provider text. Read only: no write method anywhere (CONN-001, ADR-040).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Final, Literal, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel._flags import CONNECTIONS_LEDGER_SYNC, CONNECTIONS_LIVE_LEDGER
from abacus.kernel.clock import now as business_now
from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch, signal_with_start
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.sync_scope import SyncScope, scope_of
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.connections.connect import credentials_of
from abacus.modules.connections.connector import (
    Connector,
    ConnectorError,
    Dataset,
    Period,
    RateLimited,
    RawPayload,
)
from abacus.modules.connections.connectors.quickbooks_online import PROVIDER as QBO_PROVIDER
from abacus.modules.connections.entity import REAUTH_REASONS
from abacus.modules.connections.events import (
    ChangeEventDetected,
    LedgerSnapshotRecorded,
    LedgerSyncPaused,
)
from abacus.modules.connections.ledger_sync_contract import LedgerNotConnected
from abacus.modules.connections.ledger_sync_types import (
    PLAN_TICK,
    SYNC_ENTITY,
    SYNC_NOW,
    LedgerSyncInput,
    PlanTickInput,
    PlanTickResult,
    SyncEntityInput,
    SyncEntityResult,
    SyncNowSignal,
)
from abacus.modules.connections.ledger_sync_workflow import LedgerSyncWorkflow
from abacus.modules.connections.models import Connection, SyncRun
from abacus.modules.connections.qbo_format import (
    parse_qbo_accounts,
    parse_qbo_general_ledger,
    parse_qbo_trial_balance,
)
from abacus.modules.connections.repository import LIVE, live_connection_for, set_connection
from abacus.modules.connections.service import connector_for
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.api import stage_content
from abacus.modules.identity.api import AuthContext, authorise, firm_time_zone
from abacus.modules.ledger.api import (
    MonthAccount,
    MonthIncomplete,
    MonthRegisterLine,
    NormalisedTrialBalance,
    NormaliseError,
    Unvalidated,
    latest_month_snapshot,
    month_bounds,
    record_month_snapshot,
)

ACTOR: Final = "connections:ledger_sync"
PROVIDER_METER: Final = "intuit"
DATASETS: Final[tuple[Dataset, ...]] = ("accounts", "trial_balance_month", "gl_detail")
TICK: Final = timedelta(hours=1)
MIN_WAIT: Final = 60
MAX_WAIT: Final = 3600
# Intuit's change-data-capture looks back at most 30 days; an older cursor pulls everything.
CDC_LOOKBACK: Final = timedelta(days=30)
MAX_ACCOUNT_PAGES: Final = 50
SYNC_PROVIDERS: Final = frozenset({QBO_PROVIDER})
_DEFAULT_HOURS: Final = {"start": "07:00", "end": "19:00"}

SyncState = Literal["synced", "unchanged", "rate_limited", "needs_reauth", "paused", "failed"]
Trigger = Literal["schedule", "on_demand"]

_log = get_logger(__name__)
_synced = meter(__name__).create_counter(
    "abacus.ledger_sync.synced", description="Entity syncs, by outcome"
)
_freshness = meter(__name__).create_histogram(
    "abacus.ledger_sync.freshness_minutes",
    description="Minutes since the entity's previous successful sync, at each success (SLO 60±15)",
)


# The closes scope is the kernel's slot (`kernel.sync_scope`): closes registers, we read.


# --- Schedules ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Schedule:
    connection_id: UUID
    business_hours: dict[str, str]
    paused_reason: str | None
    next_run_at: datetime | None
    cdc_cursor: datetime | None
    retry_at: datetime | None
    last_failure_code: str | None


_SCHEDULE = text(
    "SELECT connection_id, business_hours, paused_reason, next_run_at, cdc_cursor, retry_at, "
    "last_failure_code FROM sync_schedules WHERE connection_id = :c"
)
_SCHEDULE_LOCK = text(
    "SELECT connection_id, business_hours, paused_reason, next_run_at, cdc_cursor, retry_at, "
    "last_failure_code FROM sync_schedules WHERE connection_id = :c FOR UPDATE"
)
_INSERT_SCHEDULE = text(
    "INSERT INTO sync_schedules (tenant_id, connection_id, cadence, next_run_at) "
    "VALUES (:t, :c, 'hourly', :n) ON CONFLICT (connection_id) DO NOTHING"
)
_SET_SCHEDULE = text(
    "UPDATE sync_schedules SET paused_reason = :paused, next_run_at = :next, "
    "cdc_cursor = :cursor, retry_at = :retry, last_failure_code = :failure "
    "WHERE connection_id = :c"
)


def _schedule(row: Sequence[object]) -> Schedule:
    hours = cast(dict[str, str], row[1]) if isinstance(row[1], dict) else dict(_DEFAULT_HOURS)
    return Schedule(
        cast(UUID, row[0]),
        hours,
        cast(str | None, row[2]),
        cast(datetime | None, row[3]),
        cast(datetime | None, row[4]),
        cast(datetime | None, row[5]),
        cast(str | None, row[6]),
    )


async def schedule_of(
    session: AsyncSession, connection_id: UUID, *, lock: bool = False
) -> Schedule | None:
    found = (
        await session.execute(_SCHEDULE_LOCK if lock else _SCHEDULE, {"c": connection_id})
    ).first()
    return None if found is None else _schedule(found)


async def ensure_schedule(session: AsyncSession, connection: Connection, at: datetime) -> Schedule:
    """The connection's schedule, created (due now) on first sight. A system write of its own
    row: the caller's unit of work records it."""
    await session.execute(
        _INSERT_SCHEDULE, {"t": connection.tenant_id, "c": connection.id, "n": at}
    )
    found = await schedule_of(session, connection.id)
    if found is None:  # inserted or present: RLS hides nothing in the tenant's own session
        raise NotFound("sync_schedule")
    return found


async def _save(session: AsyncSession, schedule: Schedule) -> None:
    await session.execute(
        _SET_SCHEDULE,
        {
            "c": schedule.connection_id,
            "paused": schedule.paused_reason,
            "next": schedule.next_run_at,
            "cursor": schedule.cdc_cursor,
            "retry": schedule.retry_at,
            "failure": schedule.last_failure_code,
        },
    )


def _clock(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def in_business_hours(at: datetime, hours: dict[str, str], zone: ZoneInfo) -> bool:
    local = at.astimezone(zone)
    if local.weekday() >= 5:
        return False
    start = _clock(hours.get("start", _DEFAULT_HOURS["start"]))
    end = _clock(hours.get("end", _DEFAULT_HOURS["end"]))
    return start <= local.time() < end


def next_opening(at: datetime, hours: dict[str, str], zone: ZoneInfo) -> datetime:
    """The next instant inside business hours (now, if already inside)."""
    if in_business_hours(at, hours, zone):
        return at
    local = at.astimezone(zone)
    start = _clock(hours.get("start", _DEFAULT_HOURS["start"]))
    day = local.date()
    for offset in range(8):
        candidate = datetime.combine(day + timedelta(days=offset), start, tzinfo=zone)
        if candidate > local and candidate.weekday() < 5:
            return candidate
    return at + TICK  # unreachable for a 5-day week; keeps the loop bounded


async def _zone(tenant: TenantContext) -> ZoneInfo:
    return ZoneInfo(await firm_time_zone(tenant))


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", ACTOR)


# --- What is due --------------------------------------------------------------------------------


@dataclass(frozen=True)
class TickPlan:
    wait_seconds: int
    connection_ids: list[str] = field(default_factory=list[str])


async def _live_ledgers(tenant: TenantContext, entity_ids: Sequence[UUID]) -> list[Connection]:
    if not entity_ids:
        return []
    async with tenant_session(tenant) as session:
        return list(
            (
                await session.execute(
                    select(Connection)
                    .where(
                        Connection.client_entity_id.in_(list(entity_ids)),
                        Connection.category == "ledger",
                        Connection.status.in_(LIVE),
                        Connection.provider.in_(sorted(SYNC_PROVIDERS)),
                    )
                    .order_by(Connection.created_at, Connection.id)
                )
            )
            .scalars()
            .all()
        )


async def plan_tick(tenant_id: UUID) -> TickPlan:
    """Which connections are due now, and how long the workflow sleeps after them."""
    tenant = _system(tenant_id)
    if not await flag_enabled(tenant, CONNECTIONS_LEDGER_SYNC, fresh=True):
        return TickPlan(MAX_WAIT)
    at = await business_now(tenant)
    zone = await _zone(tenant)
    scope = await scope_of(tenant)
    connections = await _live_ledgers(tenant, list(scope))
    due: list[str] = []
    wake = at + TICK
    async with uow(tenant) as tx:
        for connection in connections:
            schedule = await ensure_schedule(tx.session, connection, at)
            if schedule.paused_reason is not None:
                continue
            ready = max(filter(None, (schedule.next_run_at, schedule.retry_at)), default=at)
            if ready <= at and in_business_hours(at, schedule.business_hours, zone):
                due.append(str(connection.id))
            else:
                wake = min(wake, next_opening(max(ready, at), schedule.business_hours, zone))
        if connections:
            tx.record(
                "ledger.sync_planned",
                target=Target("firm", tenant_id),
                after=Ref(due=len(due)),
            )
    wait = int((wake - at).total_seconds())
    return TickPlan(min(max(wait, MIN_WAIT), MAX_WAIT), due)


# --- One entity's sync --------------------------------------------------------------------------


@dataclass(frozen=True)
class SyncOutcome:
    state: SyncState
    snapshots: int = 0
    calls: int = 0
    failure_code: str | None = None


@dataclass
class _Pulled:
    dataset: Dataset
    payload: RawPayload


_METER_SELECT = text(
    "SELECT calls, budget FROM connection_meter_usage WHERE provider = :p AND month = :m"
)
# The app inserts a month's row without its count, then adds to it (0882's column grants).
_METER_OPEN = text(
    "INSERT INTO connection_meter_usage (tenant_id, provider, month) "
    "VALUES (:t, :p, :m) ON CONFLICT (tenant_id, provider, month) DO NOTHING"
)
_METER_ADD = text(
    "UPDATE connection_meter_usage SET calls = calls + :n, updated_at = clock_timestamp() "
    "WHERE tenant_id = :t AND provider = :p AND month = :m"
)


async def meter_state(session: AsyncSession, month: str) -> tuple[int, int | None]:
    found = (await session.execute(_METER_SELECT, {"p": PROVIDER_METER, "m": month})).first()
    if found is None:
        return 0, None
    return int(found[0]), (None if found[1] is None else int(found[1]))


async def add_calls(session: AsyncSession, tenant_id: UUID, month: str, calls: int) -> None:
    if calls > 0:
        key = {"t": tenant_id, "p": PROVIDER_METER, "m": month}
        await session.execute(_METER_OPEN, key)
        await session.execute(_METER_ADD, {**key, "n": calls})


def _accounts(payloads: Sequence[RawPayload]) -> tuple[MonthAccount, ...]:
    out: list[MonthAccount] = []
    for payload in payloads:
        for a in parse_qbo_accounts(payload.content):
            out.append(
                MonthAccount(
                    a.external_id,
                    a.number,
                    a.name,
                    a.classification,
                    a.account_type,
                    a.account_subtype,
                    a.parent_external_id,
                    None,
                    a.is_contra,
                    a.active,
                )
            )
    return tuple(out)


def _register(payload: RawPayload) -> tuple[MonthRegisterLine, ...]:
    return tuple(
        MonthRegisterLine(
            r.line_ref,
            r.account_ref,
            r.external_txn_id,
            r.txn_date,
            r.txn_type,
            r.doc_number,
            r.payee,
            r.memo,
            r.offset_account_ref,
            r.amount,
        )
        for r in parse_qbo_general_ledger(payload.content)
    )


def _tb(payload: RawPayload) -> NormalisedTrialBalance:
    return parse_qbo_trial_balance(payload.content)


async def _pull(connector: Connector, dataset: Dataset, period: Period) -> list[RawPayload]:
    """One dataset for one month; the chart of accounts a page at a time."""
    if dataset != "accounts":
        return [await connector.pull(dataset, period, None)]
    pages: list[RawPayload] = []
    cursor: str | None = None
    for _ in range(MAX_ACCOUNT_PAGES):
        page = await connector.pull(dataset, period, cursor)
        pages.append(page)
        cursor = page.next_cursor
        if cursor is None:
            break
    return pages


async def _record_runs(
    tenant: TenantContext,
    connection: Connection,
    scope: SyncScope,
    period: str,
    pulled: Sequence[_Pulled],
    trigger: Trigger,
    started_by: str,
    first_run_id: UUID | None = None,
) -> list[UUID]:
    """One finished `sync_runs` row per pulled dataset, its raw bytes stored write-once. A Sync
    now names its first run with the request's id (the 202's `sync_run_id`)."""
    start, end = month_bounds(period)
    run_ids: list[UUID] = []
    stored = [(p, await stage_content(tenant.tenant_id, p.payload.content)) for p in pulled]
    async with uow(tenant) as tx:
        for no, (item, obj) in enumerate(stored):
            run_id = first_run_id if (no == 0 and first_run_id is not None) else uuid4()
            # The app inserts a run's start, then records its raw result (0009's column grants;
            # `sync_runs_forward_only` keeps it write-once). It ends at its snapshot (0900).
            await tx.session.execute(
                insert(SyncRun).values(
                    id=run_id,
                    tenant_id=tenant.tenant_id,
                    client_entity_id=connection.client_entity_id,
                    connection_id=connection.id,
                    engagement_id=scope.engagement_id,
                    request_item_id=None,
                    trigger=trigger,
                    label=None,
                    dataset=item.dataset,
                    period_start=start,
                    period_end=end,
                    started_by=started_by,
                )
            )
            await tx.session.execute(
                update(SyncRun)
                .where(SyncRun.id == run_id)
                .values(
                    raw_storage_key=obj.key,
                    raw_version_id=obj.version_id,
                    raw_fingerprint=obj.fingerprint,
                    raw_size_bytes=obj.size,
                    raw_pulled_at=item.payload.pulled_at,
                    source=item.payload.source,
                )
            )
            tx.record(
                "sync_run.raw_stored",
                target=Target("sync_run", run_id),
                after=Ref(raw_fingerprint=obj.fingerprint),
            )
            run_ids.append(run_id)
    return run_ids


async def _pause(
    tenant: TenantContext, connection: Connection, scope: SyncScope | None, reason: str
) -> None:
    """Pause the entity's scheduled syncs; the firm is told once per pause
    (`ledger_sync_paused`)."""
    async with uow(tenant) as tx:
        schedule = await schedule_of(tx.session, connection.id, lock=True)
        if schedule is None or schedule.paused_reason == reason:
            tx.record(
                "ledger.sync_paused",
                target=Target("connection", connection.id),
                after=Ref(repeat=1),
            )
            return
        await _save(
            tx.session,
            Schedule(
                schedule.connection_id,
                schedule.business_hours,
                reason,
                schedule.next_run_at,
                schedule.cdc_cursor,
                schedule.retry_at,
                reason,
            ),
        )
        tx.emit(
            LedgerSyncPaused(
                connection_id=connection.id,
                client_entity_id=connection.client_entity_id,
                engagement_id=None if scope is None else scope.engagement_id,
                reason=reason,
            )
        )
        tx.record(
            "ledger.sync_paused",
            target=Target("connection", connection.id),
            after=Ref(repeat=0),
        )


async def _fail(
    tenant: TenantContext, connection: Connection, code: str, retry_at: datetime | None
) -> None:
    async with uow(tenant) as tx:
        schedule = await schedule_of(tx.session, connection.id, lock=True)
        if schedule is None:
            raise NotFound("sync_schedule")
        at = await business_now(tenant)
        await _save(
            tx.session,
            Schedule(
                schedule.connection_id,
                schedule.business_hours,
                schedule.paused_reason,
                at + TICK,
                schedule.cdc_cursor,
                retry_at,
                code,
            ),
        )
        tx.record("ledger.sync", target=Target("connection", connection.id), after=Ref(ok=0))


async def _connection(tenant: TenantContext, connection_id: UUID) -> Connection | None:
    async with tenant_session(tenant) as session:
        found = (
            await session.execute(select(Connection).where(Connection.id == connection_id))
        ).scalar_one_or_none()
    if found is None or found.status not in LIVE or found.category != "ledger":
        return None
    return found


async def sync_entity(
    tenant_id: UUID,
    connection_id: UUID,
    trigger: Trigger = "schedule",
    started_by: str = ACTOR,
    request_id: UUID | None = None,
) -> SyncOutcome:
    """One entity's sync (the module docstring's steps). Safe to repeat: an unchanged month
    records nothing, and a second set of the same content is found, not written."""
    tenant = _system(tenant_id)
    connection = await _connection(tenant, connection_id)
    if connection is None:
        return SyncOutcome("failed", failure_code="ledger_not_connected")
    if not (
        await flag_enabled(tenant, CONNECTIONS_LEDGER_SYNC, fresh=True)
        and await flag_enabled(tenant, CONNECTIONS_LIVE_LEDGER, fresh=True)
    ):
        _synced.add(1, {"outcome": "paused"})
        return SyncOutcome("paused", failure_code="connector_paused")
    scope = (await scope_of(tenant)).get(connection.client_entity_id)
    at = await business_now(tenant)
    async with uow(tenant) as tx:
        schedule = await ensure_schedule(tx.session, connection, at)
        tx.record(
            "ledger.sync_started", target=Target("connection", connection.id), after=Ref(n=1)
        )
    if connection.status_reason_code in REAUTH_REASONS:
        await _pause(tenant, connection, scope, "needs_reauth")
        _synced.add(1, {"outcome": "needs_reauth"})
        return SyncOutcome("needs_reauth", failure_code=connection.status_reason_code)
    if scope is None:
        return SyncOutcome("unchanged")
    month = at.strftime("%Y-%m")
    async with tenant_session(tenant) as session:
        calls, budget = await meter_state(session, month)
    if budget is not None and calls >= budget:
        if trigger == "schedule":
            await _pause(tenant, connection, scope, "meter_budget_exhausted")
            _synced.add(1, {"outcome": "paused"})
            return SyncOutcome("paused", failure_code="meter_budget_exhausted")
    elif schedule.paused_reason == "meter_budget_exhausted":
        schedule = Schedule(
            schedule.connection_id,
            schedule.business_hours,
            None,
            schedule.next_run_at,
            schedule.cdc_cursor,
            schedule.retry_at,
            schedule.last_failure_code,
        )  # fmt: skip  -- a new month (or a raised budget) lifts the budget pause

    connector = connector_for(connection, await credentials_of(tenant, connection))
    snapshots = 0
    changed: tuple[str, ...]
    try:
        if schedule.cdc_cursor is None or at - schedule.cdc_cursor > CDC_LOOKBACK:
            changed = DATASETS
        else:
            changed = tuple(await connector.changes_since(schedule.cdc_cursor))
        recorded: list[tuple[UUID, str]] = []
        for period in scope.periods:
            start, end = month_bounds(period)
            span = Period(start, end)
            first = await _first_set(tenant, connection.client_entity_id, period)
            wanted: tuple[Dataset, ...] = (
                DATASETS if first else tuple(d for d in DATASETS if d in changed)
            )
            if not wanted:
                continue
            pulled: list[_Pulled] = []
            for dataset in wanted:
                for payload in await _pull(connector, dataset, span):
                    pulled.append(_Pulled(dataset, payload))
            ref = await _record_set(
                tenant,
                connection,
                scope,
                period,
                pulled,
                trigger,
                started_by,
                request_id if not recorded else None,
            )
            if ref is not None:
                recorded.append(ref)
        snapshots = len(recorded)
    except RateLimited as exc:
        retry = at + timedelta(seconds=exc.retry_after or 60)
        await _fail(tenant, connection, exc.code, retry)
        await _meter_only(tenant, month, _calls_of(connector))
        _synced.add(1, {"outcome": "rate_limited"})
        return SyncOutcome("rate_limited", calls=_calls_of(connector), failure_code=exc.code)
    except ConnectorError as exc:
        await _meter_only(tenant, month, _calls_of(connector))
        if exc.code in REAUTH_REASONS:
            async with uow(tenant) as tx:
                await set_connection(
                    tx.session,
                    connection.id,
                    status="needs_attention",
                    status_reason_code=exc.code,
                )
                tx.record(
                    "connection.health_checked",
                    target=Target("connection", connection.id),
                    after=Ref(ok=0),
                )
            await _pause(tenant, connection, scope, "needs_reauth")
            _synced.add(1, {"outcome": "needs_reauth"})
            return SyncOutcome("needs_reauth", failure_code=exc.code)
        await _fail(tenant, connection, exc.code, None)
        _synced.add(1, {"outcome": "failed"})
        return SyncOutcome("failed", calls=_calls_of(connector), failure_code=exc.code)
    except (NormaliseError, Unvalidated, MonthIncomplete) as exc:
        code = str(getattr(exc, "code", None) or exc) or "invalid_payload"
        safe = code if code.replace("_", "").isalnum() and code.islower() else "invalid_payload"
        await _fail(tenant, connection, safe[:64], None)
        await _meter_only(tenant, month, _calls_of(connector))
        _synced.add(1, {"outcome": "failed"})
        return SyncOutcome("failed", calls=_calls_of(connector), failure_code=safe[:64])

    calls_made = _calls_of(connector)
    async with uow(tenant) as tx:
        await add_calls(tx.session, tenant_id, month, calls_made)
        fresh = await schedule_of(tx.session, connection.id, lock=True)
        base = fresh or schedule
        await _save(
            tx.session,
            Schedule(
                base.connection_id,
                base.business_hours,
                None,
                at + TICK,
                at,
                None,
                None,
            ),
        )
        previous = connection.last_sync_at
        await set_connection(tx.session, connection.id, last_sync_at=at)
        if previous is not None:
            _freshness.record((at - previous).total_seconds() / 60)
        tx.record(
            "ledger.sync_now" if trigger == "on_demand" else "ledger.sync",
            target=Target("connection", connection.id),
            after=Ref(ok=1, snapshots=snapshots, calls=calls_made),
        )
    _synced.add(1, {"outcome": "synced" if snapshots else "unchanged"})
    return SyncOutcome("synced" if snapshots else "unchanged", snapshots, calls_made)


def _calls_of(connector: Connector) -> int:
    calls = getattr(connector, "calls", 0)
    return calls if isinstance(calls, int) else 0


async def _meter_only(tenant: TenantContext, month: str, calls: int) -> None:
    if calls <= 0:
        return
    async with uow(tenant) as tx:
        await add_calls(tx.session, tenant.tenant_id, month, calls)
        tx.record(
            "ledger.sync_metered", target=Target("firm", tenant.tenant_id), after=Ref(n=calls)
        )


async def _first_set(tenant: TenantContext, client_entity_id: UUID, period: str) -> bool:
    async with tenant_session(tenant) as session:
        return await latest_month_snapshot(session, client_entity_id, period) is None


async def _record_set(
    tenant: TenantContext,
    connection: Connection,
    scope: SyncScope,
    period: str,
    pulled: Sequence[_Pulled],
    trigger: Trigger,
    started_by: str,
    first_run_id: UUID | None = None,
) -> tuple[UUID, str] | None:
    """Store the raw bytes, then record the month's set; None when its content is unchanged."""
    by = {p.dataset: [x.payload for x in pulled if x.dataset == p.dataset] for p in pulled}
    tb = _tb(by["trial_balance_month"][0]) if "trial_balance_month" in by else None
    accounts = _accounts(by["accounts"]) if "accounts" in by else None
    register = _register(by["gl_detail"][0]) if "gl_detail" in by else None
    pulled_at = max(p.payload.pulled_at for p in pulled)
    run_ids = await _record_runs(
        tenant, connection, scope, period, pulled, trigger, started_by, first_run_id
    )
    async with uow(tenant) as tx:
        ref = await record_month_snapshot(
            tx,
            client_entity_id=connection.client_entity_id,
            period=period,
            tb=tb,
            accounts=accounts,
            register=register,
            pulled_at=pulled_at,
            source=f"{connection.provider}:{period}",
        )
        for run_id in run_ids:
            await tx.session.execute(
                update(SyncRun)
                .where(SyncRun.id == run_id, SyncRun.status == "running")
                .values(snapshot_id=ref.id, status="succeeded", finished_at=system_now())
            )
        if not ref.created:
            tx.record(
                "ledger.sync_unchanged",
                target=Target("ledger_snapshot", ref.id),
                after=Ref(created=0),
            )
            return None
        tx.emit(
            LedgerSnapshotRecorded(
                client_entity_id=connection.client_entity_id, snapshot_id=ref.id
            )
        )
        tx.emit(
            ChangeEventDetected(
                client_entity_id=connection.client_entity_id,
                connection_id=connection.id,
                snapshot_id=ref.id,
                period=period,
                datasets=sorted(by),
            )
        )
    return ref.id, period


# --- The routes' facts ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SyncFacts:
    connection_id: UUID | None
    provider: str | None
    state: str
    last_synced_at: datetime | None
    next_sync_at: datetime | None
    retry_at: datetime | None
    failure_code: str | None
    meter_month: str
    meter_calls: int
    meter_budget: int | None


async def sync_facts(tenant: TenantContext, client_entity_id: UUID) -> SyncFacts:
    """What the CLS-02 rail and CLS-04 header show (`Synced 10:02 AM · next 11:02 AM`)."""
    at = await business_now(tenant)
    month = at.strftime("%Y-%m")
    async with tenant_session(tenant) as session:
        connection = await live_connection_for(session, client_entity_id)
        calls, budget = await meter_state(session, month)
        schedule = None if connection is None else await schedule_of(session, connection.id)
    if connection is None:
        return SyncFacts(None, None, "not_connected", None, None, None, None, month, calls, budget)
    state = "synced"
    failure = None if schedule is None else schedule.last_failure_code
    if connection.status_reason_code in REAUTH_REASONS or (
        schedule is not None and schedule.paused_reason == "needs_reauth"
    ):
        state = "needs_reauth"
    elif schedule is not None and schedule.paused_reason is not None:
        state = "paused"
    elif schedule is not None and schedule.retry_at is not None and schedule.retry_at > at:
        state = "rate_limited"
    elif schedule is not None and schedule.next_run_at is not None and schedule.next_run_at <= at:
        state = "syncing"
    return SyncFacts(
        connection.id,
        connection.provider,
        state,
        connection.last_sync_at,
        None if schedule is None else schedule.next_run_at,
        None if schedule is None else schedule.retry_at,
        failure,
        month,
        calls,
        budget,
    )


# --- Activities and the routes' service ----------------------------------------------------------


@activity.defn(name=PLAN_TICK)
async def plan_tick_activity(given: PlanTickInput) -> PlanTickResult:
    plan = await plan_tick(UUID(given.tenant_id))
    return PlanTickResult(plan.wait_seconds, plan.connection_ids)


@activity.defn(name=SYNC_ENTITY)
async def sync_entity_activity(given: SyncEntityInput) -> SyncEntityResult:
    trigger: Trigger = "on_demand" if given.trigger == "on_demand" else "schedule"
    outcome = await sync_entity(
        UUID(given.tenant_id),
        UUID(given.connection_id),
        trigger,
        given.started_by,
        None if given.request_id is None else UUID(given.request_id),
    )
    return SyncEntityResult(outcome.state, outcome.snapshots, outcome.calls, outcome.failure_code)


ACTIVITIES = (plan_tick_activity, sync_entity_activity)


def workflow_id(tenant_id: UUID) -> str:
    return f"ledger_sync:{tenant_id}"


async def _entity_engagement(ctx: AuthContext, client_entity_id: UUID) -> UUID:
    """The engagement a person reaches the entity's sync through: its unlocked close's. An entity
    without one is not found (404, nothing revealed)."""
    scope = (await scope_of(ctx.tenant)).get(client_entity_id)
    if scope is None:
        raise NotFound("client_entity")
    return scope.engagement_id


async def status_for(ctx: AuthContext, client_entity_id: UUID) -> SyncFacts:
    engagement_id = await _entity_engagement(ctx, client_entity_id)
    await authorise(ctx, "ledger.read", (await get_ref(ctx, engagement_id)).resource())
    return await sync_facts(ctx.tenant, client_entity_id)


@dataclass(frozen=True)
class SyncNowAccepted:
    request_id: UUID
    state: str


async def request_sync_now(ctx: AuthContext, client_entity_id: UUID) -> SyncNowAccepted:
    """Sync now: authorised for a Senior and above (`ledger.sync_now`), logged, and signalled to
    the firm's `LedgerSyncWorkflow`, which runs the entity at once. 409 `ledger_not_connected`
    when the entity has no live ledger connection."""
    engagement_id = await _entity_engagement(ctx, client_entity_id)
    await authorise(ctx, "ledger.sync_now", (await get_ref(ctx, engagement_id)).resource())
    async with tenant_session(ctx.tenant) as session:
        connection = await live_connection_for(session, client_entity_id)
    if connection is None or connection.provider not in SYNC_PROVIDERS:
        raise LedgerNotConnected("client_entity")
    request_id = uuid4()
    async with uow(ctx.tenant) as tx:
        tx.record(
            "ledger.sync_now",
            target=Target("connection", connection.id),
            after=Ref(sync_run_id=request_id, engagement_id=engagement_id),
        )
    await signal_with_start(
        LedgerSyncWorkflow,
        LedgerSyncInput(str(ctx.tenant_id)),
        id=workflow_id(ctx.tenant_id),
        signal=SYNC_NOW,
        payload=SyncNowSignal(str(connection.id), str(request_id), str(ctx.user_id)),
    )
    return SyncNowAccepted(request_id, "syncing")


async def ensure_sync_workflow(tenant_id: UUID) -> None:
    """Start the firm's sync loop if it is not running (the closes module calls this when a close
    is generated for an entity with a live ledger connection). Idempotent: a running workflow
    with this id is left alone."""
    await dispatch(
        LedgerSyncWorkflow,
        LedgerSyncInput(str(tenant_id)),
        id=workflow_id(tenant_id),
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )

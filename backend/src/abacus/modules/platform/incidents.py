"""The security incident register (Q-02-T33; Q-02 AC-38, AC-39, §4.2 to §4.8; OQ-5; ADR-097;
DEC-290).

A firm's Qualified Individual (`security_admin`, `incident.manage`) records an incident; the
register computes the FTC clock (16 CFR 314.4(j)): a **notification event** is unencrypted data of
500 or more consumers, and notice is due 30 calendar days after discovery, counted in the firm's
time zone with no business-day roll (I-CLOCKS):

    ftc_notify_by = incident_clock(discovered_at, "America/Chicago")   # Sep 10 -> Oct 10

When Accrued itself has an incident touching firms' data, platform staff propagate it (RB-27):
`IncidentPropagation` writes one entry per named firm, as the system, with Accrued's facts and
the moment the firm was given notice (`dpa_notice_at`, the DPA's 72-hour clock from Accrued's
confirmation). Propagation is repeat-safe: one entry per firm and Accrued reference.

Behind `compliance.incidents` (off: 404). The read side, timeline and decisions are G-02's.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Final, Literal, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel import clock
from abacus.kernel._flags import COMPLIANCE_INCIDENTS
from abacus.kernel.db import TenantContext, platform_transaction, tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    authorise,
    firm_tenancy,
    firm_time_zone,
)
from abacus.modules.platform.events import IncidentPropagated, IncidentRecorded
from abacus.modules.platform.workflow_types import (
    IncidentFactsInput,
    IncidentPropagationInput,
    IncidentPropagationOutcome,
    IncidentPropagationStep,
    IncidentStepResult,
)
from abacus.modules.platform.workflows import (
    IncidentPropagationWorkflow,
    incident_propagation_workflow_id,
)

EventKind = Literal[
    "unauthorized_access",
    "credential_attack",
    "data_exposure",
    "lost_device",
    "vendor_incident",
    "other",
]
Source = Literal["firm", "accrued"]
CLOCK_DAYS: Final = 30  # FTC notice: 30 calendar days after discovery (16 CFR 314.4(j))
NOTIFY_THRESHOLD: Final = 500  # consumers, unencrypted
DPA_NOTICE: Final = timedelta(hours=72)  # Accrued -> firm notice (DPA SLA; RB-27)
MAX_FIRMS: Final = 500  # firms one propagation may name
_SKEW: Final = timedelta(minutes=5)  # clocks disagree a little; a discovery is never later
_log = get_logger(__name__)
_failed_firms = meter(__name__).create_counter(
    "abacus.incident.propagation_failed_firms",
    description="Firms an incident propagation could not write after every attempt (RB-27)",
)
PROPAGATION_ACTOR: Final = (
    "incident_propagation"  # the only system id that writes an Accrued entry
)
WORKFLOWS: dict[type, WorkClass] = {IncidentPropagationWorkflow: "time_sensitive"}
register_work_classes(WORKFLOWS)


class DiscoveredInFuture(DomainInvalid):
    """An incident is discovered at or before the moment it is recorded."""

    code = "discovered_in_future"


class ConfirmedOutOfOrder(DomainInvalid):
    """Accrued confirms an incident after discovering it and before propagating it."""

    code = "confirmed_out_of_order"


class PropagationRunning(DomainConflict):
    """A propagation of this Accrued incident is still running: wait for it, then name any
    further firms in a new one."""

    code = "incident_propagation_running"


class IncidentFactsChanged(DomainConflict):
    """A firm already has this Accrued incident with other facts. Nothing is written: a
    correction is a new Accrued reference (DEC-290)."""

    code = "incident_facts_changed"


class FirmNotFound(Exception):
    """A named firm doesn't exist (the activity doesn't retry it; RB-27's manual step)."""


@dataclass(frozen=True)
class IncidentFacts:
    title: str  # Confidential
    event_kind: EventKind
    discovered_at: datetime
    consumers_affected: int | None
    unencrypted: bool | None


@dataclass(frozen=True)
class IncidentView:
    id: UUID
    ref: str
    title: str
    event_kind: EventKind
    discovered_at: datetime
    consumers_affected: int | None
    unencrypted: bool | None
    notification_event: bool
    ftc_notify_by: date
    clock_day: int  # calendar days since discovery, in the firm's zone (0 on the day)
    source: Source
    accrued_ref: str | None
    accrued_confirmed_at: datetime | None
    dpa_notice_at: datetime | None
    created_at: datetime


# --- the clock (pure) ------------------------------------------------------------------------


def discovered_on(discovered_at: datetime, zone: str) -> date:
    """The discovery's calendar date in the firm's zone."""
    if discovered_at.tzinfo is None:
        raise ValueError("discovered_at needs a time zone")
    return discovered_at.astimezone(ZoneInfo(zone)).date()


def incident_clock(discovered_at: datetime, zone: str) -> date:
    """`platform.api.incident_clock`: the FTC notice date, the discovery date in the firm's zone
    plus 30 calendar days. No business-day roll: a Saturday stays a Saturday (I-CLOCKS)."""
    return discovered_on(discovered_at, zone) + timedelta(days=CLOCK_DAYS)


def clock_day(discovered_at: datetime, zone: str, on: date) -> int:
    """How many calendar days of the 30 have passed on `on` ("Day 4 of 30" on Sep 14 for a
    Sep 10 discovery)."""
    return (on - discovered_on(discovered_at, zone)).days


def notification_event(consumers_affected: int | None, unencrypted: bool | None) -> bool:
    """The register's generated column, for callers without a row: unencrypted data of 500 or
    more consumers. Unknown counts as not (yet) an event."""
    return bool(unencrypted) and (consumers_affected or 0) >= NOTIFY_THRESHOLD


def reason_sha256(reason: str) -> str:
    return hashlib.sha256(reason.encode()).hexdigest()


# --- reading ---------------------------------------------------------------------------------

_SELECT = text(
    "SELECT id, ref, title, event_kind, discovered_at, consumers_affected, unencrypted, "
    "notification_event, ftc_notify_by, source, accrued_ref, accrued_confirmed_at, "
    "dpa_notice_at, created_at FROM security_incidents WHERE id = :id"
)


async def _view(tenant: TenantContext, incident_id: UUID) -> IncidentView:
    zone = await firm_time_zone(tenant)
    on = (await clock.now(tenant)).astimezone(ZoneInfo(zone)).date()
    async with tenant_session(tenant) as session:
        row = (await session.execute(_SELECT, {"id": incident_id})).mappings().one()
    discovered = cast(datetime, row["discovered_at"])
    return IncidentView(
        id=cast(UUID, row["id"]),
        ref=str(row["ref"]),
        title=str(row["title"]),
        event_kind=cast(EventKind, row["event_kind"]),
        discovered_at=discovered,
        consumers_affected=cast(int | None, row["consumers_affected"]),
        unencrypted=cast(bool | None, row["unencrypted"]),
        notification_event=bool(row["notification_event"]),
        ftc_notify_by=cast(date, row["ftc_notify_by"]),
        clock_day=clock_day(discovered, zone, on),
        source=cast(Source, row["source"]),
        accrued_ref=cast(str | None, row["accrued_ref"]),
        accrued_confirmed_at=cast(datetime | None, row["accrued_confirmed_at"]),
        dpa_notice_at=cast(datetime | None, row["dpa_notice_at"]),
        created_at=cast(datetime, row["created_at"]),
    )


# --- writing ---------------------------------------------------------------------------------


async def open_incidents(tenant: TenantContext) -> int:
    """G-02-T14 (AC-30): the firm's incidents still under investigation, for the posture."""
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT count(*) FROM security_incidents WHERE status = 'investigating'")
        )
    return int(found or 0)


async def _next_ref(session: AsyncSession, tenant_id: UUID, year: int) -> str:
    """The firm's next `INC-<year>-NNN`, under a transaction lock per firm and year so two
    entries recorded at once never take the same number."""
    prefix = f"INC-{year:04d}-"
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"security_incidents:{tenant_id}:{year}"},
    )
    last = await session.scalar(
        text(
            "SELECT max(split_part(ref, '-', 3)::integer) FROM security_incidents "
            "WHERE ref LIKE :prefix"
        ),
        {"prefix": f"{prefix}%"},
    )
    return f"{prefix}{int(last or 0) + 1:03d}"


_INSERT = text(
    "INSERT INTO security_incidents (id, tenant_id, ref, title, event_kind, discovered_at, "
    "consumers_affected, unencrypted, ftc_notify_by, source, accrued_ref, accrued_confirmed_at, "
    "dpa_notice_at, facts_sha256, created_by) VALUES (:id, :tenant, :ref, :title, :kind, "
    ":discovered, :consumers, :unencrypted, :notify_by, :source, :accrued_ref, :confirmed, "
    "CASE WHEN :source = 'accrued' THEN clock_timestamp() END, :facts, :by) "
    "RETURNING notification_event"
)


async def _require_flag(tenant: TenantContext) -> None:
    if not await flag_enabled(tenant, COMPLIANCE_INCIDENTS):
        raise NotFound(COMPLIANCE_INCIDENTS.name)


async def record_incident(ctx: AuthContext, facts: IncidentFacts) -> IncidentView:
    """`POST /v1/firm/security/incidents`: the firm's QI records an incident; the register
    computes the clock (AC-38)."""
    await _require_flag(ctx.tenant)
    await authorise(ctx, "incident.manage", Resource.firm(ctx.tenant_id))
    if facts.discovered_at > await clock.now(ctx.tenant) + _SKEW:
        raise DiscoveredInFuture
    zone = await firm_time_zone(ctx.tenant)
    incident_id = uuid4()
    async with uow(ctx.tenant) as tx:
        ref = await _next_ref(
            tx.session, ctx.tenant_id, discovered_on(facts.discovered_at, zone).year
        )
        event = bool(
            await tx.session.scalar(
                _INSERT,
                {
                    "id": incident_id,
                    "tenant": ctx.tenant_id,
                    "ref": ref,
                    "title": facts.title,
                    "kind": facts.event_kind,
                    "discovered": facts.discovered_at,
                    "consumers": facts.consumers_affected,
                    "unencrypted": facts.unencrypted,
                    "notify_by": incident_clock(facts.discovered_at, zone),
                    "source": "firm",
                    "accrued_ref": None,
                    "confirmed": None,
                    "facts": None,
                    "by": ctx.user_id,
                },
            )
        )
        tx.record(
            "incident.recorded",
            target=Target("security_incident", incident_id),
            after=Ref(notification_event=int(event)),
        )
        tx.emit(
            IncidentRecorded(
                incident_id=incident_id, notification_event=event, by_user=ctx.user_id
            )
        )
    return await _view(ctx.tenant, incident_id)


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", PROPAGATION_ACTOR)


def facts_sha256(facts: IncidentFactsInput) -> str:
    """The fingerprint of Accrued's facts (canonical JSON): the same facts are the same entry."""
    canonical = json.dumps(asdict(facts), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _facts_of(given: IncidentFactsInput) -> tuple[IncidentFacts, datetime]:
    facts = IncidentFacts(
        title=given.title,
        event_kind=cast(EventKind, given.event_kind),
        discovered_at=datetime.fromisoformat(given.discovered_at),
        consumers_affected=given.consumers_affected,
        unencrypted=given.unencrypted,
    )
    return facts, datetime.fromisoformat(given.confirmed_at)


_EXISTING = text("SELECT ref, facts_sha256 FROM security_incidents WHERE accrued_ref = :ref")


async def _existing(ctx: TenantContext, accrued_ref: str) -> tuple[str, str | None] | None:
    async with tenant_session(ctx) as session:
        row = (await session.execute(_EXISTING, {"ref": accrued_ref})).one_or_none()
    return None if row is None else (str(row.ref), cast(str | None, row.facts_sha256))


async def propagate_into(step: IncidentPropagationStep) -> IncidentStepResult:
    """One firm's entry for an Accrued incident, as the system (AC-39): Accrued's facts, the
    firm's own `INC-` reference and clock, and `dpa_notice_at` stamped as the entry is written
    and its notice queued. Repeat-safe: the same facts again return the entry (`identical`);
    different facts raise `IncidentFactsChanged` and write nothing."""
    tenant_id = UUID(step.tenant_id)
    ctx = _system(tenant_id)
    if await firm_tenancy(ctx) is None:
        raise FirmNotFound
    fingerprint = facts_sha256(step.facts)
    found = await _existing(ctx, step.accrued_ref)
    if found is not None:
        if found[1] != fingerprint:
            raise IncidentFactsChanged
        return IncidentStepResult(step.tenant_id, found[0], "identical")
    facts, confirmed = _facts_of(step.facts)
    zone = await firm_time_zone(ctx)
    incident_id = uuid4()
    async with uow(ctx) as tx:
        ref = await _next_ref(tx.session, tenant_id, discovered_on(facts.discovered_at, zone).year)
        event = bool(
            await tx.session.scalar(
                _INSERT,
                {
                    "id": incident_id,
                    "tenant": tenant_id,
                    "ref": ref,
                    "title": facts.title,
                    "kind": facts.event_kind,
                    "discovered": facts.discovered_at,
                    "consumers": facts.consumers_affected,
                    "unencrypted": facts.unencrypted,
                    "notify_by": incident_clock(facts.discovered_at, zone),
                    "source": "accrued",
                    "accrued_ref": step.accrued_ref,
                    "confirmed": confirmed,
                    "facts": fingerprint,
                    "by": None,
                },
            )
        )
        tx.record(
            "incident.propagated",
            target=Target("security_incident", incident_id),
            after=Ref(
                staff_id=UUID(step.staff_id),
                reason_hash=step.reason_sha256,
                facts_hash=fingerprint,
                notification_event=int(event),
            ),
        )
        tx.emit(IncidentPropagated(incident_id=incident_id, notification_event=event))
    if clock.system_now() - confirmed > DPA_NOTICE:
        # Recorded anyway (a late notice is still the notice); the alarm is RB-27's.
        _log.warning("incident.dpa_notice_late", tenant_id=str(tenant_id), ref=ref)
    return IncidentStepResult(step.tenant_id, ref, "written")


# --- the staff record (incident_propagations; global, definer functions only) -----------------

Event = Literal["requested", "refused", "completed"]
Refusal = Literal[
    "firm_not_found",
    "register_off",
    "facts_changed",
    "confirmed_out_of_order",
    "propagation_running",
    "firm_count",
]
_RECORD = text(
    "SELECT record_incident_propagation(:ref, :event, :staff, :reason, :facts, :firms, "
    ":written, :identical, CAST(:failed AS uuid[]), :refusal)"
)
_LOG_ROWS = text("SELECT * FROM incident_propagation_log(:ref)")


@dataclass(frozen=True)
class PropagationEvent:
    recorded_at: datetime
    event: Event
    staff_id: UUID
    firms: int
    written: int
    identical: int
    failed_tenant_ids: tuple[UUID, ...]
    refusal: Refusal | None


@dataclass(frozen=True)
class PropagationStarted:
    """What a staff request did: the firms the run will write, and the firms that already have
    this incident with these same facts (skipped, not written again)."""

    started: list[UUID]
    identical: list[UUID]


async def _record(
    actor: str,
    *,
    ref: str,
    event: Event,
    staff_id: UUID,
    reason_hash: str,
    facts_hash: str | None,
    firms: int,
    written: int = 0,
    identical: int = 0,
    failed: Sequence[str] = (),
    refusal: Refusal | None = None,
) -> None:
    async with platform_transaction(actor) as conn:
        await conn.execute(
            _RECORD,
            {
                "ref": ref,
                "event": event,
                "staff": staff_id,
                "reason": reason_hash,
                "facts": facts_hash,
                "firms": firms,
                "written": written,
                "identical": identical,
                "failed": list(failed),
                "refusal": refusal,
            },
        )


async def finish_propagation(outcome: IncidentPropagationOutcome) -> None:
    """The run's end, recorded once for staff (v2): how many firms were written or identical,
    and which failed every attempt. A failed firm is logged and counted, never silent."""
    await _record(
        PROPAGATION_ACTOR,
        ref=outcome.accrued_ref,
        event="completed",
        staff_id=UUID(outcome.staff_id),
        reason_hash=outcome.reason_sha256,
        facts_hash=None,
        firms=outcome.firms,
        written=outcome.written,
        identical=outcome.identical,
        failed=outcome.failed_tenant_ids,
    )
    if outcome.failed_tenant_ids:
        _failed_firms.add(len(outcome.failed_tenant_ids))
        _log.error(
            "incident.propagation_failed_firms",
            accrued_ref=outcome.accrued_ref,
            failed=len(outcome.failed_tenant_ids),
            tenant_ids=list(outcome.failed_tenant_ids),
        )


async def propagation_log(accrued_ref: str) -> list[PropagationEvent]:
    """Staff: every request and run end for an Accrued reference, oldest first."""
    async with platform_transaction(PROPAGATION_ACTOR) as conn:
        rows = (await conn.execute(_LOG_ROWS, {"ref": accrued_ref})).mappings().all()
    return [
        PropagationEvent(
            recorded_at=cast(datetime, r["recorded_at"]),
            event=cast(Event, r["event"]),
            staff_id=cast(UUID, r["staff_id"]),
            firms=int(r["firms"]),
            written=int(r["written"]),
            identical=int(r["identical"]),
            failed_tenant_ids=tuple(cast(list[UUID], r["failed_tenant_ids"])),
            refusal=cast(Refusal | None, r["refusal"]),
        )
        for r in rows
    ]


async def start_propagation(
    staff_id: UUID,
    accrued_ref: str,
    tenant_ids: Sequence[UUID],
    facts: IncidentFactsInput,
    reason: str,
) -> PropagationStarted:
    """Staff (RB-27): start `IncidentPropagation` for the named firms. Every firm must exist and
    have `compliance.incidents` on (else 404); a firm that already has this incident with other
    facts refuses the whole request (409 `incident_facts_changed`); in every refusal nothing
    starts and RB-27's manual step covers it. Firms that already have it with these facts are
    reported as identical and not written again. Every request is recorded for staff, refused
    ones included (`incident_propagations`)."""
    firms = list(dict.fromkeys(tenant_ids))
    actor = f"staff:{staff_id}"
    reason_hash = reason_sha256(reason)
    fingerprint = facts_sha256(facts)

    async def refuse(refusal: Refusal, error: Exception) -> Exception:
        await _record(
            actor,
            ref=accrued_ref,
            event="refused",
            staff_id=staff_id,
            reason_hash=reason_hash,
            facts_hash=fingerprint,
            firms=len(firms),
            refusal=refusal,
        )
        return error

    if not firms or len(firms) > MAX_FIRMS:
        raise await refuse("firm_count", NotFound("security_incident_firms"))
    parsed, confirmed = _facts_of(facts)
    now = clock.system_now()
    if not (parsed.discovered_at <= confirmed <= now + _SKEW):
        raise await refuse("confirmed_out_of_order", ConfirmedOutOfOrder())
    started: list[UUID] = []
    identical: list[UUID] = []
    for tenant_id in firms:
        ctx = _system(tenant_id)
        if await firm_tenancy(ctx) is None:
            raise await refuse("firm_not_found", NotFound("firm"))
        if not await flag_enabled(ctx, COMPLIANCE_INCIDENTS):
            raise await refuse("register_off", NotFound(COMPLIANCE_INCIDENTS.name))
        found = await _existing(ctx, accrued_ref)
        if found is None:
            started.append(tenant_id)
        elif found[1] == fingerprint:
            identical.append(tenant_id)
        else:
            raise await refuse("facts_changed", IncidentFactsChanged())
    if started:
        try:
            await dispatch(
                IncidentPropagationWorkflow,
                IncidentPropagationInput(
                    accrued_ref=accrued_ref,
                    tenant_ids=tuple(str(t) for t in started),
                    facts=facts,
                    staff_id=str(staff_id),
                    reason_sha256=reason_hash,
                ),
                id=incident_propagation_workflow_id(accrued_ref),
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
                id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
            )
        except WorkflowAlreadyStartedError:
            raise await refuse("propagation_running", PropagationRunning()) from None
    await _record(
        actor,
        ref=accrued_ref,
        event="requested",
        staff_id=staff_id,
        reason_hash=reason_hash,
        facts_hash=fingerprint,
        firms=len(firms),
        identical=len(identical),
    )
    return PropagationStarted(started, identical)

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
from collections.abc import Sequence
from dataclasses import dataclass
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
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
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
    IncidentPropagationStep,
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
    "dpa_notice_at, created_by) VALUES (:id, :tenant, :ref, :title, :kind, :discovered, "
    ":consumers, :unencrypted, :notify_by, :source, :accrued_ref, :confirmed, "
    "CASE WHEN :source = 'accrued' THEN clock_timestamp() END, :by) "
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
    return TenantContext(tenant_id, "system", "incident_propagation")


def _facts_of(given: IncidentFactsInput) -> tuple[IncidentFacts, datetime]:
    facts = IncidentFacts(
        title=given.title,
        event_kind=cast(EventKind, given.event_kind),
        discovered_at=datetime.fromisoformat(given.discovered_at),
        consumers_affected=given.consumers_affected,
        unencrypted=given.unencrypted,
    )
    return facts, datetime.fromisoformat(given.confirmed_at)


async def propagate_into(step: IncidentPropagationStep) -> str:
    """One firm's entry for an Accrued incident, as the system (AC-39): Accrued's facts, the
    firm's own `INC-` reference and clock, and `dpa_notice_at` stamped as the entry is written
    and its notice queued. Repeat-safe: a firm that already has the entry gets it back."""
    tenant_id = UUID(step.tenant_id)
    ctx = _system(tenant_id)
    if await firm_tenancy(ctx) is None:
        raise FirmNotFound
    async with tenant_session(ctx) as session:
        existing = await session.scalar(
            text("SELECT ref FROM security_incidents WHERE accrued_ref = :ref"),
            {"ref": step.accrued_ref},
        )
    if existing is not None:
        return str(existing)
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
                notification_event=int(event),
            ),
        )
        tx.emit(IncidentPropagated(incident_id=incident_id, notification_event=event))
    if clock.system_now() - confirmed > DPA_NOTICE:
        # Recorded anyway (a late notice is still the notice); the alarm is RB-27's.
        _log.warning("incident.dpa_notice_late", tenant_id=str(tenant_id), ref=ref)
    return ref


async def start_propagation(
    staff_id: UUID,
    accrued_ref: str,
    tenant_ids: Sequence[UUID],
    facts: IncidentFactsInput,
    reason: str,
) -> list[UUID]:
    """Staff (RB-27): start `IncidentPropagation` for the named firms. Every firm must exist and
    have `compliance.incidents` on (else 404, nothing starts: RB-27's manual step covers it).
    Returns the firms in the order they will be written."""
    firms = list(dict.fromkeys(tenant_ids))
    if not firms or len(firms) > MAX_FIRMS:
        raise NotFound("security_incident_firms")
    parsed, confirmed = _facts_of(facts)
    now = clock.system_now()
    if not (parsed.discovered_at <= confirmed <= now + _SKEW):
        raise ConfirmedOutOfOrder
    for tenant_id in firms:
        ctx = _system(tenant_id)
        if await firm_tenancy(ctx) is None:
            raise NotFound("firm")
        await _require_flag(ctx)
    try:
        await dispatch(
            IncidentPropagationWorkflow,
            IncidentPropagationInput(
                accrued_ref=accrued_ref,
                tenant_ids=tuple(str(t) for t in firms),
                facts=facts,
                staff_id=str(staff_id),
                reason_sha256=reason_sha256(reason),
            ),
            id=incident_propagation_workflow_id(accrued_ref),
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
        )
    except WorkflowAlreadyStartedError:
        raise PropagationRunning from None
    return firms

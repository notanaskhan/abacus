"""The firm export's monthly schedule (G-02-T19; SPEC-349 AC-25; DEC-72, DEC-623). Contract:
`docs/contracts/security-center.md` §3, §4.

Behind `security_center.v1` (off: 404).

- **Set (`firm_export.schedule`, the QI, fresh MFA):** contents and pause, against `version`
  (0 before the first save; 409 `stale_version`). Any change takes it back to
  `pending_approval` (or `paused`): both approvals are cleared, here and by 0241's trigger.
- **Approve (`firm_export.approve`, fresh MFA):** a `security_admin` and a partner, each once, two
  distinct people (DEC-72). An approver fills a seat they hold that is still empty; the same
  person again, or a seat already filled, answers 409 `approver_must_differ`; a paused schedule
  409 `schedule_paused`. With both seats filled it is `active`. An approval does not move
  `version` (it is not a change to what runs): the QI's next save still carries the version read.
- **Runs:** each change is announced (`firm_export_schedule.changed`) and its subscriber converges
  the firm's Temporal Schedule (`firm_export_schedule:<tenant>`, the 1st at 02:00 in the firm's
  time zone, through `kernel.dispatch.firm_schedule`): running only while `active`, paused
  otherwise. Each run (`FirmExportScheduleWorkflow`) re-reads the schedule and starts Q-02's
  firm export through the starter Q-02-T43 registers (`register_firm_export_starter`), which also
  notifies both approvers; until that lands nothing is exported, and the run records
  `firm_export_schedule.run_skipped` and notifies nobody (DEC-623).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping
from datetime import date, datetime
from typing import Any, Final, Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text
from temporalio import activity

from abacus.kernel import clock
from abacus.kernel._flags import SECURITY_CENTER_V1
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import FirmSchedule, WorkClass, firm_schedule, register_work_classes
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Handler, OutboxEvent, Ref, Target, uow
from abacus.modules.evidence.events import FirmExportScheduleChanged
from abacus.modules.evidence.firm_export_contract import FirmExportPersonOut
from abacus.modules.evidence.firm_export_schedule_contract import (
    FirmExportScheduleIn,
    FirmExportScheduleOut,
    ScheduleApprovalOut,
)
from abacus.modules.evidence.workflows import (
    FirmExportScheduleWorkflow,
    firm_export_schedule_id,
)
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    firm_time_zone,
    names_of,
    partner_members,
    security_admins,
)

SUBJECT: Final = "firm_export_schedule"
DAY_OF_MONTH: Final = 1
HOUR: Final = 2
Seat = Literal["security_admin", "partner"]
_log = get_logger(__name__)


class ScheduleStale(DomainConflict):
    """The schedule changed since it was read (409)."""

    code = "stale_version"


class ScheduleApproverMustDiffer(DomainConflict):
    """Two distinct people approve, one per seat: the same person again, or a seat already
    filled, is refused (DEC-72)."""

    code = "approver_must_differ"


class SchedulePaused(DomainConflict):
    """A paused schedule is not approved: unpause it (which waits for both again) first."""

    code = "schedule_paused"


async def _gate(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, SECURITY_CENTER_V1):
        raise NotFound(SECURITY_CENTER_V1.name)


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden(action, "role")


_ROW = text(
    "SELECT time_zone, contents, paused, status, approved_security_by, approved_partner_by, "
    "version FROM firm_export_schedules"
)
_ROW_LOCKED = text(
    "SELECT time_zone, contents, paused, status, approved_security_by, approved_partner_by, "
    "version FROM firm_export_schedules FOR UPDATE"
)
Row = Mapping[Any, Any]  # Any: an untyped database row


def next_run_on(time_zone: str, now: datetime) -> date:
    """The next 1st at 02:00 in the firm's zone after `now`."""
    local = now.astimezone(ZoneInfo(time_zone))
    this_month = local.replace(day=DAY_OF_MONTH, hour=HOUR, minute=0, second=0, microsecond=0)
    if local < this_month:
        return this_month.date()
    year, month = (local.year + 1, 1) if local.month == 12 else (local.year, local.month + 1)
    return date(year, month, DAY_OF_MONTH)


async def _out(tenant: TenantContext, row: Row) -> FirmExportScheduleOut:
    columns: tuple[tuple[Seat, str], ...] = (
        ("security_admin", "approved_security_by"),
        ("partner", "approved_partner_by"),
    )
    seats: list[tuple[Seat, UUID]] = [
        (seat, cast(UUID, row[c])) for seat, c in columns if row[c] is not None
    ]
    names = await names_of([u for _, u in seats])
    status = str(row["status"])
    return FirmExportScheduleOut(
        cadence="monthly",
        day_of_month=1,
        local_time="02:00",
        time_zone=str(row["time_zone"]),
        contents=cast(Any, list(row["contents"])),  # Any: the CHECKed content codes
        status=cast(Any, status),  # Any: the CHECKed status codes
        approvals=[
            ScheduleApprovalOut(
                seat=seat,
                approved_by=FirmExportPersonOut(user_id=user, display_name=names.get(user, "")),
            )
            for seat, user in seats
        ],
        next_run_on=(
            next_run_on(str(row["time_zone"]), await clock.now(tenant))
            if status == "active"
            else None
        ),
        version=int(row["version"]),
    )


async def _read_row(tenant: TenantContext) -> Row | None:
    async with tenant_session(tenant) as session:
        return (await session.execute(_ROW)).mappings().one_or_none()


async def read(ctx: AuthContext) -> FirmExportScheduleOut:
    """The card; 404 while the firm has no schedule."""
    await _gate(ctx)
    row = await _read_row(ctx.tenant)
    if row is None:
        raise NotFound(SUBJECT)
    return await _out(ctx.tenant, row)


_INSERT = text(
    "INSERT INTO firm_export_schedules (tenant_id, time_zone, contents, paused, status, "
    "updated_by) VALUES (:tenant, :zone, CAST(:contents AS jsonb), :paused, :status, :by) "
    "ON CONFLICT (tenant_id) DO NOTHING RETURNING version"
)
_UPDATE = text(
    "UPDATE firm_export_schedules SET time_zone = :zone, contents = CAST(:contents AS jsonb), "
    "paused = :paused, status = :status, approved_security_by = NULL, "
    "approved_partner_by = NULL, version = version + 1, updated_by = :by "
    "WHERE version = :version RETURNING version"
)


async def put(ctx: AuthContext, body: FirmExportScheduleIn) -> FirmExportScheduleOut:
    """Set the schedule; it waits for both approvals again. Audited
    `firm_export_schedule.updated`."""
    await _gate(ctx)
    _human(ctx, "firm_export.schedule")
    zone = await firm_time_zone(ctx.tenant)
    params = {
        "tenant": ctx.tenant_id,
        "zone": zone,
        "contents": json.dumps(list(dict.fromkeys(body.contents))),
        "paused": body.paused,
        "status": "paused" if body.paused else "pending_approval",
        "by": ctx.user_id,
        "version": body.version,
    }
    async with uow(ctx.tenant) as tx:
        version = await tx.session.scalar(_INSERT if body.version == 0 else _UPDATE, params)
        if version is None:
            raise ScheduleStale
        tx.record(
            "firm_export_schedule.updated",
            target=Target(SUBJECT, ctx.tenant_id),
            after=Ref(version=int(version), paused=int(body.paused)),
        )
        tx.emit(FirmExportScheduleChanged(tenant_id=ctx.tenant_id))
    return await read(ctx)


async def _seats(tenant_id: UUID, user_id: UUID) -> list[Seat]:
    seats: list[Seat] = []
    if user_id in await security_admins(tenant_id):
        seats.append("security_admin")
    if user_id in await partner_members(tenant_id):
        seats.append("partner")
    return seats


_APPROVE: Final = {
    "security_admin": text(
        "UPDATE firm_export_schedules SET approved_security_by = :by, updated_by = :by, "
        "status = CASE WHEN approved_partner_by IS NOT NULL THEN 'active' ELSE status END "
        "WHERE approved_security_by IS NULL RETURNING status"
    ),
    "partner": text(
        "UPDATE firm_export_schedules SET approved_partner_by = :by, updated_by = :by, "
        "status = CASE WHEN approved_security_by IS NOT NULL THEN 'active' ELSE status END "
        "WHERE approved_partner_by IS NULL RETURNING status"
    ),
}


async def approve(ctx: AuthContext) -> FirmExportScheduleOut:
    """A `security_admin` or a partner approves once; the second distinct approver in the other
    seat makes it `active`. Audited `firm_export_schedule.approved`."""
    await _gate(ctx)
    _human(ctx, "firm_export.approve")
    mine = await _seats(ctx.tenant_id, ctx.user_id)
    async with uow(ctx.tenant) as tx:
        row = (await tx.session.execute(_ROW_LOCKED)).mappings().one_or_none()
        if row is None:
            raise NotFound(SUBJECT)
        if row["paused"]:
            raise SchedulePaused
        if ctx.user_id in (row["approved_security_by"], row["approved_partner_by"]):
            raise ScheduleApproverMustDiffer
        open_seats = [
            seat
            for seat in mine
            if row["approved_security_by" if seat == "security_admin" else "approved_partner_by"]
            is None
        ]
        if not open_seats:
            raise ScheduleApproverMustDiffer
        seat = open_seats[0]
        status = await tx.session.scalar(_APPROVE[seat], {"by": ctx.user_id})
        if status is None:
            raise ScheduleApproverMustDiffer
        tx.record(
            "firm_export_schedule.approved",
            target=Target(SUBJECT, ctx.tenant_id),
            after=Ref(active=int(status == "active")),
        )
        tx.emit(FirmExportScheduleChanged(tenant_id=ctx.tenant_id))
    return await read(ctx)


# --- the Temporal Schedule ---------------------------------------------------------------------


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "firm_export_schedule")


async def sync_schedule(tenant_id: UUID) -> Literal["created", "updated", "none"]:
    """Converge the firm's Temporal Schedule on its record: running only while `active`."""
    row = await _read_row(_system(tenant_id))
    if row is None:
        return "none"
    return await firm_schedule(
        FirmSchedule(
            id=firm_export_schedule_id(tenant_id),
            workflow=FirmExportScheduleWorkflow,
            arg=str(tenant_id),
            day_of_month=DAY_OF_MONTH,
            hour=HOUR,
            minute=0,
            time_zone=str(row["time_zone"]),
            note="G-02-T19: the firm's monthly export (DEC-72 dual approval)",
        ),
        paused=row["status"] != "active",
    )


async def on_changed(event: OutboxEvent) -> None:
    await sync_schedule(event.tenant_id)


SUBSCRIPTIONS: dict[str, Handler] = {FirmExportScheduleChanged.event_type: on_changed}

# Q-02-T43's firm export: `(tenant_id, approvers) -> export id`, starting `FirmExportWorkflow`
# with both approvals on record and notifying both approvers (`firm_export_ready` per run).
FirmExportStarter = Callable[[UUID, tuple[UUID, UUID]], Awaitable[UUID]]
_starter: list[FirmExportStarter] = []


def register_firm_export_starter(starter: FirmExportStarter) -> None:
    """Q-02-T43 registers the scheduled export's start (once)."""
    if _starter and _starter[0] is not starter:
        raise RuntimeError("the firm export starter is already registered")
    _starter[:] = [starter]


async def run_scheduled(tenant_id: UUID) -> str:
    """One scheduled run: only an `active` schedule exports, through Q-02's starter."""
    system = _system(tenant_id)
    row = await _read_row(system)
    if row is None or row["status"] != "active":
        return "inactive"
    approvers = (cast(UUID, row["approved_security_by"]), cast(UUID, row["approved_partner_by"]))
    if not _starter:
        async with uow(system) as tx:
            tx.record("firm_export_schedule.run_skipped", target=Target(SUBJECT, tenant_id))
        _log.warning("firm_export_schedule.no_starter", tenant_id=str(tenant_id))
        return "skipped"
    export_id = await _starter[0](tenant_id, approvers)
    async with uow(system) as tx:
        tx.record(
            "firm_export_schedule.run_started",
            target=Target(SUBJECT, tenant_id),
            after=Ref(export_id=export_id),
        )
    return "started"


@activity.defn(name="evidence.firm_export_scheduled_run")
async def scheduled_run_activity(tenant_id: str) -> str:
    return await run_scheduled(UUID(tenant_id))


WORKFLOWS: dict[type, WorkClass] = {FirmExportScheduleWorkflow: "batch"}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (scheduled_run_activity,)

__all__ = [
    "ACTIVITIES",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "FirmExportStarter",
    "approve",
    "next_run_on",
    "put",
    "read",
    "register_firm_export_starter",
    "run_scheduled",
    "sync_schedule",
]

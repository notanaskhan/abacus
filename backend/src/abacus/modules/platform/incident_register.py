"""The incident register's read side, timeline and two-person decisions (G-02-T18; SPEC-349
AC-21 to AC-23; DEC-625). Contract: `docs/contracts/security-center.md` §3, §4.

On Q-02's kernel (`incidents.py`: the entries and their FTC clock). Behind `security_center.v1`
and `compliance.incidents` (either off: 404).

- **Clock (AC-21):** `clock_day`, `ftc_notify_by` and the reminder dates are the kernel's, in the
  firm's time zone on the business clock ("Day 4 of 30 · notify by Oct 10").
- **Decisions (AC-22):** one partner and the QI (`security_admin`), distinct, each with a fresh
  second factor (the matrix). The first decider names the other (`second_decider_user_id`), who
  must be able to fill the other seat (422 `second_decider_invalid` otherwise); the incident reads
  "Waiting for" them (`incident_decision_requested`). Only the named person completes it, with the
  same kind; anyone else, or the same person again, answers 409 `decider_must_differ`; a decided
  incident 409 `already_decided`. `close_not_reportable` closes the incident;
  `start_notification` stamps the notification's start. The database holds the same rules
  (0240's triggers), so no path round them exists.
- **Timeline (AC-23):** append-only and attributed (the QI's `incident.manage`); an Accrued
  incident (RB-27) opens with Accrued's own entry, `source: accrued`, no author.
- **Reminders (AC-23):** the `IncidentClockReminders` job notifies the QI and the partners on days
  20, 25 and 29 of an open notification event's clock, once each (`security_incident_reminders`).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Final, Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, column, select, table, text
from temporalio import activity

from abacus.kernel import clock
from abacus.kernel._flags import COMPLIANCE_INCIDENTS, SECURITY_CENTER_V1
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import (
    capped_total,
    decode_cursor,
    envelope,
    keyset,
    page_of,
    query_hash,
)
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import (
    AuthContext,
    firm_tenant_ids,
    firm_time_zone,
    names_of,
    partner_members,
    security_admins,
)
from abacus.modules.platform.events import (
    IncidentDeadlineApproaching,
    IncidentDecisionRequested,
)
from abacus.modules.platform.governance_errors import DeciderMustDiffer
from abacus.modules.platform.incidents import CLOCK_DAYS, clock_day, discovered_on
from abacus.modules.platform.security_center_contract import (
    GovernancePersonOut,
    IncidentDecisionIn,
    IncidentDecisionOut,
    IncidentPendingDecisionOut,
    IncidentTimelineEntryIn,
    IncidentTimelineEntryOut,
    SecurityIncidentDetailOut,
    SecurityIncidentOut,
    SecurityIncidentPageOut,
)

SUBJECT: Final = "security_incident"
RESOURCE: Final = "security_incidents"
REMINDER_DAYS: Final = (20, 25, 29)
Seat = Literal["partner", "qualified_individual"]
_ACCRUED_ENTRY: Final = uuid.UUID("6f1d0c1e-7b1a-4a53-9a8e-5d2d3c4b5a69")  # uuid5 namespace
_log = get_logger(__name__)


class AlreadyDecided(DomainConflict):
    """Both people have decided this incident: nothing more is recorded (AC-22)."""

    code = "already_decided"


class SecondDeciderInvalid(DomainInvalid):
    """The first decision names nobody, or someone who cannot fill the other seat (a partner if
    the QI decides first, the QI if a partner does)."""

    code = "second_decider_invalid"


class DecisionKindDiffers(DomainConflict):
    """The second decider decides what the first did, or nothing: a different call starts over
    only once this one is settled."""

    code = "decision_kind_differs"


async def _gate(ctx: AuthContext) -> None:
    for flag in (SECURITY_CENTER_V1, COMPLIANCE_INCIDENTS):
        if not await flag_enabled(ctx.tenant, flag):
            raise NotFound(flag.name)


# --- reading ---------------------------------------------------------------------------------

_I = table(
    "security_incidents",
    column("id"),
    column("ref"),
    column("title"),
    column("event_kind"),
    column("discovered_at"),
    column("consumers_affected"),
    column("unencrypted"),
    column("notification_event"),
    column("ftc_notify_by"),
    column("status"),
    column("source"),
    column("accrued_ref"),
    column("accrued_confirmed_at"),
    column("dpa_notice_at"),
    column("created_at"),
    column("closed_at"),
    column("notification_started_at"),
)
_DECISIONS = text(
    "SELECT incident_id, kind, seat, decided_by, waiting_for, decided_at "
    "FROM security_incident_decisions WHERE incident_id = ANY(:ids) ORDER BY decided_at"
)
_TIMELINE = text(
    "SELECT id, occurred_at, code, facts, note, source, author_user_id, recorded_at "
    "FROM security_incident_timeline WHERE incident_id = :id ORDER BY recorded_at, id"
)

Row = Mapping[str, Any]  # Any: an untyped database row


@dataclass(frozen=True)
class _Decision:
    kind: str
    seat: Seat
    decided_by: UUID
    waiting_for: UUID | None
    decided_at: datetime


def _person(user: UUID, names: Mapping[UUID, str]) -> GovernancePersonOut:
    return GovernancePersonOut(user_id=user, display_name=names.get(user, ""))


def _other(seat: Seat) -> Seat:
    return "partner" if seat == "qualified_individual" else "qualified_individual"


def _incident_out(
    row: Row, decisions: Sequence[_Decision], zone: str, on: date, names: Mapping[UUID, str]
) -> dict[str, object]:
    discovered = cast(datetime, row["discovered_at"])
    pending = None
    done: list[IncidentDecisionOut] = []
    shown = [
        IncidentDecisionOut(
            kind=cast(Any, d.kind),  # Any: the CHECKed decision kinds
            decided_by=_person(d.decided_by, names),
            seat=d.seat,
            decided_at=d.decided_at,
        )
        for d in decisions
    ]
    waiting = decisions[0].waiting_for if len(decisions) == 1 else None
    if waiting is not None:
        first = decisions[0]
        pending = IncidentPendingDecisionOut(
            kind=cast(Any, first.kind),  # Any: the CHECKed decision kinds
            first=shown[0],
            waiting_for=_person(waiting, names),
            waiting_for_seat=_other(first.seat),
        )
    elif len(decisions) == 2:
        done = shown
    return {
        "id": row["id"],
        "ref": row["ref"],
        "title": row["title"],
        "event_kind": row["event_kind"],
        "discovered_at": discovered,
        "consumers_affected": row["consumers_affected"],
        "unencrypted": row["unencrypted"],
        "notification_event": bool(row["notification_event"]),
        "ftc_notify_by": row["ftc_notify_by"],
        "clock_day": clock_day(discovered, zone, on),
        "clock_days": CLOCK_DAYS,
        "status": row["status"],
        "source": row["source"],
        "accrued_ref": row["accrued_ref"],
        "created_at": row["created_at"],
        "pending_decision": pending,
        "decisions": done,
        "notification_started_at": row["notification_started_at"],
    }


async def _decisions(tenant: TenantContext, ids: Sequence[UUID]) -> dict[UUID, list[_Decision]]:
    found: dict[UUID, list[_Decision]] = {}
    if not ids:
        return found
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_DECISIONS, {"ids": list(ids)})).mappings().all()
    for r in rows:
        found.setdefault(cast(UUID, r["incident_id"]), []).append(
            _Decision(
                kind=str(r["kind"]),
                seat=cast(Seat, r["seat"]),
                decided_by=cast(UUID, r["decided_by"]),
                waiting_for=cast(UUID | None, r["waiting_for"]),
                decided_at=cast(datetime, r["decided_at"]),
            )
        )
    return found


def _people(decisions: Mapping[UUID, Sequence[_Decision]]) -> set[UUID]:
    people: set[UUID] = set()
    for rows in decisions.values():
        for d in rows:
            people.add(d.decided_by)
            if d.waiting_for is not None:
                people.add(d.waiting_for)
    return people


async def _today(tenant: TenantContext) -> tuple[str, date]:
    zone = await firm_time_zone(tenant)
    return zone, (await clock.now(tenant)).astimezone(ZoneInfo(zone)).date()


async def list_incidents(
    ctx: AuthContext, status: str | None, cursor: str | None, limit: int
) -> SecurityIncidentPageOut:
    """AC-21: newest discovery first, each with its clock today; `counts` open and closed."""
    await _gate(ctx)
    digest = query_hash(status=status)
    after = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=RESOURCE, query=digest)
        if cursor
        else None
    )
    base = select(*_I.c)
    if status is not None:
        base = base.where(_I.c.status == status)
    async with tenant_session(ctx.tenant) as session:
        stmt = keyset(
            base,
            sort=cast(ColumnElement[object], _I.c.discovered_at),
            id_column=cast(ColumnElement[object], _I.c.id),
            after=after,
            descending=True,
            limit=limit,
        )
        fetched = [dict(m) for m in (await session.execute(stmt)).mappings().all()]
        total = await capped_total(session, base)
        counted = await session.execute(
            text("SELECT status, count(*) FROM security_incidents GROUP BY status")
        )
        counts = {"open": 0, "closed": 0}
        for code, n in counted.all():
            counts["open" if code == "investigating" else "closed"] += int(n)
    rows, position = page_of(
        fetched, limit=limit, key=lambda r: r["discovered_at"], id_of=lambda r: r["id"]
    )
    decisions = await _decisions(ctx.tenant, [cast(UUID, r["id"]) for r in rows])
    names = await names_of(sorted(_people(decisions), key=str))
    zone, on = await _today(ctx.tenant)
    items = [
        SecurityIncidentOut.model_validate(
            _incident_out(r, decisions.get(cast(UUID, r["id"]), []), zone, on, names)
        )
        for r in rows
    ]
    page = envelope(
        items,
        next_position=position,
        tenant_id=ctx.tenant_id,
        resource=RESOURCE,
        query=digest,
        total=total,
        counts=counts,
    )
    return SecurityIncidentPageOut.model_validate(page.model_dump())


async def _row(tenant: TenantContext, incident_id: UUID) -> dict[str, object]:
    async with tenant_session(tenant) as session:
        found = (
            (await session.execute(select(*_I.c).where(_I.c.id == incident_id)))
            .mappings()
            .one_or_none()
        )
    if found is None:
        raise NotFound(SUBJECT)
    return dict(found)


def reminders_on(discovered_at: datetime, zone: str) -> list[date]:
    start = discovered_on(discovered_at, zone)
    return [start + timedelta(days=d) for d in REMINDER_DAYS]


def _accrued_entry(row: Row) -> IncidentTimelineEntryOut:
    """RB-27: an Accrued incident opens with Accrued's own entry (no author)."""
    return IncidentTimelineEntryOut(
        id=uuid.uuid5(_ACCRUED_ENTRY, str(row["id"])),
        occurred_at=cast(datetime, row["accrued_confirmed_at"]),
        code="reported_by_accrued",
        facts={"accrued_ref": cast(str, row["accrued_ref"])},
        note=None,
        source="accrued",
        author=None,
        recorded_at=cast(datetime, row["dpa_notice_at"]),
    )


async def get_incident(ctx: AuthContext, incident_id: UUID) -> SecurityIncidentDetailOut:
    """ADM-06 d: the drawer; 404 for another firm's or an unknown incident."""
    await _gate(ctx)
    row = await _row(ctx.tenant, incident_id)
    decisions = await _decisions(ctx.tenant, [incident_id])
    async with tenant_session(ctx.tenant) as session:
        entries = (await session.execute(_TIMELINE, {"id": incident_id})).mappings().all()
    people = _people(decisions) | {
        cast(UUID, e["author_user_id"]) for e in entries if e["author_user_id"] is not None
    }
    names = await names_of(sorted(people, key=str))
    zone, on = await _today(ctx.tenant)
    timeline = [_accrued_entry(row)] if row["source"] == "accrued" else []
    timeline += [
        IncidentTimelineEntryOut(
            id=cast(UUID, e["id"]),
            occurred_at=cast(datetime, e["occurred_at"]),
            code=str(e["code"]),
            facts=cast(dict[str, Any], e["facts"] or {}),  # Any: jsonb facts, validated in
            note=cast(str | None, e["note"]),
            source=e["source"],
            author=(
                _person(cast(UUID, e["author_user_id"]), names)
                if e["author_user_id"] is not None
                else None
            ),
            recorded_at=cast(datetime, e["recorded_at"]),
        )
        for e in entries
    ]
    return SecurityIncidentDetailOut.model_validate(
        {
            **_incident_out(row, decisions.get(incident_id, []), zone, on, names),
            "timeline": timeline,
            "reminders_on": reminders_on(cast(datetime, row["discovered_at"]), zone),
        }
    )


# --- writing ---------------------------------------------------------------------------------

_APPEND = text(
    "INSERT INTO security_incident_timeline (tenant_id, incident_id, occurred_at, code, facts, "
    "note, source, author_user_id) VALUES (:tenant, :incident, :occurred, :code, "
    "CAST(:facts AS jsonb), :note, 'firm', :author) RETURNING id, recorded_at"
)


async def append_entry(
    ctx: AuthContext, incident_id: UUID, body: IncidentTimelineEntryIn
) -> IncidentTimelineEntryOut:
    """AC-23: one attributed entry, never edited or removed."""
    await _gate(ctx)
    await _row(ctx.tenant, incident_id)
    async with uow(ctx.tenant) as tx:
        found = (
            (
                await tx.session.execute(
                    _APPEND,
                    {
                        "tenant": ctx.tenant_id,
                        "incident": incident_id,
                        "occurred": body.occurred_at,
                        "code": body.code,
                        "facts": json.dumps(body.facts, sort_keys=True),
                        "note": body.note,
                        "author": ctx.user_id,
                    },
                )
            )
            .mappings()
            .one()
        )
        tx.record(
            "incident.timeline_appended",
            target=Target(SUBJECT, incident_id),
            after=Ref(entry_id=cast(UUID, found["id"])),
        )
    names = await names_of([ctx.user_id])
    return IncidentTimelineEntryOut(
        id=cast(UUID, found["id"]),
        occurred_at=body.occurred_at,
        code=body.code,
        facts=dict(body.facts),
        note=body.note,
        source="firm",
        author=_person(ctx.user_id, names),
        recorded_at=cast(datetime, found["recorded_at"]),
    )


async def _seats(tenant_id: UUID, user_id: UUID) -> set[Seat]:
    seats: set[Seat] = set()
    if user_id in await security_admins(tenant_id):
        seats.add("qualified_individual")
    if user_id in await partner_members(tenant_id):
        seats.add("partner")
    return seats


_LOCK = text("SELECT status FROM security_incidents WHERE id = :id FOR UPDATE")
_DECIDE = text(
    "INSERT INTO security_incident_decisions (tenant_id, incident_id, kind, seat, decided_by, "
    "waiting_for, note) VALUES (:tenant, :incident, :kind, :seat, :by, :waiting, :note)"
)
_CLOSE = text("UPDATE security_incidents SET status = 'closed' WHERE id = :id")
_NOTIFY = text(
    "UPDATE security_incidents SET notification_started_at = clock_timestamp() WHERE id = :id"
)


async def record_decision(
    ctx: AuthContext, incident_id: UUID, body: IncidentDecisionIn
) -> SecurityIncidentOut:
    """AC-22: the first decider's call waits for the person named; that person's same call
    completes it. Each decider's call is audited `incident.decision_recorded`, the completion
    `incident.decided`."""
    await _gate(ctx)
    await _row(ctx.tenant, incident_id)
    mine = await _seats(ctx.tenant_id, ctx.user_id)
    async with uow(ctx.tenant) as tx:
        status = await tx.session.scalar(_LOCK, {"id": incident_id})
        if status is None:
            raise NotFound(SUBJECT)
        rows = (
            (
                await tx.session.execute(
                    text(
                        "SELECT kind, seat, decided_by, waiting_for FROM "
                        "security_incident_decisions WHERE incident_id = :id ORDER BY decided_at"
                    ),
                    {"id": incident_id},
                )
            )
            .mappings()
            .all()
        )
        if len(rows) >= 2 or status != "investigating":
            raise AlreadyDecided
        if not rows:
            if not mine:
                raise DeciderMustDiffer  # the matrix let them in, but they fill no seat
            seat: Seat = "qualified_individual" if "qualified_individual" in mine else "partner"
            second = body.second_decider_user_id
            if second is None:
                raise SecondDeciderInvalid(facts={"seat": _other(seat)})
            if second == ctx.user_id:
                raise DeciderMustDiffer
            if _other(seat) not in await _seats(ctx.tenant_id, second):
                raise SecondDeciderInvalid(facts={"seat": _other(seat)})
            await tx.session.execute(
                _DECIDE,
                {
                    "tenant": ctx.tenant_id,
                    "incident": incident_id,
                    "kind": body.kind,
                    "seat": seat,
                    "by": ctx.user_id,
                    "waiting": second,
                    "note": body.note,
                },
            )
            tx.record(
                "incident.decision_recorded",
                target=Target(SUBJECT, incident_id),
                after=Ref(waiting_for_user_id=second),
            )
            tx.emit(
                IncidentDecisionRequested(
                    incident_id=incident_id, waiting_for_user_id=second, by_user=ctx.user_id
                )
            )
        else:
            first = rows[0]
            if first["decided_by"] == ctx.user_id or first["waiting_for"] != ctx.user_id:
                raise DeciderMustDiffer
            seat = _other(cast(Seat, first["seat"]))
            if seat not in mine:
                raise DeciderMustDiffer
            if first["kind"] != body.kind:
                raise DecisionKindDiffers
            await tx.session.execute(
                _DECIDE,
                {
                    "tenant": ctx.tenant_id,
                    "incident": incident_id,
                    "kind": body.kind,
                    "seat": seat,
                    "by": ctx.user_id,
                    "waiting": None,
                    "note": body.note,
                },
            )
            await tx.session.execute(
                _CLOSE if body.kind == "close_not_reportable" else _NOTIFY, {"id": incident_id}
            )
            tx.record(
                "incident.decision_recorded",
                target=Target(SUBJECT, incident_id),
                after=Ref(first_user_id=cast(UUID, first["decided_by"])),
            )
            tx.record(
                "incident.decided",
                target=Target(SUBJECT, incident_id),
                after=Ref(
                    first_user_id=cast(UUID, first["decided_by"]),
                    second_user_id=ctx.user_id,
                ),
            )
    detail = await get_incident(ctx, incident_id)
    return SecurityIncidentOut.model_validate(
        detail.model_dump(exclude={"timeline", "reminders_on"})
    )


# --- reminders (days 20, 25 and 29) --------------------------------------------------------------

_DUE = text(
    "SELECT i.id, i.discovered_at FROM security_incidents i "
    "WHERE i.status = 'investigating' AND i.notification_event "
    "AND NOT EXISTS (SELECT 1 FROM security_incident_reminders r "
    "WHERE r.incident_id = i.id AND r.day = :day)"
)
_REMIND = text(
    "INSERT INTO security_incident_reminders (tenant_id, incident_id, day) "
    "VALUES (:tenant, :incident, :day) ON CONFLICT DO NOTHING RETURNING day"
)
REMINDER_ACTOR: Final = "incident_clock_reminders"


class _AlreadySent(Exception):
    """A reminder another run already sent: the unit of work rolls back."""


async def remind_firm(tenant_id: UUID) -> int:
    """One firm's due reminders: each open notification event on day 20, 25 or 29 of its clock
    (or past it, for a day a late run missed), once per day, to the QI and the partners."""
    system = TenantContext(tenant_id, "system", REMINDER_ACTOR)
    zone, on = await _today(system)
    sent = 0
    for day in REMINDER_DAYS:
        async with tenant_session(system) as session:
            due = (await session.execute(_DUE, {"day": day})).mappings().all()
        for row in due:
            discovered = cast(datetime, row["discovered_at"])
            if not day <= clock_day(discovered, zone, on) <= CLOCK_DAYS:
                continue
            incident_id = cast(UUID, row["id"])
            try:
                async with uow(system) as tx:
                    wrote = await tx.session.scalar(
                        _REMIND, {"tenant": tenant_id, "incident": incident_id, "day": day}
                    )
                    if wrote is None:
                        raise _AlreadySent  # another run sent it: roll back, record nothing
                    tx.record(
                        "incident.reminder_sent",
                        target=Target(SUBJECT, incident_id),
                        after=Ref(day=day),
                    )
                    tx.emit(IncidentDeadlineApproaching(incident_id=incident_id, day=day))
            except _AlreadySent:
                continue
            sent += 1
    return sent


@activity.defn(name="platform.incident_reminders")
async def incident_reminders_activity() -> int:
    """Every firm with the register on, one at a time; one firm's failure is logged by id and the
    others still run."""
    sent = 0
    for tenant_id in await firm_tenant_ids():
        try:
            system = TenantContext(tenant_id, "system", REMINDER_ACTOR)
            if not await flag_enabled(system, COMPLIANCE_INCIDENTS):
                continue
            sent += await remind_firm(tenant_id)
        except Exception as exc:
            _log.error(
                "incident_reminders.failed", tenant_id=str(tenant_id), error=type(exc).__name__
            )
    return sent


__all__ = [
    "REMINDER_DAYS",
    "AlreadyDecided",
    "DecisionKindDiffers",
    "SecondDeciderInvalid",
    "append_entry",
    "get_incident",
    "incident_reminders_activity",
    "list_incidents",
    "record_decision",
    "remind_firm",
    "reminders_on",
]

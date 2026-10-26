"""ADM-07's read service (G-02-T08; SPEC-349 AC-1 to AC-10; DEC-60, DEC-420, DEC-434).

`list_events`, `get_event` and `events_for_work_item` read `audit_events` through the kernel's
composed read surface (`kernel.uow.explorer`) and answer the contract's shapes.

**Who sees an event** (security review, S9; SPEC-349 §4, §7, §9), all in SQL so that `total`
and `counts` never include an omitted row and nothing says rows were left out (DEC-43):

- An event's engagement is its `engagement_id`, else its target when that is an engagement.
  An event with an engagement is shown when `visible(ctx, "audit_event.read", engagement)`
  admits it: engagement roles, in-scope readers and firm roles as the matrix says, minus walls
  on the engagement's client. So walls key on a client derived from `engagement_id`, for history
  and new events alike (security review L4).
- An event with no engagement (sign-ins, security settings, walls, firm structure, unscoped
  history) is firm-level: only a reader allowed `audit_event.read_firm_level` at the firm sees it
  (`firm_admin`, `security_admin`, the QM owner `quality_partner` and platform support; DEC-434).
  Engagement roles never do. A firm-level reader walled from any client sees, of these, only
  the kinds that can name no client (`targets.FIRM_LEVEL`), and of those only events whose
  references name no client it is walled from and no client-side identifier it cannot place
  (`FIRM_SAFE_REFS`; security review M1: `legal_hold.placed` carries its client in `after_ref`,
  and `audit_events.client_id` is not filled by writers yet). Unplaced history fails closed.
- A stored `client_id` the reader is walled from hides the event whatever else holds.

**What a row carries:** the actor grammar (`person`, `via_agent` with the person it acted for,
`policy`, `system`, `support`); the catalogue's category and marker, `ok` only for a person or a
policy (AC-3); identifier facts from the references, never a fingerprint or a value (M4);
request context only for readers allowed `audit_event.read_request_context` (DEC-420: the
three `REQUEST_CONTEXT_READERS`), null for everyone else; and the
IP filter only for those readers too, so nobody else can probe who used an address.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Final, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import (
    ColumnElement,
    Select,
    and_,
    case,
    exists,
    false,
    func,
    literal,
    null,
    or_,
    select,
    true,
)
from sqlalchemy import cast as sql_cast
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.listing import (
    TOTAL_CAP,
    ListPage,
    Position,
    capped_total,
    decode_cursor,
    envelope,
    keyset,
    page_of,
    query_hash,
)
from abacus.kernel.uow.chain import leaf
from abacus.kernel.uow.explorer import AUDIT_EVENTS, leaf_version_at
from abacus.modules.audit_trail import labels as label_index
from abacus.modules.audit_trail import values as event_values
from abacus.modules.audit_trail.activity_catalogue import activity_of
from abacus.modules.audit_trail.audit_log_contract import (
    ActorKind,
    AuditActorOut,
    AuditEventDetail,
    AuditEventRow,
    AuditPersonOut,
    AuditSessionOut,
    AuditSourceOut,
    AuditTargetOut,
    Fact,
    Mark,
)
from abacus.modules.audit_trail.targets import FIRM_LEVEL
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    allowed_actions,
    firm_time_zone,
    member_facts,
    names_of,
    visible,
    walled_from,
)
from abacus.modules.platform.api import AuditEventRef, audit_labels, audit_source

READ: Final = "audit_event.read"
RESOURCE: Final = "audit_events"
# DEC-434: firm-level events (no engagement) for the readers this action allows at the firm;
# DEC-420: request context for the readers this one allows. Both are matrix rows, never roles
# read here (AUTHZ-002).
READ_FIRM_LEVEL: Final = "audit_event.read_firm_level"
READ_REQUEST_CONTEXT: Final = "audit_event.read_request_context"
WORK_ITEM_LIMIT: Final = 500
_UUID: Final = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
_FINGERPRINT: Final = re.compile(r"[0-9a-f]{64}")
_PERSON_REF: Final = re.compile(r"(?:^|_)user_id$")

t = AUDIT_EVENTS.c
# The event's engagement: its scope, else its target when the target is an engagement.
ENGAGEMENT: Final[ColumnElement[UUID]] = func.coalesce(
    t.engagement_id,
    case(
        (
            and_(t.target_type == "engagement", t.target_id.op("~")(_UUID)),
            sql_cast(t.target_id, PgUUID(as_uuid=True)),
        ),
        else_=null(),
    ),
)
# The actor grammar's kind, in SQL, for the filter and the counts.
GRAMMAR: Final[ColumnElement[str]] = case(
    (t.actor_kind == "human", literal("person")),
    (and_(t.actor_kind == "agent", t.on_behalf_of_user_id.is_not(None)), literal("via_agent")),
    (t.actor_kind == "policy", literal("policy")),
    (t.actor_kind == "support", literal("support")),
    else_=literal("system"),
)
COUNTED: Final = ("person", "via_agent", "policy", "system")


@dataclass(frozen=True)
class EventFilter:
    """The list's filters (SPEC-349 §4); None means any."""

    actor_kind: ActorKind | None = None
    actor_id: UUID | None = None
    object_type: str | None = None
    action: str | None = None
    from_date: date | None = None
    to_date: date | None = None
    office_id: UUID | None = None
    ip: str | None = None
    q: str | None = None
    since_seq: int | None = None

    def digest(self) -> str:
        return query_hash(
            actor_kind=self.actor_kind,
            actor_id=self.actor_id,
            object_type=self.object_type,
            action=self.action,
            from_date=self.from_date,
            to_date=self.to_date,
            office_id=self.office_id,
            ip=self.ip,
            q=self.q,
            since_seq=self.since_seq,
        )


@dataclass(frozen=True)
class Reader:
    ctx: AuthContext
    firm: bool  # reads firm-level events (DEC-434)
    walled: frozenset[UUID]
    request_context: bool  # DEC-420


async def reader_of(ctx: AuthContext) -> Reader:
    # L5: a probe, not a check: an ordinary read logs no `authz.denied` for the rows it narrows.
    allowed = await allowed_actions(
        ctx, Resource.firm(ctx.tenant_id), (READ_FIRM_LEVEL, READ_REQUEST_CONTEXT)
    )
    return Reader(
        ctx,
        firm=READ_FIRM_LEVEL in allowed,
        walled=await walled_from(ctx.tenant, ctx.user_id),
        request_context=READ_REQUEST_CONTEXT in allowed,
    )


# Reference keys a firm-level event may carry to a walled reader: people and firm structure.
# Any other identifier in its references (a client, contact, entity, engagement, work item or
# record of one) can name a walled client's work, so a walled reader does not see the event
# (fail closed; security review M1). `client_id` is checked exactly instead.
FIRM_SAFE_REFS: Final = frozenset(
    {"user_id", "staff_id", "approver_user_id", "on_behalf_of", "initiator", "uploaded_by"}
    | {"security_admin", "office", "office_id", "team_id", "methodology_version_id"}
    | {"supersedes_id"}
)
# Firm-level kinds whose target is itself client- or contact-side (a person's engagement draft
# before any engagement exists; a portal email's link to one contact). The explorer cannot place
# them, so a walled reader sees none (security review, re-review 2).
CLIENT_SIDE_TARGETS: Final = frozenset({"engagement_draft", "secure_link"})
_NO_REFS: Final = literal({}, JSONB)


def _names_walled_work(walled: frozenset[UUID]) -> ColumnElement[bool]:
    """A firm-level event whose references name a walled client, or name any client-side
    identifier the explorer cannot place (security review M1)."""

    def unplaced(refs: ColumnElement[Any]) -> ColumnElement[bool]:  # Any: jsonb
        # Each side on its own: `before || after` would let an after key hide a before id.
        pairs = func.jsonb_each_text(func.coalesce(refs, _NO_REFS)).table_valued("key", "value")
        pairs = pairs.render_derived()
        return exists(
            select(literal(1))
            .select_from(pairs)
            .where(
                pairs.c.value.op("~")(_UUID),
                pairs.c.key.not_in(sorted(FIRM_SAFE_REFS | {"client_id"})),
            )
        )

    clients = sorted(str(c) for c in walled)
    # Coalesced: a missing key is NULL, and NOT (NULL OR false) would hide the event too.
    named = func.coalesce(t.before_ref["client_id"].astext, "").in_(clients)
    return or_(
        named,
        func.coalesce(t.after_ref["client_id"].astext, "").in_(clients),
        unplaced(t.before_ref),
        unplaced(t.after_ref),
    )


def shown_to(reader: Reader) -> ColumnElement[bool]:
    """The events `reader` may see (the module docstring's rules)."""
    clauses: list[ColumnElement[bool]] = [
        and_(ENGAGEMENT.is_not(None), visible(reader.ctx, READ, ENGAGEMENT))
    ]
    if reader.firm:
        firm_level: ColumnElement[bool] = ENGAGEMENT.is_(None)
        if reader.walled:
            firm_level = and_(
                firm_level,
                t.target_type.in_(sorted(FIRM_LEVEL - CLIENT_SIDE_TARGETS)),
                ~_names_walled_work(reader.walled),
            )
        clauses.append(firm_level)
    shown = or_(*clauses)
    if reader.walled:
        shown = and_(shown, or_(t.client_id.is_(None), t.client_id.not_in(sorted(reader.walled))))
    return shown


def _person_filter(actor_id: UUID) -> ColumnElement[bool]:
    return or_(t.actor_id == str(actor_id), t.on_behalf_of_user_id == actor_id)


async def _bounds(ctx: AuthContext, where: EventFilter) -> tuple[datetime | None, datetime | None]:
    """`from` and `to` as instants: whole days in the firm's time zone, `to` inclusive."""
    if where.from_date is None and where.to_date is None:
        return None, None
    zone = ZoneInfo(await firm_time_zone(ctx.tenant))
    start = datetime.combine(where.from_date, time(), zone) if where.from_date else None
    end = (
        datetime.combine(where.to_date + timedelta(days=1), time(), zone)
        if where.to_date
        else None
    )
    return start, end


async def _conditions(
    reader: Reader, where: EventFilter, *, with_actor_kind: bool
) -> list[ColumnElement[bool]]:
    found: list[ColumnElement[bool]] = [shown_to(reader)]
    if with_actor_kind and where.actor_kind is not None:
        found.append(GRAMMAR.in_([where.actor_kind]))
    if where.actor_id is not None:
        found.append(_person_filter(where.actor_id))
    if where.object_type is not None:
        found.append(t.target_type == where.object_type)
    if where.action is not None:
        found.append(t.action == where.action)
    start, end = await _bounds(reader.ctx, where)
    if start is not None:
        found.append(t.effective_at >= start)
    if end is not None:
        found.append(t.effective_at < end)
    if where.office_id is not None:
        found.append(t.office_id == where.office_id)
    if where.ip is not None:
        # DEC-420: only a request-context reader may filter on what only they can see.
        found.append(
            t.ip == sql_cast(literal(where.ip), INET) if reader.request_context else false()
        )
    if where.since_seq is not None:
        found.append(t.seq > where.since_seq)
    return found


_COLUMNS: Final = (
    t.id,
    t.tenant_id,
    t.seq,
    t.occurred_at,
    t.effective_at,
    t.actor_kind,
    t.actor_id,
    t.action,
    t.target_type,
    t.target_id,
    t.before_ref,
    t.after_ref,
    t.trace_id,
    t.engagement_id,
    t.work_item_id,
    t.on_behalf_of_user_id,
    t.policy_ref,
    func.host(t.ip).label("ip"),
    t.user_agent_family,
    t.device_label,
    t.session_id,
    t.auth_method,
    t.mfa_at,
    t.client_id,
    t.office_id,
    ENGAGEMENT.label("engagement_of"),
)


def _select(conditions: Sequence[ColumnElement[bool]]) -> Select[*tuple[Any, ...]]:  # a wide row
    return select(*_COLUMNS).where(and_(true(), *conditions))


Row = Mapping[str, Any]  # Any: an untyped database row


def _uuid(value: object) -> UUID | None:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _refs(value: object) -> dict[str, str | int]:
    if isinstance(value, dict):
        return cast(dict[str, str | int], value)
    return {}


def _facts(row: Row) -> dict[str, Fact]:
    """Identifier facts only (M4): ids and counts from the references, never a fingerprint;
    the catalogue's fact names narrow them when it lists any."""
    named = activity_of(str(row["action"])).facts
    facts: dict[str, Fact] = {}
    for prefix, refs in (("before_", _refs(row["before_ref"])), ("", _refs(row["after_ref"]))):
        for key, value in refs.items():
            if isinstance(value, str) and _FINGERPRINT.fullmatch(value):
                continue
            name = f"{prefix}{key}"
            if named and key not in named:
                continue
            facts[name] = value
    return facts


def _people(rows: Sequence[Row]) -> set[UUID]:
    found: set[UUID] = set()
    for row in rows:
        if row["actor_kind"] in ("human", "support") and (u := _uuid(row["actor_id"])):
            found.add(u)
        if row["on_behalf_of_user_id"] is not None:
            found.add(cast(UUID, row["on_behalf_of_user_id"]))
        for key, value in {**_refs(row["before_ref"]), **_refs(row["after_ref"])}.items():
            if _PERSON_REF.search(key) and (u := _uuid(value)):
                found.add(u)
    return found


def _person(user: UUID | None, names: Mapping[UUID, str]) -> AuditPersonOut | None:
    if user is None:
        return None
    return AuditPersonOut(user_id=user, display_name=names.get(user, ""))


def _agent_id(actor_id: str) -> str:
    """`agent:workbench.reporter:run` -> `workbench.reporter`: the agent by id, never a name."""
    parts = actor_id.split(":")
    return parts[1] if len(parts) >= 2 and parts[0] == "agent" else actor_id


def _actor(row: Row, names: Mapping[UUID, str]) -> AuditActorOut:
    kind = str(row["actor_kind"])
    on_behalf = cast(UUID | None, row["on_behalf_of_user_id"])
    if kind == "human":
        return AuditActorOut(kind="person", person=_person(_uuid(row["actor_id"]), names))
    if kind == "support":
        return AuditActorOut(kind="support", person=_person(_uuid(row["actor_id"]), names))
    if kind == "agent" and on_behalf is not None:
        return AuditActorOut(
            kind="via_agent",
            on_behalf_of=_person(on_behalf, names),
            agent_id=_agent_id(str(row["actor_id"])),
        )
    if kind == "policy":
        return AuditActorOut(kind="policy", policy_ref=cast(str | None, row["policy_ref"]))
    return AuditActorOut(kind="system")


def _mark(actor: AuditActorOut, mark: Mark) -> Mark:
    """AC-3 (INV-1): an approval's `ok` names a person or a policy, never the agent or system."""
    return mark if mark != "ok" or actor.kind in ("person", "policy") else "pl"


def _run_id(row: Row) -> UUID | None:
    refs = _refs(row["after_ref"])
    return _uuid(refs.get("run_id") or refs.get("agent_run_id") or "") if refs else None


@dataclass(frozen=True)
class _Labels:
    names: Mapping[UUID, str]
    targets: Mapping[tuple[str, str], str]


async def _labels(ctx: AuthContext, rows: Sequence[Row]) -> _Labels:
    names = await names_of(sorted(_people(rows), key=str)) if rows else {}
    by_type: dict[str, set[str]] = {}
    for row in rows:
        by_type.setdefault(str(row["target_type"]), set()).add(str(row["target_id"]))
    targets: dict[tuple[str, str], str] = {}
    for kind, ids in by_type.items():
        for target, label in (await audit_labels(ctx, kind, sorted(ids))).items():
            targets[(kind, target)] = label.text
    return _Labels(names, targets)


def row_of(row: Row, reader: Reader, found: _Labels) -> AuditEventRow:
    """One row as `reader` may see it."""
    actor = _actor(row, found.names)
    activity = activity_of(str(row["action"]))
    facts = _facts(row)
    fact_labels = {
        str(value): found.names[u]
        for value in facts.values()
        if isinstance(value, str) and (u := _uuid(value)) is not None and u in found.names
    }
    run_id = _run_id(row)
    return AuditEventRow(
        seq=int(row["seq"]),
        effective_at=cast(datetime, row["effective_at"]),
        action=str(row["action"]),
        category=activity.category,
        mark=_mark(actor, activity.mark),
        actor=actor,
        target=AuditTargetOut(
            type=str(row["target_type"]),
            id=str(row["target_id"]),
            label=found.targets.get((str(row["target_type"]), str(row["target_id"]))),
            engagement_id=cast(UUID | None, row["engagement_of"]),
            client_id=cast(UUID | None, row["client_id"]),
        ),
        detail_facts=facts,
        labels=fact_labels,
        office_id=cast(UUID | None, row["office_id"]),
        ip=cast(str | None, row["ip"]) if reader.request_context else None,
        run_id=run_id,
        link_kind="run" if run_id is not None else "none",
    )


async def list_events(
    ctx: AuthContext, where: EventFilter, cursor: str | None, limit: int
) -> ListPage[AuditEventRow]:
    """AC-1, AC-2, AC-6, AC-7 and the F-04 harness's `since_seq` (oldest first after it). The
    route has checked the principal (L1) and the flag; every event is narrowed here."""
    reader = await reader_of(ctx)
    ascending = where.since_seq is not None
    digest = where.digest()
    after: Position | None = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=RESOURCE, query=digest)
        if cursor
        else None
    )
    conditions = await _conditions(reader, where, with_actor_kind=True)
    others = await _conditions(reader, where, with_actor_kind=False)
    async with tenant_session(ctx.tenant) as session:
        if where.q is not None:
            # L3: the search is a predicate inside this query, so visibility and the page's
            # limit apply together (no cap before visibility).
            await label_index.catch_up(ctx.tenant_id)
            matched = label_index.matching(t.seq, where.q)
            conditions.append(matched)
            others.append(matched)
        stmt = keyset(
            _select(conditions),
            sort=cast(ColumnElement[object], t.seq),
            id_column=cast(ColumnElement[object], t.seq),
            after=after,
            descending=not ascending,
            limit=limit,
        )
        fetched = [dict(m) for m in (await session.execute(stmt)).mappings().all()]
        total = await capped_total(session, _select(conditions))
        counts = await _counts(session, others)
    rows, next_position = page_of(
        fetched, limit=limit, key=lambda r: r["seq"], id_of=lambda r: r["seq"]
    )
    found = await _labels(ctx, rows)
    return envelope(
        [row_of(r, reader, found) for r in rows],
        next_position=next_position,
        tenant_id=ctx.tenant_id,
        resource=RESOURCE,
        query=digest,
        total=total,
        counts=counts,
    )


async def _counts(
    session: AsyncSession, conditions: Sequence[ColumnElement[bool]]
) -> dict[str, int]:
    """`all` and each actor kind over the other filters, capped like `total`."""
    sub = (
        select(GRAMMAR.label("kind"))
        .where(and_(true(), *conditions))
        .limit(TOTAL_CAP + 1)
        .subquery()
    )
    grouped = await session.execute(select(sub.c.kind, func.count()).group_by(sub.c.kind))
    by_kind = {str(kind): int(n) for kind, n in grouped.all()}
    counts = {kind: min(by_kind.get(kind, 0), TOTAL_CAP) for kind in COUNTED}
    counts["all"] = min(sum(by_kind.values()), TOTAL_CAP)
    return counts


_LEAF_ROW: Final = (
    "id",
    "tenant_id",
    "seq",
    "occurred_at",
    "effective_at",
    "actor_kind",
    "actor_id",
    "action",
    "target_type",
    "target_id",
    "before_ref",
    "after_ref",
    "trace_id",
    "engagement_id",
    "work_item_id",
    "on_behalf_of_user_id",
    "policy_ref",
    "ip",
    "user_agent_family",
    "device_label",
    "session_id",
    "auth_method",
    "mfa_at",
    "client_id",
    "office_id",
)


def _event_ref(row: Row) -> AuditEventRef:
    return AuditEventRef(
        seq=int(row["seq"]),
        action=str(row["action"]),
        target_type=str(row["target_type"]),
        target_id=str(row["target_id"]),
        before_ref=_refs(row["before_ref"]) or None,
        after_ref=_refs(row["after_ref"]) or None,
        engagement_id=cast(UUID | None, row["engagement_of"]),
        actor_kind=str(row["actor_kind"]),
        actor_id=str(row["actor_id"]),
        trace_id=cast(str | None, row["trace_id"]),
    )


async def get_event(ctx: AuthContext, seq: int) -> AuditEventDetail:
    """AC-9, AC-10: one event in full; walled or invisible answers 404, as unknown (DEC-43)."""
    reader = await reader_of(ctx)
    async with tenant_session(ctx.tenant) as session:
        found = (
            (await session.execute(_select([shown_to(reader), t.seq == seq]))).mappings().first()
        )
        if found is None:
            raise NotFound("audit_event")
        row = dict(found)
        version = await leaf_version_at(session, seq)
    labels = await _labels(ctx, [row])
    base = row_of(row, reader, labels)
    event = _event_ref(row)
    values = await event_values.values_for(ctx, event)
    source = await audit_source(ctx, event)
    actor = base.actor
    person = actor.person or actor.on_behalf_of
    if person is not None:
        facts = await member_facts(ctx.tenant, person.user_id)
        if facts is not None:
            person = person.model_copy(update={"level": facts.level, "office_id": facts.office_id})
            actor = actor.model_copy(
                update={"person": person} if actor.person else {"on_behalf_of": person}
            )
    shown = reader.request_context
    session_out = (
        AuditSessionOut(
            session_id=cast(UUID | None, row["session_id"]),
            auth_method=row["auth_method"],  # the CHECK's closed list
            mfa_at=cast(datetime | None, row["mfa_at"]),
        )
        if shown and any(row[k] is not None for k in ("session_id", "auth_method", "mfa_at"))
        else None
    )
    return AuditEventDetail(
        **base.model_dump(exclude={"actor"}),
        actor=actor,
        occurred_at=cast(datetime, row["occurred_at"]),
        device_label=cast(str | None, row["device_label"]) if shown else None,
        user_agent_family=cast(str | None, row["user_agent_family"]) if shown else None,
        session=session_out,
        content_hash=leaf({k: row[k] for k in _LEAF_ROW}, version).hex(),
        values=values,
        source=(
            AuditSourceOut(
                run_id=source.run_id,
                agent_id=source.agent_id,
                run_no=source.run_no,
                started_at=source.started_at,
                initiator=_person(source.initiator_user_id, labels.names),
            )
            if source is not None
            else None
        ),
    )


async def events_for_work_item(
    ctx: AuthContext, work_item_id: UUID, *, as_of_seq: int | None = None
) -> list[AuditEventRow]:
    """A-01's binder export: one work item's events, oldest first, as `ctx` may see them
    (bounded at `WORK_ITEM_LIMIT`), up to the export's snapshot `as_of_seq` when given. The caller
    has authorised its read of the work item."""
    reader = await reader_of(ctx)
    conditions = [shown_to(reader), t.work_item_id == work_item_id]
    if as_of_seq is not None:
        conditions.append(t.seq <= as_of_seq)
    async with tenant_session(ctx.tenant) as session:
        stmt = _select(conditions).order_by(t.seq).limit(WORK_ITEM_LIMIT)
        rows = [dict(m) for m in (await session.execute(stmt)).mappings().all()]
    found = await _labels(ctx, rows)
    return [row_of(r, reader, found) for r in rows]


__all__ = [
    "READ_FIRM_LEVEL",
    "READ_REQUEST_CONTEXT",
    "EventFilter",
    "Reader",
    "events_for_work_item",
    "get_event",
    "list_events",
    "reader_of",
    "row_of",
    "shown_to",
]

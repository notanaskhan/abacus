"""CLI-06's single intake, live (P-07-T42; P-07 §3.3 Story 3.1, §4.2 M8; DEC-374, DEC-430).

- **Drafts** (`client_intake_drafts`, 0177): the person's own (another person's, or a discarded
  one, answers 404), autosaved with `seen_version` (409 `stale_version`), discarded rather than
  deleted. The payload is the contract's `ClientIntakeDraftPayload` as JSON: identifiers and
  typed values only, no TIN field (DEC-374). The SSN guard (P-07 OQ-4): on a firm that is not
  synthetic, an SSN or ITIN form in any of the draft's text (names, emails) is refused 422
  `tin_kind_not_allowed` before anything is stored; an EIN form is accepted.
- **Validation per step**, as `(field, code)` pairs: the entity's mode and names, registered
  codes for entity types, relationship kinds and contact roles, a known service type and its
  forms, the period, the engagement partner, and `date_of_death_required` when Form 706 is
  among the services (CLI-06 i). The conflicts step reports `gate_unmet` until the draft's own
  conflict check is clear for the person.
- **Commit** (`client.intake`, a live person only, OQ-2): one unit of work writes the client (or
  a new entity under an existing client the person may see; DEC-62), the entity's type and date
  of death, the relationship edges, the contacts with their roles on the entity, one **Prospect**
  engagement per engagement type and period with the engagement partner on its team and its work
  items by service (a service names the forms it creates; Form 56 is a line item only), and with
  `start_acceptance` an acceptance record per engagement. It needs the draft's own conflict
  check, which searched the names the draft holds now (the server builds them from the draft,
  `subject_names`; security review H1) and is clear for the committing person, re-read inside
  the unit of work (409 `gate_unmet`); an autosave since the commit read the draft is 409
  `stale_version`. It refuses a new client whose
  normalised name is a client the person may see (409 `possible_duplicate`). One
  `client_intake.committed` event; `engagement.created` outbox events. The draft keeps what the
  commit answered, so a committed draft answers the same again (the route also replays by
  `Idempotency-Key`); a failure anywhere leaves nothing behind.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import Column, FetchedValue, MetaData, RowMapping, Table, func, insert, select
from sqlalchemy import update as sql_update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import DateTime, Integer, Text

from abacus.kernel import clock
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.tin_patterns import find_tins
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements import acceptance as acceptance_model
from abacus.modules.engagements.drafts import work_items_for
from abacus.modules.engagements.events import EngagementCreated
from abacus.modules.engagements.models import Engagement
from abacus.modules.engagements.record import GateUnmet
from abacus.modules.engagements.repository import insert_engagement
from abacus.modules.engagements.service import PossibleDuplicate
from abacus.modules.engagements.type_catalogue import CatalogueEntry, entry_of
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    add_rolled_forward_member,
    allowed_actions,
    authorise,
    hidden_clients,
    is_synthetic_firm,
    member_facts,
)
from abacus.modules.organisations.api import (
    CONTACT_ROLES,
    ENTITY_TYPES,
    RELATIONSHIP_KINDS,
    ClientRecordChange,
    EntityAttributes,
    SubjectNames,
    TinKindNotAllowed,
    add_intake_contact,
    add_intake_relationship,
    check_clear_for,
    client_with_entity,
    create_client,
    same_name_client,
    set_client_record,
    set_entity_attributes,
)

INTAKE: Final = "client.intake"
CLEAR_CONFLICT: Final = "conflict.clear"
SUBJECT: Final = "client_intake_draft"  # the conflict check's subject kind (DEC-373)
Step = Literal["entity", "relationships", "contacts", "services", "conflicts", "review"]
STEPS: Final[tuple[Step, ...]] = (
    "entity",
    "relationships",
    "contacts",
    "services",
    "conflicts",
    "review",
)
# Steps whose problems the commit refuses as 422 `draft_incomplete`; the conflicts step is the
# commit's 409 `gate_unmet` instead (the contract's order).
_COMMIT_STEPS: Final[tuple[Step, ...]] = ("entity", "relationships", "contacts", "services")
# A service the intake records as a line item that creates no engagement or work item in v1
# (P-07 §2 CLI-06: Form 56, the fiduciary's notice).
LINE_ITEM_ONLY: Final = frozenset({"form_56"})
DEATH_FORM: Final = "706"  # Form 706 needs the date of death (CLI-06 i)
_GATED_TINS: Final = frozenset({"ssn", "itin"})  # P-07 OQ-4, as `seal_tin`'s rule
_NAME_MAX: Final = 190
# ED-116 (DEC-461): the keys a second commit of the same draft meets when the first committed
# while it ran (the entity's name or TIN, a contact's email on the client).
_RACED: Final = frozenset(
    {"client_entities_one_name", "client_entities_one_tin", "contacts_one_email"}
)

_meta = MetaData()
drafts = Table(
    "client_intake_drafts",
    _meta,
    Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=FetchedValue()),
    Column("tenant_id", PgUUID(as_uuid=True)),
    Column("created_by", PgUUID(as_uuid=True)),
    Column("step", Text),
    Column("payload", JSONB),
    Column("version", Integer),
    Column("saved_at", DateTime(timezone=True)),
    Column("discarded_at", DateTime(timezone=True)),
    Column("committed_at", DateTime(timezone=True)),
    Column("committed_client_id", PgUUID(as_uuid=True)),
    Column("result", JSONB),
)


class IntakeStaleVersion(DomainConflict):
    code = "stale_version"


class IntakeIncomplete(DomainInvalid):
    """A step of the draft still has a problem (`facts.step`): validate it to see which."""

    code = "draft_incomplete"


@dataclass(frozen=True)
class IntakeDraftView:
    id: UUID
    created_by: UUID
    step: str
    payload: dict[str, object]
    committed_client_id: UUID | None
    version: int
    saved_at: datetime


@dataclass(frozen=True)
class Problem:
    field: str
    code: str


@dataclass(frozen=True)
class Committed:
    draft_id: UUID
    client_id: UUID
    client_entity_id: UUID
    engagement_ids: list[UUID]
    engagement_status: str
    work_item_ids: list[UUID]
    conflict_check_id: UUID | None
    acceptance_record_id: UUID | None

    def stored(self) -> dict[str, object]:
        """Identifiers only, as the draft keeps them."""
        return {
            "draft_id": str(self.draft_id),
            "client_id": str(self.client_id),
            "client_entity_id": str(self.client_entity_id),
            "engagement_ids": [str(e) for e in self.engagement_ids],
            "engagement_status": self.engagement_status,
            "work_item_ids": [str(w) for w in self.work_item_ids],
            "conflict_check_id": _str(self.conflict_check_id),
            "acceptance_record_id": _str(self.acceptance_record_id),
        }

    @classmethod
    def from_stored(cls, raw: dict[str, object]) -> Committed:
        return cls(
            UUID(cast(str, raw["draft_id"])),
            UUID(cast(str, raw["client_id"])),
            UUID(cast(str, raw["client_entity_id"])),
            [UUID(e) for e in cast(list[str], raw["engagement_ids"])],
            cast(str, raw["engagement_status"]),
            [UUID(w) for w in cast(list[str], raw["work_item_ids"])],
            _uuid(raw.get("conflict_check_id")),
            _uuid(raw.get("acceptance_record_id")),
        )


def _str(value: UUID | None) -> str | None:
    return None if value is None else str(value)


def _uuid(value: object) -> UUID | None:
    return UUID(value) if isinstance(value, str) and value else None


def _date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value) if isinstance(value, str) and value else None


# --- payload accessors (the contract validated its shape) ---------------------------------------


def _entity(p: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], p.get("entity") or {})


def _list(p: dict[str, object], key: str) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], p.get(key) or [])


def _texts(p: dict[str, object]) -> list[tuple[str, str]]:
    """Every free-text value of the payload, by field."""
    out: list[tuple[str, str]] = []
    entity = _entity(p)
    for key in ("client_display_name", "entity_name"):
        value = entity.get(key)
        if isinstance(value, str):
            out.append((f"entity.{key}", value))
    for i, contact in enumerate(_list(p, "contacts")):
        for key in ("display_name", "email"):
            value = contact.get(key)
            if isinstance(value, str):
                out.append((f"contacts.{i}.{key}", value))
    return out


def _services(p: dict[str, object]) -> list[tuple[dict[str, object], CatalogueEntry | None]]:
    return [(s, entry_of(cast(str | None, s.get("type_code")))) for s in _list(p, "services")]


def _forms(service: dict[str, object], entry: CatalogueEntry) -> tuple[str, ...]:
    asked = cast(list[str] | None, service.get("forms"))
    return entry.forms if not asked else tuple(dict.fromkeys(asked))


def _creates_engagement(service: dict[str, object]) -> bool:
    return service.get("type_code") not in LINE_ITEM_ONLY


# --- guards -------------------------------------------------------------------------------------


def _live_human(ctx: AuthContext) -> None:
    """OQ-2, INV-1: a person's own act, never an agent, the platform, a client or support."""
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(INTAKE, "role")


async def _tin_guard(ctx: AuthContext, payload: dict[str, object]) -> None:
    """P-07 OQ-4 on the draft's text: no SSN or ITIN on a real firm (the digits never echo)."""
    gated = [
        name
        for name, value in _texts(payload)
        if any(m.type in _GATED_TINS for m in find_tins(value))
    ]
    if gated and not await is_synthetic_firm(ctx.tenant):
        raise TinKindNotAllowed(facts={"field": gated[0]})


async def _walled_client(
    ctx: AuthContext, payload: dict[str, object], committed: UUID | None = None
) -> None:
    """An existing client the person is walled from reads as unknown (DEC-43); once committed,
    the client the draft created or added to (security review L3: a replay re-applies walls)."""
    client = committed or _uuid(_entity(payload).get("client_id"))
    if client is not None and await hidden_clients(ctx.tenant, ctx.user_id, [client]):
        raise NotFound("client")


async def _gate(ctx: AuthContext) -> None:
    _live_human(ctx)
    await authorise(ctx, INTAKE, Resource.firm(ctx.tenant_id))


# --- drafts -------------------------------------------------------------------------------------


def _view(r: RowMapping) -> IntakeDraftView:
    return IntakeDraftView(
        id=cast(UUID, r["id"]),
        created_by=cast(UUID, r["created_by"]),
        step=cast(str, r["step"]),
        payload=cast(dict[str, object], r["payload"] or {}),
        committed_client_id=cast(UUID | None, r["committed_client_id"]),
        version=cast(int, r["version"]),
        saved_at=cast(datetime, r["saved_at"]),
    )


async def _own_row(session: AsyncSession, ctx: AuthContext, draft_id: UUID) -> RowMapping:
    row = (
        (
            await session.execute(
                select(drafts).where(
                    drafts.c.id == draft_id,
                    drafts.c.created_by == ctx.user_id,
                    drafts.c.discarded_at.is_(None),
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise NotFound("client_intake_draft")
    return row


async def create_draft(ctx: AuthContext, step: str, payload: dict[str, object]) -> IntakeDraftView:
    await _gate(ctx)
    await _tin_guard(ctx, payload)
    await _walled_client(ctx, payload)
    async with uow(ctx.tenant) as tx:
        row = (
            (
                await tx.session.execute(
                    insert(drafts)
                    .values(
                        tenant_id=ctx.tenant_id, created_by=ctx.user_id, step=step, payload=payload
                    )
                    .returning(drafts)
                )
            )
            .mappings()
            .one()
        )
        tx.record("client_intake.started", target=Target(SUBJECT, cast(UUID, row["id"])))
    return _view(row)


async def get_draft(ctx: AuthContext, draft_id: UUID) -> IntakeDraftView:
    """The owner's draft; 404 once a wall stands between them and its client (DEC-227)."""
    await _gate(ctx)
    async with tenant_session(ctx.tenant) as session:
        found = _view(await _own_row(session, ctx, draft_id))
    await _walled_client(ctx, found.payload, found.committed_client_id)
    return found


async def draft_visible(ctx: AuthContext, draft_id: UUID) -> bool:
    """For organisations' conflict checks (DEC-375, L4; DEC-430): the caller's own live draft,
    or, for a person who may clear conflict hits (a partner or manager), any live draft of the
    firm, so a hit on the firm admin's intake can be cleared (CLI-06 h); never one whose client
    is walled off from them."""
    try:
        await get_draft(ctx, draft_id)
    except (NotFound, Forbidden):
        pass
    else:
        return True
    may = await allowed_actions(ctx, Resource.firm(ctx.tenant_id), [CLEAR_CONFLICT])
    if CLEAR_CONFLICT not in may:
        return False
    async with tenant_session(ctx.tenant) as session:
        row = (
            (
                await session.execute(
                    select(drafts.c.payload, drafts.c.committed_client_id).where(
                        drafts.c.id == draft_id, drafts.c.discarded_at.is_(None)
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        return False
    try:
        await _walled_client(
            ctx,
            cast(dict[str, object], row["payload"] or {}),
            cast(UUID | None, row["committed_client_id"]),
        )
    except NotFound:
        return False
    return True


async def update_draft(
    ctx: AuthContext,
    draft_id: UUID,
    seen_version: int,
    *,
    step: str | None,
    payload: dict[str, object] | None,
) -> IntakeDraftView:
    """Autosave (operational state: its audit event names the version only)."""
    await _gate(ctx)
    if payload is not None:
        await _tin_guard(ctx, payload)
        await _walled_client(ctx, payload)
    values: dict[str, object] = {
        k: v for k, v in (("step", step), ("payload", payload)) if v is not None
    }
    async with uow(ctx.tenant) as tx:
        await _own_row(tx.session, ctx, draft_id)
        row = (
            (
                await tx.session.execute(
                    sql_update(drafts)
                    .where(
                        drafts.c.id == draft_id,
                        drafts.c.version == seen_version,
                        drafts.c.discarded_at.is_(None),
                        drafts.c.committed_at.is_(None),
                    )
                    .values(
                        **values, version=drafts.c.version + 1, saved_at=func.clock_timestamp()
                    )
                    .returning(drafts)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise IntakeStaleVersion(facts={"draft_id": str(draft_id)})
        tx.record(
            "client_intake.saved",
            target=Target(SUBJECT, draft_id),
            after=Ref(version=cast(int, row["version"])),
        )
    return _view(row)


async def discard_draft(ctx: AuthContext, draft_id: UUID) -> datetime:
    await _gate(ctx)
    async with uow(ctx.tenant) as tx:
        await _own_row(tx.session, ctx, draft_id)
        at = (
            await tx.session.execute(
                sql_update(drafts)
                .where(drafts.c.id == draft_id, drafts.c.committed_at.is_(None))
                .values(discarded_at=func.clock_timestamp())
                .returning(drafts.c.discarded_at)
            )
        ).scalar_one_or_none()
        if at is None:  # committed already: nothing to discard
            raise NotFound("client_intake_draft")
        tx.record("client_intake.discarded", target=Target(SUBJECT, draft_id))
    return cast(datetime, at)


# --- validation ---------------------------------------------------------------------------------


def problems_of(p: dict[str, object], step: str) -> list[Problem]:
    """What a step still lacks, as registered codes (never prose). The conflicts step's gate is
    `conflict_problems` (it reads the check)."""
    out: list[Problem] = []
    entity = _entity(p)
    if step == "entity":
        mode = entity.get("mode")
        if mode is None:
            out.append(Problem("entity.mode", "required"))
        elif mode == "existing_client":
            for key in ("client_id", "entity_name"):
                if not entity.get(key):
                    out.append(Problem(f"entity.{key}", "required"))
        elif not entity.get("client_display_name"):
            out.append(Problem("entity.client_display_name", "required"))
        kind = entity.get("entity_type")
        if kind is None:
            out.append(Problem("entity.entity_type", "required"))
        elif kind not in ENTITY_TYPES:
            out.append(Problem("entity.entity_type", "unknown_code"))
    if step == "relationships":
        for i, rel in enumerate(_list(p, "relationships")):
            if rel.get("kind") not in RELATIONSHIP_KINDS:
                out.append(Problem(f"relationships.{i}.kind", "unknown_code"))
    if step == "contacts":
        for i, contact in enumerate(_list(p, "contacts")):
            roles = cast(list[str], contact.get("roles") or [])
            if any(r not in CONTACT_ROLES for r in roles):
                out.append(Problem(f"contacts.{i}.roles", "unknown_code"))
    if step == "services":
        out.extend(_service_problems(p, entity))
    return out


def _service_problems(p: dict[str, object], entity: dict[str, object]) -> list[Problem]:
    out: list[Problem] = []
    services = _services(p)
    if not services:
        return [Problem("services", "required")]
    death_form = False
    for i, (service, entry) in enumerate(services):
        if not _creates_engagement(service):
            continue
        if entry is None:
            out.append(Problem(f"services.{i}.type_code", "unknown_engagement_type"))
            continue
        forms = _forms(service, entry)
        if any(f not in entry.forms for f in forms):
            out.append(Problem(f"services.{i}.forms", "unknown_code"))
        death_form = death_form or DEATH_FORM in forms
        start = _date(service.get("fiscal_period_start"))
        end = _date(service.get("fiscal_period_end"))
        for key, value in (("fiscal_period_start", start), ("fiscal_period_end", end)):
            if value is None:
                out.append(Problem(f"services.{i}.{key}", "required"))
        if start and end and end < start:
            out.append(Problem(f"services.{i}.fiscal_period_end", "before_start"))
    if any(_creates_engagement(s) for s, _ in services) and not p.get(
        "engagement_partner_user_id"
    ):
        out.append(Problem("engagement_partner_user_id", "required"))
    if death_form and not entity.get("date_of_death"):
        out.append(Problem("entity.date_of_death", "date_of_death_required"))
    return out


def names_of(p: dict[str, object]) -> SubjectNames:
    """What the draft's conflict check searches (security review H1, DEC-430): the client's name
    (typed, or the existing client's), the entity's, each contact's, and each related entity's."""
    entity = _entity(p)
    typed = [
        v
        for v in (entity.get("client_display_name"), entity.get("entity_name"))
        if isinstance(v, str) and v
    ]
    typed += [
        cast(str, c["display_name"])
        for c in _list(p, "contacts")
        if isinstance(c.get("display_name"), str)
    ]
    client = _uuid(entity.get("client_id")) if entity.get("mode") == "existing_client" else None
    related = [_uuid(x.get("related_entity_id")) for x in _list(p, "relationships")]
    return SubjectNames(
        names=tuple(typed),
        client_ids=() if client is None else (client,),
        entity_ids=tuple(r for r in related if r is not None),
    )


async def subject_names(ctx: AuthContext, draft_id: UUID) -> SubjectNames | None:
    """Organisations' names provider for a `client_intake_draft` subject: a live, uncommitted
    draft (the caller's visibility was checked first, `draft_visible`)."""
    async with tenant_session(ctx.tenant) as session:
        payload = (
            await session.execute(
                select(drafts.c.payload).where(
                    drafts.c.id == draft_id,
                    drafts.c.discarded_at.is_(None),
                    drafts.c.committed_at.is_(None),
                )
            )
        ).scalar_one_or_none()
    return None if payload is None else names_of(cast(dict[str, object], payload))


async def conflict_problems(
    ctx: AuthContext, draft_id: UUID, p: dict[str, object], session: AsyncSession | None = None
) -> bool:
    """True when the draft's own conflict check searched the names the draft holds now and is
    clear for this person; in `session` when given (the commit's unit of work)."""
    check = _uuid(p.get("conflict_check_id"))
    if check is None:
        return False
    if session is not None:
        return await check_clear_for(
            session, ctx, check, subject_kind=SUBJECT, subject_id=draft_id, expected=names_of(p)
        )
    async with tenant_session(ctx.tenant) as own:
        return await check_clear_for(
            own, ctx, check, subject_kind=SUBJECT, subject_id=draft_id, expected=names_of(p)
        )


async def validate_draft(ctx: AuthContext, draft_id: UUID, step: str) -> list[Problem]:
    found = await get_draft(ctx, draft_id)
    problems = problems_of(found.payload, step)
    if step == "conflicts" and not await conflict_problems(ctx, draft_id, found.payload):
        problems.append(Problem("conflict_check_id", "gate_unmet"))
    return problems


# --- commit -------------------------------------------------------------------------------------


async def check_commit(ctx: AuthContext, draft_id: UUID) -> None:
    """The route's check before its `Idempotency-Key` lookup, so a replay is authorised too:
    a live person with the action, and the draft is their own."""
    await _gate(ctx)
    async with tenant_session(ctx.tenant) as session:
        row = await _own_row(session, ctx, draft_id)
    await _walled_client(
        ctx,
        cast(dict[str, object], row["payload"] or {}),
        cast(UUID | None, row["committed_client_id"]),
    )


async def _stored(ctx: AuthContext, draft_id: UUID) -> Committed | None:
    async with tenant_session(ctx.tenant) as session:
        row = await _own_row(session, ctx, draft_id)
    raw = cast(dict[str, object] | None, row["result"])
    return None if raw is None else Committed.from_stored(raw)


async def _entitled(ctx: AuthContext, entry: CatalogueEntry) -> bool:
    if entry.entitlement is None:
        return True
    from abacus.modules.platform.api import entitlement  # platform's routes import identity

    return await entitlement(ctx.tenant, entry.entitlement) is not None


async def _partner(ctx: AuthContext, p: dict[str, object]) -> UUID | None:
    """DEC-375 (M3): the engagement partner is a partner-level staff member of the firm."""
    user = _uuid(p.get("engagement_partner_user_id"))
    if user is None:
        return None
    facts = await member_facts(ctx.tenant, user)
    if facts is None or facts.client or facts.level != "partner":
        raise DomainInvalid(facts={"field": "engagement_partner_user_id"})
    return user


GroupKey = tuple[str, str, date, date]  # engagement type, family, period start and end


def _groups(p: dict[str, object]) -> dict[GroupKey, list[tuple[CatalogueEntry, tuple[str, ...]]]]:
    """One Prospect engagement per engagement type and period, holding its services' forms."""
    groups: dict[GroupKey, list[tuple[CatalogueEntry, tuple[str, ...]]]] = {}
    for service, entry in _services(p):
        if not _creates_engagement(service) or entry is None:
            continue
        start = cast(date, _date(service.get("fiscal_period_start")))
        end = cast(date, _date(service.get("fiscal_period_end")))
        key = (entry.engagement_type, entry.family, start, end)
        groups.setdefault(key, []).append((entry, _forms(service, entry)))
    return groups


def _constraint(exc: DBAPIError) -> str | None:
    orig = getattr(exc, "orig", None)
    return getattr(orig, "constraint_name", None) or getattr(
        getattr(orig, "__cause__", None), "constraint_name", None
    )


async def commit_intake(ctx: AuthContext, draft_id: UUID, start_acceptance: bool) -> Committed:
    """One unit of work for the whole estate. A commit that loses a race with another commit of
    the same draft (ED-116) answers what the winner stored, as a later commit would, or 409
    `stale_version` when the draft was not committed; its unit of work rolled back (DEC-461)."""
    try:
        return await _commit(ctx, draft_id, start_acceptance)
    except IntegrityError as exc:
        if _constraint(exc) not in _RACED:
            raise
    done = await _stored(ctx, draft_id)
    if done is not None:
        return done
    raise IntakeStaleVersion(facts={"draft_id": str(draft_id)})


async def _commit(ctx: AuthContext, draft_id: UUID, start_acceptance: bool) -> Committed:
    await _gate(ctx)
    async with tenant_session(ctx.tenant) as session:
        found = _view(await _own_row(session, ctx, draft_id))
    done = await _stored(ctx, draft_id)
    if done is not None:
        return done  # a committed draft answers what it answered (idempotent)
    p = found.payload
    await _tin_guard(ctx, p)
    for step in _COMMIT_STEPS:
        if problems_of(p, step):
            raise IntakeIncomplete(facts={"step": step, "draft_id": str(draft_id)})
    entity = _entity(p)
    existing = _uuid(entity.get("client_id")) if entity.get("mode") == "existing_client" else None
    if existing is not None:
        await _walled_client(ctx, p)
        try:
            await authorise(ctx, INTAKE, Resource.client(ctx.tenant_id, existing))
        except Forbidden as denied:
            if denied.layer == "wall":
                raise NotFound("client") from None
            raise
    else:
        twin = await same_name_client(ctx, cast(str, entity["client_display_name"]))
        if twin is not None:
            raise PossibleDuplicate(facts={"client_id": str(twin)})
    if not await conflict_problems(ctx, draft_id, p):
        raise GateUnmet(facts={"gate": "conflict_check", "draft_id": str(draft_id)})
    groups = _groups(p)
    for entries in groups.values():
        for entry, _ in entries:
            if not await _entitled(ctx, entry):
                raise IntakeIncomplete(facts={"step": "services", "draft_id": str(draft_id)})
    partner = await _partner(ctx, p)
    check_id = _uuid(p.get("conflict_check_id"))
    kind: acceptance_model.Kind = (
        "new_engagement_existing_client" if existing is not None else "new_client"
    )
    today = await clock.today(ctx.tenant)  # a relationship's start without a date of death
    async with uow(ctx.tenant) as tx:
        # H1, L2: the check is re-read in this unit of work against the names the draft holds.
        if not await conflict_problems(ctx, draft_id, p, tx.session):
            raise GateUnmet(facts={"gate": "conflict_check", "draft_id": str(draft_id)})
        if existing is not None:
            made = await client_with_entity(
                tx, ctx.tenant_id, existing, None, cast(str, entity["entity_name"])
            )
        else:
            display = cast(str, entity["client_display_name"])
            made = await create_client(
                tx, ctx.tenant_id, display, cast(str | None, entity.get("entity_name")) or display
            )
            await set_client_record(tx, made.client_id, ClientRecordChange(status="prospect"))
        client_id, entity_id = made.client_id, made.client_entity_id
        await set_entity_attributes(
            tx,
            entity_id,
            EntityAttributes(
                entity_type=cast(str, entity["entity_type"]),  # pyright: ignore[reportArgumentType] -- a code validated against ENTITY_TYPES
                date_of_death=_date(entity.get("date_of_death")),
            ),
        )
        for rel in _list(p, "relationships"):
            await add_intake_relationship(
                tx,
                ctx,
                client_id=client_id,
                from_entity_id=entity_id,
                to_entity_id=UUID(cast(str, rel["related_entity_id"])),
                kind=cast(str, rel["kind"]),
                effective_from=_date(entity.get("date_of_death")) or today,
            )
        for contact in _list(p, "contacts"):
            await add_intake_contact(
                tx,
                ctx,
                client_id=client_id,
                entity_id=entity_id,
                name=cast(str, contact["display_name"]),
                email=cast(str | None, contact.get("email")),
                roles=cast(list[str], contact.get("roles") or []),
            )
        name = cast(str, entity.get("entity_name") or entity.get("client_display_name"))
        engagement_ids: list[UUID] = []
        work: list[UUID] = []
        record_id: UUID | None = None
        for (engagement_type, family, start, end), entries in groups.items():
            engagement_id = uuid4()
            await insert_engagement(
                tx.session,
                engagement_id=engagement_id,
                tenant_id=ctx.tenant_id,
                client_id=client_id,
                client_entity_id=entity_id,
                name=f"{name[:_NAME_MAX]} {end.year}",
                fiscal_period_start=start,
                fiscal_period_end=end,
                created_by=ctx.user_id,
                type=engagement_type,
                prospect=True,
            )
            tx.record(
                "engagement.created",
                target=Target("engagement", engagement_id),
                after=Ref(client_intake_draft_id=draft_id),
            )
            if partner is not None:
                # Inside the creating unit of work, after `client.intake` was authorised: the
                # engagement is new (start_acceptance's way, DEC-372).
                await add_rolled_forward_member(
                    tx, ctx, engagement_id, client_id, partner, "engagement_partner"
                )
            target = await tx.session.get(Engagement, engagement_id)
            if target is None:
                raise NotFound("engagement")
            for entry, forms in entries:
                made_items = await work_items_for(
                    tx, ctx, target, replace(entry, forms=forms), target.name
                )
                work.extend(w for w in made_items if w not in work)
            if start_acceptance:
                opened = await acceptance_model.open_record(
                    tx,
                    ctx,
                    engagement_id=engagement_id,
                    client_id=client_id,
                    family=family,
                    prior_engagement_id=None,
                    kind=kind,
                )
                record_id = record_id or opened
            engagement_ids.append(engagement_id)
            tx.emit(EngagementCreated(engagement_id=engagement_id))
        result = Committed(
            draft_id,
            client_id,
            entity_id,
            engagement_ids,
            "prospect",
            work,
            check_id,
            record_id,
        )
        claimed = (
            await tx.session.execute(
                sql_update(drafts)
                .where(
                    drafts.c.id == draft_id,
                    drafts.c.committed_at.is_(None),
                    drafts.c.discarded_at.is_(None),
                    # The payload committed is the one read and checked (an autosave since: 409).
                    drafts.c.version == found.version,
                )
                .values(
                    committed_at=func.clock_timestamp(),
                    committed_client_id=client_id,
                    result=result.stored(),
                    # L5: the client tables hold the data now; the draft keeps identifiers only.
                    payload={},
                    saved_at=func.clock_timestamp(),
                )
                .returning(drafts.c.id)
            )
        ).scalar_one_or_none()
        if claimed is None:  # a concurrent commit or discard got there first
            raise IntakeStaleVersion(facts={"draft_id": str(draft_id)})
        linked: dict[str, UUID] = {
            k: v
            for k, v in (("conflict_check_id", check_id), ("acceptance_record_id", record_id))
            if v is not None
        }
        tx.record(
            "client_intake.committed",
            target=Target("client", client_id),
            after=Ref(
                client_intake_draft_id=draft_id,
                client_entity_id=entity_id,
                engagements=len(engagement_ids),
                work_items=len(work),
                **linked,
            ),
        )
    return result

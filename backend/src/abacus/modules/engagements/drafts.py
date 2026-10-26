"""ENG-03's wizard backend, live (P-07-T16; SPEC-321 AC-18, AC-19; DEC-225).

- The catalogue (`type_catalogue.py`) with each entry's availability: an entitlement-gated type
  (SOC 1, SOC 2: `attest`) is `needs_entitlement` for a firm without it.
- Drafts: own scope (another person's draft, discarded or not, answers 404), autosaved with
  `seen_version` (409 `stale_version`), discarded rather than deleted. A draft names a catalogue
  code; anything else (single audit included) is 422 `unknown_engagement_type`.
- StepCheck per step: problems as `(field, code)` pairs, plus the draft's gates. G1 is met for a
  draft when the client entity has an engagement of the draft's type and period that a partner
  accepted (the acceptance decision, SPEC-025's record until P-07-T35's): "Granite Peak's draft
  cannot pass step 1 until G1 is met".
- Create: one unit of work completes that accepted engagement from the draft: its period label
  and methodology pin, its work items by the type's cardinality, the team (each new member is
  asked to confirm independence) and `engagement.created`. 409 `possible_duplicate` when another
  open engagement of the same entity, type and period exists, until `confirm_duplicate`; 409
  `gate_unmet` (G1); 422 `draft_incomplete` naming the first step with a problem. A created
  draft answers its first result again (idempotent; the route also honours `Idempotency-Key`).
- "Start acceptance" (P-07-T35, DEC-372): under `client.intake`, a Prospect engagement for the
  draft's client entity, type, name and period with the draft's team, and its acceptance record
  pinned to the firm's questionnaire for the type's family; the draft points at the prospect, so
  its G1 reads that record. A second call answers the same engagement and record.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import (
    Column,
    FetchedValue,
    MetaData,
    RowMapping,
    Table,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import DateTime, Integer, Text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements import acceptance as acceptance_model
from abacus.modules.engagements.acceptance_tables import g1_decision
from abacus.modules.engagements.events import EngagementCreated
from abacus.modules.engagements.gate_policy import required_gates
from abacus.modules.engagements.models import Engagement, WorkItem
from abacus.modules.engagements.record import GateBlocker, GateUnmet, GateView
from abacus.modules.engagements.repository import insert_engagement
from abacus.modules.engagements.service import PossibleDuplicate, lock_ref
from abacus.modules.engagements.slots import NewWorkItem, work_item_provider
from abacus.modules.engagements.type_catalogue import (
    CATALOGUE,
    CatalogueEntry,
    WizardStep,
    entry_of,
    steps_of,
)
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    add_member,
    add_rolled_forward_member,
    authorise,
    engagement_team_query,
    hidden_clients,
)
from abacus.modules.organisations.api import client_of_entity

CREATE: Final = "engagement.create"
_OPEN_FOR_DUPLICATES: Final = ("declined", "archived")
_COMPLETABLE: Final = "accepted"
_STEP_ORDER: Final[tuple[WizardStep, ...]] = (
    "client_type",
    "standards_methodology",
    "period_deadlines",
    "team_independence",
    "binder_portal",
    "letter_review",
)
_PARTNER: Final = "engagement_partner"

_meta = MetaData()
drafts = Table(
    "engagement_drafts",
    _meta,
    Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=FetchedValue()),
    Column("tenant_id", PgUUID(as_uuid=True)),
    Column("created_by", PgUUID(as_uuid=True)),
    Column("client_id", PgUUID(as_uuid=True)),
    Column("client_entity_id", PgUUID(as_uuid=True)),
    Column("type_code", Text),
    Column("step", Text),
    Column("payload", JSONB),
    Column("prospect_engagement_id", PgUUID(as_uuid=True)),
    Column("created_engagement_id", PgUUID(as_uuid=True)),
    Column("version", Integer),
    Column("saved_at", DateTime(timezone=True)),
    Column("discarded_at", DateTime(timezone=True)),
)


class UnknownEngagementType(DomainInvalid):
    """The type is not in the engagement-type catalogue (single audit included, DEC-19)."""

    code = "unknown_engagement_type"


class DraftStaleVersion(DomainConflict):
    code = "stale_version"


class DraftIncomplete(DomainInvalid):
    """A step of the draft still has a problem (`facts.step`): validate it to see which."""

    code = "draft_incomplete"


class EntityOutsideClient(DomainInvalid):
    """The client entity is not one of the draft's client's entities."""

    code = "entity_outside_client"


@dataclass(frozen=True)
class CatalogueItem:
    entry: CatalogueEntry
    available: bool
    steps: list[tuple[WizardStep, tuple[str, ...]]]


async def _entitled(ctx: AuthContext, module: Literal["attest", "group_audit"]) -> bool:
    from abacus.modules.platform.api import entitlement  # platform's routes import identity

    return await entitlement(ctx.tenant, module) is not None


async def catalogue(ctx: AuthContext) -> list[CatalogueItem]:
    await authorise(ctx, CREATE, Resource.firm(ctx.tenant_id))
    attest = await _entitled(ctx, "attest")
    return [CatalogueItem(e, e.entitlement is None or attest, steps_of(e)) for e in CATALOGUE]


# --- drafts -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class DraftView:
    id: UUID
    created_by: UUID
    client_id: UUID | None
    client_entity_id: UUID | None
    type_code: str | None
    step: str
    payload: dict[str, object]
    prospect_engagement_id: UUID | None
    created_engagement_id: UUID | None
    version: int
    saved_at: datetime
    gates: list[GateView] = field(default_factory=list[GateView])


@dataclass(frozen=True)
class DraftChange:
    client_id: UUID | None = None
    client_entity_id: UUID | None = None
    type_code: str | None = None
    step: str | None = None
    payload: dict[str, object] | None = None


def _check_type(code: str | None) -> None:
    if code is not None and entry_of(code) is None:
        raise UnknownEngagementType(facts={"type_code": code})


async def _check_scope(
    ctx: AuthContext, client_id: UUID | None, entity_id: UUID | None
) -> UUID | None:
    """The client the draft names, after `engagement.create` is authorised on it: given an
    entity, always the entity's own client (an entity alone never skips the check). A walled or
    unknown client or entity is 404 before anything else is said about it (DEC-43, DEC-227); an
    entity of another client the person may see is 422 `entity_outside_client`."""
    owner = client_id
    if entity_id is not None:
        owner = await client_of_entity(ctx.tenant, entity_id)
        if owner is None:
            raise NotFound("client_entity")
    if owner is None:
        return None
    # `authorise` does not wall a firm-level resource (identity's `_walled` needs an engagement),
    # so the person's walls are read here, before the role check (create_engagement's way).
    if await hidden_clients(ctx.tenant, ctx.user_id, [owner]):
        raise NotFound("client")
    try:
        await authorise(ctx, CREATE, Resource.client(ctx.tenant_id, owner))
    except Forbidden as denied:
        if denied.layer == "wall":
            raise NotFound("client") from None
        raise
    if client_id is not None and owner != client_id:
        await _check_scope(ctx, client_id, None)  # the named client is checked as well
        raise EntityOutsideClient(facts={"client_entity_id": str(entity_id)})
    return owner


def _view(r: RowMapping) -> DraftView:
    return DraftView(
        id=cast(UUID, r["id"]),
        created_by=cast(UUID, r["created_by"]),
        client_id=cast(UUID | None, r["client_id"]),
        client_entity_id=cast(UUID | None, r["client_entity_id"]),
        type_code=cast(str | None, r["type_code"]),
        step=cast(str, r["step"]),
        payload=cast(dict[str, object], r["payload"] or {}),
        prospect_engagement_id=cast(UUID | None, r["prospect_engagement_id"]),
        created_engagement_id=cast(UUID | None, r["created_engagement_id"]),
        version=cast(int, r["version"]),
        saved_at=cast(datetime, r["saved_at"]),
    )


async def _own(session: AsyncSession, ctx: AuthContext, draft_id: UUID) -> DraftView:
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
        raise NotFound("engagement_draft")
    return _view(row)


async def create_draft(
    ctx: AuthContext,
    *,
    client_id: UUID | None,
    client_entity_id: UUID | None,
    type_code: str | None,
    step: str,
    payload: dict[str, object],
) -> DraftView:
    await authorise(ctx, CREATE, Resource.firm(ctx.tenant_id))
    _check_type(type_code)
    await _check_scope(ctx, client_id, client_entity_id)
    async with uow(ctx.tenant) as tx:
        row = (
            (
                await tx.session.execute(
                    insert(drafts)
                    .values(
                        tenant_id=ctx.tenant_id,
                        created_by=ctx.user_id,
                        client_id=client_id,
                        client_entity_id=client_entity_id,
                        type_code=type_code,
                        step=step,
                        payload=payload,
                    )
                    .returning(drafts)
                )
            )
            .mappings()
            .one()
        )
        tx.record(
            "engagement_draft.started", target=Target("engagement_draft", cast(UUID, row["id"]))
        )
    return await _with_gates(ctx, _view(row))


async def get_draft(ctx: AuthContext, draft_id: UUID) -> DraftView:
    """The owner's draft; 404 once a wall stands between them and its client (DEC-227)."""
    await authorise(ctx, CREATE, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        found = await _own(session, ctx, draft_id)
    await _check_scope(ctx, found.client_id, found.client_entity_id)
    return await _with_gates(ctx, found)


async def update_draft(
    ctx: AuthContext, draft_id: UUID, seen_version: int, change: DraftChange
) -> DraftView:
    """Autosave: operational state, so its audit event names the version only."""
    await authorise(ctx, CREATE, Resource.firm(ctx.tenant_id))
    _check_type(change.type_code)
    async with tenant_session(ctx.tenant) as session:
        current = await _own(session, ctx, draft_id)
    client_id = change.client_id or current.client_id
    entity_id = change.client_entity_id or current.client_entity_id
    await _check_scope(ctx, client_id, entity_id)
    values: dict[str, object] = {
        k: v
        for k, v in (
            ("client_id", change.client_id),
            ("client_entity_id", change.client_entity_id),
            ("type_code", change.type_code),
            ("step", change.step),
            ("payload", change.payload),
        )
        if v is not None
    }
    async with uow(ctx.tenant) as tx:
        row = (
            (
                await tx.session.execute(
                    update(drafts)
                    .where(
                        drafts.c.id == draft_id,
                        drafts.c.created_by == ctx.user_id,
                        drafts.c.version == seen_version,
                        drafts.c.discarded_at.is_(None),
                        drafts.c.created_engagement_id.is_(None),
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
            raise DraftStaleVersion(facts={"draft_id": str(draft_id)})
        # Every unit of work audits; an autosave records only the version it wrote.
        tx.record(
            "engagement_draft.saved",
            target=Target("engagement_draft", draft_id),
            after=Ref(version=cast(int, row["version"])),
        )
    return await _with_gates(ctx, _view(row))


async def discard_draft(ctx: AuthContext, draft_id: UUID) -> datetime:
    await authorise(ctx, CREATE, Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        await _own(tx.session, ctx, draft_id)
        at = (
            await tx.session.execute(
                update(drafts)
                .where(drafts.c.id == draft_id, drafts.c.created_engagement_id.is_(None))
                .values(discarded_at=func.clock_timestamp())
                .returning(drafts.c.discarded_at)
            )
        ).scalar_one_or_none()
        if at is None:  # created already: nothing to discard
            raise NotFound("engagement_draft")
        tx.record("engagement_draft.discarded", target=Target("engagement_draft", draft_id))
    return at


# --- validation and gates -----------------------------------------------------------------------


def _date(payload: dict[str, object], key: str) -> date | None:
    value = payload.get(key)
    if isinstance(value, date):
        return value
    return date.fromisoformat(value) if isinstance(value, str) else None


async def _g1_engagement(
    session: AsyncSession, d: DraftView, client_id: UUID | None
) -> Engagement | None:
    """The engagement whose acceptance the draft's G1 reads: the draft's own prospect, or the
    client entity's engagement of this type and period that is waiting to be completed. Only
    within `client_id`, the client `_check_scope` authorised (DEC-227)."""
    if client_id is None:
        return None
    if d.prospect_engagement_id is not None:
        found = await session.get(Engagement, d.prospect_engagement_id)
        return found if found is not None and found.client_id == client_id else None
    entry = entry_of(d.type_code)
    end = _date(d.payload, "fiscal_period_end")
    if entry is None or d.client_entity_id is None or end is None:
        return None
    return (
        await session.execute(
            select(Engagement)
            .where(
                Engagement.client_id == client_id,
                Engagement.client_entity_id == d.client_entity_id,
                Engagement.type == entry.engagement_type,
                Engagement.fiscal_period_end == end,
                Engagement.status.in_(("prospect", _COMPLETABLE)),
            )
            .order_by(Engagement.created_at.desc(), Engagement.id)
            .limit(1)
        )
    ).scalar_one_or_none()


async def _gates(ctx: AuthContext, d: DraftView) -> list[GateView]:
    entry = entry_of(d.type_code)
    if entry is None:
        return []
    client_id = await _check_scope(ctx, d.client_id, d.client_entity_id)
    async with tenant_session(ctx.tenant) as session:
        target = await _g1_engagement(session, d, client_id)
        acceptance = None if target is None else await g1_decision(session, target.id)
    views: list[GateView] = []
    for gate in required_gates(entry.engagement_type):
        if gate == "G1":
            if acceptance is not None and acceptance.accepted:
                views.append(
                    GateView(
                        "G1",
                        True,
                        met_at=acceptance.decided_at,
                        met_by_user_id=acceptance.decided_by,
                    )
                )
            else:
                ref = target.id if target is not None else d.id
                kind = "engagement" if target is not None else "engagement_draft"
                views.append(GateView("G1", False, [GateBlocker(kind, ref, "acceptance")]))
        elif gate in ("G2", "G3"):
            views.append(GateView(gate, False))  # not started: they follow the create
    return views


async def _with_gates(ctx: AuthContext, d: DraftView) -> DraftView:
    return replace(d, gates=await _gates(ctx, d))


@dataclass(frozen=True)
class Problem:
    field: str
    code: str


def problems_of(d: DraftView, step: WizardStep) -> list[Problem]:
    """What the step still lacks, as registered codes (never prose)."""
    p = d.payload
    out: list[Problem] = []
    if step == "client_type":
        for name, value in (
            ("client_id", d.client_id),
            ("client_entity_id", d.client_entity_id),
            ("type_code", d.type_code),
        ):
            if value is None:
                out.append(Problem(name, "required"))
    entry = entry_of(d.type_code)
    attest = entry is not None and entry.family == "audit_assurance"
    if step == "standards_methodology" and attest and not p.get("standards_code"):
        out.append(Problem("standards_code", "required"))
    if step == "period_deadlines":
        for name in ("name", "fiscal_period_start", "fiscal_period_end"):
            if not p.get(name):
                out.append(Problem(name, "required"))
        start, end = _date(p, "fiscal_period_start"), _date(p, "fiscal_period_end")
        if start and end and end < start:
            out.append(Problem("fiscal_period_end", "before_start"))
    if step == "team_independence":
        team = cast(list[dict[str, object]], p.get("team") or [])
        if sum(1 for m in team if m.get("role") == _PARTNER) != 1:
            out.append(Problem("team", "one_engagement_partner"))
    return out


@dataclass(frozen=True)
class StepCheck:
    draft_id: UUID
    step: WizardStep
    problems: list[Problem]
    gates: list[GateView]

    @property
    def valid(self) -> bool:
        g1 = next((g for g in self.gates if g.gate == "G1"), None)
        blocked = self.step == "client_type" and g1 is not None and not g1.met
        return not self.problems and not blocked


async def validate_draft(ctx: AuthContext, draft_id: UUID, step: WizardStep) -> StepCheck:
    d = await get_draft(ctx, draft_id)
    return StepCheck(draft_id, step, problems_of(d, step), d.gates)


# --- create ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Created:
    engagement_id: UUID
    engagement_status: str
    work_item_ids: list[UUID]
    independence_requested_user_ids: list[UUID]
    methodology_version_id: UUID | None


async def _work_items(
    tx: UnitOfWork, ctx: AuthContext, target: Engagement, entry: CatalogueEntry, name: str
) -> list[UUID]:
    """The type's work items (cardinality, chapter 03 §3.1); ones already there are kept."""
    existing = (
        await tx.session.execute(
            select(WorkItem.id, WorkItem.kind, WorkItem.name).where(
                WorkItem.engagement_id == target.id, WorkItem.archived_at.is_(None)
            )
        )
    ).all()
    wanted: list[tuple[str, dict[str, str | int | date | None]]] = []
    year = target.fiscal_period_start.year
    if entry.work_item_kind == "tax_return":
        wanted = [
            (f"Form {form.upper()}", {"form": form, "tax_year": year}) for form in entry.forms
        ]
    elif entry.work_item_kind == "close":
        wanted = [(name, {"period": target.fiscal_period_start.strftime("%Y-%m")})]
    elif entry.work_item_kind in ("assurance", "advisory_project"):
        wanted = [(name, {"name": name, "assurance_type": entry.engagement_type})]
    ids = [wid for wid, kind, _ in existing if kind == entry.work_item_kind]
    have = {n for _, kind, n in existing if kind == entry.work_item_kind}
    if entry.work_item_kind in ("assurance", "advisory_project", "close") and ids:
        return ids  # one per engagement (or per period): already there
    provider = work_item_provider(entry.work_item_kind) if wanted else None
    for item_name, details in wanted:
        if item_name in have or provider is None:
            continue
        wid = (
            await tx.session.execute(
                insert(WorkItem)
                .values(
                    tenant_id=ctx.tenant_id,
                    engagement_id=target.id,
                    client_id=target.client_id,
                    client_entity_id=target.client_entity_id,
                    kind=entry.work_item_kind,
                    name=item_name,
                    period_start=target.fiscal_period_start,
                    period_end=target.fiscal_period_end,
                    created_by=ctx.user_id,
                )
                .returning(WorkItem.id)
            )
        ).scalar_one()
        await provider.create(
            tx, NewWorkItem(ctx.tenant_id, wid, target.id, target.client_entity_id, details)
        )
        tx.record("work_item.created", target=Target("engagement", target.id))
        ids.append(wid)
    return ids


async def check_create(ctx: AuthContext, draft_id: UUID) -> None:
    """The route's check before its `Idempotency-Key` lookup, so a replay is authorised too
    (the stored answer runs no service call): the action, then the draft is the person's own."""
    await authorise(ctx, CREATE, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        await _own(session, ctx, draft_id)


async def create_from_draft(
    ctx: AuthContext, draft_id: UUID, *, confirm_duplicate: bool
) -> Created:
    await authorise(ctx, CREATE, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        d = await _own(session, ctx, draft_id)
    scoped = await _check_scope(ctx, d.client_id, d.client_entity_id)
    entry = entry_of(d.type_code)
    if d.type_code is not None and entry is None:
        raise UnknownEngagementType(facts={"type_code": d.type_code})
    if d.created_engagement_id is not None:
        return await _created(ctx, d.created_engagement_id, [])
    for step in _STEP_ORDER:
        if problems_of(d, step):
            raise DraftIncomplete(facts={"step": step, "draft_id": str(draft_id)})
    if entry is None or d.client_id is None or d.client_entity_id is None:
        raise DraftIncomplete(facts={"step": "client_type", "draft_id": str(draft_id)})
    if entry.entitlement is not None and not await _entitled(ctx, entry.entitlement):
        raise UnknownEngagementType(facts={"type_code": entry.code})
    group_audit = bool(d.payload.get("group_audit"))
    if group_audit and not (entry.group_audit_allowed and await _entitled(ctx, "group_audit")):
        raise DraftIncomplete(facts={"step": "client_type", "draft_id": str(draft_id)})
    async with tenant_session(ctx.tenant) as session:
        target = await _g1_engagement(session, d, scoped)
        acceptance = None if target is None else await g1_decision(session, target.id)
    if (
        target is None
        or target.status != _COMPLETABLE
        or acceptance is None
        or not acceptance.accepted
    ):
        raise GateUnmet(facts={"gate": "G1", "draft_id": str(draft_id)})
    async with tenant_session(ctx.tenant) as session:
        duplicate = (
            await session.execute(
                select(Engagement.id)
                .where(
                    Engagement.client_entity_id == target.client_entity_id,
                    Engagement.type == target.type,
                    Engagement.fiscal_period_end == target.fiscal_period_end,
                    Engagement.status.not_in(_OPEN_FOR_DUPLICATES),
                    Engagement.id != target.id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
    if duplicate is not None and not confirm_duplicate:
        raise PossibleDuplicate(facts={"engagement_id": str(duplicate)})
    name = str(d.payload.get("name") or target.name)
    methodology = cast(str | None, d.payload.get("methodology_version_id"))
    team = cast(list[dict[str, str]], d.payload.get("team") or [])
    requested: list[UUID] = []
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, target.id)
        # On the client, as `_check_scope` did: the derived `firm_partner` (DEC-225) holds
        # `engagement.create` on firm and client resources, never on an engagement (DEC-132).
        await authorise(ctx, CREATE, Resource.client(ctx.tenant_id, ref.client_id))
        claimed = (
            await tx.session.execute(
                update(drafts)
                .where(drafts.c.id == draft_id, drafts.c.created_engagement_id.is_(None))
                .values(created_engagement_id=target.id, saved_at=func.clock_timestamp())
                .returning(drafts.c.id)
            )
        ).scalar_one_or_none()
        if claimed is None:  # a concurrent create got there first
            raise DraftStaleVersion(facts={"draft_id": str(draft_id)})
        values: dict[str, object] = {}
        label = d.payload.get("period_label")
        if isinstance(label, str) and label:
            values["period_label"] = label
        if methodology and target.methodology_version_id is None:
            values["methodology_version_id"] = UUID(methodology)
        if values:
            await tx.session.execute(
                update(Engagement).where(Engagement.id == target.id).values(**values)
            )
        work = await _work_items(tx, ctx, target, entry, name)
        roster = engagement_team_query().subquery("roster")
        on_team = set(
            (
                await tx.session.execute(
                    select(roster.c.user_id).where(roster.c.engagement_id == target.id)
                )
            )
            .scalars()
            .all()
        )
        for member in team:
            user = UUID(member["user_id"])
            if user in on_team:
                continue
            await add_member(tx, ctx, target.id, ref.client_id, user, member["role"])  # pyright: ignore[reportArgumentType] -- a role code the draft validated
            requested.append(user)
            on_team.add(user)
        tx.record(
            "engagement.created",
            target=Target("engagement", target.id),
            after=Ref(draft_id=draft_id, work_items=len(work)),
        )
        tx.emit(EngagementCreated(engagement_id=target.id))
    return await _created(ctx, target.id, requested)


async def _created(ctx: AuthContext, engagement_id: UUID, requested: list[UUID]) -> Created:
    async with tenant_session(ctx.tenant) as session:
        engagement = await session.get(Engagement, engagement_id)
        if engagement is None:
            raise NotFound("engagement")
        work = (
            (
                await session.execute(
                    select(WorkItem.id)
                    .where(WorkItem.engagement_id == engagement_id, WorkItem.archived_at.is_(None))
                    .order_by(WorkItem.created_at, WorkItem.id)
                )
            )
            .scalars()
            .all()
        )
    return Created(
        engagement_id,
        engagement.status,
        list(work),
        requested,
        engagement.methodology_version_id,
    )


# --- start acceptance (P-07-T35) -----------------------------------------------------------------

INTAKE: Final = "client.intake"
_START_STEPS: Final[tuple[WizardStep, ...]] = (
    "client_type",
    "period_deadlines",
    "team_independence",
)


@dataclass(frozen=True)
class AcceptanceStarted:
    draft_id: UUID
    engagement_id: UUID
    acceptance_record_id: UUID
    engagement_status: str


async def start_acceptance(ctx: AuthContext, draft_id: UUID) -> AcceptanceStarted:
    """ENG-03 d "Start acceptance" (OQ-2, DEC-143, DEC-372): one unit of work creates a Prospect
    engagement for the draft's client entity, type, name and period, puts the draft's team on
    it (each asked to confirm independence), and opens its acceptance record. Nothing is
    accepted: accepting is the engagement partner's decision on the record. The draft points at
    the prospect, so a second call answers the same engagement and record."""
    if ctx.client or ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(INTAKE, "role")
    await authorise(ctx, INTAKE, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        d = await _own(session, ctx, draft_id)
    if d.created_engagement_id is not None:
        raise DraftStaleVersion(facts={"draft_id": str(draft_id)})
    if d.prospect_engagement_id is not None:
        record_id = await acceptance_model.record_id_of(ctx.tenant, d.prospect_engagement_id)
        if record_id is not None:
            async with tenant_session(ctx.tenant) as session:
                prospect = await session.get(Engagement, d.prospect_engagement_id)
            status = prospect.status if prospect is not None else "prospect"
            return AcceptanceStarted(draft_id, d.prospect_engagement_id, record_id, status)
    entry = entry_of(d.type_code)
    for step in _START_STEPS:
        if problems_of(d, step):
            raise DraftIncomplete(facts={"step": step, "draft_id": str(draft_id)})
    if entry is None or d.client_id is None or d.client_entity_id is None:
        raise DraftIncomplete(facts={"step": "client_type", "draft_id": str(draft_id)})
    if entry.entitlement is not None and not await _entitled(ctx, entry.entitlement):
        raise UnknownEngagementType(facts={"type_code": entry.code})
    owner = await client_of_entity(ctx.tenant, d.client_entity_id)
    if owner is None or await hidden_clients(ctx.tenant, ctx.user_id, [owner]):
        raise NotFound("client")
    if owner != d.client_id:
        raise EntityOutsideClient(facts={"client_entity_id": str(d.client_entity_id)})
    try:
        await authorise(ctx, INTAKE, Resource.client(ctx.tenant_id, owner))
    except Forbidden as denied:
        if denied.layer == "wall":
            raise NotFound("client") from None
        raise
    start = _date(d.payload, "fiscal_period_start")
    end = _date(d.payload, "fiscal_period_end")
    if start is None or end is None:
        raise DraftIncomplete(facts={"step": "period_deadlines", "draft_id": str(draft_id)})
    prior_raw = d.payload.get("prior_engagement_id")
    prior = UUID(prior_raw) if isinstance(prior_raw, str) and prior_raw else None
    if prior is not None:
        async with tenant_session(ctx.tenant) as session:
            before = await session.get(Engagement, prior)
        if before is None or before.client_entity_id != d.client_entity_id:
            raise DomainInvalid(facts={"field": "prior_engagement_id"})
    team = cast(list[dict[str, str]], d.payload.get("team") or [])
    engagement_id = uuid4()
    async with uow(ctx.tenant) as tx:
        await insert_engagement(
            tx.session,
            engagement_id=engagement_id,
            tenant_id=ctx.tenant_id,
            client_id=owner,
            client_entity_id=d.client_entity_id,
            name=str(d.payload.get("name")),
            fiscal_period_start=start,
            fiscal_period_end=end,
            created_by=ctx.user_id,
            type=entry.engagement_type,
            prior_engagement_id=prior,
            prospect=True,
        )
        claimed = (
            await tx.session.execute(
                update(drafts)
                .where(
                    drafts.c.id == draft_id,
                    drafts.c.prospect_engagement_id.is_(None),
                    drafts.c.created_engagement_id.is_(None),
                )
                .values(prospect_engagement_id=engagement_id, saved_at=func.clock_timestamp())
                .returning(drafts.c.id)
            )
        ).scalar_one_or_none()
        if claimed is None:  # a concurrent start got there first
            raise DraftStaleVersion(facts={"draft_id": str(draft_id)})
        tx.record(
            "engagement.created",
            target=Target("engagement", engagement_id),
            after=Ref(draft_id=draft_id),
        )
        on_team: set[UUID] = set()
        for member in team:
            user = UUID(member["user_id"])
            if user in on_team:
                continue
            # Inside the creating unit of work, after `client.intake` was authorised: the
            # engagement is new, so no one holds a role on it yet to add members (roll-forward's
            # way, SPEC-025 AC-2). Each person is re-checked (active, not walled, consent).
            await add_rolled_forward_member(tx, ctx, engagement_id, owner, user, member["role"])  # pyright: ignore[reportArgumentType] -- a role code the draft validated
            on_team.add(user)
        record_id = await acceptance_model.open_record(
            tx,
            ctx,
            engagement_id=engagement_id,
            client_id=owner,
            family=entry.family,
            prior_engagement_id=prior,
        )
        tx.record(
            "engagement_draft.started_acceptance",
            target=Target("engagement_draft", draft_id),
            after=Ref(engagement_id=engagement_id),
        )
        tx.emit(EngagementCreated(engagement_id=engagement_id))
    return AcceptanceStarted(draft_id, engagement_id, record_id, "prospect")

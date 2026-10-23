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
- "Start acceptance" stays a stub until the acceptance record exists (P-07-T35, DEC-225).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Final, Literal, cast
from uuid import UUID

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
from abacus.modules.engagements.events import EngagementCreated
from abacus.modules.engagements.gate_policy import required_gates
from abacus.modules.engagements.models import Engagement, WorkItem
from abacus.modules.engagements.record import GateBlocker, GateUnmet, GateView
from abacus.modules.engagements.repository import latest_acceptance
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
    Resource,
    add_member,
    authorise,
    engagement_team_query,
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


async def _check_scope(ctx: AuthContext, client_id: UUID | None, entity_id: UUID | None) -> None:
    """The client must be one the person may act on (walls first, 404); an entity must be the
    client's."""
    if client_id is not None:
        await authorise(ctx, CREATE, Resource.client(ctx.tenant_id, client_id))
    if entity_id is not None:
        owner = await client_of_entity(ctx.tenant, entity_id)
        if owner is None or (client_id is not None and owner != client_id):
            raise EntityOutsideClient(facts={"client_entity_id": str(entity_id)})


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
    await authorise(ctx, CREATE, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        found = await _own(session, ctx, draft_id)
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


async def _g1_engagement(session: AsyncSession, d: DraftView) -> Engagement | None:
    """The engagement whose acceptance the draft's G1 reads: the draft's own prospect, or the
    client entity's engagement of this type and period that is waiting to be completed."""
    if d.prospect_engagement_id is not None:
        return await session.get(Engagement, d.prospect_engagement_id)
    entry = entry_of(d.type_code)
    end = _date(d.payload, "fiscal_period_end")
    if entry is None or d.client_entity_id is None or end is None:
        return None
    return (
        await session.execute(
            select(Engagement)
            .where(
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
    async with tenant_session(ctx.tenant) as session:
        target = await _g1_engagement(session, d)
        acceptance = None if target is None else await latest_acceptance(session, target.id)
    views: list[GateView] = []
    for gate in required_gates(entry.engagement_type):
        if gate == "G1":
            if acceptance is not None and acceptance.decision == "accepted":
                views.append(GateView("G1", True, met_at=acceptance.created_at))
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


async def create_from_draft(
    ctx: AuthContext, draft_id: UUID, *, confirm_duplicate: bool
) -> Created:
    await authorise(ctx, CREATE, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        d = await _own(session, ctx, draft_id)
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
        target = await _g1_engagement(session, d)
        acceptance = None if target is None else await latest_acceptance(session, target.id)
    if (
        target is None
        or target.status != _COMPLETABLE
        or acceptance is None
        or acceptance.decision != "accepted"
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
        await authorise(ctx, CREATE, ref.resource())
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

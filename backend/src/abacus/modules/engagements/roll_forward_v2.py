"""Roll-forward v2 (P-07-T55; ENG-13; P-07 Story 7.1; DEC-805).

Next year's engagement from a released one (`delivered` or `archived`; any other source answers
409 `roll_forward_source_not_released`), through a saved draft the wizard edits and a Create that
does everything in one unit of work. The v1 carry categories, each Carry or Skip:

- `team`: last year's people with their roles, less anyone who has left or is now walled from
  the client (`available` false; they cannot be carried);
- `template`: the source's methodology template at its current version, pinned at Create
  (ENG-13 b; reconciling a newer version's changes is K-03's, ENG-13 c, fixture-only);
- `request_list`: last year's whole request list, every item as Draft, never client-visible;
- `prior_year_notes`: the new engagement links last year's record (its notes, letters and
  archive), read-only.

Create makes a Prospect engagement with `prior_engagement_id`, puts the carried team on it (each
asked to confirm independence), opens a continuance acceptance record (G1 again; nothing is
accepted here) and copies the request list. Evidence, results and sign-offs never move (ADR-004):
the new engagement starts with none. Controls, mappings, prior-year balances, triggers, sheets and
learned context are not v1 categories (X-01, K-03 to K-05).

Who: `roll_forward.read` on the source (its engagement partner and manager, a firm admin or
practice leader; a walled person gets 404) and `roll_forward.create` on the client (firm admins,
practice leaders, partners and managers by level). A person's act only, never an agent's.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import Column, FetchedValue, MetaData, Table, func, insert, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Date, DateTime, Integer, Text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.engagements import acceptance as acceptance_model
from abacus.modules.engagements.events import EngagementCreated
from abacus.modules.engagements.models import Engagement
from abacus.modules.engagements.repository import insert_engagement
from abacus.modules.engagements.roll_forward import RollForwardUnavailable, TeamMemberUnavailable
from abacus.modules.engagements.service import EngagementRef, get_ref, pin_methodology
from abacus.modules.engagements.type_catalogue import BY_CODE
from abacus.modules.identity.api import (
    Actor,
    AuthContext,
    Forbidden,
    Resource,
    add_rolled_forward_member,
    allowed_actions,
    authorise,
    available_staff,
    engagement_team,
    member_facts,
)
from abacus.modules.methodology.api import latest_versions, version_detail

READ: Final = "roll_forward.read"
CREATE: Final = "roll_forward.create"
SUBJECT: Final = "roll_forward_draft"
RELEASED: Final = frozenset({"delivered", "archived"})
CATEGORIES: Final = ("team", "template", "request_list", "prior_year_notes")
_PARTNER: Final = "engagement_partner"
_NAME_LIMIT: Final = 200

Category = Literal["team", "template", "request_list", "prior_year_notes"]
TemplateDecision = Literal["current", "skip"]

# (who, last year's engagement) -> how many requests it has; (the creating unit of work, who,
# the new engagement, last year's) -> how many were copied, all as Draft. `requests` registers.
CountRequests = Callable[[AuthContext, UUID], Awaitable[int]]
CopyRequests = Callable[[UnitOfWork, AuthContext, UUID, UUID], Awaitable[int]]
_requests: tuple[CountRequests, CopyRequests] | None = None


def register_draft_request_copy(count: CountRequests, copy: CopyRequests) -> None:
    global _requests
    if _requests is not None and _requests != (count, copy):
        raise RuntimeError("the roll-forward request copy is already registered")
    _requests = (count, copy)


class RollForwardSourceNotReleased(DomainConflict):
    """The source is not `delivered` or `archived` (`facts.status`): nothing is created."""

    code = "roll_forward_source_not_released"


class RollForwardStale(DomainConflict):
    """The draft moved past the version the person saw, or was created or discarded."""

    code = "stale_version"


class RollForwardInvalid(DomainInvalid):
    """A carry choice the draft cannot hold (`facts.field`): a person not on last year's team or
    not available, a template when the source has none, a period that ends before it starts."""

    code = "roll_forward_invalid"


_meta = MetaData()
drafts = Table(
    "roll_forward_drafts",
    _meta,
    Column("id", PgUUID(as_uuid=True), primary_key=True, server_default=FetchedValue()),
    Column("tenant_id", PgUUID(as_uuid=True)),
    Column("source_engagement_id", PgUUID(as_uuid=True)),
    Column("created_by", PgUUID(as_uuid=True)),
    Column("target_period_start", Date),
    Column("target_period_end", Date),
    Column("name", Text),
    Column("selections", JSONB),
    Column("team", JSONB),
    Column("template_decision", Text),
    Column("created_engagement_id", PgUUID(as_uuid=True)),
    Column("version", Integer),
    Column("created_at", DateTime(timezone=True)),
    Column("saved_at", DateTime(timezone=True)),
    Column("discarded_at", DateTime(timezone=True)),
)


# --- views -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TeamCarry:
    user_id: UUID
    display_name: str
    role: str
    available: bool


@dataclass(frozen=True)
class TemplateCarry:
    template_id: UUID
    template_name: str
    source_version: int
    current_version_id: UUID
    current_version: int

    @property
    def current(self) -> bool:
        """Last year's version is still the current one: nothing to reconcile (ENG-13 b)."""
        return self.source_version == self.current_version


@dataclass(frozen=True)
class Catalogue:
    team: list[TeamCarry]
    template: TemplateCarry | None
    request_count: int


@dataclass(frozen=True)
class Source:
    engagement_id: UUID
    name: str
    status: str
    fiscal_period_start: date
    fiscal_period_end: date


@dataclass(frozen=True)
class DraftView:
    id: UUID
    source: Source
    target_period_start: date
    target_period_end: date
    name: str
    selections: dict[str, bool]
    team: list[tuple[UUID, str]]
    template_decision: str
    version: int
    saved_at: datetime
    created_engagement_id: UUID | None
    catalogue: Catalogue
    allowed_actions: list[str]


@dataclass(frozen=True)
class DraftChange:
    target_period_start: date | None = None
    target_period_end: date | None = None
    name: str | None = None
    selections: Mapping[str, bool] | None = None
    team_user_ids: Sequence[UUID] | None = None
    template_decision: TemplateDecision | None = None


@dataclass(frozen=True)
class Created:
    engagement_id: UUID
    status: str
    prior_engagement_id: UUID
    acceptance_record_id: UUID
    requests_created: int
    team_requested: list[UUID]
    methodology_version_id: UUID | None


# --- helpers -----------------------------------------------------------------------------------


def _person(ctx: Actor, action: str) -> AuthContext:
    """A person's own act: never an agent, the platform, a client principal or support."""
    if (
        not isinstance(cast(object, ctx), AuthContext)
        or cast(AuthContext, ctx).client
        or ctx.tenant.actor_kind != "human"
        or cast(AuthContext, ctx).is_support
    ):
        raise Forbidden(action, "role")
    return cast(AuthContext, ctx)


async def _check(ctx: AuthContext, action: str, resource: Resource) -> None:
    """`authorise`, with a wall answering 404 like every other read of the client (DEC-43)."""
    try:
        await authorise(ctx, action, resource)
    except Forbidden as denied:
        if denied.layer == "wall":
            raise NotFound("engagement") from None
        raise


def next_year(day: date) -> date:
    """The same day a year on; Feb 29 becomes Feb 28."""
    try:
        return day.replace(year=day.year + 1)
    except ValueError:
        return day.replace(year=day.year + 1, day=28)


def next_name(name: str, source_end: date, target_end: date) -> str:
    """The source's name with its period's year moved on ("PY2025 EBP Audit" -> "PY2026 EBP
    Audit"); a name without that year is kept as it is."""
    moved = re.sub(rf"(?<!\d){source_end.year}(?!\d)", str(target_end.year), name)
    return moved[:_NAME_LIMIT]


def _family_of(engagement_type: str) -> str:
    for entry in BY_CODE.values():
        if entry.engagement_type == engagement_type:
            return entry.family
    raise RollForwardInvalid(facts={"field": "type"})


async def _source(ctx: AuthContext, engagement_id: UUID) -> tuple[EngagementRef, Engagement]:
    """The source, readable by the caller (`roll_forward.read`; walls 404), and released."""
    ref = await get_ref(ctx, engagement_id)
    await _check(ctx, READ, ref.resource())
    async with tenant_session(ctx.tenant) as session:
        row = await session.get(Engagement, engagement_id)
    if row is None:
        raise NotFound("engagement")
    if row.status not in RELEASED:
        raise RollForwardSourceNotReleased(facts={"status": row.status})
    return ref, row


async def _template(ctx: AuthContext, version_id: UUID | None) -> TemplateCarry | None:
    if version_id is None:
        return None
    then = await version_detail(ctx.tenant, version_id)
    latest = [
        v.version_id
        for v in await latest_versions(ctx.tenant)
        if v.template_id == then.summary.template_id
    ]
    now = await version_detail(ctx.tenant, latest[0]) if latest else then
    return TemplateCarry(
        then.summary.template_id,
        now.summary.template_name,
        then.summary.version,
        now.summary.version_id,
        now.summary.version,
    )


async def _catalogue(ctx: AuthContext, ref: EngagementRef, row: Engagement) -> Catalogue:
    if _requests is None:
        raise RollForwardUnavailable("requests")
    available = await available_staff(ctx.tenant, ref.client_id)
    team = [
        TeamCarry(m.user_id, m.display_name, m.role, m.user_id in available)
        for m in await engagement_team(ctx, row.id)
    ]
    return Catalogue(
        team=team,
        template=await _template(ctx, row.methodology_version_id),
        request_count=await _requests[0](ctx, row.id),
    )


def _source_of(row: Engagement) -> Source:
    return Source(row.id, row.name, row.status, row.fiscal_period_start, row.fiscal_period_end)


async def _own(
    session: AsyncSession, ctx: AuthContext, source_id: UUID, draft_id: UUID
) -> RowMapping:
    found = (
        (
            await session.execute(
                select(drafts).where(
                    drafts.c.id == draft_id,
                    drafts.c.source_engagement_id == source_id,
                    drafts.c.created_by == ctx.user_id,
                    drafts.c.discarded_at.is_(None),
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if found is None:
        raise NotFound(SUBJECT)
    return found


async def _view(
    ctx: AuthContext, row: RowMapping, source: Engagement, catalogue: Catalogue
) -> DraftView:
    team = cast(list[dict[str, str]], row["team"])
    selections = cast(dict[str, bool], row["selections"])
    held = await allowed_actions(ctx, Resource.client(ctx.tenant_id, source.client_id), [CREATE])
    return DraftView(
        id=cast(UUID, row["id"]),
        source=_source_of(source),
        target_period_start=cast(date, row["target_period_start"]),
        target_period_end=cast(date, row["target_period_end"]),
        name=cast(str, row["name"]),
        selections={c: bool(selections.get(c, False)) for c in CATEGORIES},
        team=[(UUID(m["user_id"]), m["role"]) for m in team],
        template_decision=cast(str, row["template_decision"]),
        version=cast(int, row["version"]),
        saved_at=cast(datetime, row["saved_at"]),
        created_engagement_id=cast(UUID | None, row["created_engagement_id"]),
        catalogue=catalogue,
        allowed_actions=sorted(held),
    )


def _team_of(catalogue: Catalogue, user_ids: Sequence[UUID]) -> list[dict[str, str]]:
    """Each carried person with last year's role; only people on last year's team who are
    available now (not left, not walled)."""
    by_id = {m.user_id: m for m in catalogue.team}
    chosen: list[dict[str, str]] = []
    for user_id in dict.fromkeys(user_ids):
        member = by_id.get(user_id)
        if member is None or not member.available:
            raise RollForwardInvalid(facts={"field": "team"})
        chosen.append({"user_id": str(user_id), "role": member.role})
    return chosen


def _scope(engagement_id: UUID) -> Scope:
    return Scope(engagement_id=engagement_id)


# --- the draft ---------------------------------------------------------------------------------


async def create_draft(ctx: Actor, source_id: UUID) -> DraftView:
    """ENG-13 "Roll forward…": a draft carrying everything v1 can, by default: the available
    team, the template at its current version, the request list and the prior-year notes; next
    year's period and name."""
    person = _person(ctx, CREATE)
    ref, source = await _source(person, source_id)
    await _check(person, CREATE, Resource.client(person.tenant_id, ref.client_id))
    catalogue = await _catalogue(person, ref, source)
    start = next_year(source.fiscal_period_start)
    end = next_year(source.fiscal_period_end)
    async with uow(person.tenant) as tx:
        draft_id = (
            await tx.session.execute(
                insert(drafts)
                .values(
                    tenant_id=person.tenant_id,
                    source_engagement_id=source.id,
                    created_by=person.user_id,
                    target_period_start=start,
                    target_period_end=end,
                    name=next_name(source.name, source.fiscal_period_end, end),
                    selections={c: True for c in CATEGORIES}
                    | ({} if catalogue.template else {"template": False}),
                    team=_team_of(catalogue, [m.user_id for m in catalogue.team if m.available]),
                    template_decision="current" if catalogue.template else "skip",
                )
                .returning(drafts.c.id)
            )
        ).scalar_one()
        tx.record(
            "roll_forward_draft.created",
            target=Target(SUBJECT, draft_id),
            after=Ref(source_engagement_id=source.id, requests=catalogue.request_count),
            scope=_scope(source.id),
        )
    return await get_draft(person, source_id, draft_id)


async def get_draft(ctx: Actor, source_id: UUID, draft_id: UUID) -> DraftView:
    person = _person(ctx, READ)
    ref, source = await _source(person, source_id)
    async with tenant_session(person.tenant) as session:
        row = await _own(session, person, source_id, draft_id)
    return await _view(person, row, source, await _catalogue(person, ref, source))


async def update_draft(
    ctx: Actor, source_id: UUID, draft_id: UUID, seen_version: int, change: DraftChange
) -> DraftView:
    """ENG-13's autosave: each Carry · Skip, the team, the template decision, the period and
    the name, on the version the person saw (409 `stale_version` otherwise)."""
    person = _person(ctx, CREATE)
    ref, source = await _source(person, source_id)
    await _check(person, CREATE, Resource.client(person.tenant_id, ref.client_id))
    catalogue = await _catalogue(person, ref, source)
    async with tenant_session(person.tenant) as session:
        row = await _own(session, person, source_id, draft_id)
    if row["created_engagement_id"] is not None or row["version"] != seen_version:
        raise RollForwardStale(facts={"version": cast(int, row["version"])})
    values: dict[str, object] = {}
    start = change.target_period_start or cast(date, row["target_period_start"])
    end = change.target_period_end or cast(date, row["target_period_end"])
    if end <= start:
        raise RollForwardInvalid(facts={"field": "target_period_end"})
    if change.target_period_start is not None:
        values["target_period_start"] = start
    if change.target_period_end is not None:
        values["target_period_end"] = end
    if change.name is not None:
        name = " ".join(change.name.split())
        if not 1 <= len(name) <= _NAME_LIMIT:
            raise RollForwardInvalid(facts={"field": "name"})
        values["name"] = name
    selections = dict(cast(dict[str, bool], row["selections"]))
    if change.selections is not None:
        for key, carry in change.selections.items():
            if key not in CATEGORIES:
                raise RollForwardInvalid(facts={"field": "selections"})
            selections[key] = bool(carry)
        values["selections"] = selections
    decision = change.template_decision or cast(str, row["template_decision"])
    if change.template_decision is not None:
        values["template_decision"] = decision
    if (decision == "current" or selections.get("template")) and catalogue.template is None:
        raise RollForwardInvalid(facts={"field": "template"})
    if change.team_user_ids is not None:
        values["team"] = _team_of(catalogue, change.team_user_ids)
    async with uow(person.tenant) as tx:
        moved = (
            await tx.session.execute(
                update(drafts)
                .where(
                    drafts.c.id == draft_id,
                    drafts.c.version == seen_version,
                    drafts.c.created_engagement_id.is_(None),
                    drafts.c.discarded_at.is_(None),
                )
                .values(**values, version=drafts.c.version + 1, saved_at=func.clock_timestamp())
                .returning(drafts.c.version)
            )
        ).scalar_one_or_none()
        if moved is None:
            raise RollForwardStale(facts={"version": seen_version})
        tx.record(
            "roll_forward_draft.saved",
            target=Target(SUBJECT, draft_id),
            after=Ref(version=moved),
            scope=_scope(source.id),
        )
    return await get_draft(person, source_id, draft_id)


async def discard_draft(ctx: Actor, source_id: UUID, draft_id: UUID) -> datetime:
    """Escape → "Discard this draft?": the draft is set aside; nothing was created."""
    person = _person(ctx, CREATE)
    ref, _ = await _source(person, source_id)
    await _check(person, CREATE, Resource.client(person.tenant_id, ref.client_id))
    async with uow(person.tenant) as tx:
        row = await _own(tx.session, person, source_id, draft_id)
        if row["created_engagement_id"] is not None:
            raise RollForwardStale(facts={"version": cast(int, row["version"])})
        at = (
            await tx.session.execute(
                update(drafts)
                .where(drafts.c.id == draft_id)
                .values(discarded_at=func.clock_timestamp())
                .returning(drafts.c.discarded_at)
            )
        ).scalar_one()
        tx.record(
            "roll_forward_draft.discarded",
            target=Target(SUBJECT, draft_id),
            scope=_scope(source_id),
        )
    return cast(datetime, at)


# --- Create --------------------------------------------------------------------------------------


async def check_create(ctx: Actor, source_id: UUID, draft_id: UUID) -> None:
    """The route's check before its `Idempotency-Key` lookup, so a replay is authorised too (the
    stored answer runs no service call): a person, the source readable and released, the
    action on the client, and the draft the person's own."""
    person = _person(ctx, CREATE)
    ref, _ = await _source(person, source_id)
    await _check(person, CREATE, Resource.client(person.tenant_id, ref.client_id))
    async with tenant_session(person.tenant) as session:
        await _own(session, person, source_id, draft_id)


async def create(ctx: Actor, source_id: UUID, draft_id: UUID) -> Created:
    """ENG-13 e "Create": in one unit of work, a Prospect engagement with `prior_engagement_id`,
    the carried team (each asked to confirm independence), the template's current version pinned,
    a continuance acceptance record, and the request list as Draft. A second call answers the
    engagement the first made."""
    person = _person(ctx, CREATE)
    ref, source = await _source(person, source_id)
    await _check(person, CREATE, Resource.client(person.tenant_id, ref.client_id))
    async with tenant_session(person.tenant) as session:
        row = await _own(session, person, source_id, draft_id)
    if row["created_engagement_id"] is not None:
        return await _created(person, cast(UUID, row["created_engagement_id"]), source.id, [], 0)
    catalogue = await _catalogue(person, ref, source)
    selections = cast(dict[str, bool], row["selections"])
    team = cast(list[dict[str, str]], row["team"]) if selections.get("team") else []
    _team_of(catalogue, [UUID(m["user_id"]) for m in team])  # still on the team and available
    for member in team:
        if member["role"] == _PARTNER:  # DEC-375 (M3): a partner-level person
            facts = await member_facts(person.tenant, UUID(member["user_id"]))
            if facts is None or facts.client or facts.level != "partner":
                raise RollForwardInvalid(facts={"field": "team"})
    template = catalogue.template
    pin = (
        template.current_version_id
        if template is not None
        and selections.get("template")
        and row["template_decision"] == "current"
        else None
    )
    family = _family_of(source.type)
    if selections.get("request_list") and _requests is None:
        raise RollForwardUnavailable("requests")
    engagement_id = uuid4()
    requested: list[UUID] = []
    async with uow(person.tenant) as tx:
        await insert_engagement(
            tx.session,
            engagement_id=engagement_id,
            tenant_id=person.tenant_id,
            client_id=source.client_id,
            client_entity_id=source.client_entity_id,
            name=cast(str, row["name"]),
            fiscal_period_start=cast(date, row["target_period_start"]),
            fiscal_period_end=cast(date, row["target_period_end"]),
            created_by=person.user_id,
            type=source.type,
            prior_engagement_id=source.id,
            prospect=True,
        )
        claimed = (
            await tx.session.execute(
                update(drafts)
                .where(
                    drafts.c.id == draft_id,
                    drafts.c.version == row["version"],
                    drafts.c.created_engagement_id.is_(None),
                    drafts.c.discarded_at.is_(None),
                )
                .values(created_engagement_id=engagement_id, saved_at=func.clock_timestamp())
                .returning(drafts.c.id)
            )
        ).scalar_one_or_none()
        if claimed is None:  # a concurrent save or create got there first
            raise RollForwardStale(facts={"version": cast(int, row["version"])})
        tx.record(
            "engagement.created",
            target=Target("engagement", engagement_id),
            after=Ref(roll_forward_draft_id=draft_id),
        )
        for member in team:
            user = UUID(member["user_id"])
            try:
                await add_rolled_forward_member(
                    tx,
                    person,
                    engagement_id,
                    source.client_id,
                    user,
                    member["role"],  # pyright: ignore[reportArgumentType] -- a role code last year's team held
                )
            except NotFound:
                raise TeamMemberUnavailable(str(user)) from None
            requested.append(user)
        if pin is not None:
            await pin_methodology(tx, engagement_id, pin)
        record_id = await acceptance_model.open_record(
            tx,
            person,
            engagement_id=engagement_id,
            client_id=source.client_id,
            family=family,
            prior_engagement_id=source.id,
        )
        copied = 0
        if selections.get("request_list") and _requests is not None:
            copied = await _requests[1](tx, person, engagement_id, source.id)
        tx.record(
            "engagement.rolled_forward",
            target=Target("engagement", engagement_id),
            after=Ref(
                prior_engagement_id=source.id,
                items_created=copied,
                team_added=len(requested),
                notes_linked=int(bool(selections.get("prior_year_notes"))),
                evidence_copied=0,
            ),
        )
        tx.emit(EngagementCreated(engagement_id=engagement_id))
    return await _created(person, engagement_id, source.id, requested, copied, record_id)


async def _created(
    ctx: AuthContext,
    engagement_id: UUID,
    prior_engagement_id: UUID,
    requested: list[UUID],
    copied: int,
    record_id: UUID | None = None,
) -> Created:
    async with tenant_session(ctx.tenant) as session:
        engagement = await session.get(Engagement, engagement_id)
    if engagement is None:
        raise NotFound("engagement")
    record = record_id or await acceptance_model.record_id_of(ctx.tenant, engagement_id)
    if record is None:
        raise NotFound("acceptance_record")
    if not copied and _requests is not None:
        copied = await _requests[0](ctx, engagement_id)
    return Created(
        engagement_id=engagement_id,
        status=engagement.status,
        prior_engagement_id=prior_engagement_id,
        acceptance_record_id=record,
        requests_created=copied,
        team_requested=requested,
        methodology_version_id=engagement.methodology_version_id,
    )


__all__ = [
    "CATEGORIES",
    "Catalogue",
    "Created",
    "DraftChange",
    "DraftView",
    "RollForwardInvalid",
    "RollForwardSourceNotReleased",
    "RollForwardStale",
    "TeamCarry",
    "TemplateCarry",
    "check_create",
    "create",
    "create_draft",
    "discard_draft",
    "get_draft",
    "next_name",
    "next_year",
    "register_draft_request_copy",
    "update_draft",
]

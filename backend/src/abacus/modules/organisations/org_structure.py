"""Offices, teams and groups (G-01-T08; G-01 sections 3.7, 4.3; ADM-03a).

Offices and teams are filters and review pools, never an access boundary (DEC-30): nothing here
is read by `authorise`, and the one matrix pair `org_structure.read` / `org_structure.manage`
names no office. Reads are firm structure (LIST_EXEMPT, like `offices_in_firm`); every write is a
firm admin's or security admin's with fresh MFA, versioned (409 `stale_version`) and audited.
A person's seats, roster and service lines are identity's; organisations asks through
`identity.api`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Final, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    SeasonalAccessEnds,
    active_staff_among,
    allowed_actions,
    authorise,
    reconcile_service_lines,
    set_seasonal_access_ends,
    staff_holding_line,
    staff_seats_by_office,
)
from abacus.modules.organisations.events import OfficeCreated, OfficeUpdated
from abacus.modules.organisations.models import Office, Team
from abacus.modules.organisations.rosters import rosters, set_roster
from abacus.modules.organisations.slots import office_fact_providers

READ: Final = "org_structure.read"
MANAGE: Final = "org_structure.manage"
_log = get_logger(__name__)
_OFFICE_FIELDS: Final = (
    "name",
    "code",
    "is_hq",
    "time_zone",
    "address_line1",
    "address_line2",
    "city",
    "region_code",
    "postal_code",
    "lead_user_id",
    "default_reviewer_pool_team_id",
)
_TEAM_FIELDS: Final = ("name", "kind", "service_line", "office_id", "lead_user_id")


class OfficeCodeTaken(DomainConflict):
    """Office codes are unique per firm (AC7.2): ADM-03's `?expand=` key and CCH's mapping."""

    code = "office_code_taken"


class OneHq(DomainConflict):
    """A firm has one headquarters office (AC7.2); clear the current one first."""

    code = "one_hq"


class OfficeNameTaken(DomainConflict):
    code = "office_name_taken"


class TeamNameTaken(DomainConflict):
    code = "team_name_taken"


class StaleOrgStructure(DomainConflict):
    code = "stale_version"


class OrgStructureInvalid(DomainInvalid):
    """A value the office or team refuses: an unknown time zone, a lead or member who isn't the
    firm's active staff, a reviewer pool that isn't the firm's team, a service-line team without
    its line (facts name the field)."""

    code = "org_structure_invalid"


@dataclass(frozen=True)
class OfficeView:
    id: UUID
    name: str
    code: str
    is_hq: bool
    time_zone: str
    address_line1: str | None
    address_line2: str | None
    city: str | None
    region_code: str | None
    postal_code: str | None
    lead_user_id: UUID | None
    default_reviewer_pool_team_id: UUID | None
    seats: int
    version: int
    facts: dict[str, int] = field(default_factory=dict[str, int])
    allowed_actions: list[str] = field(default_factory=list[str])


@dataclass(frozen=True)
class TeamView:
    id: UUID
    name: str
    kind: str
    service_line: str | None
    office_id: UUID | None
    lead_user_id: UUID | None
    member_ids: list[UUID]
    version: int
    allowed_actions: list[str] = field(default_factory=list[str])


async def _lines_authority(ctx: AuthContext) -> None:
    """A service-line team's roster and line set people's service lines, which decide
    `in_scope` for practice leaders and quality partners: the authority to set service lines
    directly (`firm.manage_users`, a firm admin with fresh MFA), not just `org_structure.manage`
    (G-01-T08 security review; DEC-317)."""
    await authorise(ctx, "firm.manage_users", Resource.firm(ctx.tenant_id))


def _human(ctx: AuthContext) -> None:
    """INV-1 behind the matrix: only a signed-in person of the firm changes its structure."""
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden(MANAGE, "role")


async def _actions(ctx: AuthContext) -> list[str]:
    return sorted(await allowed_actions(ctx, Resource.firm(ctx.tenant_id), (MANAGE,)))


# --- offices ---------------------------------------------------------------------------------


async def _facts(ctx: AuthContext, office_ids: Sequence[UUID]) -> dict[UUID, dict[str, int]]:
    found: dict[UUID, dict[str, int]] = {office: {} for office in office_ids}
    for name, provider in sorted(office_fact_providers().items()):
        try:
            counts = await provider(ctx.tenant)
        except Exception as exc:  # a registered fact that fails is left out (fail soft)
            _log.warning("office_fact.unavailable", fact=name, error=type(exc).__name__)
            continue
        for office, n in counts.items():
            if office in found:
                found[office][name] = int(n)
    return found


def _office_view(row: Office, seats: int, facts: dict[str, int], actions: list[str]) -> OfficeView:
    return OfficeView(
        row.id,
        row.name,
        row.code,
        row.is_hq,
        row.time_zone,
        row.address_line1,
        row.address_line2,
        row.city,
        row.region_code,
        row.postal_code,
        row.lead_user_id,
        row.default_reviewer_pool_team_id,
        seats,
        row.version,
        facts,
        actions,
    )


async def list_offices(ctx: AuthContext) -> list[OfficeView]:
    """AC7.1: the HQ first, then by name; seats derived from active memberships."""
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        rows = list(
            (await session.execute(select(Office).order_by(Office.is_hq.desc(), Office.name)))
            .scalars()
            .all()
        )
    seats = await staff_seats_by_office(ctx.tenant)
    facts = await _facts(ctx, [r.id for r in rows])
    actions = await _actions(ctx)
    return [_office_view(r, seats.get(r.id, 0), facts[r.id], actions) for r in rows]


async def office(ctx: AuthContext, office_id: UUID) -> OfficeView:
    for found in await list_offices(ctx):
        if found.id == office_id:
            return found
    raise NotFound("office")


def _zone(name: object) -> None:
    try:
        ZoneInfo(str(name))
    except (ZoneInfoNotFoundError, ValueError):
        raise OrgStructureInvalid(facts={"field": "time_zone"}) from None


async def _check_office(
    tx: UnitOfWork, values: Mapping[str, object], office_id: UUID | None
) -> None:
    _zone(values["time_zone"])
    others = select(Office.id).where(Office.id != (office_id or UUID(int=0)))
    if await tx.session.scalar(others.where(Office.code == values["code"]).limit(1)):
        raise OfficeCodeTaken(facts={"code": str(values["code"])})
    if await tx.session.scalar(others.where(Office.name == values["name"]).limit(1)):
        raise OfficeNameTaken
    if values["is_hq"] and await tx.session.scalar(others.where(Office.is_hq).limit(1)):
        raise OneHq
    lead = cast(UUID | None, values["lead_user_id"])
    if lead is not None and lead not in await active_staff_among(tx.session, [lead]):
        raise OrgStructureInvalid(facts={"field": "lead_user_id"})
    pool = cast(UUID | None, values["default_reviewer_pool_team_id"])
    if pool is not None and not await tx.session.scalar(select(Team.id).where(Team.id == pool)):
        raise OrgStructureInvalid(facts={"field": "default_reviewer_pool_team_id"})


def _constraint(exc: IntegrityError) -> str | None:
    orig = exc.orig
    return getattr(orig, "constraint_name", None) or getattr(
        getattr(orig, "__cause__", None), "constraint_name", None
    )


def _conflict(exc: IntegrityError) -> DomainConflict | None:
    """A race the pre-checks lost, as its conflict."""
    return {
        "offices_code_unique": OfficeCodeTaken(),
        "offices_one_hq": OneHq(),
        "offices_tenant_id_name_key": OfficeNameTaken(),
        "teams_tenant_id_name_key": TeamNameTaken(),
    }.get(_constraint(exc) or "")


async def create_office(ctx: AuthContext, values: Mapping[str, object]) -> OfficeView:
    """AC7.2: 409 `office_code_taken`, `one_hq`; 422 for an unknown time zone or lead."""
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    _human(ctx)
    try:
        async with uow(ctx.tenant) as tx:
            await _check_office(tx, values, None)
            office_id = (
                await tx.session.execute(
                    insert(Office)
                    .values(
                        tenant_id=ctx.tenant_id,
                        **{name: values[name] for name in _OFFICE_FIELDS},
                    )
                    .returning(Office.id)
                )
            ).scalar_one()
            tx.record("office.created", target=Target("office", office_id))
            tx.emit(OfficeCreated(office_id=office_id))
    except IntegrityError as exc:
        conflict = _conflict(exc)
        if conflict is None:
            raise
        raise conflict from None
    return await office(ctx, office_id)


async def update_office(
    ctx: AuthContext, office_id: UUID, version: int | None, values: Mapping[str, object]
) -> OfficeView:
    """Every field as sent, against the version read (409 `stale_version`)."""
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    _human(ctx)
    if version is None:
        raise OrgStructureInvalid(facts={"field": "version"})
    try:
        async with uow(ctx.tenant) as tx:
            row = await tx.session.get(Office, office_id)
            if row is None:
                raise NotFound("office")
            if row.version != version:
                raise StaleOrgStructure(facts={"version": row.version})
            await _check_office(tx, values, office_id)
            changed = sorted(n for n in _OFFICE_FIELDS if getattr(row, n) != values[n])
            done = await tx.session.execute(
                update(Office)
                .where(Office.id == office_id, Office.version == version)
                .values(version=Office.version + 1, **{n: values[n] for n in _OFFICE_FIELDS})
                .returning(Office.id)
                .execution_options(synchronize_session=False)
            )
            if done.scalar_one_or_none() is None:
                raise StaleOrgStructure(facts={"version": version})
            tx.record(
                "office.updated",
                target=Target("office", office_id),
                after=Ref(version=version + 1, **dict.fromkeys(changed, 1)),
            )
            tx.emit(OfficeUpdated(office_id=office_id, fields=changed))
    except IntegrityError as exc:
        conflict = _conflict(exc)
        if conflict is None:
            raise
        raise conflict from None
    return await office(ctx, office_id)


# --- teams and groups ------------------------------------------------------------------------


async def _team_views(
    session: AsyncSession, rows: Sequence[Team], actions: list[str]
) -> list[TeamView]:
    members = await rosters(session, [r.id for r in rows])
    return [
        TeamView(
            r.id,
            r.name,
            r.kind,
            r.service_line,
            r.office_id,
            r.lead_user_id,
            members.get(r.id, []),
            r.version,
            actions,
        )
        for r in rows
    ]


async def list_teams(ctx: AuthContext) -> list[TeamView]:
    """AC7.3: teams and groups with their rosters, by name."""
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    actions = await _actions(ctx)
    async with tenant_session(ctx.tenant) as session:
        rows = list((await session.execute(select(Team).order_by(Team.name))).scalars().all())
        return await _team_views(session, rows, actions)


async def team(ctx: AuthContext, team_id: UUID) -> TeamView:
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    actions = await _actions(ctx)
    async with tenant_session(ctx.tenant) as session:
        row = await session.get(Team, team_id)
        if row is None:
            raise NotFound("team")
        return (await _team_views(session, [row], actions))[0]


async def _check_team(tx: UnitOfWork, values: Mapping[str, object], team_id: UUID | None) -> None:
    if (values["kind"] == "service_line") != (values["service_line"] is not None):
        raise OrgStructureInvalid(facts={"field": "service_line"})
    others = select(Team.id).where(Team.id != (team_id or UUID(int=0)))
    if await tx.session.scalar(others.where(Team.name == values["name"]).limit(1)):
        raise TeamNameTaken
    office_id = cast(UUID | None, values["office_id"])
    if office_id is not None and not await tx.session.scalar(
        select(Office.id).where(Office.id == office_id)
    ):
        raise OrgStructureInvalid(facts={"field": "office_id"})
    lead = cast(UUID | None, values["lead_user_id"])
    if lead is not None and lead not in await active_staff_among(tx.session, [lead]):
        raise OrgStructureInvalid(facts={"field": "lead_user_id"})


async def create_team(ctx: AuthContext, values: Mapping[str, object]) -> TeamView:
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    _human(ctx)
    if values["kind"] == "service_line":
        await _lines_authority(ctx)
    try:
        async with uow(ctx.tenant) as tx:
            await _check_team(tx, values, None)
            team_id = (
                await tx.session.execute(
                    insert(Team)
                    .values(
                        tenant_id=ctx.tenant_id, **{name: values[name] for name in _TEAM_FIELDS}
                    )
                    .returning(Team.id)
                )
            ).scalar_one()
            if values["service_line"] is not None:
                # The line is now managed: its holders keep it only through a team (AC7.4).
                for user in await staff_holding_line(tx.session, str(values["service_line"])):
                    await reconcile_service_lines(tx, user)
            tx.record("team.created", target=Target("team", team_id))
    except IntegrityError as exc:
        conflict = _conflict(exc)
        if conflict is None:
            raise
        raise conflict from None
    return await team(ctx, team_id)


async def update_team(
    ctx: AuthContext, team_id: UUID, version: int | None, values: Mapping[str, object]
) -> TeamView:
    """A kind or line change re-derives the members' service lines (AC7.4)."""
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    _human(ctx)
    if version is None:
        raise OrgStructureInvalid(facts={"field": "version"})
    try:
        async with uow(ctx.tenant) as tx:
            row = await tx.session.get(Team, team_id)
            if row is None:
                raise NotFound("team")
            if row.version != version:
                raise StaleOrgStructure(facts={"version": row.version})
            if "service_line" in (row.kind, values["kind"]):
                await _lines_authority(ctx)
            await _check_team(tx, values, team_id)
            changed = sorted(n for n in _TEAM_FIELDS if getattr(row, n) != values[n])
            lines_moved = (row.kind, row.service_line) != (values["kind"], values["service_line"])
            done = await tx.session.execute(
                update(Team)
                .where(Team.id == team_id, Team.version == version)
                .values(version=Team.version + 1, **{n: values[n] for n in _TEAM_FIELDS})
                .returning(Team.id)
                .execution_options(synchronize_session=False)
            )
            if done.scalar_one_or_none() is None:
                raise StaleOrgStructure(facts={"version": version})
            if lines_moved:
                # The members, and anyone holding the line the team now manages (AC7.4).
                affected = set((await rosters(tx.session, [team_id]))[team_id])
                if values["service_line"] is not None:
                    line = str(values["service_line"])
                    affected |= set(await staff_holding_line(tx.session, line))
                for user in sorted(affected, key=str):
                    await reconcile_service_lines(tx, user)
            tx.record(
                "team.updated",
                target=Target("team", team_id),
                after=Ref(version=version + 1, **dict.fromkeys(changed, 1)),
            )
    except IntegrityError as exc:
        conflict = _conflict(exc)
        if conflict is None:
            raise
        raise conflict from None
    return await team(ctx, team_id)


async def set_team_members(ctx: AuthContext, team_id: UUID, member_ids: list[UUID]) -> TeamView:
    """The whole roster; each change audited, and service lines follow (AC7.4)."""
    await authorise(ctx, MANAGE, Resource.firm(ctx.tenant_id))
    _human(ctx)
    async with uow(ctx.tenant) as tx:
        row = await tx.session.get(Team, team_id)
        if row is None:
            raise NotFound("team")
        if row.kind == "service_line":
            await _lines_authority(ctx)
        wanted = list(dict.fromkeys(member_ids))
        if set(wanted) - await active_staff_among(tx.session, wanted):
            raise OrgStructureInvalid(facts={"field": "member_ids"})
        added, removed = await set_roster(tx, ctx.tenant_id, team_id, wanted)
        if added or removed:
            await tx.session.execute(
                update(Team)
                .where(Team.id == team_id)
                .values(version=Team.version + 1)
                .execution_options(synchronize_session=False)
            )
    return await team(ctx, team_id)


async def set_seasonal_group_date(ctx: AuthContext, on: date) -> SeasonalAccessEnds:
    """AC7.3: the Seasonal group's date is every seasonal member's access end (identity's)."""
    return await set_seasonal_access_ends(ctx, on)

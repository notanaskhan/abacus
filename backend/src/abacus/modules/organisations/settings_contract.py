"""The firm-settings family contract, v1: ADM-03's offices, teams and groups (G-01-T02 stub,
live since G-01-T08; ADR-139, P-36). Contract: `docs/contracts/firm-settings.md`; the identity
half is `identity/settings_contract.py`.

Live for every firm (`firm_settings.v2` retired by G-01-T17, DEC-594). Offices and teams are
filters and review pools, never an access boundary (DEC-30): no value here takes part in an
authorisation decision. The service is `org_structure.py`.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import tenant_session
from abacus.kernel.text import SingleLineText
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    GlanceRow,
    active_wall_count,
    current_context,
)
from abacus.modules.organisations import org_structure

Ctx = Annotated[AuthContext, Depends(current_context)]
TeamKind = Literal[
    "service_line",
    "practice_group",
    "eqr_pool",
    "monitoring_reviewers",
    "reviewer_pool",
    "custom",
]
OfficeCode = Annotated[str, Field(pattern=r"^[A-Z]{2,6}$")]
ServiceLine = Literal["audit", "tax", "cas", "advisory"]


class FirmOfficeOut(BaseModel):
    """ADM-03a's office. `seats` is derived from memberships; facts other modules register come
    as counts by key."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("internal")]
    code: Annotated[str, classified("internal")]
    is_hq: Annotated[bool, classified("internal")]
    time_zone: Annotated[str, classified("internal")]
    address_line1: Annotated[str | None, classified("internal")] = None
    address_line2: Annotated[str | None, classified("internal")] = None
    city: Annotated[str | None, classified("internal")] = None
    region_code: Annotated[str | None, classified("internal")] = None
    postal_code: Annotated[str | None, classified("internal")] = None
    lead_user_id: Annotated[UUID | None, classified("internal")] = None
    default_reviewer_pool_team_id: Annotated[UUID | None, classified("internal")] = None
    seats: Annotated[int, classified("internal")]
    facts: Annotated[dict[str, int], classified("internal")] = {}
    allowed_actions: Annotated[list[str], classified("internal")] = []
    version: Annotated[int, classified("internal")] = 0  # G-01-T08: PATCH sends it back


class FirmOfficeIn(BaseModel):
    """409 `office_code_taken`, `one_hq`, `office_name_taken`; the time zone is an IANA name.
    PATCH sends the `version` it read (409 `stale_version`; 422 without one)."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    version: Annotated[int | None, Field(default=None, ge=0), classified("internal")]

    name: Annotated[SingleLineText, Field(min_length=1, max_length=120), classified("internal")]
    code: Annotated[OfficeCode, classified("internal")]
    is_hq: Annotated[bool, classified("internal")] = False
    time_zone: Annotated[str, Field(max_length=64), classified("internal")]
    address_line1: Annotated[
        SingleLineText | None, Field(default=None, max_length=200), classified("internal")
    ]
    address_line2: Annotated[
        SingleLineText | None, Field(default=None, max_length=200), classified("internal")
    ]
    city: Annotated[
        SingleLineText | None, Field(default=None, max_length=120), classified("internal")
    ]
    region_code: Annotated[str | None, Field(default=None, max_length=8), classified("internal")]
    postal_code: Annotated[str | None, Field(default=None, max_length=16), classified("internal")]
    lead_user_id: Annotated[UUID | None, classified("internal")] = None
    default_reviewer_pool_team_id: Annotated[UUID | None, classified("internal")] = None


class FirmTeamOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("internal")]
    kind: Annotated[TeamKind, classified("internal")]
    office_id: Annotated[UUID | None, classified("internal")] = None
    lead_user_id: Annotated[UUID | None, classified("internal")] = None
    member_ids: Annotated[list[UUID], classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")] = []
    service_line: Annotated[ServiceLine | None, classified("internal")] = None  # G-01-T08
    version: Annotated[int, classified("internal")] = 0


class FirmTeamIn(BaseModel):
    """A `service_line` team names its line, and only it does (422 `org_structure_invalid`);
    409 `team_name_taken`. PATCH sends the `version` it read."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    name: Annotated[SingleLineText, Field(min_length=1, max_length=120), classified("internal")]
    kind: Annotated[TeamKind, classified("internal")]
    office_id: Annotated[UUID | None, classified("internal")] = None
    lead_user_id: Annotated[UUID | None, classified("internal")] = None
    service_line: Annotated[ServiceLine | None, classified("internal")] = None
    version: Annotated[int | None, Field(default=None, ge=0), classified("internal")]


class FirmTeamMembersIn(BaseModel):
    """The whole roster; a service-line team also sets the members' service lines (AC7.4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    member_ids: Annotated[list[UUID], Field(max_length=500), classified("internal")]


class SeasonalAccessEndsIn(BaseModel):
    """ADM-03a's Seasonal group: one date for every seasonal member, one audit row each."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    access_ends_on: Annotated[date, classified("internal")]


class SeasonalAccessEndsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_ends_on: Annotated[date, classified("internal")]
    members: Annotated[int, classified("internal")]


def _office_out(view: org_structure.OfficeView) -> FirmOfficeOut:
    return FirmOfficeOut.model_validate(asdict(view))


def _team_out(view: org_structure.TeamView) -> FirmTeamOut:
    return FirmTeamOut.model_validate(asdict(view))


def _office_values(body: FirmOfficeIn) -> dict[str, object]:
    return body.model_dump(exclude={"version"})


def _team_values(body: FirmTeamIn) -> dict[str, object]:
    return body.model_dump(exclude={"version"})


org_settings_router = AbacusRouter(prefix="/v1/firm", tags=["firm-settings"])


@org_settings_router.get(
    "/offices", action="org_structure.read", response_model=list[FirmOfficeOut]
)
async def offices_route(ctx: Ctx) -> list[FirmOfficeOut]:
    """ADM-03a: the HQ first, then by name, with derived seats and registered facts."""
    return [_office_out(o) for o in await org_structure.list_offices(ctx)]


@org_settings_router.post(
    "/offices",
    action="org_structure.manage",
    response_model=FirmOfficeOut,
    status_code=201,
    errors=(409,),
)
async def create_office_route(body: FirmOfficeIn, ctx: Ctx) -> FirmOfficeOut:
    """Fresh MFA."""
    return _office_out(await org_structure.create_office(ctx, _office_values(body)))


@org_settings_router.patch(
    "/offices/{office_id}",
    action="org_structure.manage",
    response_model=FirmOfficeOut,
    errors=(409,),
)
async def update_office_route(office_id: UUID, body: FirmOfficeIn, ctx: Ctx) -> FirmOfficeOut:
    return _office_out(
        await org_structure.update_office(ctx, office_id, body.version, _office_values(body))
    )


@org_settings_router.get("/teams", action="org_structure.read", response_model=list[FirmTeamOut])
async def teams_route(ctx: Ctx) -> list[FirmTeamOut]:
    return [_team_out(t) for t in await org_structure.list_teams(ctx)]


@org_settings_router.post(
    "/teams",
    action="org_structure.manage",
    response_model=FirmTeamOut,
    status_code=201,
    errors=(409,),
)
async def create_team_route(body: FirmTeamIn, ctx: Ctx) -> FirmTeamOut:
    return _team_out(await org_structure.create_team(ctx, _team_values(body)))


@org_settings_router.patch(
    "/teams/{team_id}", action="org_structure.manage", response_model=FirmTeamOut, errors=(409,)
)
async def update_team_route(team_id: UUID, body: FirmTeamIn, ctx: Ctx) -> FirmTeamOut:
    return _team_out(
        await org_structure.update_team(ctx, team_id, body.version, _team_values(body))
    )


@org_settings_router.put(
    "/teams/{team_id}/members", action="org_structure.manage", response_model=FirmTeamOut
)
async def set_team_members_route(team_id: UUID, body: FirmTeamMembersIn, ctx: Ctx) -> FirmTeamOut:
    return _team_out(await org_structure.set_team_members(ctx, team_id, list(body.member_ids)))


@org_settings_router.put(
    "/groups/seasonal/access-ends",
    action="firm.manage_users",
    response_model=SeasonalAccessEndsOut,
)
async def set_seasonal_access_ends_route(
    body: SeasonalAccessEndsIn, ctx: Ctx
) -> SeasonalAccessEndsOut:
    """Fresh MFA; one audit row per seasonal member."""
    done = await org_structure.set_seasonal_group_date(ctx, body.access_ends_on)
    return SeasonalAccessEndsOut(access_ends_on=done.access_ends_on, members=done.members)


# --- At a glance: Offices & teams (G-01-T04; AC2.1, AC2.4) --------------------------------------

_COUNTS = text("SELECT (SELECT count(*) FROM offices), (SELECT count(*) FROM teams)")


async def offices_glance(ctx: AuthContext) -> GlanceRow | None:
    async with tenant_session(ctx.tenant) as session:
        offices, teams = (await session.execute(_COUNTS)).one()
    facts = {"offices": int(offices), "teams": int(teams)}
    walls = await active_wall_count(ctx)
    if walls is not None:
        facts["walls"] = walls
    return GlanceRow("offices_teams", "ok", facts, "/settings/offices")

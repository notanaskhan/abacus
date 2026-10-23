"""The firm-settings family contract, v1: ADM-03's offices, teams and groups (G-01-T02 stub;
ADR-139, P-36). Contract: `docs/contracts/firm-settings.md`; the identity half is
`identity/settings_contract.py`.

Behind `firm_settings.v2`: off, every route here answers 404; on, 501 `not_implemented` until
G-01-T08 (offices, teams and groups live). Offices and teams are filters and review pools, never
an access boundary (DEC-30): no value here takes part in an authorisation decision.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import FIRM_SETTINGS_V2
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.text import SingleLineText
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

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


class FirmOfficeIn(BaseModel):
    """409 `office_code_taken`, `one_hq`; the time zone is an IANA name."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

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


class FirmTeamIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    name: Annotated[SingleLineText, Field(min_length=1, max_length=120), classified("internal")]
    kind: Annotated[TeamKind, classified("internal")]
    office_id: Annotated[UUID | None, classified("internal")] = None
    lead_user_id: Annotated[UUID | None, classified("internal")] = None


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


async def _stub(ctx: AuthContext) -> NoReturn:
    if not await flag_enabled(ctx.tenant, FIRM_SETTINGS_V2):
        raise NotFound("firm_settings.v2")
    raise NotImplementedYet


org_settings_router = AbacusRouter(prefix="/v1/firm", tags=["firm-settings"])


@org_settings_router.get(
    "/offices", action="org_structure.read", response_model=list[FirmOfficeOut], errors=(501,)
)
async def offices_route(ctx: Ctx) -> list[FirmOfficeOut]:
    await _stub(ctx)


@org_settings_router.post(
    "/offices",
    action="org_structure.manage",
    response_model=FirmOfficeOut,
    status_code=201,
    errors=(409, 501),
)
async def create_office_route(body: FirmOfficeIn, ctx: Ctx) -> FirmOfficeOut:
    """Fresh MFA."""
    await _stub(ctx)


@org_settings_router.patch(
    "/offices/{office_id}",
    action="org_structure.manage",
    response_model=FirmOfficeOut,
    errors=(409, 501),
)
async def update_office_route(office_id: UUID, body: FirmOfficeIn, ctx: Ctx) -> FirmOfficeOut:
    await _stub(ctx)


@org_settings_router.get(
    "/teams", action="org_structure.read", response_model=list[FirmTeamOut], errors=(501,)
)
async def teams_route(ctx: Ctx) -> list[FirmTeamOut]:
    await _stub(ctx)


@org_settings_router.post(
    "/teams",
    action="org_structure.manage",
    response_model=FirmTeamOut,
    status_code=201,
    errors=(501,),
)
async def create_team_route(body: FirmTeamIn, ctx: Ctx) -> FirmTeamOut:
    await _stub(ctx)


@org_settings_router.patch(
    "/teams/{team_id}", action="org_structure.manage", response_model=FirmTeamOut, errors=(501,)
)
async def update_team_route(team_id: UUID, body: FirmTeamIn, ctx: Ctx) -> FirmTeamOut:
    await _stub(ctx)


@org_settings_router.put(
    "/teams/{team_id}/members",
    action="org_structure.manage",
    response_model=FirmTeamOut,
    errors=(501,),
)
async def set_team_members_route(team_id: UUID, body: FirmTeamMembersIn, ctx: Ctx) -> FirmTeamOut:
    await _stub(ctx)


@org_settings_router.put(
    "/groups/seasonal/access-ends",
    action="firm.manage_users",
    response_model=SeasonalAccessEndsOut,
    errors=(501,),
)
async def set_seasonal_access_ends_route(
    body: SeasonalAccessEndsIn, ctx: Ctx
) -> SeasonalAccessEndsOut:
    await _stub(ctx)

"""The firm-settings family contract, v1: ADM-01, ADM-02 and ADM-03's identity half (G-01-T02
stub; ADR-139, P-36). Contract: `docs/contracts/firm-settings.md`.

Behind `firm_settings.v2`: off, every route here answers 404; on, 501 `not_implemented` until
the task that implements it (G-01-T04 settings; T05 people; T09 walls v2; T12 service lines;
T13 annual independence). Offices and teams are organisations' (`organisations/
settings_contract.py`).

Routes that already exist keep their paths and grow additively in their tasks:
`GET /v1/firm/staff`, `POST /v1/firm/staff/invitations` (+ resend, revoke),
`PUT /v1/firm/staff/{user_id}/role`, `POST /v1/firm/staff/{user_id}/revoke` (deactivate's alias
for one release), `GET /v1/walls`, `POST /v1/walls`, `POST /v1/walls/{wall_id}/remove`. Their v2
shapes are fixed here (`StaffRowV2Out`, `WallV2Out`) and tested with the rest.

Walls use 404 semantics everywhere (INV-3, DEC-43): no model here has a hidden or hidden-count
field, or any count derived from walled rows. `region` is never writable (AC1.5). Every write is
a live person's (INV-1): the matrix denies agent and system.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import FIRM_SETTINGS_V2
from abacus.kernel._statuses import (
    AnnualIndependenceStatus,
    MembershipStatus,
    WallApprovalStatus,
)
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.kernel.text import MultiLineText, SingleLineText
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.routing import AbacusRouter, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]

# The settings sections (ADM-01 §3.1; the order is the section list's).
Section = Literal["general", "profile", "defaults", "plan"]
SectionGroup = Literal["firm", "people", "security", "data", "quality", "integrations"]
GlanceTone = Literal["ok", "attention", "partial", "none"]
RoleTemplate = Literal[
    "partner",
    "manager",
    "tax_reviewer",
    "senior",
    "staff",
    "tax_preparer",
    "firm_admin",
    "it_security",
]
Level = Literal["partner", "manager", "senior", "staff", "seasonal", "admin"]
Band = Literal["partners", "managers", "seniors", "staff", "seasonal", "operations"]
DeactivationReason = Literal["manual", "access_ended", "scim_deprovisioned"]
GridCell = Literal["allow", "conditional", "delegated", "deny", "locked"]
GridSource = Literal["matrix", "policy"]
AnnualDecision = Literal["confirmed", "declined"]
AnnualStatus = AnnualIndependenceStatus  # C2 `annual_independence`
ServiceLine = Literal["audit", "tax", "cas", "advisory"]
ContentVisibility = Literal["engagement_team_only", "service_line"]
CrossLineAccess = Literal["handoffs_only", "by_request"]
WallReason = Literal[
    "personal_relationship", "financial_interest", "relative", "prior_employment", "other"
]
WallBlocker = Literal["relationship_partner", "wall_exists", "own_wall"]


# --- ADM-01: overview and sections ---------------------------------------------------------------


class SettingsSectionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    group: Annotated[SectionGroup, classified("internal")]
    visible: Annotated[bool, classified("internal")]
    planned: Annotated[bool, classified("internal")] = False  # listed, not built yet


class GlanceRowOut(BaseModel):
    """One registered area's status line ("46 of 46 seats · 0 pending invites"); words come
    from the copy registry by `key` and `facts`. `unavailable` when its provider failed."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    tone: Annotated[GlanceTone, classified("internal")]
    facts: Annotated[dict[str, int], classified("internal")] = {}
    href: Annotated[str | None, classified("internal")] = None
    unavailable: Annotated[bool, classified("internal")] = False


class SettingsOverviewOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    firm_name: Annotated[str, classified("confidential")]
    sections: Annotated[list[SettingsSectionOut], classified("internal")]
    at_a_glance: Annotated[list[GlanceRowOut], classified("internal")]
    as_of: Annotated[datetime, classified("internal")]


class SettingValueOut(BaseModel):
    """A registered key with its value. Values are JSON scalars; a Confidential key's value is
    never in an audit row (AC1.2)."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    value: Annotated[str | int | bool | None, classified("confidential")]
    editable: Annotated[bool, classified("internal")]


class SettingsSectionValuesOut(BaseModel):
    """A section's keys; Plan & seats is absent for `security_admin` (AC1.7)."""

    model_config = ConfigDict(frozen=True)

    section: Annotated[Section, classified("internal")]
    values: Annotated[list[SettingValueOut], classified("internal")]
    version: Annotated[int, classified("internal")]
    read_only_reason: Annotated[str | None, classified("internal")] = None
    allowed_actions: Annotated[list[str], classified("internal")] = []


class SettingsPatchIn(BaseModel):
    """Only registered keys (422 `unknown_setting`); `version` as read (409 `stale_version`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Annotated[int, Field(ge=0), classified("internal")]
    values: Annotated[
        dict[str, str | int | bool | None], Field(max_length=50), classified("confidential")
    ]


# --- ADM-02: people ------------------------------------------------------------------------------


class SignInOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    at: Annotated[datetime, classified("internal")]
    method: Annotated[str, classified("internal")]  # "microsoft_sso", ...
    mfa: Annotated[bool, classified("internal")]
    ip: Annotated[str | None, classified("confidential")] = None


class StaffRowV2Out(BaseModel):
    """ADM-02a's row: the v2 shape `GET /v1/firm/staff` grows into (G-01-T05)."""

    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    email: Annotated[str, classified("confidential")]
    title: Annotated[str | None, classified("confidential")] = None
    role_template: Annotated[RoleTemplate, classified("internal")]
    level: Annotated[Level, classified("internal")]
    band: Annotated[Band, classified("internal")]
    status: Annotated[MembershipStatus, classified("internal")]
    office_id: Annotated[UUID | None, classified("internal")] = None
    team_ids: Annotated[list[UUID], classified("internal")] = []
    service_lines: Annotated[list[ServiceLine], classified("internal")] = []
    access_ends_on: Annotated[date | None, classified("internal")] = None
    offshore: Annotated[bool, classified("internal")] = False
    last_sign_in_at: Annotated[datetime | None, classified("internal")] = None
    invitation_expires_on: Annotated[date | None, classified("internal")] = None
    allowed_actions: Annotated[list[str], classified("internal")] = []


class PersonOut(BaseModel):
    """ADM-02d's drawer."""

    model_config = ConfigDict(frozen=True)

    row: Annotated[StaffRowV2Out, classified("confidential")]
    firm_role: Annotated[str | None, classified("internal")] = None
    security_admin: Annotated[bool, classified("internal")] = False
    wall_ids: Annotated[
        list[UUID], classified("internal")
    ] = []  # the person's own walls (ADM-02d)
    assignment_count: Annotated[int, classified("internal")] = 0
    recent_sign_ins: Annotated[list[SignInOut], classified("confidential")] = []
    annual_independence: Annotated[AnnualStatus, classified("internal")] = (
        AnnualIndependenceStatus.NOT_YET
    )
    version: Annotated[int, classified("internal")]


class PersonPatchIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    version: Annotated[int, Field(ge=0), classified("internal")]
    title: Annotated[
        SingleLineText | None, Field(default=None, max_length=120), classified("confidential")
    ]
    office_id: Annotated[UUID | None, classified("internal")] = None
    team_ids: Annotated[list[UUID] | None, Field(max_length=20), classified("internal")] = None
    service_lines: Annotated[list[ServiceLine] | None, classified("internal")] = None
    access_ends_on: Annotated[date | None, classified("internal")] = None
    offshore: Annotated[bool | None, classified("internal")] = None


class SecurityRoleIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    security_admin: Annotated[bool, classified("internal")]


class DeactivateIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    reason: Annotated[DeactivationReason, classified("internal")] = "manual"
    note: Annotated[
        MultiLineText | None, Field(default=None, max_length=500), classified("confidential")
    ]


class GridRowOut(BaseModel):
    """One capability row; cells per template computed from the compiled matrix and the firm's
    overrides, or from `role-templates.yaml` for actions not yet in the matrix."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    actions: Annotated[list[str], classified("internal")]
    cells: Annotated[dict[str, GridCell], classified("internal")]
    conditions: Annotated[dict[str, str], classified("internal")] = {}
    source: Annotated[GridSource, classified("internal")]
    locked: Annotated[bool, classified("internal")] = False


class RoleTemplateOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[RoleTemplate, classified("internal")]
    levels: Annotated[list[Level], classified("internal")]
    member_count: Annotated[int, classified("internal")]


class RoleTemplatesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    templates: Annotated[list[RoleTemplateOut], classified("internal")]
    grid: Annotated[list[GridRowOut], classified("internal")]


class AnnualRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    status: Annotated[AnnualStatus, classified("internal")]
    decided_at: Annotated[datetime | None, classified("internal")] = None
    note: Annotated[str | None, classified("confidential")] = None


class AnnualIndependenceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    year: Annotated[int, classified("internal")]
    rows: Annotated[list[AnnualRowOut], classified("internal")]
    counts: Annotated[dict[str, int], classified("internal")]


class AnnualConfirmIn(BaseModel):
    """For oneself only: no user id in the body (AC6.3, structural)."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    year: Annotated[int, Field(ge=2025, le=2100), classified("internal")]
    decision: Annotated[AnnualDecision, classified("internal")]
    statement_version: Annotated[int, Field(ge=1), classified("internal")]
    note: Annotated[
        MultiLineText | None, Field(default=None, max_length=1000), classified("confidential")
    ]


class AnnualConfirmedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    year: Annotated[int, classified("internal")]
    decision: Annotated[AnnualDecision, classified("internal")]
    decided_at: Annotated[datetime, classified("internal")]


# --- ADM-03: service lines, offshore, walls v2 ---------------------------------------------------


class ServiceLinePolicyOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    service_line: Annotated[ServiceLine, classified("internal")]
    enabled: Annotated[bool, classified("internal")]
    lead_user_id: Annotated[UUID | None, classified("internal")] = None
    content_visible_to: Annotated[ContentVisibility, classified("internal")]
    cross_line_access: Annotated[CrossLineAccess, classified("internal")]
    version: Annotated[int, classified("internal")]


class ServiceLinePolicyIn(BaseModel):
    """Audit is always `engagement_team_only` (422 `audit_locked`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Annotated[int, Field(ge=0), classified("internal")]
    enabled: Annotated[bool, classified("internal")]
    lead_user_id: Annotated[UUID | None, classified("internal")] = None
    content_visible_to: Annotated[ContentVisibility, classified("internal")]
    cross_line_access: Annotated[CrossLineAccess, classified("internal")]


class OffshoreOut(BaseModel):
    """ADM-03d. The two policy toggles are always on and locked (AC9.3)."""

    model_config = ConfigDict(frozen=True)

    member_ids: Annotated[list[UUID], classified("internal")]
    consented_client_count: Annotated[int, classified("internal")]
    block_without_consent: Annotated[Literal[True], classified("internal")] = True
    mask_tins: Annotated[Literal[True], classified("internal")] = True


class WallV2Out(BaseModel):
    """The v2 shape `GET /v1/walls` grows into (G-01-T09)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    reason_code: Annotated[WallReason, classified("internal")]
    reason_text: Annotated[str | None, classified("confidential")] = None
    created_by: Annotated[UUID, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    approver_user_id: Annotated[UUID | None, classified("internal")] = None
    approval_status: Annotated[WallApprovalStatus, classified("internal")]
    approved_at: Annotated[datetime | None, classified("internal")] = None
    allowed_actions: Annotated[list[str], classified("internal")] = []


class WallPreviewOut(BaseModel):
    """What adding the wall would do: blockers and the effect counts (AC8.1, AC8.3)."""

    model_config = ConfigDict(frozen=True)

    blockers: Annotated[list[WallBlocker], classified("internal")]
    assignments_ended: Annotated[int, classified("internal")]


class WallEventOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Annotated[str, classified("internal")]
    at: Annotated[datetime, classified("internal")]
    actor_user_id: Annotated[UUID | None, classified("internal")] = None


# --- routes --------------------------------------------------------------------------------------


async def _stub(ctx: AuthContext) -> NoReturn:
    if not await flag_enabled(ctx.tenant, FIRM_SETTINGS_V2):
        raise NotFound("firm_settings.v2")
    raise NotImplementedYet


settings_router = AbacusRouter(prefix="/v1/firm", tags=["firm-settings"])
walls_v2_router = AbacusRouter(prefix="/v1/walls", tags=["firm-settings"])
me_router = AbacusRouter(prefix="/v1/me", tags=["firm-settings"])


@settings_router.get(
    "/settings/overview",
    action="firm.read_settings",
    response_model=SettingsOverviewOut,
    errors=(501,),
)
async def settings_overview_route(ctx: Ctx) -> SettingsOverviewOut:
    """ADM-01: sections for the caller and At a glance (each provider within 500 ms)."""
    await _stub(ctx)


@settings_router.get(
    "/settings/{section}",
    action="firm.read_settings",
    response_model=SettingsSectionValuesOut,
    errors=(501,),
)
async def settings_section_route(section: Section, ctx: Ctx) -> SettingsSectionValuesOut:
    await _stub(ctx)


@settings_router.patch(
    "/settings/{section}",
    action="firm.manage_settings",
    response_model=SettingsSectionValuesOut,
    errors=(409, 501),
)
async def update_settings_section_route(
    section: Section, body: SettingsPatchIn, ctx: Ctx
) -> SettingsSectionValuesOut:
    """Fresh MFA; 422 `unknown_setting`, `display_name_required`; 409 `stale_version`."""
    await _stub(ctx)


@settings_router.get(
    "/staff/{user_id}", action="firm.read_people", response_model=PersonOut, errors=(501,)
)
async def person_route(user_id: UUID, ctx: Ctx) -> PersonOut:
    await _stub(ctx)


@settings_router.patch(
    "/staff/{user_id}", action="firm.manage_users", response_model=PersonOut, errors=(409, 501)
)
async def update_person_route(user_id: UUID, body: PersonPatchIn, ctx: Ctx) -> PersonOut:
    """Fresh MFA; 409 `stale_version`, `offshore_assignment_conflict`."""
    await _stub(ctx)


@settings_router.put(
    "/staff/{user_id}/security-role",
    action="security_role.assign",
    response_model=PersonOut,
    errors=(409, 501),
)
async def set_security_role_route(user_id: UUID, body: SecurityRoleIn, ctx: Ctx) -> PersonOut:
    """`security_admin` only; 409 `last_admin`."""
    await _stub(ctx)


@settings_router.post(
    "/staff/{user_id}/deactivate",
    action="firm.manage_users",
    response_model=PersonOut,
    errors=(409, 501),
)
async def deactivate_person_route(user_id: UUID, body: DeactivateIn, ctx: Ctx) -> PersonOut:
    """Ends sessions and frees the seat; 409 `last_admin`. `/revoke` stays an alias."""
    await _stub(ctx)


@settings_router.get(
    "/role-templates", action="firm.read_people", response_model=RoleTemplatesOut, errors=(501,)
)
async def role_templates_route(ctx: Ctx) -> RoleTemplatesOut:
    await _stub(ctx)


@settings_router.get(
    "/independence/annual",
    action="independence.annual_read",
    response_model=AnnualIndependenceOut,
    errors=(501,),
)
async def annual_independence_route(
    ctx: Ctx, year: Annotated[int, Query(ge=2025, le=2100)]
) -> AnnualIndependenceOut:
    await _stub(ctx)


@settings_router.get(
    "/service-lines",
    action="firm.read_settings",
    response_model=list[ServiceLinePolicyOut],
    errors=(501,),
)
async def service_lines_route(ctx: Ctx) -> list[ServiceLinePolicyOut]:
    await _stub(ctx)


@settings_router.put(
    "/service-lines/{line}",
    action="service_line_policy.manage",
    response_model=ServiceLinePolicyOut,
    errors=(409, 501),
)
async def set_service_line_route(
    line: ServiceLine, body: ServiceLinePolicyIn, ctx: Ctx
) -> ServiceLinePolicyOut:
    """Fresh MFA; 422 `audit_locked`; 409 `stale_version`."""
    await _stub(ctx)


@settings_router.get(
    "/offshore", action="firm.read_settings", response_model=OffshoreOut, errors=(501,)
)
async def offshore_route(ctx: Ctx) -> OffshoreOut:
    await _stub(ctx)


@walls_v2_router.get(
    "/preview", action="wall.create", response_model=WallPreviewOut, errors=(501,)
)
async def wall_preview_route(
    ctx: Ctx, user_id: Annotated[UUID, Query()], client_id: Annotated[UUID, Query()]
) -> WallPreviewOut:
    await _stub(ctx)


@walls_v2_router.post(
    "/{wall_id}/approve", action="wall.approve", response_model=WallV2Out, errors=(409, 501)
)
async def approve_wall_route(wall_id: UUID, ctx: Ctx) -> WallV2Out:
    """The named partner only, fresh MFA; 409 `already_approved`; 403 `not_named_approver`."""
    await _stub(ctx)


@walls_v2_router.get(
    "/{wall_id}/events",
    action="wall.list",
    response_model=ListPage[WallEventOut],
    errors=(501,),
)
async def wall_events_route(
    wall_id: UUID, ctx: Ctx, cursor: Annotated[str | None, Query(max_length=512)] = None
) -> ListPage[WallEventOut]:
    await _stub(ctx)


@me_router.post(
    "/independence/annual",
    action="independence.annual_confirm",
    response_model=AnnualConfirmedOut,
    status_code=201,
    errors=(501,),
)
async def confirm_annual_independence_route(body: AnnualConfirmIn, ctx: Ctx) -> AnnualConfirmedOut:
    """Oneself only (`independence.annual_confirm`); agents and the system can't confirm."""
    await _stub(ctx)

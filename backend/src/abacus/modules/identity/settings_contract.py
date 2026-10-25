"""The firm-settings family contract, v1: ADM-01, ADM-02 and ADM-03's identity half (G-01-T02
stub; ADR-139, P-36). Contract: `docs/contracts/firm-settings.md`.

Behind `firm_settings.v2`: off, every route here answers 404; on, 501 `not_implemented` until
the task that implements it (G-01-T04 settings; T05 people; T09 walls v2; T12 service lines;
T13 annual independence); all are live now. Offices and teams are organisations' (`organisations/
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

from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated, Literal, NoReturn, cast
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
from abacus.kernel.listing import CursorInvalid, ListPage
from abacus.kernel.text import MultiLineText, SingleLineText
from abacus.modules.identity import offshore, people, service_lines, settings_registry, walls
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.routing import AbacusRouter, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]

# The settings sections (ADM-01 §3.1; the order is the section list's).
Section = Literal["profile", "defaults", "plan"]
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
    """ADM-02a's row: the v2 shape `GET /v1/firm/staff` grew into (G-01-T05). A pending
    invitation is a row too (ADM-02f): `invitation_id` set, `user_id` null."""

    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID | None, classified("internal")]
    invitation_id: Annotated[UUID | None, classified("internal")] = None
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
    # The date access is set to end; G-01-T13's access-end job enforces it (DEC-285).
    access_ends_on: Annotated[date | None, classified("internal")] = None
    offshore: Annotated[bool, classified("internal")] = False
    # This firm's sign-ins only; none for someone who belongs to another firm (DEC-286).
    last_sign_in_at: Annotated[datetime | None, classified("internal")] = None
    invitation_expires_on: Annotated[date | None, classified("internal")] = None
    deactivated_on: Annotated[date | None, classified("internal")] = None  # ADM-02e
    allowed_actions: Annotated[list[str], classified("internal")] = []


class StaffTalliesOut(BaseModel):
    """ADM-02a's tally strip, firm-wide (never filtered). `seats_used` counts pending invitations
    (AC3.4); `seats_total` is the provisioned seat count (DEC-285); `walls_active` is present only
    for a reader who may list walls (AC2.4)."""

    model_config = ConfigDict(frozen=True)

    seats_used: Annotated[int, classified("internal")]
    seats_total: Annotated[int | None, classified("internal")] = None
    seats_pending: Annotated[int, classified("internal")]
    partners: Annotated[int, classified("internal")]
    professionals: Annotated[int, classified("internal")]
    operations: Annotated[int, classified("internal")]
    sso_mfa: Annotated[int, classified("internal")]
    signed_in_of: Annotated[int, classified("internal")]
    walls_active: Annotated[int | None, classified("internal")] = None
    seasonal: Annotated[int, classified("internal")]
    seasonal_access_ends_on: Annotated[date | None, classified("internal")] = None


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


async def _gate(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, FIRM_SETTINGS_V2):
        raise NotFound("firm_settings.v2")


async def _stub(ctx: AuthContext) -> NoReturn:
    await _gate(ctx)
    raise NotImplementedYet


def _section(view: settings_registry.SectionView) -> SettingsSectionValuesOut:
    return SettingsSectionValuesOut(
        section=view.section,
        values=[
            SettingValueOut(key=k.key, value=v, editable=k.editable and not view.read_only_reason)
            for k, v in view.values
        ],
        version=view.version,
        read_only_reason=view.read_only_reason,
        allowed_actions=view.allowed_actions,
    )


settings_router = AbacusRouter(prefix="/v1/firm", tags=["firm-settings"])
walls_v2_router = AbacusRouter(prefix="/v1/walls", tags=["firm-settings"])
me_router = AbacusRouter(prefix="/v1/me", tags=["firm-settings"])


@settings_router.get(
    "/settings/overview", action="firm.read_settings", response_model=SettingsOverviewOut
)
async def settings_overview_route(ctx: Ctx) -> SettingsOverviewOut:
    """ADM-01: sections for the caller and At a glance (each provider within 500 ms)."""
    await _gate(ctx)
    found = await settings_registry.overview(ctx)
    return SettingsOverviewOut(
        firm_name=found.firm_name,
        sections=[
            SettingsSectionOut(key=key, group="firm", visible=visible)
            for key, visible in found.sections
        ],
        at_a_glance=[
            GlanceRowOut(
                key=r.key, tone=r.tone, facts=r.facts, href=r.href, unavailable=r.unavailable
            )
            for r in found.at_a_glance
        ],
        as_of=found.as_of,
    )


@settings_router.get(
    "/settings/{section}", action="firm.read_settings", response_model=SettingsSectionValuesOut
)
async def settings_section_route(section: Section, ctx: Ctx) -> SettingsSectionValuesOut:
    await _gate(ctx)
    return _section(await settings_registry.read_section(ctx, section))


@settings_router.patch(
    "/settings/{section}",
    action="firm.manage_settings",
    response_model=SettingsSectionValuesOut,
    errors=(409,),
)
async def update_settings_section_route(
    section: Section, body: SettingsPatchIn, ctx: Ctx
) -> SettingsSectionValuesOut:
    """Fresh MFA; 422 `unknown_setting`, `display_name_required`; 409 `stale_version`."""
    await _gate(ctx)
    await settings_registry.save_section(ctx, section, body.version, body.values)
    return _section(await settings_registry.read_section(ctx, section))


def row_out(row: people.StaffRow) -> StaffRowV2Out:
    return StaffRowV2Out(
        user_id=row.user_id,
        invitation_id=row.invitation_id,
        display_name=row.display_name,
        email=row.email,
        title=row.title,
        role_template=row.role_template,
        level=row.level,
        band=row.band,
        status=MembershipStatus(row.status),
        office_id=row.office_id,
        team_ids=row.team_ids,
        service_lines=cast(list[ServiceLine], row.service_lines),
        access_ends_on=row.access_ends_on,
        offshore=row.offshore,
        last_sign_in_at=row.last_sign_in_at,
        invitation_expires_on=row.invitation_expires_on,
        deactivated_on=row.deactivated_on,
        allowed_actions=row.allowed_actions,
    )


def tallies_out(t: people.Tallies) -> StaffTalliesOut:
    return StaffTalliesOut.model_validate(asdict(t))


async def _person_out(ctx: AuthContext, user_id: UUID) -> PersonOut:
    found = await people.staff_user(ctx, user_id)
    return PersonOut(
        row=row_out(found.row),
        firm_role=found.firm_role,
        security_admin=found.firm_role == "security_admin",
        wall_ids=found.wall_ids,
        assignment_count=found.assignment_count,
        recent_sign_ins=[
            SignInOut(at=s.at, method=s.method, mfa=s.mfa) for s in found.recent_sign_ins
        ],
        version=found.version,
    )


@settings_router.get("/staff/{user_id}", action="firm.read_people", response_model=PersonOut)
async def person_route(user_id: UUID, ctx: Ctx) -> PersonOut:
    """ADM-02d: the person's template, attributes, walls, assignments and last sign-ins."""
    await _gate(ctx)
    return await _person_out(ctx, user_id)


@settings_router.patch(
    "/staff/{user_id}", action="firm.manage_users", response_model=PersonOut, errors=(409,)
)
async def update_person_route(user_id: UUID, body: PersonPatchIn, ctx: Ctx) -> PersonOut:
    """Fresh MFA; a field sent as null clears it; 409 `stale_version`,
    `offshore_assignment_conflict`; 422 `access_ends_required`."""
    await _gate(ctx)
    changes = {name: getattr(body, name) for name in body.model_fields_set if name != "version"}
    await people.update_person(ctx, user_id, body.version, changes)
    return await _person_out(ctx, user_id)


@settings_router.put(
    "/staff/{user_id}/security-role",
    action="security_role.assign",
    response_model=PersonOut,
    errors=(409,),
)
async def set_security_role_route(user_id: UUID, body: SecurityRoleIn, ctx: Ctx) -> PersonOut:
    """`security_admin` only; 409 `last_admin`, `firm_role_held`."""
    await _gate(ctx)
    await people.set_security_role(ctx, user_id, body.security_admin)
    return await _person_out(ctx, user_id)


@settings_router.post(
    "/staff/{user_id}/deactivate",
    action="firm.manage_users",
    response_model=PersonOut,
    errors=(409,),
)
async def deactivate_person_route(user_id: UUID, body: DeactivateIn, ctx: Ctx) -> PersonOut:
    """Ends sessions and frees the seat; 409 `last_admin`. `/revoke` stays an alias."""
    await _gate(ctx)
    await people.deactivate(ctx, user_id, body.reason)
    return await _person_out(ctx, user_id)


@settings_router.get("/role-templates", action="firm.read_people", response_model=RoleTemplatesOut)
async def role_templates_route(ctx: Ctx) -> RoleTemplatesOut:
    """ADM-02b: eight templates with counts, the grid and the locked agent row."""
    await _gate(ctx)
    found = await people.role_templates(ctx)
    return RoleTemplatesOut(
        templates=[
            RoleTemplateOut(key=t.key, levels=t.levels, member_count=t.member_count)
            for t in found.templates
        ],
        grid=[
            GridRowOut(
                key=g.key,
                actions=g.actions,
                cells=g.cells,
                conditions=g.conditions,
                source=g.source,
                locked=g.locked,
            )
            for g in found.grid
        ],
    )


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


def _line_out(policy: service_lines.Policy) -> ServiceLinePolicyOut:
    return ServiceLinePolicyOut(
        service_line=policy.service_line,
        enabled=policy.enabled,
        lead_user_id=policy.lead_user_id,
        content_visible_to=policy.content_visible_to,
        cross_line_access=policy.cross_line_access,
        version=policy.version,
    )


@settings_router.get(
    "/service-lines",
    action="firm.read_settings",
    response_model=list[ServiceLinePolicyOut],
)
async def service_lines_route(ctx: Ctx) -> list[ServiceLinePolicyOut]:
    """ADM-03's service lines (AC10.1): the four lines in order; a line never saved reads its
    defaults ("Engagement team only", "Hand-offs only", version 0)."""
    await _gate(ctx)
    return [_line_out(p) for p in await service_lines.policies(ctx)]


@settings_router.put(
    "/service-lines/{line}",
    action="service_line_policy.manage",
    response_model=ServiceLinePolicyOut,
    errors=(409,),
)
async def set_service_line_route(
    line: ServiceLine, body: ServiceLinePolicyIn, ctx: Ctx
) -> ServiceLinePolicyOut:
    """Fresh MFA; 422 `audit_locked` (Audit is never widened) and `service_line_lead_invalid`;
    409 `stale_version`. Members whose reach changes get `access.changed` (AC10.2)."""
    await _gate(ctx)
    return _line_out(
        await service_lines.set_policy(
            ctx,
            line,
            version=body.version,
            enabled=body.enabled,
            lead_user_id=body.lead_user_id,
            content_visible_to=body.content_visible_to,
            cross_line_access=body.cross_line_access,
        )
    )


@settings_router.get("/offshore", action="firm.read_settings", response_model=OffshoreOut)
async def offshore_route(ctx: Ctx) -> OffshoreOut:
    """ADM-03d: the offshore members and the clients a valid offshore-disclosure consent covers
    (0 until T-01 registers the provider; DEC-52). The two policy toggles are always on."""
    await _gate(ctx)
    found = await offshore.offshore_group(ctx)
    return OffshoreOut(
        member_ids=found.member_ids, consented_client_count=found.consented_client_count
    )


async def _wall_v2(ctx: AuthContext, wall: walls.WallView) -> WallV2Out:
    return WallV2Out(
        id=wall.id,
        user_id=wall.user_id,
        client_id=wall.client_id,
        reason_code=wall.reason_code,
        reason_text=wall.reason_text,
        created_by=wall.created_by,
        created_at=wall.created_at,
        approver_user_id=wall.approver_user_id,
        approval_status=WallApprovalStatus(wall.approval_status),
        approved_at=wall.approved_at,
        allowed_actions=await walls.wall_actions(ctx, wall),
    )


@walls_v2_router.get("/preview", action="wall.create", response_model=WallPreviewOut)
async def wall_preview_route(
    ctx: Ctx, user_id: Annotated[UUID, Query()], client_id: Annotated[UUID, Query()]
) -> WallPreviewOut:
    """AC8.1, AC8.3: what saving would refuse and the assignments it would end; a client the
    caller can't see answers 404 (DEC-43)."""
    await _gate(ctx)
    found = await walls.preview(ctx, user_id=user_id, client_id=client_id)
    return WallPreviewOut(
        blockers=cast(list[WallBlocker], found.blockers),
        assignments_ended=found.assignments_ended,
    )


@walls_v2_router.post(
    "/{wall_id}/approve", action="wall.approve", response_model=WallV2Out, errors=(409,)
)
async def approve_wall_route(wall_id: UUID, ctx: Ctx) -> WallV2Out:
    """The named partner only, fresh MFA; 409 `already_approved`; 403 `not_named_approver`."""
    await _gate(ctx)
    return await _wall_v2(ctx, await walls.approve_wall(ctx, wall_id))


@walls_v2_router.get(
    "/{wall_id}/events", action="wall.list", response_model=ListPage[WallEventOut]
)
async def wall_events_route(
    wall_id: UUID, ctx: Ctx, cursor: Annotated[str | None, Query(max_length=512)] = None
) -> ListPage[WallEventOut]:
    """ADM-03g: the wall's log, newest first, from the audit trail (fresh MFA)."""
    await _gate(ctx)
    before = _cursor(cursor)
    events, next_seq, total = await walls.wall_events(ctx, wall_id, before, _EVENTS_PAGE)
    return ListPage[WallEventOut](
        items=[
            WallEventOut(event_type=e.event_type, at=e.at, actor_user_id=e.actor_user_id)
            for e in events
        ],
        next_cursor=None if next_seq is None else str(next_seq),
        total=total,
    )


_EVENTS_PAGE = 50


def _cursor(cursor: str | None) -> int | None:
    if cursor is None:
        return None
    if not cursor.isdigit():
        raise CursorInvalid
    return int(cursor)


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

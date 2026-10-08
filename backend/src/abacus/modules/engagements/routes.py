"""Engagement routes (SPEC-000 §8; TASK-008 design §3). Metadata only: content is served by the
content routes (request items), each with its own action (ADR-024)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus.kernel.classification import classified
from abacus.kernel.config import settings
from abacus.kernel.text import SingleLineText
from abacus.modules.engagements.service import (
    EngagementMetadata,
    EngagementView,
    NewEngagement,
    TemplateVersionSummary,
    add_to_team,
    change_team_role,
    client_contacts_of,
    create_engagement,
    engagement_metadata,
    engagements_for,
    import_template,
    invite_client,
    methodology_templates,
    methodology_version,
    remove_client_contact,
    remove_from_team,
    resend_client_invitation,
    revoke_client_invitation,
    self_join,
    team_candidates,
    team_of_engagement,
)
from abacus.modules.engagements.workbook import Problem, TemplateInvalid
from abacus.modules.identity.api import AbacusRouter, AuthContext, EngagementRole, current_context

router = AbacusRouter(prefix="/v1/engagements", tags=["engagements"])
Name = Annotated[SingleLineText, Field(min_length=1, max_length=200), classified("confidential")]


class EngagementIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    name: Name
    client_name: Name
    client_entity_name: Name
    fiscal_period_start: Annotated[date, classified("confidential")]
    fiscal_period_end: Annotated[date, classified("confidential")]

    @model_validator(mode="after")
    def _period(self) -> EngagementIn:
        if self.fiscal_period_end <= self.fiscal_period_start:
            raise ValueError("fiscal_period_end must be after fiscal_period_start")
        return self


class TeamMemberOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    role: Annotated[EngagementRole, classified("internal")]


class EngagementSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Name
    type: Annotated[Literal["audit"], classified("internal")]
    status: Annotated[Literal["active", "archived"], classified("internal")]
    client_name: Name
    client_entity_name: Name
    fiscal_period_start: Annotated[date, classified("confidential")]
    fiscal_period_end: Annotated[date, classified("confidential")]
    created_at: Annotated[datetime, classified("internal")]


class EngagementOut(EngagementSummaryOut):
    team: Annotated[list[TeamMemberOut], classified("confidential")]


def _summary(view: EngagementView) -> EngagementSummaryOut:
    # Validation, not coercion: an unexpected type or status from the database is an error.
    return EngagementSummaryOut.model_validate(view, from_attributes=True)


def _out(metadata: EngagementMetadata) -> EngagementOut:
    team = [
        TeamMemberOut(user_id=m.user_id, display_name=m.display_name, role=m.role)
        for m in metadata.team
    ]
    return EngagementOut(**_summary(metadata.engagement).model_dump(), team=team)


Ctx = Annotated[AuthContext, Depends(current_context)]


@router.post("", action="engagement.create", response_model=EngagementOut, status_code=201)
async def create_engagement_route(body: EngagementIn, ctx: Ctx) -> EngagementOut:
    new = NewEngagement(
        name=body.name,
        client_name=body.client_name,
        client_entity_name=body.client_entity_name,
        fiscal_period_start=body.fiscal_period_start,
        fiscal_period_end=body.fiscal_period_end,
    )
    return _out(await create_engagement(ctx, new))


@router.get("", action="engagement.read_metadata", response_model=list[EngagementSummaryOut])
async def list_engagements_route(ctx: Ctx) -> list[EngagementSummaryOut]:
    return [_summary(s) for s in await engagements_for(ctx)]


@router.get("/{engagement_id}", action="engagement.read_metadata", response_model=EngagementOut)
async def get_engagement_route(engagement_id: UUID, ctx: Ctx) -> EngagementOut:
    return _out(await engagement_metadata(ctx, engagement_id))


@router.post(
    "/{engagement_id}/self-join",
    action="engagement.self_join",
    response_model=EngagementOut,
    errors=(409,),
)
async def self_join_route(engagement_id: UUID, ctx: Ctx) -> EngagementOut:
    """ADR-024; SPEC-013 AC-8: a firm admin joins (as reviewer) and the team is notified."""
    return _out(await self_join(ctx, engagement_id))


# --- Engagement team (SPEC-017 §8) -------------------------------------------------------------

StaffRoleName = Literal["engagement_partner", "manager", "senior", "staff", "reviewer"]


class CandidateOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]


class TeamMemberIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: Annotated[UUID, classified("internal")]
    role: Annotated[StaffRoleName, classified("internal")]


class TeamRoleIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    role: Annotated[StaffRoleName, classified("internal")]


@router.get(
    "/{engagement_id}/team", action="engagement.read_metadata", response_model=list[TeamMemberOut]
)
async def team_route(engagement_id: UUID, ctx: Ctx) -> list[TeamMemberOut]:
    team = await team_of_engagement(ctx, engagement_id)
    return [
        TeamMemberOut(user_id=m.user_id, display_name=m.display_name, role=m.role) for m in team
    ]


@router.get(
    "/{engagement_id}/team/candidates",
    action="engagement.member_add",
    response_model=list[CandidateOut],
)
async def team_candidates_route(engagement_id: UUID, ctx: Ctx) -> list[CandidateOut]:
    found = await team_candidates(ctx, engagement_id)
    return [CandidateOut(user_id=c.user_id, display_name=c.display_name) for c in found]


@router.post(
    "/{engagement_id}/team",
    action="engagement.member_add",
    response_model=list[TeamMemberOut],
    status_code=201,
)
async def add_team_member_route(
    engagement_id: UUID, body: TeamMemberIn, ctx: Ctx
) -> list[TeamMemberOut]:
    await add_to_team(ctx, engagement_id, body.user_id, body.role)
    return await team_route(engagement_id, ctx)


@router.put(
    "/{engagement_id}/team/{user_id}",
    action="engagement.member_add",
    response_model=list[TeamMemberOut],
    errors=(409,),
)
async def change_team_role_route(
    engagement_id: UUID, user_id: UUID, body: TeamRoleIn, ctx: Ctx
) -> list[TeamMemberOut]:
    await change_team_role(ctx, engagement_id, user_id, body.role)
    return await team_route(engagement_id, ctx)


@router.delete(
    "/{engagement_id}/team/{user_id}",
    action="engagement.member_remove",
    response_model=list[TeamMemberOut],
    errors=(409,),
)
async def remove_team_member_route(
    engagement_id: UUID, user_id: UUID, ctx: Ctx
) -> list[TeamMemberOut]:
    await remove_from_team(ctx, engagement_id, user_id)
    return await team_route(engagement_id, ctx)


# --- Client contacts (SPEC-015 §8) -------------------------------------------------------------


class ClientInvitationIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    email: Annotated[str, Field(min_length=3, max_length=320), classified("confidential")]
    role: Annotated[Literal["client_admin", "client_contributor"], classified("internal")]


class ClientInvitationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    invitation_id: Annotated[UUID, classified("internal")]


class ClientContactOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[Literal["member", "invitation"], classified("internal")]
    id: Annotated[UUID, classified("internal")]
    role: Annotated[str, classified("internal")]
    email: Annotated[str | None, classified("confidential")]
    expires_at: Annotated[datetime | None, classified("internal")]


@router.post(
    "/{engagement_id}/client-invitations",
    action="client_contact.invite",
    response_model=ClientInvitationOut,
    status_code=201,
    errors=(409,),
)
async def invite_client_route(
    engagement_id: UUID, body: ClientInvitationIn, ctx: Ctx
) -> ClientInvitationOut:
    """The link is emailed, never returned (SPEC-015 AC-1)."""
    invitation_id = await invite_client(ctx, engagement_id, body.email, body.role)
    return ClientInvitationOut(invitation_id=invitation_id)


@router.get(
    "/{engagement_id}/client-contacts",
    action="client_contact.read",
    response_model=list[ClientContactOut],
)
async def client_contacts_route(engagement_id: UUID, ctx: Ctx) -> list[ClientContactOut]:
    return [
        ClientContactOut.model_validate(asdict(c))
        for c in await client_contacts_of(ctx, engagement_id)
    ]


@router.post(
    "/{engagement_id}/client-invitations/{invitation_id}/revoke",
    action="client_contact.invite",
    response_model=ClientInvitationOut,
)
async def revoke_client_invitation_route(
    engagement_id: UUID, invitation_id: UUID, ctx: Ctx
) -> ClientInvitationOut:
    await revoke_client_invitation(ctx, engagement_id, invitation_id)
    return ClientInvitationOut(invitation_id=invitation_id)


@router.post(
    "/{engagement_id}/client-invitations/{invitation_id}/resend",
    action="client_contact.invite",
    response_model=ClientInvitationOut,
)
async def resend_client_invitation_route(
    engagement_id: UUID, invitation_id: UUID, ctx: Ctx
) -> ClientInvitationOut:
    await resend_client_invitation(ctx, engagement_id, invitation_id)
    return ClientInvitationOut(invitation_id=invitation_id)


class RemovedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]


@router.delete(
    "/{engagement_id}/client-contacts/{user_id}",
    action="client_contact.remove",
    response_model=RemovedOut,
)
async def remove_client_contact_route(engagement_id: UUID, user_id: UUID, ctx: Ctx) -> RemovedOut:
    await remove_client_contact(ctx, engagement_id, user_id)
    return RemovedOut(user_id=user_id)


# --- Methodology templates (SPEC-008 §8) -------------------------------------------------------

methodology_router = AbacusRouter(prefix="/v1/methodology", tags=["methodology"])
TemplateName = Annotated[SingleLineText, Field(min_length=1, max_length=100)]


class TemplateVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_id: Annotated[UUID, classified("internal")]
    template_name: Annotated[str, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]
    version: Annotated[int, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


class AreaOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("internal")]
    name: Annotated[str, classified("internal")]


class TemplateItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    area_code: Annotated[str, classified("internal")]
    description: Annotated[str, classified("internal")]
    tier: Annotated[str, classified("internal")]


class AccountRuleOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    area_code: Annotated[str, classified("internal")]
    account_from: Annotated[str, classified("internal")]
    account_to: Annotated[str, classified("internal")]


class MethodologyVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary: Annotated[TemplateVersionOut, classified("internal")]
    areas: Annotated[list[AreaOut], classified("internal")]
    items: Annotated[list[TemplateItemOut], classified("internal")]
    rules: Annotated[list[AccountRuleOut], classified("internal")]


def _version_out(summary: TemplateVersionSummary) -> TemplateVersionOut:
    return TemplateVersionOut.model_validate(asdict(summary))


def _loc(problem: Problem) -> tuple[str | int, ...]:
    where = (problem.sheet, problem.row, problem.column)
    return ("body", *(part for part in where if part is not None))


async def _body(request: Request) -> bytes:
    """The workbook, read up to the limit (a larger body is refused before it is all read)."""
    limit = settings().methodology_max_bytes
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > limit:
            raise TemplateInvalid([Problem(None, None, None, "too_large")])
    return bytes(data)


@methodology_router.post(
    "/templates/{name}/versions",
    action="methodology.manage",
    response_model=TemplateVersionOut,
    status_code=201,
)
async def import_template_route(
    name: TemplateName, request: Request, ctx: Ctx
) -> TemplateVersionOut:
    """The raw `.xlsx` workbook is the request body (TASK-023 D3: no multipart dependency)."""
    try:
        summary = await import_template(ctx, name, await _body(request))
    except TemplateInvalid as invalid:
        # Where and what, never the cell (ADR-052), in the validation error shape.
        raise RequestValidationError(
            [
                {
                    "loc": _loc(problem),
                    "msg": problem.code,
                    "type": problem.code,
                }
                for problem in invalid.problems
            ]
        ) from None
    return _version_out(summary)


@methodology_router.get(
    "/templates", action="methodology.read", response_model=list[TemplateVersionOut]
)
async def list_templates_route(ctx: Ctx) -> list[TemplateVersionOut]:
    return [_version_out(s) for s in await methodology_templates(ctx)]


@methodology_router.get(
    "/versions/{version_id}", action="methodology.read", response_model=MethodologyVersionOut
)
async def get_version_route(version_id: UUID, ctx: Ctx) -> MethodologyVersionOut:
    view = await methodology_version(ctx, version_id)
    return MethodologyVersionOut(
        summary=_version_out(view.summary),
        areas=[AreaOut(code=a.code, name=a.name) for a in view.areas],
        items=[
            TemplateItemOut(area_code=i.area_code, description=i.description, tier=i.tier)
            for i in view.items
        ],
        rules=[
            AccountRuleOut(
                area_code=r.area_code, account_from=r.account_from, account_to=r.account_to
            )
            for r in view.rules
        ],
    )

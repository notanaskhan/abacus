"""Engagement routes (SPEC-000 §8; TASK-008 design §3). Metadata only: content is served by the
content routes (request items), each with its own action (ADR-024)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus.kernel._statuses import ClientInvitationStatus, EngagementStatus
from abacus.kernel.classification import classified
from abacus.kernel.listing import ListPage
from abacus.kernel.text import SingleLineText
from abacus.modules.engagements import team as team_model
from abacus.modules.engagements.gates import engagement_gates
from abacus.modules.engagements.onboarding import Onboarding, StepId, acknowledge_step, onboarding
from abacus.modules.engagements.onboarding import dismiss as dismiss_onboarding
from abacus.modules.engagements.roll_forward import ItemKind, RollForward, propose
from abacus.modules.engagements.service import (
    KEEP_HOURS,
    AiExclusion,
    EngagementMetadata,
    EngagementType,
    EngagementView,
    NewEngagement,
    add_to_team,
    ai_exclusion,
    change_team_role,
    client_contacts_of,
    create_engagement,
    engagement_metadata,
    engagement_resource_of,
    engagements_for,
    firm_clients,
    invite_client,
    remove_client_contact,
    remove_from_team,
    resend_client_invitation,
    revoke_client_invitation,
    search_clients,
    self_join,
    set_ai_exclusion_of,
    team_candidates,
)
from abacus.modules.engagements.work_items import list_work_items, work_items_of
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    EngagementRole,
    allowed_actions,
    current_context,
)

router = AbacusRouter(prefix="/v1/engagements", tags=["engagements"])
Name = Annotated[SingleLineText, Field(min_length=1, max_length=200), classified("confidential")]


StaffRole = Literal["engagement_partner", "manager", "senior", "staff", "reviewer"]


class RollForwardMemberIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: Annotated[UUID, classified("internal")]
    role: Annotated[StaffRole, classified("internal")]


class RollForwardIn(BaseModel):
    """SPEC-025 AC-2 (TASK-048): exactly what the person confirmed from the proposal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    prior_engagement_id: Annotated[UUID, classified("internal")]
    team: Annotated[list[RollForwardMemberIn], Field(max_length=200), classified("internal")]
    version_id: Annotated[UUID | None, classified("internal")]
    prior_item_ids: Annotated[list[UUID], Field(max_length=2000), classified("internal")]
    template_keys: Annotated[list[int], Field(max_length=2000), classified("internal")] = []


class EngagementIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    name: Name
    client_name: Name
    client_entity_name: Name
    fiscal_period_start: Annotated[date, classified("confidential")]
    fiscal_period_end: Annotated[date, classified("confidential")]
    # SPEC-024 AC-6: the engagement's type.
    type: Annotated[EngagementType, classified("internal")] = "fs_audit"
    # SPEC-025 AC-1: an existing client (and entity), picked rather than typed; the names above
    # are then the chosen ones (or, with no entity id, the new entity's name).
    client_id: Annotated[UUID | None, classified("internal")] = None
    client_entity_id: Annotated[UUID | None, classified("internal")] = None
    confirm_new: Annotated[bool, classified("internal")] = False
    roll_forward: Annotated[RollForwardIn | None, classified("internal")] = None

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


class TeamRosterMemberOut(TeamMemberOut):
    """The team routes' rows (P-07-T30, ENG-05): hours, the portal flag, when the person joined
    and their independence confirmation here. C1's engagement projection keeps `TeamMemberOut`."""

    budget_hours: Annotated[Decimal | None, classified("internal")] = None
    shown_on_portal: Annotated[bool, classified("internal")] = False
    proposed_at: Annotated[datetime | None, classified("internal")] = None
    independence: Annotated[
        Literal["requested", "confirmed", "declined"] | None, classified("internal")
    ] = None


class EngagementSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Name
    type: Annotated[EngagementType, classified("internal")]
    # F-03-T12: the registry's 8 lifecycle codes (C2), generated from status-vocabulary.yaml.
    status: Annotated[EngagementStatus, classified("internal")]
    service_line: Annotated[Literal["audit", "tax", "cas", "advisory"], classified("internal")]
    client_name: Name
    client_entity_name: Name
    fiscal_period_start: Annotated[date, classified("confidential")]
    fiscal_period_end: Annotated[date, classified("confidential")]
    created_at: Annotated[datetime, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]  # SPEC-303 (TASK-304)
    client_entity_id: Annotated[UUID, classified("internal")]


class GateOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    gate: Annotated[Literal["G1", "G2", "G3"], classified("internal")]
    met: Annotated[bool, classified("internal")]
    blockers: Annotated[list[str], classified("internal")]


class EngagementOut(EngagementSummaryOut):
    team: Annotated[list[TeamMemberOut], classified("confidential")]
    # C1 (F-03-T19): the G1 to G3 gates the type requires; filled on GET /v1/engagements/{id}.
    gates: Annotated[list[GateOut], classified("internal")] = []
    # C1 live (F-03-T31): what the caller may do on it (evaluated, never recorded as a check).
    allowed_actions: Annotated[list[str], classified("internal")] = []


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


@router.post(
    "", action="engagement.create", response_model=EngagementOut, status_code=201, errors=(409,)
)
async def create_engagement_route(body: EngagementIn, ctx: Ctx) -> EngagementOut:
    new = NewEngagement(
        name=body.name,
        client_name=body.client_name,
        client_entity_name=body.client_entity_name,
        fiscal_period_start=body.fiscal_period_start,
        fiscal_period_end=body.fiscal_period_end,
        type=body.type,
        client_id=body.client_id,
        client_entity_id=body.client_entity_id,
        confirm_new=body.confirm_new,
        roll_forward=_roll(body.roll_forward),
    )
    return _out(await create_engagement(ctx, new))


def _roll(body: RollForwardIn | None) -> RollForward | None:
    if body is None:
        return None
    return RollForward(
        body.prior_engagement_id,
        [(m.user_id, m.role) for m in body.team],
        body.version_id,
        body.prior_item_ids,
        body.template_keys,
    )


class RollForwardProposalIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    client_entity_id: Annotated[UUID, classified("internal")]
    type: Annotated[EngagementType, classified("internal")] = "fs_audit"
    fiscal_period_start: Annotated[date, classified("confidential")]
    prior_engagement_id: Annotated[UUID | None, classified("internal")] = None


class PriorChoiceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    fiscal_period_start: Annotated[date, classified("confidential")]
    fiscal_period_end: Annotated[date, classified("confidential")]


class ProposedMemberOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    role: Annotated[StaffRole, classified("internal")]
    available: Annotated[bool, classified("internal")]


class ProposedTemplateOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_id: Annotated[UUID, classified("internal")]
    template_name: Annotated[str, classified("internal")]
    version_last_year: Annotated[int, classified("internal")]
    latest_version_id: Annotated[UUID, classified("internal")]
    latest_version: Annotated[int, classified("internal")]


class ProposedItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[ItemKind, classified("internal")]
    description: Annotated[str, classified("confidential")]
    audit_area: Annotated[str, classified("confidential")]
    tier: Annotated[str | None, classified("internal")]
    client_visible: Annotated[bool, classified("internal")]
    ticked: Annotated[bool, classified("internal")]
    prior_item_id: Annotated[UUID | None, classified("internal")]
    template_key: Annotated[int | None, classified("internal")]


class RollForwardProposalOut(BaseModel):
    """SPEC-025 AC-2: nothing is stored; `prior` is None when there's nothing to roll forward."""

    model_config = ConfigDict(frozen=True)

    prior: Annotated[PriorChoiceOut | None, classified("confidential")]
    others: Annotated[list[PriorChoiceOut], classified("confidential")]
    team: Annotated[list[ProposedMemberOut], classified("confidential")]
    template: Annotated[ProposedTemplateOut | None, classified("internal")]
    items: Annotated[list[ProposedItemOut], classified("confidential")]


@router.post(
    "/proposal", action="engagement.create", response_model=RollForwardProposalOut, errors=(409,)
)
async def proposal_route(body: RollForwardProposalIn, ctx: Ctx) -> RollForwardProposalOut:
    """SPEC-025 AC-2: last year's team, template and items to confirm; nothing is stored."""
    found = await propose(
        ctx,
        client_entity_id=body.client_entity_id,
        type=body.type,
        fiscal_period_start=body.fiscal_period_start,
        prior_engagement_id=body.prior_engagement_id,
    )
    return RollForwardProposalOut.model_validate(asdict(found))


@router.get("", action="engagement.read_metadata", response_model=list[EngagementSummaryOut])
async def list_engagements_route(ctx: Ctx) -> list[EngagementSummaryOut]:
    return [_summary(s) for s in await engagements_for(ctx)]


@router.get("/{engagement_id}", action="engagement.read_metadata", response_model=EngagementOut)
async def get_engagement_route(engagement_id: UUID, ctx: Ctx) -> EngagementOut:
    metadata = await engagement_metadata(ctx, engagement_id)
    gates = await engagement_gates(ctx.tenant, engagement_id, metadata.engagement.type)
    allowed = await allowed_actions(
        ctx, await engagement_resource_of(ctx.tenant, engagement_id), ENGAGEMENT_ACTIONS
    )
    return _out(metadata).model_copy(
        update={
            "gates": [GateOut.model_validate(asdict(g)) for g in gates],
            "allowed_actions": sorted(allowed),
        }
    )


# C1 live (F-03-T31): the actions a client of the projection may offer on an engagement.
ENGAGEMENT_ACTIONS: tuple[str, ...] = (
    "engagement.update",
    "engagement.hold",
    "engagement.archive",
    "engagement.member_add",
    "engagement.member_remove",
    "acceptance.record",
    "letter.record",
    "work_item.create",
    "request_item.create",
    "client_contact.invite",
    "engagement_contact.designate",
)


class WorkItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[
        Literal["assurance", "tax_return", "close", "notice", "advisory_project"],
        classified("internal"),
    ]
    name: Name
    status: Annotated[Literal["active", "archived"], classified("internal")]
    period_start: Annotated[date | None, classified("confidential")]
    period_end: Annotated[date | None, classified("confidential")]
    due_on: Annotated[date | None, classified("internal")]
    phase: Annotated[str | None, classified("internal")]


@router.get(
    "/{engagement_id}/work-items",
    action="work_item.read_metadata",
    response_model=list[WorkItemOut],
)
async def work_items_route(engagement_id: UUID, ctx: Ctx) -> list[WorkItemOut]:
    """F-03-T05 (C1): the engagement's work items."""
    return [WorkItemOut.model_validate(asdict(w)) for w in await work_items_of(ctx, engagement_id)]


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

# P-07-T30: `specialist` joins; the EQR is set through `POST …/eqr`, never as a team role.
StaffRoleName = Literal[
    "engagement_partner", "manager", "senior", "staff", "reviewer", "specialist"
]
BudgetHours = Annotated[Decimal, Field(ge=0, max_digits=7, decimal_places=1)]


class CandidateOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]


class TeamMemberIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: Annotated[UUID, classified("internal")]
    role: Annotated[StaffRoleName, classified("internal")]
    budget_hours: Annotated[BudgetHours | None, classified("internal")] = None  # P-07-T30


class TeamRoleIn(BaseModel):
    """ "Change role…" and "Edit hours…": either or both; an absent field is unchanged
    (`budget_hours: null` clears the hours)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: Annotated[StaffRoleName | None, classified("internal")] = None
    budget_hours: Annotated[BudgetHours | None, classified("internal")] = None

    @model_validator(mode="after")
    def _something(self) -> TeamRoleIn:
        if self.role is None and "budget_hours" not in self.model_fields_set:
            raise ValueError("name a role or budget hours")
        return self


@router.get(
    "/{engagement_id}/team",
    action="engagement.read_metadata",
    response_model=list[TeamRosterMemberOut],
)
async def team_route(engagement_id: UUID, ctx: Ctx) -> list[TeamRosterMemberOut]:
    """SPEC-017; P-07-T30 adds ENG-05's hours, portal flag, joined date and independence."""
    team = await team_model.team_of(ctx, engagement_id)
    return [TeamRosterMemberOut.model_validate(asdict(m)) for m in team]


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
    response_model=list[TeamRosterMemberOut],
    status_code=201,
)
async def add_team_member_route(
    engagement_id: UUID, body: TeamMemberIn, ctx: Ctx
) -> list[TeamRosterMemberOut]:
    await add_to_team(ctx, engagement_id, body.user_id, body.role, body.budget_hours)
    return await team_route(engagement_id, ctx)


@router.put(
    "/{engagement_id}/team/{user_id}",
    action="engagement.member_add",
    response_model=list[TeamRosterMemberOut],
    errors=(409,),
)
async def change_team_role_route(
    engagement_id: UUID, user_id: UUID, body: TeamRoleIn, ctx: Ctx
) -> list[TeamRosterMemberOut]:
    hours = body.budget_hours if "budget_hours" in body.model_fields_set else KEEP_HOURS
    await change_team_role(ctx, engagement_id, user_id, body.role, hours)
    return await team_route(engagement_id, ctx)


@router.delete(
    "/{engagement_id}/team/{user_id}",
    action="engagement.member_remove",
    response_model=list[TeamRosterMemberOut],
    errors=(409,),
)
async def remove_team_member_route(
    engagement_id: UUID, user_id: UUID, ctx: Ctx
) -> list[TeamRosterMemberOut]:
    await remove_from_team(ctx, engagement_id, user_id)
    if user_id == ctx.user_id:
        # SPEC-017 §12: a person may leave; they can no longer read the team (Q-03-T007).
        return []
    return await team_route(engagement_id, ctx)


# --- Client contacts (SPEC-015 §8) -------------------------------------------------------------


class ClientInvitationIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    email: Annotated[str, Field(min_length=3, max_length=320), classified("confidential")]
    role: Annotated[Literal["client_admin", "client_contributor"], classified("internal")]


class ClientInvitationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    invitation_id: Annotated[UUID, classified("internal")]


class ClientInvitationCreatedOut(ClientInvitationOut):
    """ED-007 (SPEC-015 AC-1): the new invitation's id, email and status; never the link."""

    email: Annotated[str, classified("confidential")]
    status: Annotated[ClientInvitationStatus, classified("internal")]


class ClientContactOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[Literal["member", "invitation"], classified("internal")]
    id: Annotated[UUID, classified("internal")]
    role: Annotated[str, classified("internal")]
    email: Annotated[str | None, classified("confidential")]
    expires_at: Annotated[datetime | None, classified("internal")]
    display_name: Annotated[str | None, classified("confidential")] = None


@router.post(
    "/{engagement_id}/client-invitations",
    action="client_contact.invite",
    response_model=ClientInvitationCreatedOut,
    status_code=201,
    errors=(409,),
)
async def invite_client_route(
    engagement_id: UUID, body: ClientInvitationIn, ctx: Ctx
) -> ClientInvitationCreatedOut:
    """The link is emailed, never returned (SPEC-015 AC-1)."""
    invitation_id = await invite_client(ctx, engagement_id, body.email, body.role)
    return ClientInvitationCreatedOut(
        invitation_id=invitation_id, email=body.email, status=ClientInvitationStatus.PENDING
    )


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


# --- Firm clients, for the wall picker (SPEC-019 Q4) ---------------------------------------------

firm_router = AbacusRouter(prefix="/v1/firm", tags=["firm"])


class FirmClientOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]


@firm_router.get("/clients", action="wall.create", response_model=list[FirmClientOut])
async def firm_clients_route(ctx: Ctx) -> list[FirmClientOut]:
    return [FirmClientOut(client_id=c.client_id, name=c.name) for c in await firm_clients(ctx)]


# --- The onboarding checklist (SPEC-024 AC-7; TASK-042) ----------------------------------------


class StepOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[StepId, classified("internal")]
    done: Annotated[bool, classified("internal")]
    how: Annotated[str | None, classified("internal")] = None


class OnboardingOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    steps: Annotated[list[StepOut], classified("internal")]
    dismissed: Annotated[bool, classified("internal")]
    complete: Annotated[bool, classified("internal")]


def _onboarding_out(o: Onboarding) -> OnboardingOut:
    return OnboardingOut(
        steps=[StepOut(id=s.id, done=s.done, how=s.how if s.done else None) for s in o.steps],
        dismissed=o.dismissed,
        complete=o.complete,
    )


@firm_router.get("/onboarding", action="firm.read_settings", response_model=OnboardingOut)
async def onboarding_route(ctx: Ctx) -> OnboardingOut:
    """SPEC-024 AC-7: each step's state, computed from the firm's data."""
    return _onboarding_out(await onboarding(ctx))


@firm_router.post(
    "/onboarding/{step}/acknowledge", action="firm.manage_settings", response_model=OnboardingOut
)
async def acknowledge_step_route(
    step: Literal["sso", "budget", "walls"], ctx: Ctx
) -> OnboardingOut:
    """Skip SSO for now, the budget looks right, or no walls are needed."""
    return _onboarding_out(await acknowledge_step(ctx, step))


@firm_router.post(
    "/onboarding/dismiss", action="firm.manage_settings", response_model=OnboardingOut
)
async def dismiss_onboarding_route(ctx: Ctx) -> OnboardingOut:
    return _onboarding_out(await dismiss_onboarding(ctx))


# --- The client picker (SPEC-025 AC-1; TASK-043) -----------------------------------------------


class EntityChoiceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]


class ClientChoiceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    entities: Annotated[list[EntityChoiceOut], classified("confidential")]


@firm_router.get("/clients/search", action="client.read", response_model=list[ClientChoiceOut])
async def search_clients_route(
    ctx: Ctx, q: Annotated[str, Query(min_length=1, max_length=200)]
) -> list[ClientChoiceOut]:
    """The firm's clients by name (normalised), minus any the person is walled off from."""
    return [
        ClientChoiceOut(
            id=c.id,
            name=c.name,
            entities=[EntityChoiceOut(id=e.id, name=e.name) for e in c.entities],
        )
        for c in await search_clients(ctx, q)
    ]


# SPEC-025's acceptance, letter and independence adapters (`GET …/setup`, `PUT …/acceptance`,
# `PUT …/letter`, `POST …/independence`) and `GET /v1/firm/confirmations` retired with P-07-T59
# (DEC-905): CLI-07, CLI-08 and ENG-02's recorded letter are their v2 routes.


# --- AI exclusion (SPEC-036; TASK-076) ----------------------------------------------------------


class AiExclusionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    excluded: Annotated[bool, classified("internal")]
    excluded_at: Annotated[datetime | None, classified("internal")] = None
    excluded_by: Annotated[UUID | None, classified("internal")] = None
    reason: Annotated[str | None, classified("confidential")] = None


class AiExclusionIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    excluded: Annotated[bool, classified("internal")]
    reason: Annotated[str | None, Field(max_length=300), classified("confidential")] = None


def _exclusion_out(found: AiExclusion) -> AiExclusionOut:
    return AiExclusionOut(
        excluded=found.excluded_at is not None,
        excluded_at=found.excluded_at,
        excluded_by=found.excluded_by,
        reason=found.reason,
    )


@router.get(
    "/{engagement_id}/ai-exclusion",
    action="engagement.read_metadata",
    response_model=AiExclusionOut,
)
async def ai_exclusion_route(engagement_id: UUID, ctx: Ctx) -> AiExclusionOut:
    return _exclusion_out(await ai_exclusion(ctx, engagement_id))


@router.put(
    "/{engagement_id}/ai-exclusion",
    action="engagement.ai_exclude",
    response_model=AiExclusionOut,
)
async def set_ai_exclusion_route(
    engagement_id: UUID, body: AiExclusionIn, ctx: Ctx
) -> AiExclusionOut:
    """SPEC-036 AC-6: the engagement partner switches AI off for this engagement, or on again."""
    return _exclusion_out(
        await set_ai_exclusion_of(ctx, engagement_id, body.excluded, body.reason)
    )


# --- C1 live (F-03-T31): the firm-wide work-item list --------------------------------------------

work_items_router = AbacusRouter(prefix="/v1/work-items", tags=["engagements"])


class WorkItemRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    kind: Annotated[
        Literal["assurance", "tax_return", "close", "notice", "advisory_project"],
        classified("internal"),
    ]
    name: Name
    status: Annotated[Literal["active", "archived"], classified("internal")]
    period_start: Annotated[date | None, classified("confidential")]
    period_end: Annotated[date | None, classified("confidential")]
    due_on: Annotated[date | None, classified("internal")]


@work_items_router.get(
    "", action="work_item.read_metadata", response_model=ListPage[WorkItemRowOut]
)
async def list_work_items_route(
    ctx: Ctx,
    engagement_id: Annotated[UUID | None, Query()] = None,
    kind: Annotated[str | None, Query(max_length=40)] = None,
    status: Annotated[str | None, Query(max_length=40)] = None,
    cursor: Annotated[str | None, Query(max_length=2000)] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> ListPage[WorkItemRowOut]:
    """Work items the caller may read, on the list envelope with per-status counts (C1 live)."""
    page = await list_work_items(
        ctx, engagement_id=engagement_id, kind=kind, status=status, cursor=cursor, limit=limit
    )
    return ListPage[WorkItemRowOut](
        items=[
            WorkItemRowOut.model_validate(
                {k: v for k, v in asdict(row).items() if k != "created_at"}
            )
            for row in page.items
        ],
        next_cursor=page.next_cursor,
        total=page.total,
        total_capped=page.total_capped,
        counts=page.counts,
    )

"""ENG-13's roll-forward routes (P-07-T55; P-07 §4.3; DEC-805), behind
`engagements.roll_forward_v2` (off: 404).

    POST   /v1/engagements/{engagement_id}/roll-forward/drafts               a draft (201)
    GET    /v1/engagements/{engagement_id}/roll-forward/drafts/{draft_id}    the draft
    PATCH  /v1/engagements/{engagement_id}/roll-forward/drafts/{draft_id}    autosave
    DELETE /v1/engagements/{engagement_id}/roll-forward/drafts/{draft_id}    discard
    POST   /v1/engagements/{engagement_id}/roll-forward/drafts/{draft_id}/create  (201)

`engagement_id` is the source. 409 `roll_forward_source_not_released` unless it is delivered or
archived; 409 `stale_version` on a moved draft; 422 `roll_forward_invalid`. Create takes an
`Idempotency-Key` and answers the same engagement to a replay.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import ENGAGEMENTS_ROLL_FORWARD_V2
from abacus.kernel._statuses import EngagementStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.text import SingleLineText
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.engagements import roll_forward_v2 as service
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
TemplateDecision = Literal["current", "skip"]


class RollForwardSourceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    status: Annotated[EngagementStatus, classified("internal")]
    fiscal_period_start: Annotated[date, classified("internal")]
    fiscal_period_end: Annotated[date, classified("internal")]


class RollForwardSelectionsOut(BaseModel):
    """Carry (true) or Skip (false), per v1 category."""

    model_config = ConfigDict(frozen=True)

    team: Annotated[bool, classified("internal")]
    template: Annotated[bool, classified("internal")]
    request_list: Annotated[bool, classified("internal")]
    prior_year_notes: Annotated[bool, classified("internal")]


class RollForwardSelectionsIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    team: Annotated[bool | None, classified("internal")] = None
    template: Annotated[bool | None, classified("internal")] = None
    request_list: Annotated[bool | None, classified("internal")] = None
    prior_year_notes: Annotated[bool | None, classified("internal")] = None


class RollForwardTeamMemberOut(BaseModel):
    """Last year's person: `available` false when they have left or are now walled."""

    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("internal")]
    role: Annotated[str, classified("internal")]
    available: Annotated[bool, classified("internal")]


class RollForwardTemplateOut(BaseModel):
    """The source's template; `current` when last year's version is still the newest."""

    model_config = ConfigDict(frozen=True)

    template_id: Annotated[UUID, classified("internal")]
    template_name: Annotated[str, classified("internal")]
    source_version: Annotated[int, classified("internal")]
    current_version_id: Annotated[UUID, classified("internal")]
    current_version: Annotated[int, classified("internal")]
    current: Annotated[bool, classified("internal")]


class RollForwardCatalogueOut(BaseModel):
    """What v1 can carry. `evidence_copied` is always 0: evidence never moves (ADR-004)."""

    model_config = ConfigDict(frozen=True)

    team: Annotated[list[RollForwardTeamMemberOut], classified("internal")]
    template: Annotated[RollForwardTemplateOut | None, classified("internal")]
    request_count: Annotated[int, classified("internal")]
    evidence_copied: Annotated[int, classified("internal")] = 0


class RollForwardPickOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    role: Annotated[str, classified("internal")]


class RollForwardDraftOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    source: Annotated[RollForwardSourceOut, classified("confidential")]
    target_period_start: Annotated[date, classified("internal")]
    target_period_end: Annotated[date, classified("internal")]
    name: Annotated[str, classified("confidential")]
    selections: Annotated[RollForwardSelectionsOut, classified("internal")]
    team: Annotated[list[RollForwardPickOut], classified("internal")]
    template_decision: Annotated[TemplateDecision, classified("internal")]
    version: Annotated[int, classified("internal")]
    saved_at: Annotated[datetime, classified("internal")]
    created_engagement_id: Annotated[UUID | None, classified("internal")]
    catalogue: Annotated[RollForwardCatalogueOut, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]


class RollForwardDraftPatchIn(BaseModel):
    """Only what changed, on the version seen."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=1), classified("internal")]
    target_period_start: Annotated[date | None, classified("internal")] = None
    target_period_end: Annotated[date | None, classified("internal")] = None
    name: Annotated[
        SingleLineText | None, Field(min_length=1, max_length=200), classified("confidential")
    ] = None
    selections: Annotated[RollForwardSelectionsIn | None, classified("internal")] = None
    team_user_ids: Annotated[list[UUID] | None, Field(max_length=100), classified("internal")] = (
        None
    )
    template_decision: Annotated[TemplateDecision | None, classified("internal")] = None


class RollForwardDraftDiscardedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    draft_id: Annotated[UUID, classified("internal")]
    discarded_at: Annotated[datetime, classified("internal")]


class RollForwardCreatedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]
    engagement_status: Annotated[EngagementStatus, classified("internal")]
    prior_engagement_id: Annotated[UUID, classified("internal")]
    acceptance_record_id: Annotated[UUID, classified("internal")]
    requests_created: Annotated[int, classified("internal")]
    independence_requested_user_ids: Annotated[list[UUID], classified("internal")]
    methodology_version_id: Annotated[UUID | None, classified("internal")]


async def _gate(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, ENGAGEMENTS_ROLL_FORWARD_V2):
        raise NotFound(ENGAGEMENTS_ROLL_FORWARD_V2.name)


def _draft_out(v: service.DraftView) -> RollForwardDraftOut:
    c = v.catalogue
    t = c.template
    return RollForwardDraftOut(
        id=v.id,
        source=RollForwardSourceOut(
            engagement_id=v.source.engagement_id,
            name=v.source.name,
            status=EngagementStatus(v.source.status),
            fiscal_period_start=v.source.fiscal_period_start,
            fiscal_period_end=v.source.fiscal_period_end,
        ),
        target_period_start=v.target_period_start,
        target_period_end=v.target_period_end,
        name=v.name,
        selections=RollForwardSelectionsOut(**v.selections),
        team=[RollForwardPickOut(user_id=u, role=r) for u, r in v.team],
        template_decision="current" if v.template_decision == "current" else "skip",
        version=v.version,
        saved_at=v.saved_at,
        created_engagement_id=v.created_engagement_id,
        catalogue=RollForwardCatalogueOut(
            team=[
                RollForwardTeamMemberOut(
                    user_id=m.user_id,
                    display_name=m.display_name,
                    role=m.role,
                    available=m.available,
                )
                for m in c.team
            ],
            template=None
            if t is None
            else RollForwardTemplateOut(
                template_id=t.template_id,
                template_name=t.template_name,
                source_version=t.source_version,
                current_version_id=t.current_version_id,
                current_version=t.current_version,
                current=t.current,
            ),
            request_count=c.request_count,
        ),
        allowed_actions=v.allowed_actions,
    )


roll_forward_router = AbacusRouter(prefix="/v1/engagements", tags=["engagements"])
_DRAFTS = "/{engagement_id}/roll-forward/drafts"


@roll_forward_router.post(
    _DRAFTS,
    action="roll_forward.create",
    response_model=RollForwardDraftOut,
    status_code=201,
    errors=(409,),
)
async def roll_forward_draft_create_route(engagement_id: UUID, ctx: Ctx) -> RollForwardDraftOut:
    """ENG-13 "Roll forward…" from a delivered or archived engagement (P-07-T55)."""
    await _gate(ctx)
    return _draft_out(await service.create_draft(ctx, engagement_id))


@roll_forward_router.get(
    _DRAFTS + "/{draft_id}",
    action="roll_forward.read",
    response_model=RollForwardDraftOut,
    errors=(409,),
)
async def roll_forward_draft_route(
    engagement_id: UUID, draft_id: UUID, ctx: Ctx
) -> RollForwardDraftOut:
    await _gate(ctx)
    return _draft_out(await service.get_draft(ctx, engagement_id, draft_id))


@roll_forward_router.patch(
    _DRAFTS + "/{draft_id}",
    action="roll_forward.create",
    response_model=RollForwardDraftOut,
    errors=(409,),
)
async def roll_forward_draft_update_route(
    engagement_id: UUID, draft_id: UUID, body: RollForwardDraftPatchIn, ctx: Ctx
) -> RollForwardDraftOut:
    """Autosave: Carry · Skip per category, the team, the template decision, period and name."""
    await _gate(ctx)
    picks = body.selections.model_dump(exclude_none=True) if body.selections else None
    change = service.DraftChange(
        target_period_start=body.target_period_start,
        target_period_end=body.target_period_end,
        name=body.name,
        selections=picks,
        team_user_ids=body.team_user_ids,
        template_decision=body.template_decision,
    )
    return _draft_out(
        await service.update_draft(ctx, engagement_id, draft_id, body.seen_version, change)
    )


@roll_forward_router.delete(
    _DRAFTS + "/{draft_id}",
    action="roll_forward.create",
    response_model=RollForwardDraftDiscardedOut,
    errors=(409,),
)
async def roll_forward_draft_discard_route(
    engagement_id: UUID, draft_id: UUID, ctx: Ctx
) -> RollForwardDraftDiscardedOut:
    """Escape → "Discard this draft?": nothing was created."""
    await _gate(ctx)
    at = await service.discard_draft(ctx, engagement_id, draft_id)
    return RollForwardDraftDiscardedOut(draft_id=draft_id, discarded_at=at)


@roll_forward_router.post(
    _DRAFTS + "/{draft_id}/create",
    action="roll_forward.create",
    response_model=RollForwardCreatedOut,
    status_code=201,
    errors=(409,),
)
async def roll_forward_create_route(
    engagement_id: UUID, draft_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RollForwardCreatedOut:
    """ENG-13 e "Create": a Prospect engagement with `prior_engagement_id`, the carried team,
    the template's current version, a continuance acceptance record and the request list as
    Draft; no evidence, results or sign-offs (ADR-004)."""
    await _gate(ctx)
    await service.check_create(ctx, engagement_id, draft_id)

    async def run() -> tuple[int, dict[str, object]]:
        made = await service.create(ctx, engagement_id, draft_id)
        out = RollForwardCreatedOut(
            engagement_id=made.engagement_id,
            engagement_status=EngagementStatus(made.status),
            prior_engagement_id=made.prior_engagement_id,
            acceptance_record_id=made.acceptance_record_id,
            requests_created=made.requests_created,
            independence_requested_user_ids=made.team_requested,
            methodology_version_id=made.methodology_version_id,
        )
        return 201, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="roll_forward.create",
        key=idempotency_key,
        body={"engagement_id": str(engagement_id), "draft_id": str(draft_id)},
        run=run,
    )
    return RollForwardCreatedOut.model_validate(stored.body)

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
    create_engagement,
    engagement_metadata,
    engagements_for,
    import_template,
    methodology_templates,
    methodology_version,
    self_join,
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

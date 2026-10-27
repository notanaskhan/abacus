"""Methodology routes (SPEC-008 §8; moved from engagements by K-01-T02, paths and actions
unchanged): import a workbook as a template's next version, list templates, read a version."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.config import settings
from abacus.kernel.text import SingleLineText
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)
from abacus.modules.methodology.service import (
    EngagementType,
    Family,
    TemplateVersionSummary,
    import_template,
    methodology_templates,
    methodology_version,
)
from abacus.modules.methodology.workbook import Problem, TemplateInvalid
from abacus.modules.methodology.workbook_template import FILENAME, MEDIA_TYPE, workbook_template

Ctx = Annotated[AuthContext, Depends(current_context)]

methodology_router = AbacusRouter(prefix="/v1/methodology", tags=["methodology"])
TemplateName = Annotated[SingleLineText, Field(min_length=1, max_length=100)]


class TemplateVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_id: Annotated[UUID, classified("internal")]
    template_name: Annotated[str, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]
    version: Annotated[int, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    engagement_types: Annotated[list[EngagementType], classified("internal")] = ["fs_audit"]


class AreaOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("internal")]
    name: Annotated[str, classified("internal")]


class TemplateItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    area_code: Annotated[str, classified("internal")]
    description: Annotated[str, classified("internal")]
    tier: Annotated[str, classified("internal")]
    # SPEC-031 guidance; SPEC-035 Q3 (TASK-074): `drafted` with who approved it.
    why: Annotated[str | None, classified("internal")] = None
    good_looks_like: Annotated[str | None, classified("internal")] = None
    guidance_source: Annotated[Literal["drafted"] | None, classified("internal")] = None
    guidance_approved_by: Annotated[UUID | None, classified("internal")] = None


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
    return TemplateVersionOut.model_validate(
        {**asdict(summary), "engagement_types": list(summary.engagement_types)}
    )


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
    name: TemplateName,
    request: Request,
    ctx: Ctx,
    engagement_type: Annotated[list[EngagementType] | None, Query()] = None,
    family: Annotated[Family | None, Query()] = None,
) -> TemplateVersionOut:
    """The raw `.xlsx` workbook is the request body (TASK-023 D3: no multipart dependency).
    `engagement_type` (repeatable) tags a new template with the types it serves (SPEC-024);
    an existing template keeps its own."""
    try:
        summary = await import_template(
            ctx,
            name,
            await _body(request),
            tuple(engagement_type or ("fs_audit",)),
            family,
        )
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
async def list_templates_route(ctx: Ctx, latest: bool = False) -> list[TemplateVersionOut]:
    """Every version of every template; `latest=true` keeps each template's newest version only
    (SPEC-025 AC-3: what a new engagement is offered)."""
    return [_version_out(s) for s in await methodology_templates(ctx, latest=latest)]


@methodology_router.get(
    "/versions/{version_id}", action="methodology.read", response_model=MethodologyVersionOut
)
async def get_version_route(version_id: UUID, ctx: Ctx) -> MethodologyVersionOut:
    view = await methodology_version(ctx, version_id)
    return MethodologyVersionOut(
        summary=_version_out(view.summary),
        areas=[AreaOut(code=a.code, name=a.name) for a in view.areas],
        items=[
            TemplateItemOut(
                area_code=i.area_code,
                description=i.description,
                tier=i.tier,
                why=i.why,
                good_looks_like=i.good_looks_like,
                guidance_source="drafted" if i.guidance_source == "drafted" else None,
                guidance_approved_by=i.guidance_approved_by,
            )
            for i in view.items
        ],
        rules=[
            AccountRuleOut(
                area_code=r.area_code, account_from=r.account_from, account_to=r.account_to
            )
            for r in view.rules
        ],
    )


@methodology_router.get(
    "/workbook-template.xlsx", action="methodology.read", response_model=str, status_code=200
)
async def workbook_template_route(ctx: Ctx) -> Response:
    """K-01-T05: the blank workbook v2 (headers only) a firm fills in and imports. The body is
    the `.xlsx` (the model is only the generator's placeholder)."""
    await authorise(ctx, "methodology.read", Resource.firm(ctx.tenant_id))
    return Response(
        workbook_template(),
        media_type=MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{FILENAME}"',
            "X-Content-Type-Options": "nosniff",
        },
    )

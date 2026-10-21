"""Working-paper routes (SPEC-308; TASK-319). Reads follow `workpaper.read`; edits
`workpaper.edit`; each sign-off level is its own action in the review matrix."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._statuses import AuditSectionStatus
from abacus.kernel.classification import classified
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.workpapers.service import (
    CellEdit,
    WorkpaperDetail,
    WorkpaperSummary,
    cite,
    create_workpaper,
    set_cells,
    sign_off,
    workpaper_detail,
    workpapers_for,
)

router = AbacusRouter(prefix="/v1/engagements/{engagement_id}/workpapers", tags=["workpapers"])
Ctx = Annotated[AuthContext, Depends(current_context)]
Tickmark = Literal[
    "agreed", "footed", "cross_footed", "recalculated", "traced", "vouched", "exception"
]


class SignOffLevelOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: Annotated[int, classified("internal")]
    name: Annotated[
        Literal["preparer", "reviewer", "manager", "partner", "eqr"], classified("internal")
    ]
    signed_by_name: Annotated[str | None, classified("internal")]
    signed_at: Annotated[datetime | None, classified("internal")]
    stale: Annotated[bool, classified("internal")]


class WorkingPaperOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    code: Annotated[str, classified("internal")]
    title: Annotated[str, classified("confidential")]
    audit_area: Annotated[str | None, classified("confidential")]
    status: Annotated[AuditSectionStatus, classified("internal")]
    levels: Annotated[list[SignOffLevelOut], classified("internal")]
    cells: Annotated[int, classified("internal")]
    citations: Annotated[int, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


class CellOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    cell_key: Annotated[str, classified("internal")]
    raw: Annotated[str | None, classified("confidential")]
    value: Annotated[Decimal | None, classified("confidential")]
    text: Annotated[str | None, classified("confidential")]
    error: Annotated[bool, classified("internal")]
    formula: Annotated[bool, classified("internal")]
    tickmarks: Annotated[list[Tickmark], classified("internal")]
    set_by_name: Annotated[str, classified("internal")]
    set_at: Annotated[datetime, classified("internal")]


class CellCitationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    cell_key: Annotated[str, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]
    locator: Annotated[str | None, classified("confidential")]
    added_by_name: Annotated[str, classified("internal")]
    added_at: Annotated[datetime, classified("internal")]


class WorkingPaperVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_no: Annotated[int, classified("internal")]
    content_hash: Annotated[str, classified("internal")]
    created_by_name: Annotated[str, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


class WorkpaperDetailOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    workpaper: Annotated[WorkingPaperOut, classified("internal")]
    content_hash: Annotated[str, classified("internal")]
    cells: Annotated[list[CellOut], classified("internal")]
    citations: Annotated[list[CellCitationOut], classified("internal")]
    versions: Annotated[list[WorkingPaperVersionOut], classified("internal")]


class WorkpaperBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: Annotated[str, Field(min_length=1, max_length=20), classified("internal")]
    title: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    audit_area: Annotated[str | None, Field(max_length=120), classified("confidential")] = None


class CellBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cell_key: Annotated[str, Field(pattern=r"^[A-Z]{1,2}[1-9][0-9]{0,3}$"), classified("internal")]
    raw: Annotated[str | None, Field(max_length=2000), classified("confidential")] = None
    tickmarks: Annotated[list[Tickmark], Field(max_length=7), classified("internal")] = []


class CellsBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cells: Annotated[list[CellBody], Field(min_length=1, max_length=200), classified("internal")]


class CitationBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_version_id: Annotated[UUID, classified("internal")]
    locator: Annotated[str | None, Field(max_length=120), classified("confidential")] = None


def _summary_out(s: WorkpaperSummary) -> WorkingPaperOut:
    return WorkingPaperOut(
        id=s.id,
        code=s.code,
        title=s.title,
        audit_area=s.audit_area,
        status=s.status,
        levels=[SignOffLevelOut.model_validate(lv, from_attributes=True) for lv in s.levels],
        cells=s.cells,
        citations=s.citations,
        created_at=s.created_at,
    )


def _detail_out(d: WorkpaperDetail) -> WorkpaperDetailOut:
    return WorkpaperDetailOut(
        workpaper=_summary_out(d.summary),
        content_hash=d.content_hash,
        cells=[CellOut.model_validate(c, from_attributes=True) for c in d.cells],
        citations=[CellCitationOut.model_validate(c, from_attributes=True) for c in d.citations],
        versions=[
            WorkingPaperVersionOut.model_validate(v, from_attributes=True) for v in d.versions
        ],
    )


@router.get("", action="workpaper.read", response_model=list[WorkingPaperOut])
async def workpapers_route(engagement_id: UUID, ctx: Ctx) -> list[WorkingPaperOut]:
    """SPEC-308 AC-1: the engagement's working papers."""
    return [_summary_out(s) for s in await workpapers_for(ctx, engagement_id)]


@router.post("", action="workpaper.edit", response_model=WorkpaperDetailOut, status_code=201)
async def create_workpaper_route(
    engagement_id: UUID, body: WorkpaperBody, ctx: Ctx
) -> WorkpaperDetailOut:
    """SPEC-308 AC-2: a new working paper."""
    wp = await create_workpaper(ctx, engagement_id, body.code, body.title, body.audit_area)
    return _detail_out(await workpaper_detail(ctx, engagement_id, wp))


@router.get("/{workpaper_id}", action="workpaper.read", response_model=WorkpaperDetailOut)
async def workpaper_detail_route(
    engagement_id: UUID, workpaper_id: UUID, ctx: Ctx
) -> WorkpaperDetailOut:
    """SPEC-308 AC-3: the grid, citations, sign-offs and versions."""
    return _detail_out(await workpaper_detail(ctx, engagement_id, workpaper_id))


@router.put("/{workpaper_id}/cells", action="workpaper.edit", response_model=WorkpaperDetailOut)
async def set_cells_route(
    engagement_id: UUID, workpaper_id: UUID, body: CellsBody, ctx: Ctx
) -> WorkpaperDetailOut:
    """SPEC-308 AC-3: set cells (appended; unchanged cells write nothing)."""
    edits = [CellEdit(c.cell_key, c.raw, tuple(c.tickmarks)) for c in body.cells]
    await set_cells(ctx, engagement_id, workpaper_id, edits)
    return _detail_out(await workpaper_detail(ctx, engagement_id, workpaper_id))


@router.post(
    "/{workpaper_id}/cells/{cell_key}/citations",
    action="workpaper.edit",
    response_model=WorkpaperDetailOut,
    status_code=201,
)
async def cite_route(
    engagement_id: UUID, workpaper_id: UUID, cell_key: str, body: CitationBody, ctx: Ctx
) -> WorkpaperDetailOut:
    """SPEC-308 AC-4: cite an evidence version on a cell."""
    await cite(ctx, engagement_id, workpaper_id, cell_key, body.evidence_version_id, body.locator)
    return _detail_out(await workpaper_detail(ctx, engagement_id, workpaper_id))


@router.post(
    "/{workpaper_id}/sign-offs/prepare",
    action="sign_off.prepare",
    response_model=WorkpaperDetailOut,
    status_code=201,
)
async def sign_off_prepare_route(
    engagement_id: UUID, workpaper_id: UUID, ctx: Ctx
) -> WorkpaperDetailOut:
    """SPEC-308 AC-5: the L1 preparer signs the current content."""
    await sign_off(ctx, engagement_id, workpaper_id, 1)
    return _detail_out(await workpaper_detail(ctx, engagement_id, workpaper_id))


@router.post(
    "/{workpaper_id}/sign-offs/review",
    action="sign_off.review",
    response_model=WorkpaperDetailOut,
    status_code=201,
)
async def sign_off_review_route(
    engagement_id: UUID, workpaper_id: UUID, ctx: Ctx
) -> WorkpaperDetailOut:
    """SPEC-308 AC-5: the L2 reviewer signs the current content."""
    await sign_off(ctx, engagement_id, workpaper_id, 2)
    return _detail_out(await workpaper_detail(ctx, engagement_id, workpaper_id))


@router.post(
    "/{workpaper_id}/sign-offs/manager",
    action="sign_off.manager",
    response_model=WorkpaperDetailOut,
    status_code=201,
)
async def sign_off_manager_route(
    engagement_id: UUID, workpaper_id: UUID, ctx: Ctx
) -> WorkpaperDetailOut:
    """SPEC-308 AC-5: the L3 manager signs the current content."""
    await sign_off(ctx, engagement_id, workpaper_id, 3)
    return _detail_out(await workpaper_detail(ctx, engagement_id, workpaper_id))


@router.post(
    "/{workpaper_id}/sign-offs/partner",
    action="sign_off.partner",
    response_model=WorkpaperDetailOut,
    status_code=201,
)
async def sign_off_partner_route(
    engagement_id: UUID, workpaper_id: UUID, ctx: Ctx
) -> WorkpaperDetailOut:
    """SPEC-308 AC-5: the L4 partner signs the current content."""
    await sign_off(ctx, engagement_id, workpaper_id, 4)
    return _detail_out(await workpaper_detail(ctx, engagement_id, workpaper_id))


@router.post(
    "/{workpaper_id}/sign-offs/eqr",
    action="sign_off.eqr",
    response_model=WorkpaperDetailOut,
    status_code=201,
)
async def sign_off_eqr_route(
    engagement_id: UUID, workpaper_id: UUID, ctx: Ctx
) -> WorkpaperDetailOut:
    """SPEC-308 AC-5: the L5 engagement quality reviewer signs the current content."""
    await sign_off(ctx, engagement_id, workpaper_id, 5)
    return _detail_out(await workpaper_detail(ctx, engagement_id, workpaper_id))

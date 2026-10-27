"""Working-paper routes (SPEC-308; TASK-319). Reads follow `workpaper.read`; edits
`workpaper.edit`; each sign-off level is its own action in the review matrix."""

from __future__ import annotations

from datetime import date, datetime
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
from abacus.modules.workpapers.tie_out import (
    CheckInput,
    CheckView,
    checks_for,
    define_check,
    edit_check,
)
from abacus.modules.workpapers.ties import Component

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


class TbLinkOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("internal")]
    period_end: Annotated[date, classified("internal")]
    version_no: Annotated[int, classified("internal")]


class LinkedAccountOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_code: Annotated[str, classified("confidential")]
    account_name: Annotated[str, classified("confidential")]
    boy: Annotated[Decimal | None, classified("confidential")]
    eoy: Annotated[Decimal, classified("confidential")]


class WorkpaperDetailOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    workpaper: Annotated[WorkingPaperOut, classified("internal")]
    content_hash: Annotated[str, classified("internal")]
    cells: Annotated[list[CellOut], classified("internal")]
    citations: Annotated[list[CellCitationOut], classified("internal")]
    versions: Annotated[list[WorkingPaperVersionOut], classified("internal")]
    trial_balance: Annotated[TbLinkOut | None, classified("internal")]
    tb_accounts: Annotated[list[LinkedAccountOut], classified("confidential")]


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
        trial_balance=None
        if d.tb is None
        else TbLinkOut(
            id=d.tb.id, label=d.tb.label, period_end=d.tb.period_end, version_no=d.tb.version_no
        ),
        tb_accounts=[
            LinkedAccountOut.model_validate(a, from_attributes=True) for a in d.tb_accounts
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


# --- Tie-out checks on a trial balance (SPEC-310; TASK-321) -----------------------------------

checks_router = AbacusRouter(
    prefix="/v1/engagements/{engagement_id}/trial-balances/{tb_id}/checks", tags=["workpapers"]
)
CheckKind = Literal["balanced", "tie", "rollforward"]
CheckColumn = Literal["eoy", "boy"]


class RollforwardComponentBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: Annotated[str, Field(min_length=1, max_length=80), classified("confidential")]
    sign: Annotated[Literal[1, -1], classified("internal")]
    value: Annotated[Decimal, Field(max_digits=18, decimal_places=2), classified("confidential")]


class TieOutCheckBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: Annotated[str, Field(min_length=1, max_length=120), classified("confidential")]
    kind: Annotated[CheckKind, classified("internal")]
    accounts: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=64)]],
        Field(max_length=200),
        classified("confidential"),
    ] = []
    column: Annotated[CheckColumn, classified("internal")] = "eoy"
    negate: Annotated[bool, classified("internal")] = False
    expected: Annotated[
        Decimal | None, Field(max_digits=18, decimal_places=2), classified("confidential")
    ] = None
    components: Annotated[
        list[RollforwardComponentBody], Field(max_length=12), classified("confidential")
    ] = []
    citation_ids: Annotated[list[UUID], Field(max_length=20), classified("internal")] = []
    tolerance: Annotated[
        Decimal, Field(ge=0, max_digits=18, decimal_places=2), classified("internal")
    ] = Decimal("0.00")


class TieOutCheckEditBody(TieOutCheckBody):
    reason: Annotated[str, Field(min_length=1, max_length=500), classified("confidential")]
    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class RollforwardComponentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: Annotated[str, classified("confidential")]
    sign: Annotated[int, classified("internal")]
    value: Annotated[Decimal, classified("confidential")]


class TieResultOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Annotated[Literal["tie", "off", "pending"], classified("internal")]
    actual: Annotated[Decimal | None, classified("confidential")]
    expected: Annotated[Decimal | None, classified("confidential")]
    difference: Annotated[Decimal | None, classified("confidential")]
    formula: Annotated[str | None, classified("confidential")]
    missing: Annotated[list[str], classified("confidential")]


class TieOutCheckOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("confidential")]
    kind: Annotated[CheckKind, classified("internal")]
    accounts: Annotated[list[str], classified("confidential")]
    column: Annotated[CheckColumn, classified("internal")]
    negate: Annotated[bool, classified("internal")]
    expected: Annotated[Decimal | None, classified("confidential")]
    components: Annotated[list[RollforwardComponentOut], classified("confidential")]
    citation_ids: Annotated[list[UUID], classified("internal")]
    tolerance: Annotated[Decimal, classified("internal")]
    version_no: Annotated[int, classified("internal")]
    defined_by_name: Annotated[str, classified("internal")]
    defined_at: Annotated[datetime, classified("internal")]
    result: Annotated[TieResultOut, classified("confidential")]
    # A-02-T17: the issue a check that does not tie is linked to (AUD-06 c's flag).
    issue_id: Annotated[UUID | None, classified("internal")] = None


def _check_input(body: TieOutCheckBody) -> CheckInput:
    return CheckInput(
        body.label,
        body.kind,
        tuple(body.accounts),
        body.column,
        body.negate,
        body.expected,
        tuple(Component(c.label, c.sign, c.value) for c in body.components),
        tuple(body.citation_ids),
        body.tolerance,
    )


def _checks_out(found: list[CheckView]) -> list[TieOutCheckOut]:
    return [
        TieOutCheckOut(
            id=c.id,
            key=c.key,
            label=c.label,
            kind=c.kind,
            accounts=c.accounts,
            column=c.column,
            negate=c.negate,
            expected=c.expected,
            components=[
                RollforwardComponentOut.model_validate(x, from_attributes=True)
                for x in c.components
            ],
            citation_ids=c.citation_ids,
            tolerance=c.tolerance,
            version_no=c.version_no,
            defined_by_name=c.defined_by_name,
            defined_at=c.defined_at,
            result=TieResultOut(
                status=c.result.status,
                actual=c.result.actual,
                expected=c.result.expected,
                difference=c.result.difference,
                formula=c.result.formula,
                missing=list(c.result.missing),
            ),
            issue_id=c.issue_id,
        )
        for c in found
    ]


@checks_router.get("", action="trial_balance.read", response_model=list[TieOutCheckOut])
async def tie_out_checks_route(engagement_id: UUID, tb_id: UUID, ctx: Ctx) -> list[TieOutCheckOut]:
    """SPEC-310 AC-1: the trial balance's checks with results computed now."""
    return _checks_out(await checks_for(ctx, engagement_id, tb_id))


@checks_router.post(
    "", action="tie_out_check.define", response_model=list[TieOutCheckOut], status_code=201
)
async def define_check_route(
    engagement_id: UUID, tb_id: UUID, body: TieOutCheckBody, ctx: Ctx
) -> list[TieOutCheckOut]:
    """SPEC-310 AC-2: define a check."""
    await define_check(ctx, engagement_id, tb_id, _check_input(body))
    return _checks_out(await checks_for(ctx, engagement_id, tb_id))


@checks_router.put(
    "/{check_id}", action="tie_out_check.define", response_model=list[TieOutCheckOut]
)
async def edit_check_route(
    engagement_id: UUID, tb_id: UUID, check_id: UUID, body: TieOutCheckEditBody, ctx: Ctx
) -> list[TieOutCheckOut]:
    """SPEC-310 AC-3: change a check (a new version, with a reason)."""
    await edit_check(
        ctx, engagement_id, tb_id, check_id, _check_input(body), body.reason, body.seen_version
    )
    return _checks_out(await checks_for(ctx, engagement_id, tb_id))

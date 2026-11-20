"""SH-1 Sheets contract stub (K-03-T09; TASK-8853; SPEC-721; C23; `docs/contracts/sheets.md`;
DEC-5850). Screens SHT-01, SHT-02, SHT-04. The shapes are F-08's `SheetVM` (packages/ui
`sheet/types.ts`, F-08 §4): columns, sections with totals, rows with cell states and versions,
sign-off state and the status bar.

Every route answers: a client principal 404; `sheets.enabled` off 404 (agent-column routes also
need `agent_columns.enabled`); a write that is not a live person's 403 (INV-1); then 501 until its
K-03 build task. Cell values and row content are `confidential` (client records); ids, states and
counts are `internal`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import AGENT_COLUMNS_ENABLED, SHEETS_ENABLED
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
IfMatch = Annotated[str, Header(alias="If-Match", min_length=1, max_length=40)]
Internal = classified("internal")
Confidential = classified("confidential")
Count = Annotated[int, Field(ge=0), Internal]

ColumnType = Literal[
    "text", "number", "currency", "date", "single_select", "person", "linked_evidence",
    "linked_request", "linked_risk", "sign_off", "agent",
]  # fmt: skip
CellState = Literal["empty", "human", "suggested", "adopted", "edited"]
RunScope = Literal["all", "empty_only", "selected"]
RunRowState = Literal[
    "queued", "running", "waiting_on_inputs", "succeeded", "failed", "cancelled", "skipped_adopted"
]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class SheetColumnOptionOut(BaseModel):
    model_config = _cfg()

    value: Annotated[str, Field(max_length=80), Internal]
    label: Annotated[str, Field(max_length=120), Internal]


class SheetColumnOut(BaseModel):
    """SheetVM.columns (SheetGridColumn): key, type, label, width, frozen, agent, options."""

    model_config = _cfg()

    column_id: Annotated[UUID, Internal]
    key: Annotated[str, Field(max_length=60), Internal]
    type: Annotated[ColumnType, Internal]
    label: Annotated[str, Field(max_length=120), Internal]
    width: Annotated[int, Field(ge=40, le=800), Internal]
    frozen: Annotated[bool, Internal] = False
    agent_name: Annotated[str | None, Field(max_length=80), Internal] = None
    agent_unavailable: Annotated[Literal["real_client_data", "consent_7216"] | None, Internal] = (
        None
    )
    options: Annotated[list[SheetColumnOptionOut], Internal] = []


class SheetSectionOut(BaseModel):
    """SheetVM.sections: "STRATUM 1 — ≥ 50,000 (24)" 3,286,400.00."""

    model_config = _cfg()

    key: Annotated[str, Field(max_length=60), Internal]
    title: Annotated[str, Field(max_length=200), Internal]
    count: Count
    total: Annotated[str | None, Field(max_length=40), Confidential] = None
    sub: Annotated[bool, Internal] = False


class SheetStatusOut(BaseModel):
    """The status bar: "40 rows · 1 exception · View: Default"."""

    model_config = _cfg()

    rows: Count
    exceptions: Count
    view: Annotated[str, Field(max_length=80), Internal]
    agent_running: Annotated[bool, Internal] = False
    agent_summary: Annotated[str | None, Field(max_length=120), Internal] = None


class SheetVmOut(BaseModel):
    model_config = _cfg()

    sheet_id: Annotated[UUID, Internal]
    work_item_id: Annotated[UUID, Internal]
    title: Annotated[str, Field(max_length=200), Internal]
    columns: Annotated[list[SheetColumnOut], Internal]
    sections: Annotated[list[SheetSectionOut], Internal]
    status: Annotated[SheetStatusOut, Internal]
    signed_off: Annotated[bool, Internal] = False
    allowed_actions: Annotated[list[str], Internal] = []


class SheetCellOut(BaseModel):
    """SheetCell: value, state, raw, by, at, was, citations, exception."""

    model_config = _cfg()

    value: Annotated[str, Field(max_length=4000), Confidential]
    state: Annotated[CellState, Internal]
    raw: Annotated[str | None, Field(max_length=4000), Confidential] = None
    by: Annotated[str | None, Field(max_length=120), Confidential] = None
    at: Annotated[datetime | None, Internal] = None
    was: Annotated[str | None, Field(max_length=4000), Confidential] = None
    citation_ids: Annotated[list[UUID], Internal] = []
    exception: Annotated[bool, Internal] = False


class SheetRowOut(BaseModel):
    """SheetGridRow: key, section_key, locked, cells, version."""

    model_config = _cfg()

    row_id: Annotated[UUID, Internal]
    key: Annotated[str, Field(max_length=60), Internal]
    section_key: Annotated[str, Field(max_length=60), Internal]
    locked: Annotated[bool, Internal]
    version: Annotated[int, Field(ge=1), Internal]
    cells: Annotated[dict[str, SheetCellOut], Internal]


class SheetRowListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[SheetRowOut], Internal]
    next_cursor: Annotated[str | None, Internal] = None


class SheetRowPatchIn(BaseModel):
    model_config = _cfg()

    cells: Annotated[dict[str, str], Confidential]
    version: Annotated[int, Field(ge=1), Internal]


class SheetRowIn(BaseModel):
    model_config = _cfg()

    section_key: Annotated[str, Field(max_length=60), Internal]
    cells: Annotated[dict[str, str], Confidential] = {}


class SheetFromSampleIn(BaseModel):
    model_config = _cfg()

    sample_set_id: Annotated[UUID, Internal]


class SheetCreateIn(BaseModel):
    model_config = _cfg()

    procedure_id: Annotated[UUID, Internal]
    sheet_definition_ref: Annotated[str, Field(max_length=120), Internal]


class SheetViewOut(BaseModel):
    model_config = _cfg()

    view_id: Annotated[UUID, Internal]
    name: Annotated[str, Field(max_length=80), Internal]
    filters: Annotated[list[dict[str, str]], Internal] = []
    sort: Annotated[list[dict[str, str]], Internal] = []
    hidden: Annotated[list[str], Internal] = []


class SheetViewListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[SheetViewOut], Internal]


class SheetViewIn(BaseModel):
    model_config = _cfg()

    name: Annotated[str, Field(min_length=1, max_length=80), Internal]
    filters: Annotated[list[dict[str, str]], Internal] = []
    sort: Annotated[list[dict[str, str]], Internal] = []
    hidden: Annotated[list[str], Internal] = []


class SheetColumnIn(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,59}$"), Internal]
    type: Annotated[ColumnType, Internal]
    label: Annotated[str, Field(min_length=1, max_length=120), Internal]
    width: Annotated[int, Field(ge=40, le=800), Internal] = 160
    classification_reason: Annotated[str | None, Field(max_length=300), Internal] = None


class ColumnUsageOut(BaseModel):
    model_config = _cfg()

    filled_rows: Count
    views: Count
    in_use: Annotated[bool, Internal]


class AgentColumnOut(BaseModel):
    """SHT-04: the instruction (sanitised; @mentions are column refs), output, scope, status."""

    model_config = _cfg()

    column_id: Annotated[UUID, Internal]
    instruction: Annotated[str, Field(max_length=4000), Internal]
    mention_refs: Annotated[list[str], Internal] = []
    output_type: Annotated[Literal["single_select", "text"], Internal]
    options: Annotated[list[SheetColumnOptionOut], Internal] = []
    default_scope: Annotated[RunScope, Internal] = "empty_only"
    status: Annotated[Literal["draft", "saved"], Internal]
    saved_by: Annotated[str | None, Field(max_length=120), Confidential] = None
    saved_at: Annotated[datetime | None, Internal] = None


class AgentColumnIn(BaseModel):
    model_config = _cfg()

    instruction: Annotated[str, Field(min_length=1, max_length=4000), Internal]
    output_type: Annotated[Literal["single_select", "text"], Internal]
    options: Annotated[list[SheetColumnOptionOut], Internal] = []
    default_scope: Annotated[RunScope, Internal] = "empty_only"


class AgentPreviewIn(BaseModel):
    model_config = _cfg()

    row_ids: Annotated[list[UUID], Field(max_length=3), Internal] = []


class AgentPreviewRowOut(BaseModel):
    model_config = _cfg()

    row_id: Annotated[UUID, Internal]
    value: Annotated[str, Field(max_length=4000), Confidential]
    citation_ids: Annotated[list[UUID], Internal] = []


class AgentPreviewOut(BaseModel):
    """Preview on 3 rows: writes nothing to the sheet."""

    model_config = _cfg()

    preview_id: Annotated[UUID, Internal]
    rows: Annotated[list[AgentPreviewRowOut], Internal]


class AgentEstimateIn(BaseModel):
    model_config = _cfg()

    scope: Annotated[RunScope, Internal]
    row_ids: Annotated[list[UUID], Field(max_length=500), Internal] = []


class AgentEstimateOut(BaseModel):
    model_config = _cfg()

    rows: Count
    agent_minutes: Annotated[int, Field(ge=0), Internal]
    within_budget: Annotated[bool, Internal]


class AgentRunIn(BaseModel):
    model_config = _cfg()

    scope: Annotated[RunScope, Internal]
    row_ids: Annotated[list[UUID], Field(max_length=500), Internal] = []


class AgentColumnRunOut(BaseModel):
    """SHT-04c: Running 4 of 11; 29 on evidence arrival."""

    model_config = _cfg()

    run_id: Annotated[UUID, Internal]
    status: Annotated[Literal["queued", "running", "stopped", "succeeded", "failed"], Internal]
    rows_targeted: Count
    rows_now: Count
    rows_on_arrival: Count
    done: Count = 0


sheets_router = AbacusRouter(prefix="/v1", tags=["sheets"])
_S = "/sheets/{sheet_id}"
_A = f"{_S}/columns/{{column_id}}/agent"


async def _on(ctx: AuthContext, *flags: Flag) -> None:
    if ctx.client:
        raise NotFound(SHEETS_ENABLED.name)
    for flag in (SHEETS_ENABLED, *flags):
        if not await flag_enabled(ctx.tenant, flag):
            raise NotFound(flag.name)


async def _human(ctx: AuthContext, action: str, *flags: Flag) -> None:
    await _on(ctx, *flags)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


@sheets_router.post(
    "/work-items/{work_item_id}/sheets",
    action="sheet.configure",
    response_model=SheetVmOut,
    status_code=201,
    errors=(409, 501),
)
async def sheet_create_route(work_item_id: UUID, body: SheetCreateIn, ctx: Ctx) -> SheetVmOut:
    await _human(ctx, "sheet.configure")
    raise NotImplementedYet


@sheets_router.get(_S, action="sheet.read", response_model=SheetVmOut, errors=(501,))
async def sheet_route(sheet_id: UUID, ctx: Ctx) -> SheetVmOut:
    await _on(ctx)
    raise NotImplementedYet


@sheets_router.get(
    f"{_S}/rows", action="sheet.read", response_model=SheetRowListOut, errors=(501,)
)
async def sheet_rows_route(
    sheet_id: UUID, ctx: Ctx, view: UUID | None = None, cursor: str | None = None
) -> SheetRowListOut:
    await _on(ctx)
    raise NotImplementedYet


@sheets_router.post(
    f"{_S}/rows/from-sample",
    action="sheet.edit",
    response_model=SheetRowListOut,
    status_code=201,
    errors=(409, 501),
)
async def sheet_rows_from_sample_route(
    sheet_id: UUID, body: SheetFromSampleIn, ctx: Ctx, key: IdempotencyKey
) -> SheetRowListOut:
    await _human(ctx, "sheet.edit")
    raise NotImplementedYet


@sheets_router.post(
    f"{_S}/rows",
    action="sheet.edit",
    response_model=SheetRowOut,
    status_code=201,
    errors=(409, 501),
)
async def sheet_row_create_route(sheet_id: UUID, body: SheetRowIn, ctx: Ctx) -> SheetRowOut:
    await _human(ctx, "sheet.edit")
    raise NotImplementedYet


@sheets_router.patch(
    f"{_S}/rows/{{row_id}}", action="sheet.edit", response_model=SheetRowOut, errors=(409, 501)
)
async def sheet_row_patch_route(
    sheet_id: UUID, row_id: UUID, body: SheetRowPatchIn, ctx: Ctx
) -> SheetRowOut:
    """Cell edits through `record_value`: 412 on a stale version; 423 `row_locked`."""
    await _human(ctx, "sheet.edit")
    raise NotImplementedYet


@sheets_router.get(
    f"{_S}/views", action="sheet.read", response_model=SheetViewListOut, errors=(501,)
)
async def sheet_views_route(sheet_id: UUID, ctx: Ctx) -> SheetViewListOut:
    await _on(ctx)
    raise NotImplementedYet


@sheets_router.post(
    f"{_S}/views",
    action="sheet.edit",
    response_model=SheetViewOut,
    status_code=201,
    errors=(409, 501),
)
async def sheet_view_create_route(sheet_id: UUID, body: SheetViewIn, ctx: Ctx) -> SheetViewOut:
    await _human(ctx, "sheet.edit")
    raise NotImplementedYet


@sheets_router.patch(
    f"{_S}/views/{{view_id}}", action="sheet.edit", response_model=SheetViewOut, errors=(409, 501)
)
async def sheet_view_patch_route(
    sheet_id: UUID, view_id: UUID, body: SheetViewIn, ctx: Ctx
) -> SheetViewOut:
    await _human(ctx, "sheet.edit")
    raise NotImplementedYet


@sheets_router.post(
    f"{_S}/columns",
    action="sheet.configure",
    response_model=SheetColumnOut,
    status_code=201,
    errors=(409, 501),
)
async def sheet_column_create_route(
    sheet_id: UUID, body: SheetColumnIn, ctx: Ctx
) -> SheetColumnOut:
    """422 when a confidential type has no classification reason."""
    await _human(ctx, "sheet.configure")
    raise NotImplementedYet


@sheets_router.patch(
    f"{_S}/columns/{{column_id}}",
    action="sheet.configure",
    response_model=SheetColumnOut,
    errors=(409, 501),
)
async def sheet_column_patch_route(
    sheet_id: UUID, column_id: UUID, body: SheetColumnIn, ctx: Ctx
) -> SheetColumnOut:
    await _human(ctx, "sheet.configure")
    raise NotImplementedYet


@sheets_router.get(
    f"{_S}/columns/{{column_id}}/usage",
    action="sheet.read",
    response_model=ColumnUsageOut,
    errors=(501,),
)
async def sheet_column_usage_route(sheet_id: UUID, column_id: UUID, ctx: Ctx) -> ColumnUsageOut:
    await _on(ctx)
    raise NotImplementedYet


@sheets_router.delete(
    f"{_S}/columns/{{column_id}}",
    action="sheet.configure",
    response_model=ColumnUsageOut,
    errors=(409, 501),
)
async def sheet_column_delete_route(sheet_id: UUID, column_id: UUID, ctx: Ctx) -> ColumnUsageOut:
    """409 `column_in_use`."""
    await _human(ctx, "sheet.configure")
    raise NotImplementedYet


@sheets_router.get(_A, action="sheet.read", response_model=AgentColumnOut, errors=(501,))
async def agent_column_route(sheet_id: UUID, column_id: UUID, ctx: Ctx) -> AgentColumnOut:
    await _on(ctx, AGENT_COLUMNS_ENABLED)
    raise NotImplementedYet


@sheets_router.put(_A, action="sheet.configure", response_model=AgentColumnOut, errors=(409, 501))
async def agent_column_put_route(
    sheet_id: UUID, column_id: UUID, body: AgentColumnIn, ctx: Ctx, if_match: IfMatch
) -> AgentColumnOut:
    """422 `missing_reference`; 409 `preview_required` on save."""
    await _human(ctx, "sheet.configure", AGENT_COLUMNS_ENABLED)
    raise NotImplementedYet


@sheets_router.post(
    f"{_A}/preview", action="agent_column.run", response_model=AgentPreviewOut, errors=(409, 501)
)
async def agent_column_preview_route(
    sheet_id: UUID, column_id: UUID, body: AgentPreviewIn, ctx: Ctx
) -> AgentPreviewOut:
    await _human(ctx, "agent_column.run", AGENT_COLUMNS_ENABLED)
    raise NotImplementedYet


@sheets_router.post(
    f"{_A}/estimate", action="agent_column.run", response_model=AgentEstimateOut, errors=(501,)
)
async def agent_column_estimate_route(
    sheet_id: UUID, column_id: UUID, body: AgentEstimateIn, ctx: Ctx
) -> AgentEstimateOut:
    await _human(ctx, "agent_column.run", AGENT_COLUMNS_ENABLED)
    raise NotImplementedYet


@sheets_router.post(
    f"{_A}/runs",
    action="agent_column.run",
    response_model=AgentColumnRunOut,
    status_code=202,
    errors=(409, 501),
)
async def agent_column_run_route(
    sheet_id: UUID, column_id: UUID, body: AgentRunIn, ctx: Ctx, key: IdempotencyKey
) -> AgentColumnRunOut:
    """409 `preview_required`, `over_budget` (unless the EM overrides)."""
    await _human(ctx, "agent_column.run", AGENT_COLUMNS_ENABLED)
    raise NotImplementedYet


@sheets_router.post(
    f"{_A}/runs/{{run_id}}/stop",
    action="agent_column.run",
    response_model=AgentColumnRunOut,
    errors=(409, 501),
)
async def agent_column_stop_route(
    sheet_id: UUID, column_id: UUID, run_id: UUID, ctx: Ctx
) -> AgentColumnRunOut:
    await _human(ctx, "agent_column.run", AGENT_COLUMNS_ENABLED)
    raise NotImplementedYet


@sheets_router.get(f"{_S}/export.xlsx", action="sheet.export", response_model=bytes, errors=(501,))
async def sheet_export_route(sheet_id: UUID, ctx: Ctx) -> bytes:
    """ "Open in Excel": a deterministic xlsx (the add-in is W-04)."""
    await _on(ctx)
    raise NotImplementedYet


__all__ = ["sheets_router"]

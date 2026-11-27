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
from typing import Annotated, Literal, cast
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
# K-03-T23 (DEC-6034): a date column's display, its range check, and the four ADR-031 levels.
ColumnDisplay = Literal["date", "month"]
ColumnValidation = Literal["end_on_or_after_start"]
Classification = Literal["restricted", "confidential", "internal", "public"]
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
    # K-03-T23 (DEC-6034), additive: the configuration SHT-02 edits (the columns service is
    # K-03-T24; these are stub fields until then).
    description: Annotated[str | None, Field(max_length=300), Internal] = None
    date_range: Annotated[bool, Internal] = False
    display: Annotated[ColumnDisplay | None, Internal] = None
    required: Annotated[bool, Internal] = False
    validation: Annotated[ColumnValidation | None, Internal] = None
    classification: Annotated[Classification, Internal] = "restricted"
    visible_to_client: Annotated[bool, Internal] = False


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
    # K-03-T20 (DEC-6020), additive: code's status line ("40 rows · 0 tested · seed 0x7C31B4").
    summary: Annotated[str, Field(max_length=120), Internal] = ""
    agent_running: Annotated[bool, Internal] = False
    agent_summary: Annotated[str | None, Field(max_length=120), Internal] = None


class SheetVmOut(BaseModel):
    model_config = _cfg()

    sheet_id: Annotated[UUID, Internal]
    work_item_id: Annotated[UUID, Internal]
    # K-03-T23 (DEC-6034), additive: the engagement SHT-02's suggestion thread posts in.
    engagement_id: Annotated[UUID | None, Internal] = None
    title: Annotated[str, Field(max_length=200), Internal]
    columns: Annotated[list[SheetColumnOut], Internal]
    sections: Annotated[list[SheetSectionOut], Internal]
    status: Annotated[SheetStatusOut, Internal]
    signed_off: Annotated[bool, Internal] = False
    allowed_actions: Annotated[list[str], Internal] = []
    # K-03-T23 (DEC-6034), additive: who may change columns here (the engagement's manager), for
    # SHT-02 f's "Suggest to <name>…"; the columns service (K-03-T24) fills it.
    configurer: Annotated[str | None, Field(max_length=120), Confidential] = None


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


class SheetRowFactOut(BaseModel):
    """K-03-T22 (DEC-6033): one KV row of the drawer's Details card, in column order."""

    model_config = _cfg()

    label: Annotated[str, Field(max_length=120), Internal]
    type: Annotated[ColumnType, Internal]
    value: Annotated[str, Field(max_length=4000), Confidential]


class SheetRowWhyOut(BaseModel):
    """The agent's reason for one suggested cell (the Why card). `rationale` is agent text,
    rendered only through AgentText; its citations are the cell's anchor's stack
    (`GET /v1/citations?anchor_type=sheet_row&anchor_id=<row>&anchor_ref=<column_key>`)."""

    model_config = _cfg()

    column_key: Annotated[str, Field(max_length=60), Internal]
    suggestion_id: Annotated[UUID, Internal]
    status: Annotated[str, Field(max_length=20), Internal]
    version: Annotated[int, Field(ge=1), Internal]
    rationale: Annotated[str | None, Field(max_length=4000), Confidential] = None
    citation_count: Count = 0
    # The run that made it: the drawer's Agents tab reads `GET /v1/agent-runs/{id}`.
    agent_run_id: Annotated[UUID | None, Internal] = None


class SheetRowLinkOut(BaseModel):
    """One link on the drawer's Evidence, Requests or Risks tab; `label` is the evidence
    version's display name (requests and risks name theirs on their own screens)."""

    model_config = _cfg()

    kind: Annotated[Literal["evidence", "request", "risk"], Internal]
    target_id: Annotated[UUID, Internal]
    linked_at: Annotated[datetime, Internal]
    label: Annotated[str | None, Field(max_length=300), Confidential] = None


class SheetRowDetailOut(BaseModel):
    """SHT-01 e: the row drawer's read (`?ov=row:<sheet>:<key>`)."""

    model_config = _cfg()

    # The comments and to-dos tabs anchor on the row inside this engagement (C-29, C-30).
    engagement_id: Annotated[UUID, Internal]
    row: Annotated[SheetRowOut, Internal]
    facts: Annotated[list[SheetRowFactOut], Internal] = []
    why: Annotated[list[SheetRowWhyOut], Internal] = []
    links: Annotated[list[SheetRowLinkOut], Internal] = []


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
    columns_off: Annotated[list[str], Internal] = []  # DEC-43: no "hidden" field names


class SheetViewListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[SheetViewOut], Internal]


class SheetViewIn(BaseModel):
    model_config = _cfg()

    name: Annotated[str, Field(min_length=1, max_length=80), Internal]
    filters: Annotated[list[dict[str, str]], Internal] = []
    sort: Annotated[list[dict[str, str]], Internal] = []
    columns_off: Annotated[list[str], Internal] = []  # DEC-43: no "hidden" field names


class SheetColumnIn(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,59}$"), Internal]
    type: Annotated[ColumnType, Internal]
    label: Annotated[str, Field(min_length=1, max_length=120), Internal]
    width: Annotated[int, Field(ge=40, le=800), Internal] = 160
    classification_reason: Annotated[str | None, Field(max_length=300), Internal] = None
    # K-03-T23 (DEC-6034), additive: SHT-02's fields. A level below Restricted on a client-data
    # column needs `classification_reason` (K-03-T24 enforces it with 422).
    description: Annotated[str | None, Field(max_length=300), Internal] = None
    after_key: Annotated[str | None, Field(pattern=r"^[a-z][a-z0-9_]{0,59}$"), Internal] = None
    date_range: Annotated[bool, Internal] = False
    display: Annotated[ColumnDisplay | None, Internal] = None
    required: Annotated[bool, Internal] = False
    validation: Annotated[ColumnValidation | None, Internal] = None
    classification: Annotated[Classification, Internal] = "restricted"


class ColumnUsageOut(BaseModel):
    model_config = _cfg()

    filled_rows: Count
    views: Count
    in_use: Annotated[bool, Internal]
    # K-03-T23 (DEC-6034), additive: what SHT-02's "Used in" line and blocked delete name.
    view_names: Annotated[list[str], Internal] = []
    rules: Count = 0
    agent_columns: Annotated[list[str], Internal] = []


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
    status: Annotated[Literal["queued", "running", "cancelled", "succeeded", "failed"], Internal]
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


# --- K-03-T20 (DEC-6020): the sheets core service behind the routes ------------------------------


def _vm_out(vm: object) -> SheetVmOut:
    from abacus.modules.workpapers import sheets as sh

    found = cast(sh.SheetVm, vm)
    return SheetVmOut(
        sheet_id=found.id, work_item_id=found.work_item_id, title=found.title,
        engagement_id=found.engagement_id,
        columns=[
            SheetColumnOut(column_id=c.id, key=c.key, type=cast(ColumnType, c.type), label=c.name,
                           width=c.width, frozen=c.frozen)
            for c in found.columns
        ],
        sections=[
            SheetSectionOut(key=x.key, title=x.title, count=x.count,
                            total=None if x.total is None else f"{x.total:,.2f}")
            for x in found.sections
        ],
        status=SheetStatusOut(rows=found.rows, exceptions=found.exceptions, view=found.view,
                              summary=sh.status_line(found)),
    )  # fmt: skip


def _row_out(row: object) -> SheetRowOut:
    from abacus.modules.workpapers import sheets as sh

    r = cast(sh.SheetRow, row)
    return SheetRowOut(
        row_id=r.id, key=r.key, section_key=r.section_key, locked=r.locked, version=r.version,
        cells={k: SheetCellOut(value=c.value, state=cast(CellState, c.state), at=c.at,
                               exception=c.exception) for k, c in r.cells.items()},
    )  # fmt: skip


async def _one_row(ctx: AuthContext, sheet_id: UUID, row_id: UUID) -> SheetRowOut:
    from abacus.modules.workpapers import sheets as sh

    found, _ = await sh.rows(ctx, sheet_id)
    for r in found:
        if r.id == row_id:
            return _row_out(r)
    raise NotFound("sheet_row")


def _view_out(view: object) -> SheetViewOut:
    from abacus.modules.workpapers import sheets as sh

    v = cast(sh.SheetView, view)
    return SheetViewOut(
        view_id=v.id,
        name=v.name,
        filters=[dict(f) for f in v.filters],
        sort=[dict(x) for x in v.sort],
        columns_off=list(v.columns_off),
    )


@sheets_router.post(
    "/work-items/{work_item_id}/sheets",
    action="sheet.configure",
    response_model=SheetVmOut,
    status_code=201,
    errors=(409, 501),
)
async def sheet_create_route(work_item_id: UUID, body: SheetCreateIn, ctx: Ctx) -> SheetVmOut:
    await _human(ctx, "sheet.configure")
    from abacus.modules.workpapers import sheets as sh

    made = await sh.create_sheet(ctx, work_item_id, body.procedure_id, body.sheet_definition_ref)
    return _vm_out(await sh.sheet_vm(ctx, made))


@sheets_router.get(_S, action="sheet.read", response_model=SheetVmOut, errors=(501,))
async def sheet_route(sheet_id: UUID, ctx: Ctx, view: UUID | None = None) -> SheetVmOut:
    await _on(ctx)
    from abacus.modules.workpapers import sheets as sh

    return _vm_out(await sh.sheet_vm(ctx, sheet_id, view))


@sheets_router.get(
    f"{_S}/rows", action="sheet.read", response_model=SheetRowListOut, errors=(501,)
)
async def sheet_rows_route(
    sheet_id: UUID, ctx: Ctx, view: UUID | None = None, cursor: str | None = None
) -> SheetRowListOut:
    await _on(ctx)
    from abacus.modules.workpapers import sheets as sh

    del cursor  # one page: a sheet holds at most a sample's rows (K-03-T20)
    found, _ = await sh.rows(ctx, sheet_id, view)
    return SheetRowListOut(items=[_row_out(r) for r in found])


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
    """Idempotent by content: an item already on the sheet is not added again."""
    await _human(ctx, "sheet.edit")
    from abacus.modules.workpapers import sheets as sh

    del key
    added = set(await sh.add_rows_from_sample(ctx, sheet_id, body.sample_set_id))
    found, _ = await sh.rows(ctx, sheet_id)
    return SheetRowListOut(items=[_row_out(r) for r in found if r.id in added])


@sheets_router.post(
    f"{_S}/rows",
    action="sheet.edit",
    response_model=SheetRowOut,
    status_code=201,
    errors=(409, 501),
)
async def sheet_row_create_route(sheet_id: UUID, body: SheetRowIn, ctx: Ctx) -> SheetRowOut:
    await _human(ctx, "sheet.edit")
    from abacus.modules.workpapers import sheets as sh

    made = await sh.add_row(ctx, sheet_id, body.section_key, body.cells)
    return await _one_row(ctx, sheet_id, made)


@sheets_router.patch(
    f"{_S}/rows/{{row_id}}",
    action="sheet.edit",
    response_model=SheetRowOut,
    errors=(409, 412, 501),
)
async def sheet_row_patch_route(
    sheet_id: UUID, row_id: UUID, body: SheetRowPatchIn, ctx: Ctx
) -> SheetRowOut:
    """Cell edits through `record_value`: 412 on a stale version; 409 `row_locked`."""
    await _human(ctx, "sheet.edit")
    from abacus.modules.workpapers import sheets as sh

    await sh.edit_row(ctx, sheet_id, row_id, body.cells, body.version)
    return await _one_row(ctx, sheet_id, row_id)


@sheets_router.get(
    f"{_S}/rows/{{row_id}}", action="sheet.read", response_model=SheetRowDetailOut, errors=(501,)
)
async def sheet_row_detail_route(sheet_id: UUID, row_id: UUID, ctx: Ctx) -> SheetRowDetailOut:
    """K-03-T22 (DEC-6033): SHT-01's row drawer: the row, its facts, the agent's reason for each
    suggested cell and its links. 404 for a row on another sheet or out of the reader's walls."""
    await _on(ctx)
    from abacus.modules.workpapers import sheets as sh

    found = await sh.row_detail(ctx, sheet_id, row_id)
    return SheetRowDetailOut(
        engagement_id=found.engagement_id,
        row=_row_out(found.row),
        facts=[SheetRowFactOut(label=f.label, type=cast(ColumnType, f.type), value=f.value)
               for f in found.facts],
        why=[SheetRowWhyOut(column_key=w.column_key, suggestion_id=w.suggestion_id,
                            status=w.status, version=w.version, rationale=w.rationale,
                            citation_count=w.citation_count, agent_run_id=w.agent_run_id)
             for w in found.why],
        links=[SheetRowLinkOut(kind=cast(Literal["evidence", "request", "risk"], k.kind),
                               target_id=k.target_id, linked_at=k.linked_at, label=k.label)
               for k in found.links],
    )  # fmt: skip


@sheets_router.get(
    f"{_S}/views", action="sheet.read", response_model=SheetViewListOut, errors=(501,)
)
async def sheet_views_route(sheet_id: UUID, ctx: Ctx) -> SheetViewListOut:
    await _on(ctx)
    from abacus.modules.workpapers import sheets as sh

    return SheetViewListOut(items=[_view_out(v) for v in await sh.views(ctx, sheet_id)])


@sheets_router.post(
    f"{_S}/views",
    action="sheet.edit",
    response_model=SheetViewOut,
    status_code=201,
    errors=(409, 501),
)
async def sheet_view_create_route(sheet_id: UUID, body: SheetViewIn, ctx: Ctx) -> SheetViewOut:
    await _human(ctx, "sheet.edit")
    return await _saved_view(ctx, sheet_id, body, None)


@sheets_router.patch(
    f"{_S}/views/{{view_id}}", action="sheet.edit", response_model=SheetViewOut, errors=(409, 501)
)
async def sheet_view_patch_route(
    sheet_id: UUID, view_id: UUID, body: SheetViewIn, ctx: Ctx
) -> SheetViewOut:
    await _human(ctx, "sheet.edit")
    return await _saved_view(ctx, sheet_id, body, view_id)


async def _saved_view(
    ctx: AuthContext, sheet_id: UUID, body: SheetViewIn, view_id: UUID | None
) -> SheetViewOut:
    from abacus.modules.workpapers import sheets as sh

    saved = await sh.save_view(
        ctx, sheet_id, body.name, body.filters, body.sort, body.columns_off, view_id
    )
    for v in await sh.views(ctx, sheet_id):
        if v.id == saved:
            return _view_out(v)
    raise NotFound("sheet_view")


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

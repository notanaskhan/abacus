"""The A-04 workpaper core contract stub (A-04-T01; TASK-2707; DEC-1757).
Contract: `docs/contracts/workpapers-core.md`; screens AUD-04, AUD-05 and AUD-09 (the cell store).

The live SPEC-308 working-paper routes (`routes.py`: list, create, detail, PUT cells, citations,
sign-offs) and fieldwork's SPEC-300 procedure routes stay on their paths, unflagged. A-04 adds,
behind `workpapers.core`: the record projection by tab and version, versions, cell edits with
`expected_version` and a reason to override an agent value, the deterministic export, attention
flags, and the program-tailoring read and write. Draft runs are behind `workpapers.drafting` too.

Paths that would sit under a live route's parameter are moved so nothing is stubbed over it
(DEC-1757): the list with section states is `GET …/workpaper-states`, the projection
`GET …/workpapers/{id}/record`, and one procedures read serves AUD-04 and KNW-03 d
(`GET …/program-tailoring`).

The gate, in order: a client principal 404 (INV-4); the route's action on the engagement (walls
404, independence 403); 404 with the flag off; then 501 `not_implemented` until A-04-T04 (record,
versions, cells, export), T07 (procedures and tailoring), T11 (drafts) and T19 (flags).

Cell values are typed strings (`{t: "decimal", v: "48600.00"}`): code computes, the browser never
sums (ADR-050). A cell written by the agent is a suggestion until a person adopts it (ADR-005).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import WORKPAPERS_CORE, WORKPAPERS_DRAFTING
from abacus.kernel._statuses import (
    AttentionFlagStatus,
    AuditProcedureStatus,
    AuditSectionStatus,
    WorkpaperValueStateStatus,
)
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AbacusRouter, AuthContext, authorise, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
WorkpaperKind = Literal[
    "general_audit_planning", "risk_assessment", "internal_control", "service_organizations"
]
BandKind = Literal["section", "menu", "sheet"]
ValueType = Literal["decimal", "text", "date", "bool", "percent", "empty"]
ValueSource = Literal["agent", "human", "formula", "tb_linked", "engine_import"]
ProducedBy = Literal["agent", "human"]
VersionCause = Literal["draft", "adopt", "edit", "restore"]
DraftMode = Literal["gap", "risk_narrative", "risk", "ic", "soc1"]
# A procedure keeps its program step's level (0581, DEC-1761).
ProcedureLevel = Literal["foundation", "planning", "testing", "completion"]
LinkedWorkKind = Literal["workpaper", "sheet", "screens"]
# What the person may do on this record; the screen shows only these controls.
WorkpaperAction = Literal[
    "workpaper.edit",
    "workpaper.draft",
    "workpaper.export",
    "attention_flag.convert",
    "sign_off.prepare",
    "sign_off.review",
]
CellKey = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.]{1,64}$")]
SheetKey = Annotated[str, Field(pattern=r"^[a-z0-9_]{1,64}$")]


# --- the record projection (A-04 §4.3; T04) ----------------------------------------------------


class TypedValue(BaseModel):
    """A cell's value as a typed string; amounts are decimal strings from code (ADR-050)."""

    model_config = ConfigDict(frozen=True)

    t: Annotated[ValueType, classified("internal")]
    v: Annotated[str | None, Field(max_length=20_000), classified("confidential")] = None


class WorkpaperCellOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    sheet_key: Annotated[str, classified("internal")]
    cell_key: Annotated[str, classified("internal")]  # "D2" or "S1.R3.value"
    section_key: Annotated[str | None, classified("internal")]
    row_key: Annotated[str | None, classified("internal")]
    col_key: Annotated[str | None, classified("internal")]
    value: Annotated[TypedValue, classified("confidential")]
    value_source: Annotated[ValueSource, classified("internal")]
    value_state: Annotated[WorkpaperValueStateStatus, classified("internal")]
    # A pending agent value names its suggestion; the cell's `value` is then the prior value.
    suggestion_id: Annotated[UUID | None, classified("internal")]
    tickmarks: Annotated[list[str], Field(max_length=10), classified("internal")]
    citation_ids: Annotated[list[UUID], Field(max_length=50), classified("internal")]
    updated_version_no: Annotated[int, Field(ge=1), classified("internal")]


class SectionStateOut(BaseModel):
    """A section's rail row: the cockpit's state word and the requests it waits on (AC1.8)."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    title: Annotated[str, classified("internal")]
    band_kind: Annotated[BandKind, classified("internal")]
    sheet_key: Annotated[str | None, classified("internal")]
    state: Annotated[AuditSectionStatus, classified("internal")]
    waiting_on_request_ids: Annotated[list[UUID], Field(max_length=50), classified("internal")]


class SignOffRungOut(BaseModel):
    """One rung of the ladder; `stale` from the owner's content hash (C3 R-SO-8)."""

    model_config = ConfigDict(frozen=True)

    level: Annotated[Literal["L1", "L2", "L3", "L4", "EQR"], classified("internal")]
    initials: Annotated[str | None, classified("internal")]
    signed_at: Annotated[datetime | None, classified("internal")]
    stale: Annotated[bool, classified("internal")]


class AttentionFlagOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    section_key: Annotated[str, classified("internal")]
    row_key: Annotated[str | None, classified("internal")]
    kind: Annotated[Literal["pbc_gap"], classified("internal")]
    text: Annotated[str, Field(max_length=2_000), classified("confidential")]
    state: Annotated[AttentionFlagStatus, classified("internal")]
    converted_to_kind: Annotated[
        Literal["request_item", "review_note"] | None, classified("internal")
    ]
    converted_to_id: Annotated[UUID | None, classified("internal")]


class WorkpaperStateOut(BaseModel):
    """A row of `GET …/workpaper-states`: one workpaper with its sections' states."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    code: Annotated[str, classified("internal")]  # the firm's code: "GAP", "RA", "IC", "SO"
    kind: Annotated[WorkpaperKind, classified("internal")]
    title: Annotated[str, classified("internal")]
    current_version_no: Annotated[int, Field(ge=0), classified("internal")]
    sections: Annotated[list[SectionStateOut], classified("internal")]


class WorkpaperRecordOut(BaseModel):
    """The record projection for one tab at one version (AUD-04 a-f; AUD-05; AUD-09)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    code: Annotated[str, classified("internal")]
    kind: Annotated[WorkpaperKind, classified("internal")]
    title: Annotated[str, classified("internal")]
    audit_area: Annotated[str | None, classified("internal")]
    program_step_keys: Annotated[list[str], classified("internal")]
    version_no: Annotated[int, Field(ge=0), classified("internal")]
    current_version_no: Annotated[int, Field(ge=0), classified("internal")]
    content_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]
    tab: Annotated[str | None, classified("internal")]
    sections: Annotated[list[SectionStateOut], classified("internal")]
    cells: Annotated[list[WorkpaperCellOut], classified("confidential")]
    flags: Annotated[list[AttentionFlagOut], classified("confidential")]
    sign_offs: Annotated[list[SignOffRungOut], classified("internal")]
    allowed_actions: Annotated[list[WorkpaperAction], classified("internal")]


class WorkpaperVersionOut(BaseModel):
    """A version with its producer: "<person> via Agent" for a draft (INV-5)."""

    model_config = ConfigDict(frozen=True)

    version_no: Annotated[int, Field(ge=1), classified("internal")]
    content_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]
    produced_by_kind: Annotated[ProducedBy, classified("internal")]
    agent_run_id: Annotated[UUID | None, classified("internal")]
    created_by_name: Annotated[str, classified("internal")]
    on_behalf_of_name: Annotated[str | None, classified("internal")]
    cause: Annotated[VersionCause, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


# --- writes (T04, T11, T19) ---------------------------------------------------------------------


class CellEditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sheet_key: Annotated[SheetKey, classified("internal")]
    cell_key: Annotated[CellKey, classified("internal")]
    value: Annotated[TypedValue, classified("confidential")]
    # Required when the cell's current value came from the agent (422 `reason_required`).
    reason: Annotated[
        str | None, Field(min_length=1, max_length=2_000), classified("confidential")
    ] = None


class CellsEditIn(BaseModel):
    """Edit cells through `review.api.record_value` only; 409 `version_conflict` when stale."""

    model_config = ConfigDict(extra="forbid")

    expected_version: Annotated[int, Field(ge=0), classified("internal")]
    cells: Annotated[
        list[CellEditIn], Field(min_length=1, max_length=500), classified("confidential")
    ]


class WorkpaperDraftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Annotated[DraftMode, classified("internal")]
    section_key: Annotated[str | None, Field(max_length=64), classified("internal")] = None


class WorkpaperDraftStartedOut(BaseModel):
    """202: the run is queued; the agent writes suggestions only, never cell values (AC1.1)."""

    model_config = ConfigDict(frozen=True)

    run_id: Annotated[UUID, classified("internal")]
    status: Annotated[Literal["queued"], classified("internal")] = "queued"


class FlagConvertIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to: Annotated[Literal["request_draft", "review_note"], classified("internal")]


class FlagConvertedOut(BaseModel):
    """A request **draft** (SHL-14 prefill) or an open review note; nothing is sent (AC2.3)."""

    model_config = ConfigDict(frozen=True)

    flag: Annotated[AttentionFlagOut, classified("confidential")]
    draft_id: Annotated[UUID, classified("internal")]


# --- procedures and program tailoring (T07) -----------------------------------------------------


class LinkedWorkOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[LinkedWorkKind, classified("internal")]
    ref: Annotated[str, classified("internal")]


class ProgramProcedureOut(BaseModel):
    """A procedure from the pinned methodology version (Northwind: 67, 21 mandatory)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    program_code: Annotated[str, classified("internal")]  # "BH-EBP-110"
    program_step_key: Annotated[str, classified("internal")]
    number: Annotated[int, Field(ge=1), classified("internal")]
    methodology_version_id: Annotated[UUID, classified("internal")]
    level: Annotated[ProcedureLevel, classified("internal")]
    mandatory: Annotated[bool, classified("internal")]
    tailored: Annotated[bool, classified("internal")]
    tailored_rationale: Annotated[str | None, classified("confidential")]
    status: Annotated[AuditProcedureStatus, classified("internal")]
    linked_work: Annotated[LinkedWorkOut | None, classified("internal")]
    row_version: Annotated[int, Field(ge=1), classified("internal")]


class TailorIn(BaseModel):
    """Tailor a non-mandatory step (409 `mandatory_step`); a rationale is required to tailor."""

    model_config = ConfigDict(extra="forbid")

    expected_version: Annotated[int, Field(ge=1), classified("internal")]
    tailored: Annotated[bool, classified("internal")]
    rationale: Annotated[
        str | None, Field(min_length=1, max_length=2_000), classified("confidential")
    ] = None


# --- the gate ------------------------------------------------------------------------------------


async def gate(ctx: AuthContext, engagement_id: UUID, action: str, *flags: Flag) -> None:
    """Client 404; the action on the engagement (walls 404, independence 403); each flag 404."""
    if ctx.client:
        raise NotFound("workpapers")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    for flag in flags:
        if not await flag_enabled(ctx.tenant, flag):
            raise NotFound(flag.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["workpapers"])
_wp = "/workpapers/{workpaper_id}"


@router.get(
    "/workpaper-states",
    action="workpaper.read",
    response_model=ListPage[WorkpaperStateOut],
    errors=(501,),
)
async def workpaper_states_route(
    engagement_id: UUID, ctx: Ctx, kind: WorkpaperKind | None = None
) -> ListPage[WorkpaperStateOut]:
    """Every A-04 workpaper with its section states for the cockpit rail (T04)."""
    await gate(ctx, engagement_id, "workpaper.read", WORKPAPERS_CORE)
    _not_yet()


@router.get(
    f"{_wp}/record", action="workpaper.read", response_model=WorkpaperRecordOut, errors=(501,)
)
async def workpaper_record_route(
    engagement_id: UUID,
    workpaper_id: UUID,
    ctx: Ctx,
    tab: Annotated[str | None, Query(max_length=64)] = None,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> WorkpaperRecordOut:
    """The projection: sections, cells with tick and suggestion state, citation ids, flags, the
    sign-off ladder and allowed_actions (T04)."""
    await gate(ctx, engagement_id, "workpaper.read", WORKPAPERS_CORE)
    _not_yet()


@router.get(
    f"{_wp}/versions",
    action="workpaper.read",
    response_model=list[WorkpaperVersionOut],
    errors=(501,),
)
async def workpaper_versions_route(
    engagement_id: UUID, workpaper_id: UUID, ctx: Ctx
) -> list[WorkpaperVersionOut]:
    """Versions with producer and cause (T04)."""
    await gate(ctx, engagement_id, "workpaper.read", WORKPAPERS_CORE)
    _not_yet()


@router.patch(
    f"{_wp}/cells",
    action="workpaper.edit",
    response_model=WorkpaperRecordOut,
    errors=(409, 501),
)
async def workpaper_cells_edit_route(
    engagement_id: UUID,
    workpaper_id: UUID,
    body: CellsEditIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> WorkpaperRecordOut:
    """Edit cells through `review.api.record_value`; 409 `version_conflict`, 422
    `reason_required`; a later edit makes an L2 sign-off stale (AC1.3, AC1.6; T04)."""
    await gate(ctx, engagement_id, "workpaper.edit", WORKPAPERS_CORE)
    _not_yet()


@router.post(
    f"{_wp}/drafts",
    action="workpaper.draft",
    response_model=WorkpaperDraftStartedOut,
    status_code=202,
    errors=(409, 501),
)
async def workpaper_draft_route(
    engagement_id: UUID,
    workpaper_id: UUID,
    body: WorkpaperDraftIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> WorkpaperDraftStartedOut:
    """Start a section draft (`workpapers.section_drafter`); 409 `drafting_not_enabled` for a
    firm without clearance, `pack_configuration_error` before any model call (T11)."""
    await gate(ctx, engagement_id, "workpaper.draft", WORKPAPERS_CORE, WORKPAPERS_DRAFTING)
    _not_yet()


@router.get(f"{_wp}/export.xlsx", action="workpaper.export", response_model=bytes, errors=(501,))
async def workpaper_export_route(
    engagement_id: UUID,
    workpaper_id: UUID,
    ctx: Ctx,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> bytes:
    """Byte-identical XLSX for identical data; client strings as text (ADR-052); audited
    `workpaper.exported` (AC1.7; T04)."""
    await gate(ctx, engagement_id, "workpaper.export", WORKPAPERS_CORE)
    _not_yet()


@router.post(
    f"{_wp}/flags/{{flag_id}}/convert",
    action="attention_flag.convert",
    response_model=FlagConvertedOut,
    errors=(409, 501),
)
async def attention_flag_convert_route(
    engagement_id: UUID,
    workpaper_id: UUID,
    flag_id: UUID,
    body: FlagConvertIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> FlagConvertedOut:
    """Convert a PBC GAP flag to a request draft or a review note; the history records it (T19)."""
    await gate(ctx, engagement_id, "attention_flag.convert", WORKPAPERS_CORE)
    _not_yet()


@router.post(
    f"{_wp}/flags/{{flag_id}}/remind",
    action="follow_up.draft",
    response_model=FlagConvertedOut,
    errors=(409, 501),
)
async def attention_flag_remind_route(
    engagement_id: UUID,
    workpaper_id: UUID,
    flag_id: UUID,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> FlagConvertedOut:
    """A follow-up **draft** to the contact; a person sends it (T19)."""
    await gate(ctx, engagement_id, "follow_up.draft", WORKPAPERS_CORE)
    _not_yet()


@router.get(
    "/program-tailoring",
    action="procedure.read",
    response_model=ListPage[ProgramProcedureOut],
    errors=(501,),
)
async def program_tailoring_route(
    engagement_id: UUID,
    ctx: Ctx,
    program: Annotated[str | None, Query(max_length=64)] = None,
) -> ListPage[ProgramProcedureOut]:
    """The procedures from the pinned version with their tailoring: AUD-04 and KNW-03 d (T07)."""
    await gate(ctx, engagement_id, "procedure.read", WORKPAPERS_CORE)
    _not_yet()


@router.patch(
    "/procedures/{procedure_id}",
    action="procedure.tailor",
    response_model=ProgramProcedureOut,
    errors=(409, 501),
)
async def procedure_tailor_route(
    engagement_id: UUID,
    procedure_id: UUID,
    body: TailorIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> ProgramProcedureOut:
    """Tailor a non-mandatory step (409 `mandatory_step`; 409 `version_conflict`); audited
    `procedure.tailored` (AC1.9; T07)."""
    await gate(ctx, engagement_id, "procedure.tailor", WORKPAPERS_CORE)
    _not_yet()

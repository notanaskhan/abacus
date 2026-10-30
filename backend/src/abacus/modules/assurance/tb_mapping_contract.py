"""The C9 v2 contract stub: taxonomy and mapping (A-03-T03; TASK-2505; SPEC-580 AC-16; ADR-341).
Contract: `docs/contracts/ledger-mapping.md`; screen AUD-31.

The live v0 operations (SPEC-316, `mapping_routes.py`) stay on their paths, unflagged, until
A-03-T08 and T12 move AUD-31 onto these. C9 v2 adds, behind `ledger.tb_mapping`: the grouping
catalogue and the picker, mapping sets per trial balance of record, the run and its progress, one
account's edit, confirm, and the mapped trial balance. Routes live here because `ledger` has
none and imports nothing (Q-15, ADR-341 §2).

ADR-341 §5: rule mappings are computed on read and people's edits are insert-only
(`mapping_set_edits`), so an account mapping is named by its mapping set and account code, not a
stored row id (DEC-1555). Display status (In progress, Prepared, Reviewed, Changed after sign-off)
is computed, never stored. No route suggests a mapping: `suggested` and `adopted` are reserved
for A-09's TB mapper, and so is the adopt route, declared in the contract doc only.

The gate is the sampling stub's (DEC-1553): a client principal 404; the action on the engagement,
or for a mapping-set id the read at firm level with any non-person refused on a write; then 404
with the flag off; then the Granite Peak fixture where one exists, otherwise 501.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import LEDGER_TB_MAPPING
from abacus.kernel._statuses import AccountMappingStateStatus, MappingSetStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.assurance import tb_mapping_fixtures as fx
from abacus.modules.assurance.mapping import catalogue, picker
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    current_context,
    names_of,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
Money = Annotated[Decimal, classified("confidential")]
GroupingClass = Literal["assets", "liabilities", "equity", "revenue", "expenses"]
NormalBalance = Literal["debit", "credit"]
Method = Literal["prior_year_match", "number_range", "manual"]
Confidence = Literal["high", "medium"]  # words, never a percentage
RunStatus = Literal["not_started", "running", "ready", "failed"]
PriorSource = Literal["prior_engagement", "predecessor_file", "none"]
GroupingVersionStatus = Literal["draft", "published", "discarded"]
AccountCode = Annotated[str, Path(min_length=1, max_length=64)]
# What the person may do on this mapping set; the screen shows only these controls.
MappingSetAction = Literal[
    "mapping_set.run",
    "mapping_set.confirm",
    "account_mapping.edit",
    "sign_off.review",
]

# --- the taxonomy: catalogue and picker (F5) ----------------------------------------------------


class GroupingSetVersionSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    status: Annotated[GroupingVersionStatus, classified("internal")]
    effective_from: Annotated[date | None, classified("internal")]
    problems: Annotated[int, Field(ge=0), classified("internal")]
    published_by_name: Annotated[str | None, classified("internal")]
    published_at: Annotated[datetime | None, classified("internal")]


class GroupingSetSummaryOut(BaseModel):
    """One firm grouping set in the catalogue, with its versions (firm content, never code)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    key: Annotated[str, classified("internal")]
    name: Annotated[str, classified("internal")]
    current_version_no: Annotated[int | None, classified("internal")]  # newest published
    versions: Annotated[list[GroupingSetVersionSummaryOut], classified("internal")]


class FsLineOptionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    normal_balance: Annotated[NormalBalance, classified("internal")]
    grouping_key: Annotated[str, classified("internal")]
    grouping_label: Annotated[str, classified("internal")]
    class_: Annotated[GroupingClass, Field(serialization_alias="class"), classified("internal")]


class GroupingOptionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    lines: Annotated[list[FsLineOptionOut], classified("internal")]


class GroupingClassOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    class_: Annotated[GroupingClass, Field(serialization_alias="class"), classified("internal")]
    groupings: Annotated[list[GroupingOptionOut], classified("internal")]


class GroupingLinesOut(BaseModel):
    """The Change picker O1: grouped Assets · Liabilities · Equity · Revenue · Expenses, plus the
    viewer's own "Recently used" (never another person's, never a walled engagement's, INV-3)."""

    model_config = ConfigDict(frozen=True)

    grouping_set_id: Annotated[UUID, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    classes: Annotated[list[GroupingClassOut], classified("internal")]
    recently_used: Annotated[list[FsLineOptionOut], classified("internal")]


# --- mapping sets (F6) ---------------------------------------------------------------------------


class MappingTalliesOut(BaseModel):
    """Code's tallies: MAPPED n of N, NEED REVIEW n, by method, TB BALANCED n of n."""

    model_config = ConfigDict(frozen=True)

    accounts: Annotated[int, Field(ge=0), classified("internal")]
    mapped: Annotated[int, Field(ge=0), classified("internal")]
    need_review: Annotated[int, Field(ge=0), classified("internal")]
    prior_year_match: Annotated[int | None, Field(ge=0), classified("internal")]  # by method
    number_range: Annotated[int | None, Field(ge=0), classified("internal")]  # by method
    edited: Annotated[int | None, Field(ge=0), classified("internal")]
    tb_balanced: Annotated[int, Field(ge=0), classified("internal")]
    tb_count: Annotated[int, Field(ge=1), classified("internal")]


class SignOffChipOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: Annotated[int, Field(ge=1, le=5), classified("internal")]
    initials: Annotated[str, classified("internal")]
    name: Annotated[str, classified("internal")]
    at: Annotated[datetime, classified("internal")]
    stale: Annotated[bool, classified("internal")]


class MappingSetSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    trial_balance_id: Annotated[UUID, classified("internal")]
    trial_balance_version_no: Annotated[int, Field(ge=1), classified("internal")]
    client_entity_id: Annotated[UUID, classified("internal")]
    entity_name: Annotated[str, classified("confidential")]
    period_end: Annotated[date, classified("internal")]
    grouping_set_version_id: Annotated[UUID, classified("internal")]
    grouping_set_label: Annotated[str, classified("internal")]
    prior_source: Annotated[PriorSource, classified("internal")]
    run_status: Annotated[RunStatus, classified("internal")]
    status: Annotated[MappingSetStatus, classified("internal")]  # computed (ADR-341 §5)
    tallies: Annotated[MappingTalliesOut, classified("internal")]
    sign_offs: Annotated[list[SignOffChipOut], classified("internal")]
    content_hash: Annotated[str, classified("internal")]


class AccountMappingOut(BaseModel):
    """One account's row: balance from the snapshot, never typed; confidence in words."""

    model_config = ConfigDict(frozen=True)

    account_code: Annotated[str, classified("confidential")]
    account_name: Annotated[str, classified("confidential")]
    citation_match_id: Annotated[str, classified("internal")]  # `led:<snapshot>:<account>`
    balance: Money
    fs_line_id: Annotated[UUID | None, classified("internal")]
    fs_line_label: Annotated[str | None, classified("internal")]
    grouping_label: Annotated[str | None, classified("internal")]
    state: Annotated[AccountMappingStateStatus, classified("internal")]
    method: Annotated[Method | None, classified("internal")]
    confidence: Annotated[Confidence | None, classified("internal")]
    was_fs_line_label: Annotated[str | None, classified("internal")]  # "was …" after an edit
    edited_by_initials: Annotated[str | None, classified("internal")]
    edited_at: Annotated[datetime | None, classified("internal")]
    seen_version: Annotated[int, Field(ge=0), classified("internal")]  # edits so far


class GroupSubtotalOut(BaseModel):
    """A grouping's subtotal; `off` when the source TB carries a summary line that disagrees."""

    model_config = ConfigDict(frozen=True)

    grouping_key: Annotated[str, classified("internal")]
    grouping_label: Annotated[str, classified("internal")]
    subtotal: Money
    source_total: Annotated[Decimal | None, classified("confidential")]
    off: Annotated[Decimal | None, classified("confidential")]


class MappingSetOut(BaseModel):
    """`GET /v1/mapping-sets/{msid}`: AUD-31's rows, tallies and subtotals."""

    model_config = ConfigDict(frozen=True)

    summary: Annotated[MappingSetSummaryOut, classified("internal")]
    rows: Annotated[list[AccountMappingOut], classified("confidential")]
    subtotals: Annotated[list[GroupSubtotalOut], classified("confidential")]
    allowed_actions: Annotated[list[MappingSetAction], classified("internal")] = []


class MappingRunOut(BaseModel):
    """The run's progress (b-prime polls it once a second until P-10's SSE)."""

    model_config = ConfigDict(frozen=True)

    mapping_set_id: Annotated[UUID, classified("internal")]
    run_status: Annotated[RunStatus, classified("internal")]
    run_done: Annotated[int, Field(ge=0), classified("internal")]
    run_total: Annotated[int, Field(ge=0), classified("internal")]
    failure_code: Annotated[str | None, classified("internal")]


class MappedFsLineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    class_: Annotated[GroupingClass, Field(serialization_alias="class"), classified("internal")]
    grouping_key: Annotated[str, classified("internal")]
    grouping_label: Annotated[str, classified("internal")]
    fs_line_key: Annotated[str, classified("internal")]
    fs_line_label: Annotated[str, classified("internal")]
    normal_balance: Annotated[NormalBalance, classified("internal")]
    debit: Money
    credit: Money
    net: Money


class MappedTrialBalanceOut(BaseModel):
    """C9 v2's one structure for A-04, A-06, T-05 and A-10: debits, credits and net per FS line,
    computed by code, with the grouping-set version and the mapping's content hash."""

    model_config = ConfigDict(frozen=True)

    mapping_set_id: Annotated[UUID, classified("internal")]
    trial_balance_id: Annotated[UUID, classified("internal")]
    trial_balance_version_no: Annotated[int, Field(ge=1), classified("internal")]
    grouping_set_version_id: Annotated[UUID, classified("internal")]
    content_hash: Annotated[str, classified("internal")]
    lines: Annotated[list[MappedFsLineOut], classified("confidential")]
    debit: Money
    credit: Money
    unmapped: Annotated[int, Field(ge=0), classified("internal")]


class TbFsLineGroupOut(BaseModel):
    """The `group_by=fs_line` option on A-02's trial balance view (grouping, then FS line), wired
    by A-03-T08; 409 `mapping_not_confirmed` keeps the area grouping until a set is confirmed."""

    model_config = ConfigDict(frozen=True)

    grouping_key: Annotated[str, classified("internal")]
    grouping_label: Annotated[str, classified("internal")]
    fs_line_key: Annotated[str, classified("internal")]
    fs_line_label: Annotated[str, classified("internal")]
    account_codes: Annotated[list[str], classified("confidential")]
    eoy: Money
    boy: Annotated[Decimal | None, classified("confidential")]


# --- inputs --------------------------------------------------------------------------------------


class MappingRunIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trial_balance_id: Annotated[UUID, classified("internal")]
    prior_source: Annotated[PriorSource, classified("internal")] = "prior_engagement"
    predecessor_evidence_version_id: Annotated[UUID | None, classified("internal")] = None


class AccountMappingEditIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fs_line_id: Annotated[UUID | None, classified("internal")]  # null returns it to the rules
    seen_version: Annotated[int, Field(ge=0), classified("internal")]


class MappingConfirmIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_hash: Annotated[str, Field(min_length=1, max_length=100), classified("internal")]


# --- the gate ------------------------------------------------------------------------------------

_READ_OF = {
    "mapping_set.confirm": "mapping_set.read",
    "account_mapping.edit": "mapping_set.read",
}


async def _flag_or_404(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, LEDGER_TB_MAPPING):
        raise NotFound(LEDGER_TB_MAPPING.name)


async def engagement_gate(ctx: AuthContext, action: str, engagement_id: UUID) -> None:
    if ctx.client:
        raise NotFound("mapping sets")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    await _flag_or_404(ctx)


async def firm_gate(ctx: AuthContext, action: str) -> None:
    """Firm-level reads (the catalogue and picker), and mapping-set ids until T08 (DEC-1555)."""
    if ctx.client:
        raise NotFound("mapping sets")
    read = _READ_OF.get(action, action)
    if read != action and ctx.tenant.actor_kind != "human":
        raise Forbidden(action, "role")
    await authorise(ctx, read, Resource.firm(ctx.tenant_id))
    await _flag_or_404(ctx)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


router = AbacusRouter(prefix="/v1", tags=["mapping"])


@router.get(
    "/grouping-sets/catalogue",
    action="grouping_set.read",
    response_model=list[GroupingSetSummaryOut],
    errors=(),
)
async def grouping_catalogue_route(ctx: Ctx) -> list[GroupingSetSummaryOut]:
    """The firm's grouping sets and their versions, for every firm role (live, A-03-T06)."""
    await firm_gate(ctx, "grouping_set.read")
    found = await catalogue(ctx)
    names = await names_of([v.published_by for v in found if v.published_by is not None])
    sets: dict[UUID, GroupingSetSummaryOut] = {}
    for v in found:
        if v.set_id is None:
            continue
        summary = GroupingSetVersionSummaryOut(
            id=v.id,
            version_no=v.version,
            status=cast(GroupingVersionStatus, v.status),
            effective_from=v.effective_from,
            problems=len(v.problems),
            published_by_name=names.get(v.published_by) if v.published_by else None,
            published_at=v.published_at,
        )
        held = sets.get(v.set_id)
        versions = [*(held.versions if held else []), summary]
        published = [s.version_no for s in versions if s.status == "published"]
        sets[v.set_id] = GroupingSetSummaryOut(
            id=v.set_id,
            key=v.set_key,
            name=v.set_name,
            current_version_no=max(published) if published else None,
            versions=versions,
        )
    return list(sets.values())


@router.get(
    "/grouping-sets/{grouping_set_id}/versions/{version_no}/lines",
    action="grouping_set.read",
    response_model=GroupingLinesOut,
    errors=(),
)
async def grouping_lines_route(
    grouping_set_id: UUID,
    version_no: int,
    ctx: Ctx,
    q: Annotated[str | None, Query(max_length=120)] = None,
) -> GroupingLinesOut:
    """The picker: "Search groupings and FS lines", grouped by class, with Recently used
    (live, A-03-T06). `q` matches a grouping's or FS line's label or key, case-insensitively."""
    await firm_gate(ctx, "grouping_set.read")
    version_id, views, recent = await picker(ctx, grouping_set_id, version_no)
    needle = (q or "").casefold()
    options: dict[UUID, FsLineOptionOut] = {}
    classes: dict[str, list[GroupingOptionOut]] = {}
    for g in views:
        grouping_hit = needle in g.label.casefold() or needle in g.key.casefold()
        lines = [
            FsLineOptionOut(
                id=line.id,
                key=line.key,
                label=line.label,
                normal_balance=cast(NormalBalance, line.normal_balance),
                grouping_key=g.key,
                grouping_label=g.label,
                class_=cast(GroupingClass, g.class_),
            )
            for line in g.lines
        ]
        options.update({o.id: o for o in lines})
        shown = [
            o
            for o in lines
            if grouping_hit or needle in o.label.casefold() or needle in o.key.casefold()
        ]
        if shown:
            classes.setdefault(g.class_, []).append(
                GroupingOptionOut(key=g.key, label=g.label, lines=shown)
            )
    order: tuple[GroupingClass, ...] = ("assets", "liabilities", "equity", "revenue", "expenses")
    return GroupingLinesOut(
        grouping_set_id=grouping_set_id,
        version_id=version_id,
        version_no=version_no,
        classes=[
            GroupingClassOut(class_=c, groupings=classes[c])
            for c in order
            if c in classes
        ],
        recently_used=[options[i] for i in recent if i in options],
    )


@router.get(
    "/engagements/{engagement_id}/mapping-sets",
    action="mapping_set.read",
    response_model=ListPage[MappingSetSummaryOut],
    errors=(501,),
)
async def mapping_sets_route(
    engagement_id: UUID,
    ctx: Ctx,
    client_entity_id: UUID | None = None,
    period_end: date | None = None,
    label: Annotated[str | None, Query(max_length=40)] = None,
) -> ListPage[MappingSetSummaryOut]:
    """One mapping set per trial balance of record (ADR-341 §4)."""
    await engagement_gate(ctx, "mapping_set.read", engagement_id)
    found = fx.mapping_sets(engagement_id)
    if found is None:
        _not_yet()
    return ListPage[MappingSetSummaryOut](
        items=[MappingSetSummaryOut.model_validate(m) for m in found], total=len(found)
    )


@router.post(
    "/engagements/{engagement_id}/mapping-sets",
    action="mapping_set.run",
    response_model=MappingRunOut,
    status_code=202,
    errors=(409, 501),
)
async def mapping_run_start_route(
    engagement_id: UUID, body: MappingRunIn, ctx: Ctx
) -> MappingRunOut:
    """Start or re-run the rules on a TB of record (`TbMappingWorkflow`, A-03-T08); the
    subscriber starts it on adoption as system. 409 `mapping_run_in_progress`."""
    await engagement_gate(ctx, "mapping_set.run", engagement_id)
    _not_yet()


@router.get(
    "/mapping-sets/{mapping_set_id}",
    action="mapping_set.read",
    response_model=MappingSetOut,
    errors=(501,),
)
async def mapping_set_route(
    mapping_set_id: UUID,
    ctx: Ctx,
    filter_: Annotated[Literal["needs_review", "unmatched"] | None, Query(alias="filter")] = None,
    group_by: Literal["fs_line"] | None = None,
) -> MappingSetOut:
    await firm_gate(ctx, "mapping_set.read")
    _not_yet()


@router.get(
    "/mapping-sets/{mapping_set_id}/run",
    action="mapping_set.read",
    response_model=MappingRunOut,
    errors=(501,),
)
async def mapping_run_route(mapping_set_id: UUID, ctx: Ctx) -> MappingRunOut:
    await firm_gate(ctx, "mapping_set.read")
    found = fx.run(mapping_set_id)
    if found is None:
        _not_yet()
    return MappingRunOut.model_validate(found)


@router.put(
    "/mapping-sets/{mapping_set_id}/accounts/{account_code}",
    action="account_mapping.edit",
    response_model=AccountMappingOut,
    errors=(409, 501),
)
async def account_mapping_edit_route(
    mapping_set_id: UUID, account_code: AccountCode, body: AccountMappingEditIn, ctx: Ctx
) -> AccountMappingOut:
    """One account's FS line, insert-only; 412-equivalent 409 `stale_version` (A-03-T08)."""
    await firm_gate(ctx, "account_mapping.edit")
    _not_yet()


@router.post(
    "/mapping-sets/{mapping_set_id}/confirm",
    action="mapping_set.confirm",
    response_model=MappingSetSummaryOut,
    errors=(409, 501),
)
async def mapping_confirm_route(
    mapping_set_id: UUID, body: MappingConfirmIn, ctx: Ctx
) -> MappingSetSummaryOut:
    """Adopt every mapping and record L1 through review.api in one unit; 409
    `unmapped_accounts`, `content_changed` (A-03-T08)."""
    await firm_gate(ctx, "mapping_set.confirm")
    _not_yet()


@router.get(
    "/mapping-sets/{mapping_set_id}/trial-balance",
    action="mapping_set.read",
    response_model=MappedTrialBalanceOut,
    errors=(501,),
)
async def mapped_trial_balance_route(mapping_set_id: UUID, ctx: Ctx) -> MappedTrialBalanceOut:
    await firm_gate(ctx, "mapping_set.read")
    _not_yet()


ROUTERS = (router,)

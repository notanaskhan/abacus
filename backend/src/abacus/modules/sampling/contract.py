"""The sampling API contract stub (A-03-T02; TASK-2503; SPEC-580 AC-11; ADR-340).
Contract: `docs/contracts/sampling.md`; screens AUD-11 and SHL-14 c.

Every A-03 §4.3 sampling route exists with its one matrix action, behind `sampling.sample_sets`.
The gate, in order: a client principal gets 404 (clients see item requests only, INV-4); then the
route's action is authorised; then 404 with the flag off; then reads of the Brightwater Hale
fixture ids answer the fixture (`contract_fixtures.py`) and everything else 501 until its task
(T07 populations and ties, T10 sample sets, draws, approval and export, T13 the fan-out).

Work-item routes authorise on the work item's engagement. Routes keyed by a population or sample
set have no table to name their engagement until T05 lands, so the stub authorises the route's
read action at firm level (SPEC-014 counts the person's engagement roles) and refuses any
non-person on a write; the live routes authorise the write on the target's engagement (DEC-1553).

Every amount is computed by code and sent as a decimal string (ADR-050). No model carries a seed,
size, parameter or population hash to a client principal (INV-4).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import SAMPLING_SAMPLE_SETS
from abacus.kernel._statuses import CompletenessTieResultStatus, SampleSetVersionStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    current_context,
)
from abacus.modules.sampling import contract_fixtures as fx

Ctx = Annotated[AuthContext, Depends(current_context)]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Money = Annotated[Decimal, classified("confidential")]
Rate = Annotated[Decimal, Field(ge=0, le=1), classified("internal")]

SourceKind = Literal["upload", "general_ledger"]
Method = Literal[
    "attribute_nonstatistical", "attribute_statistical", "threshold_random_stratified"
]
Rmm = Literal["low", "moderate", "high"]
TestRule = Literal["all", "random", "none"]
SelectionReason = Literal["random", "threshold"]
SeedSource = Literal["server", "scenario"]
Surface = Literal["POR-03", "POR-14"]
Wave = Literal["sample"]
# What the person may do on this sample set; the screen shows only these controls.
SampleSetAction = Literal[
    "sample_set.create",
    "sample_set.approve",
    "sample_set.export",
    "sample_set.generate_requests",
    "population.create",
    "sign_off.prepare",
]

# --- populations and completeness ties (AUD-11 card 1; F2) ---------------------------------------


class CitationOut(BaseModel):
    """A cited source: the program step a parameter comes from, or the cell a tie agrees to."""

    model_config = ConfigDict(frozen=True)

    label: Annotated[
        str, Field(max_length=200), classified("internal")
    ]  # "BH-EBP-210 step 3 · Table 2"
    citation_id: Annotated[UUID | None, classified("internal")]
    verified: Annotated[
        bool, classified("internal")
    ]  # INV-2: an unverified citation is never saved


class TieComparisonOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: Annotated[
        str, Field(max_length=200), classified("confidential")
    ]  # "PayGrid YTD register"
    amount: Money
    citation: Annotated[CitationOut | None, classified("internal")]
    ledger_ref: Annotated[str | None, classified("internal")]  # a GL tie's account and window


class CompletenessTieOut(BaseModel):
    """One tie, computed by code: `tie`, `off {amount}` or `Check` (completeness_tie_result)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    position: Annotated[int, Field(ge=1), classified("internal")]
    label: Annotated[str, Field(max_length=200), classified("confidential")]
    left_amount: Annotated[Decimal | None, classified("confidential")]
    comparisons: Annotated[list[TieComparisonOut], classified("confidential")]
    difference: Annotated[Decimal | None, classified("confidential")]
    result: Annotated[CompletenessTieResultStatus, classified("internal")]
    explanation: Annotated[str | None, Field(max_length=500), classified("confidential")]
    engine_version: Annotated[str, classified("internal")]
    inputs_hash: Annotated[str, classified("internal")]


class PopulationQueryOut(BaseModel):
    """A general-ledger population's query (AUD-11f): accounts, side, kinds and window."""

    model_config = ConfigDict(frozen=True)

    account_codes: Annotated[list[str], classified("confidential")]
    side: Annotated[Literal["debit", "credit"], classified("internal")]
    kinds: Annotated[list[str], classified("internal")]
    posted_from: Annotated[date, classified("internal")]
    posted_to: Annotated[date, classified("internal")]


class PopulationSourceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[SourceKind, classified("internal")]
    # Upload: the scanned evidence version and who uploaded it.
    evidence_version_id: Annotated[UUID | None, classified("internal")] = None
    file_name: Annotated[str | None, classified("confidential")] = None
    file_version_no: Annotated[int | None, classified("internal")] = None
    uploaded_by_name: Annotated[str | None, classified("internal")] = None
    uploaded_on: Annotated[date | None, classified("internal")] = None
    # General ledger: the snapshot read through ledger.api (never a connector write, ADR-040).
    gl_snapshot_id: Annotated[UUID | None, classified("internal")] = None
    connection_label: Annotated[str | None, classified("confidential")] = None
    query: Annotated[PopulationQueryOut | None, classified("confidential")] = None
    query_label: Annotated[str | None, classified("confidential")] = None
    pulled_at: Annotated[datetime | None, classified("internal")] = None


class PopulationOut(BaseModel):
    """`GET /v1/populations/{pid}`: the population, its source facts and its ties."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    source: Annotated[PopulationSourceOut, classified("confidential")]
    record_count: Annotated[int, Field(ge=1), classified("internal")]
    record_unit: Annotated[str, Field(max_length=60), classified("internal")]  # "payments"
    amount_total: Annotated[Decimal | None, classified("confidential")]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]
    sampling_unit: Annotated[str, Field(max_length=120), classified("internal")]
    deviation_definition: Annotated[str | None, Field(max_length=500), classified("internal")]
    ties: Annotated[list[CompletenessTieOut], classified("confidential")]
    created_by_name: Annotated[str, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


# --- sample sets, versions and items (AUD-11 cards 2-4; F1, F3) ---------------------------------


class StratumOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: Annotated[int, Field(ge=1), classified("internal")]
    min_amount: Annotated[Decimal | None, classified("confidential")]
    max_amount: Annotated[Decimal | None, classified("confidential")]
    test_rule: Annotated[TestRule, classified("internal")]
    random_count: Annotated[int | None, Field(ge=0), classified("internal")]
    population_count: Annotated[int, Field(ge=0), classified("internal")]
    population_amount: Annotated[Decimal | None, classified("confidential")]
    selected_count: Annotated[int, Field(ge=0), classified("internal")]


class ParametersOut(BaseModel):
    """Card 2: the method and parameters behind the size, each with its citation."""

    model_config = ConfigDict(frozen=True)

    method: Annotated[Method, classified("internal")]
    rmm: Annotated[Rmm | None, classified("internal")]
    tolerable_rate: Annotated[Decimal | None, Field(ge=0, le=1), classified("internal")]
    expected_rate: Annotated[Decimal | None, Field(ge=0, le=1), classified("internal")]
    confidence: Annotated[Decimal | None, Field(ge=0, le=1), classified("internal")]
    computed_size: Annotated[int, Field(ge=1), classified("internal")]
    statistical_crosscheck_size: Annotated[int | None, Field(ge=1), classified("internal")]
    override_size: Annotated[int | None, Field(ge=1), classified("internal")]
    override_rationale: Annotated[str | None, Field(max_length=1000), classified("confidential")]
    final_size: Annotated[int, Field(ge=1), classified("internal")]
    seed: Annotated[int, Field(ge=0, le=16_777_215), classified("internal")]
    seed_hex: Annotated[str, Field(pattern=r"^0x[0-9A-F]{6}$"), classified("internal")]
    seed_source: Annotated[SeedSource, classified("internal")]
    sampler_version: Annotated[str, classified("internal")]
    citations: Annotated[list[CitationOut], classified("internal")]


class PersonStampOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("internal")]
    initials: Annotated[str, classified("internal")]
    at: Annotated[datetime, classified("internal")]


class SampleSetVersionOut(BaseModel):
    """Card 4's row: a version with its seed, population and computed tie summary."""

    model_config = ConfigDict(frozen=True)

    version_no: Annotated[int, Field(ge=1), classified("internal")]
    status: Annotated[SampleSetVersionStatus, classified("internal")]
    population_id: Annotated[UUID, classified("internal")]
    population_label: Annotated[str, classified("confidential")]  # "census v2"
    record_count: Annotated[int, Field(ge=1), classified("internal")]
    tie_result: Annotated[CompletenessTieResultStatus, classified("internal")]
    tie_difference: Annotated[Decimal | None, classified("confidential")]
    seed_hex: Annotated[str, Field(pattern=r"^0x[0-9A-F]{6}$"), classified("internal")]
    final_size: Annotated[int, Field(ge=1), classified("internal")]
    override_pending: Annotated[bool, classified("internal")]  # derived from override_size
    created_by_name: Annotated[str, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    prepared: Annotated[PersonStampOut | None, classified("internal")]  # the L1 "Prepared · MD"
    approved: Annotated[PersonStampOut | None, classified("internal")]  # the L2 "✓ HL"


class SampleItemOut(BaseModel):
    """One selected item; display fields only (Restricted columns are never copied, ADR-031)."""

    model_config = ConfigDict(frozen=True)

    position: Annotated[int, Field(ge=1), classified("internal")]
    record_key: Annotated[str, classified("confidential")]  # census ID or payment reference
    name: Annotated[str | None, classified("confidential")]
    hire_date: Annotated[date | None, classified("confidential")]
    amount: Annotated[Decimal | None, classified("confidential")]
    selection_reason: Annotated[SelectionReason, classified("internal")]
    stratum_position: Annotated[int | None, classified("internal")]


class SampleSetOut(BaseModel):
    """`GET /v1/sample-sets/{sid}?version=n`: AUD-11's projection of one version."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    title: Annotated[str, Field(max_length=120), classified("confidential")]
    purpose: Annotated[str | None, Field(max_length=300), classified("confidential")]
    program_step_key: Annotated[str | None, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    status: Annotated[SampleSetVersionStatus, classified("internal")]
    population: Annotated[PopulationOut, classified("confidential")]
    parameters: Annotated[ParametersOut, classified("internal")]
    strata: Annotated[list[StratumOut], classified("confidential")]
    items_total: Annotated[int, Field(ge=0), classified("internal")]
    items_amount: Annotated[Decimal | None, classified("confidential")]
    versions: Annotated[list[SampleSetVersionOut], classified("internal")]
    inputs_hash: Annotated[str, classified("internal")]
    items_hash: Annotated[str | None, classified("internal")]
    content_hash: Annotated[str | None, classified("internal")]  # the seen_hash an approval sends
    allowed_actions: Annotated[list[SampleSetAction], classified("internal")] = []


class SampleSetSummaryOut(BaseModel):
    """The header picker's row (DF-05): "Participants · 25 of 412 · Approved"."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    title: Annotated[str, Field(max_length=120), classified("confidential")]
    current_version_no: Annotated[int, Field(ge=1), classified("internal")]
    status: Annotated[SampleSetVersionStatus, classified("internal")]
    final_size: Annotated[int, Field(ge=1), classified("internal")]
    population_count: Annotated[int, Field(ge=1), classified("internal")]


class SampleSetCreatedOut(BaseModel):
    """`POST /v1/work-items/{wid}/sample-sets`: the new set, before its first draw (DEC-1662)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    title: Annotated[str, Field(max_length=120), classified("confidential")]
    purpose: Annotated[str | None, Field(max_length=300), classified("confidential")]
    program_step_key: Annotated[str | None, classified("internal")]


class DrawProgressOut(BaseModel):
    """`…/draw`: what AUD-11e polls once a second until the version is Draft or Failed."""

    model_config = ConfigDict(frozen=True)

    version_no: Annotated[int, Field(ge=1), classified("internal")]
    status: Annotated[SampleSetVersionStatus, classified("internal")]
    items_done: Annotated[int, Field(ge=0), classified("internal")]
    items_total: Annotated[int, Field(ge=0), classified("internal")]
    failure_code: Annotated[str | None, classified("internal")]
    items: Annotated[list[SampleItemOut], classified("confidential")]


class VersionStartedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_no: Annotated[int, Field(ge=1), classified("internal")]
    status_url: Annotated[str, classified("internal")]


# --- inputs --------------------------------------------------------------------------------------


class SampleSetIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=120), classified("confidential")]
    purpose: Annotated[str | None, Field(max_length=300), classified("confidential")] = None
    program_step_key: Annotated[str | None, Field(max_length=120), classified("internal")] = None


class UploadSourceIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[Literal["upload"], classified("internal")] = "upload"
    evidence_version_id: Annotated[UUID, classified("internal")]
    # Column letters or header names for record key, name, date and amount; Restricted columns
    # answer 422 `restricted_column` (ADR-031).
    column_map: Annotated[dict[str, str], classified("internal")]


class GeneralLedgerSourceIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[Literal["general_ledger"], classified("internal")] = "general_ledger"
    gl_snapshot_id: Annotated[UUID, classified("internal")]
    account_codes: Annotated[list[str], Field(min_length=1), classified("confidential")]
    side: Annotated[Literal["debit", "credit"], classified("internal")]
    kinds: Annotated[list[str], classified("internal")] = []
    posted_from: Annotated[date, classified("internal")]
    posted_to: Annotated[date, classified("internal")]


class PopulationIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: Annotated[
        UploadSourceIn | GeneralLedgerSourceIn, Field(discriminator="kind"), classified("internal")
    ]
    sampling_unit: Annotated[str, Field(min_length=1, max_length=120), classified("internal")]
    deviation_definition: Annotated[
        str, Field(min_length=1, max_length=500), classified("internal")
    ]


class TieComparisonIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    amount: Money
    citation_id: Annotated[UUID | None, classified("internal")] = None
    ledger_ref: Annotated[str | None, Field(max_length=200), classified("internal")] = None


class TieIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    comparisons: Annotated[list[TieComparisonIn], Field(min_length=1), classified("confidential")]
    explanation: Annotated[str | None, Field(max_length=500), classified("confidential")] = None


class StratumIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    min_amount: Annotated[Decimal | None, classified("confidential")] = None
    max_amount: Annotated[Decimal | None, classified("confidential")] = None
    test_rule: Annotated[TestRule, classified("internal")]
    random_count: Annotated[int | None, Field(ge=0), classified("internal")] = None


class OverrideIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    size: Annotated[int, Field(ge=1), classified("internal")]
    rationale: Annotated[str, Field(min_length=1, max_length=1000), classified("confidential")]


class ParametersIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rmm: Annotated[Rmm | None, classified("internal")] = None
    tolerable_rate: Annotated[Decimal | None, Field(gt=0, lt=1), classified("internal")] = None
    expected_rate: Annotated[Decimal | None, Field(ge=0, lt=1), classified("internal")] = None
    confidence: Annotated[Decimal | None, Field(gt=0, lt=1), classified("internal")] = None


class VersionIn(BaseModel):
    """A draw request. No field carries a seed: the server draws it (ADR-340 §5)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    population_id: Annotated[UUID, classified("internal")]
    method: Annotated[Method, classified("internal")]
    parameters: Annotated[ParametersIn, classified("internal")]
    strata: Annotated[list[StratumIn], classified("confidential")] = []
    override: Annotated[OverrideIn | None, classified("confidential")] = None


class ApproveIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_hash: Annotated[str, Field(min_length=1, max_length=100), classified("internal")]
    acknowledge_override: Annotated[bool, classified("internal")] = False


class ItemRequestTemplateIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    description: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    contact_id: Annotated[UUID | None, classified("internal")] = None
    third_party_contact_id: Annotated[UUID | None, classified("internal")] = None


class ItemRequestsIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    templates: Annotated[
        list[ItemRequestTemplateIn], Field(min_length=1, max_length=10), classified("confidential")
    ]
    due_on: Annotated[date, classified("internal")]
    wave: Annotated[Wave, classified("internal")] = "sample"


class RecipientPreviewOut(BaseModel):
    """What one recipient will see: their requests and nothing of the sample (INV-4)."""

    model_config = ConfigDict(frozen=True)

    name: Annotated[str, classified("confidential")]
    organisation: Annotated[str | None, classified("confidential")]
    surface: Annotated[Surface, classified("internal")]
    requests: Annotated[int, Field(ge=0), classified("internal")]


class ItemRequestPreviewOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    total: Annotated[int, Field(ge=0), classified("internal")]
    by_surface: Annotated[dict[str, int], classified("internal")]
    recipients: Annotated[list[RecipientPreviewOut], classified("confidential")]


class ItemRequestsCreatedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    created: Annotated[int, Field(ge=0), classified("internal")]
    by_surface: Annotated[dict[str, int], classified("internal")]
    batch_id: Annotated[UUID, classified("internal")]


# --- the gate ------------------------------------------------------------------------------------

# Writes on a population or sample set authorise their read at firm level until T05 (DEC-1553).
_READ_OF = {
    "population.create": "population.read",
    "sample_set.create": "sample_set.read",
    "sample_set.approve": "sample_set.read",
    "sample_set.export": "sample_set.read",
    "sample_set.generate_requests": "sample_set.read",
}


async def _flag_or_404(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, SAMPLING_SAMPLE_SETS):
        raise NotFound(SAMPLING_SAMPLE_SETS.name)


async def work_item_gate(ctx: AuthContext, action: str, work_item_id: UUID) -> None:
    """Client 404; the action on the work item's engagement (walls 404, independence 403); flag."""
    if ctx.client:
        raise NotFound("sample sets")
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work item")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    await _flag_or_404(ctx)


async def target_gate(ctx: AuthContext, action: str) -> None:
    """Client 404; a write refused to any non-person; the read at firm level; flag (DEC-1553)."""
    if ctx.client:
        raise NotFound("sample sets")
    read = _READ_OF.get(action, action)
    if read != action and ctx.tenant.actor_kind != "human":
        raise Forbidden(action, "role")
    await authorise(ctx, read, Resource.firm(ctx.tenant_id))
    await _flag_or_404(ctx)


async def population_gate(ctx: AuthContext, *, write: bool) -> None:
    """A live population (T07): client 404; a write refused to any non-person; the flag. The
    service then authorises the action on the population's own engagement (DEC-1553's follow-up,
    DEC-1660)."""
    if ctx.client:
        raise NotFound("sample sets")
    if write and ctx.tenant.actor_kind != "human":
        raise Forbidden("population.create", "role")
    await _flag_or_404(ctx)


async def live_gate(ctx: AuthContext, *, write: bool) -> None:
    """A live sample set (T10): client 404; a write refused to any non-person; the flag. The
    service then authorises the action on the set's own engagement (DEC-1553's follow-up)."""
    if ctx.client:
        raise NotFound("sample sets")
    if write and ctx.tenant.actor_kind != "human":
        raise Forbidden("sample_set.create", "role")
    await _flag_or_404(ctx)


work_items_router = AbacusRouter(prefix="/v1/work-items/{work_item_id}", tags=["sampling"])
populations_router = AbacusRouter(prefix="/v1/populations", tags=["sampling"])
sample_sets_router = AbacusRouter(prefix="/v1/sample-sets", tags=["sampling"])


@work_items_router.get(
    "/sample-sets",
    action="sample_set.read",
    response_model=ListPage[SampleSetSummaryOut],
    errors=(),
)
async def sample_sets_list_route(work_item_id: UUID, ctx: Ctx) -> ListPage[SampleSetSummaryOut]:
    """The header picker: every sample set on the work item with its current version (DF-05).
    A walled work item answers 404 and no count (INV-3)."""
    from abacus.modules.sampling import sample_sets  # the service imports these models

    await work_item_gate(ctx, "sample_set.read", work_item_id)
    found = await sample_sets.sample_sets_of(ctx, work_item_id)
    return ListPage[SampleSetSummaryOut](items=found, total=len(found))


@work_items_router.post(
    "/sample-sets",
    action="sample_set.create",
    response_model=SampleSetCreatedOut,
    status_code=201,
    errors=(),
)
async def sample_set_create_route(
    work_item_id: UUID, body: SampleSetIn, ctx: Ctx
) -> SampleSetCreatedOut:
    """Create a sample set; audited `sample_set.created` (T10)."""
    from abacus.modules.sampling import sample_sets  # the service imports these models

    await work_item_gate(ctx, "sample_set.create", work_item_id)
    if ctx.tenant.actor_kind != "human":
        raise Forbidden("sample_set.create", "role")
    created = await sample_sets.create_sample_set(ctx, work_item_id, body)
    return SampleSetCreatedOut(
        id=created,
        title=body.title.strip(),
        purpose=body.purpose,
        program_step_key=body.program_step_key,
    )


@work_items_router.post(
    "/populations",
    action="population.create",
    response_model=PopulationOut,
    status_code=201,
    errors=(),
)
async def population_create_route(
    work_item_id: UUID, body: PopulationIn, ctx: Ctx
) -> PopulationOut:
    """Build a population from an upload or a general-ledger query (T07): counts, total and
    SHA-256; 422 `restricted_column`, `column_map_invalid`; audited `population.created`."""
    from abacus.modules.sampling import populations  # the service imports these models

    await work_item_gate(ctx, "population.create", work_item_id)
    if ctx.tenant.actor_kind != "human":
        raise Forbidden("population.create", "role")
    return await populations.create_population(ctx, work_item_id, body)


@populations_router.get(
    "/{population_id}", action="population.read", response_model=PopulationOut, errors=()
)
async def population_route(population_id: UUID, ctx: Ctx) -> PopulationOut:
    from abacus.modules.sampling import populations  # the service imports these models

    found = fx.population(population_id)
    if found is not None:
        await target_gate(ctx, "population.read")
        return PopulationOut.model_validate(found)
    await population_gate(ctx, write=False)
    return await populations.population_view(ctx, population_id)


@populations_router.post(
    "/{population_id}/ties",
    action="population.create",
    response_model=CompletenessTieOut,
    status_code=201,
    errors=(),
)
async def population_tie_create_route(
    population_id: UUID, body: TieIn, ctx: Ctx
) -> CompletenessTieOut:
    """Record a tie; code computes the result; 422 `citation_unverified` (INV-2; T07)."""
    from abacus.modules.sampling import populations  # the service imports these models

    await population_gate(ctx, write=True)
    return await populations.record_tie(ctx, population_id, body)


@sample_sets_router.post(
    "/{sample_set_id}/versions",
    action="sample_set.create",
    response_model=VersionStartedOut,
    status_code=202,
    errors=(409,),
)
async def sample_version_create_route(
    sample_set_id: UUID, body: VersionIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> VersionStartedOut:
    """Draw a version (T10): the server seeds it and starts `SampleDrawWorkflow`; 409
    `completeness_tie_required`; 403 `seed_not_allowed` has no input to arrive through."""
    from abacus.modules.sampling import sample_sets  # the service imports these models

    await live_gate(ctx, write=True)
    return await sample_sets.start_version(ctx, sample_set_id, body, idempotency_key)


@sample_sets_router.get(
    "/{sample_set_id}", action="sample_set.read", response_model=SampleSetOut, errors=()
)
async def sample_set_route(
    sample_set_id: UUID,
    ctx: Ctx,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> SampleSetOut:
    from abacus.modules.sampling import sample_sets  # the service imports these models

    found = fx.sample_set(sample_set_id, version)
    if found is not None:
        await target_gate(ctx, "sample_set.read")
        return SampleSetOut.model_validate(found)
    await live_gate(ctx, write=False)
    return await sample_sets.sample_set_view(ctx, sample_set_id, version)


@sample_sets_router.get(
    "/{sample_set_id}/versions/{version_no}/draw",
    action="sample_set.read",
    response_model=DrawProgressOut,
    errors=(),
)
async def sample_draw_progress_route(
    sample_set_id: UUID, version_no: int, ctx: Ctx
) -> DrawProgressOut:
    from abacus.modules.sampling import sample_sets  # the service imports these models

    found = fx.draw_progress(sample_set_id, version_no)
    if found is not None:
        await target_gate(ctx, "sample_set.read")
        return DrawProgressOut.model_validate(found)
    await live_gate(ctx, write=False)
    return await sample_sets.draw_progress(ctx, sample_set_id, version_no)


@sample_sets_router.get(
    "/{sample_set_id}/versions/{version_no}/items",
    action="sample_set.read",
    response_model=ListPage[SampleItemOut],
    errors=(),
)
async def sample_items_route(
    sample_set_id: UUID,
    version_no: int,
    ctx: Ctx,
    q: Annotated[str | None, Query(max_length=120)] = None,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
) -> ListPage[SampleItemOut]:
    """The selected items with search ("Okoro" leaves Benjamin Okoro, NW-1158)."""
    from abacus.modules.sampling import sample_sets  # the service imports these models

    found = fx.items(sample_set_id, version_no, q)
    if found is not None and cursor is None:
        await target_gate(ctx, "sample_set.read")
        return ListPage[SampleItemOut](
            items=[SampleItemOut.model_validate(i) for i in found], total=len(found)
        )
    await live_gate(ctx, write=False)
    page, total, following = await sample_sets.items_page(
        ctx, sample_set_id, version_no, q, cursor
    )
    return ListPage[SampleItemOut](items=page, total=total, next_cursor=following)


@sample_sets_router.post(
    "/{sample_set_id}/versions/{version_no}/approve",
    action="sample_set.approve",
    response_model=SampleSetOut,
    errors=(409,),
)
async def sample_set_approve_route(
    sample_set_id: UUID, version_no: int, body: ApproveIn, ctx: Ctx
) -> SampleSetOut:
    """L2 approval through review.api (T10): 409 `population_not_tied`,
    `override_not_acknowledged`, `content_changed`; never the preparer (403)."""
    from abacus.modules.sampling import sample_sets  # the service imports these models

    await live_gate(ctx, write=True)
    return await sample_sets.approve(ctx, sample_set_id, version_no, body)


@sample_sets_router.get(
    "/{sample_set_id}/versions/{version_no}/export.xlsx",
    action="sample_set.export",
    response_model=bytes,
    errors=(409,),
)
async def sample_set_export_route(sample_set_id: UUID, version_no: int, ctx: Ctx) -> Response:
    """Deterministic XLSX with a cover sheet (seed, algorithm, parameters, population hash)."""
    from abacus.modules.sampling import sample_sets  # the service imports these models

    await live_gate(ctx, write=True)
    data = await sample_sets.export_xlsx(ctx, sample_set_id, version_no)
    return Response(
        content=data,
        media_type=XLSX,
        headers={
            "Content-Disposition": (
                f'attachment; filename="sample-{sample_set_id}-v{version_no}.xlsx"'
            )
        },
    )


@sample_sets_router.post(
    "/{sample_set_id}/versions/{version_no}/item-requests/preview",
    action="sample_set.generate_requests",
    response_model=ItemRequestPreviewOut,
    errors=(409,),
)
async def sample_item_requests_preview_route(
    sample_set_id: UUID, version_no: int, body: ItemRequestsIn, ctx: Ctx
) -> ItemRequestPreviewOut:
    """ "125 requests · 100 to POR-03 · 25 to POR-14" (T13); 409 `sample_not_approved`."""
    from abacus.modules.sampling import item_requests  # the service imports these models

    await live_gate(ctx, write=True)
    return await item_requests.preview(ctx, sample_set_id, version_no, body)


@sample_sets_router.post(
    "/{sample_set_id}/versions/{version_no}/item-requests",
    action="sample_set.generate_requests",
    response_model=ItemRequestsCreatedOut,
    status_code=201,
    errors=(409,),
)
async def sample_item_requests_route(
    sample_set_id: UUID,
    version_no: int,
    body: ItemRequestsIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> ItemRequestsCreatedOut:
    """Create the fan-out through requests.api.create_items_bulk (T13); 409
    `sample_not_approved`; a replay with the same key returns the stored response."""
    from abacus.modules.sampling import item_requests

    await live_gate(ctx, write=True)
    return await item_requests.create(ctx, sample_set_id, version_no, body, idempotency_key)


ROUTERS = (work_items_router, populations_router, sample_sets_router)

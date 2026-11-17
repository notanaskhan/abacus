"""Tax entity depth, other-entity workpapers and form pages v1 stubs (T-06-T07; SPEC-702 F1 to F5,
F7; `docs/contracts/{tax-entity-depth,other-entity-workpapers,form-pages}.md`). Screen families
TXP-03 fixed assets, TXP-04 book-tax, TXP-08 basis and the §754 card, TXP-09 states and PTET,
TXP-13 AAA / ASC 740 / 990, TAX-11 the form preview.

Every route answers, in order: a client principal 404 (no portal route; INV-4); its flag off 404
(`tax.entity_depth`, `tax.other_entity_workpapers`, `tax.form_preview`); a human-only route
refuses an agent, the platform or a support session 403 (INV-1); then 501 until its build task.

Classification (ADR-031, ADR-167): every return figure is TRI (`restricted`, `tri=True`): it is
read by an agent only with §7216 use and ai_disclosure in force (C19). Names of properties and
partners are TRI too. Ids, counts, states and percentages' codes are `internal`. Money is
`Decimal`, computed by code (ADR-050; DEC-77). The T-05 route `/schedules/m2` keeps its owner;
T-06-T30 adds its `variant` (as drafted, with the proposed fix).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import TAX_ENTITY_DEPTH, TAX_FORM_PREVIEW, TAX_OTHER_ENTITY_WORKPAPERS
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
Internal = classified("internal")
Tri = classified("restricted", tri=True)
Money = Annotated[Decimal, Field(max_digits=20, decimal_places=2), Tri]
Percent = Annotated[Decimal, Field(ge=0, le=100, max_digits=7, decimal_places=4), Tri]

Tally = Literal["tie", "off", "check"]
AssetView = Literal["register", "by_property", "dispositions"]
BasisView = Literal["basis", "s752"]
StatesView = Literal["apportionment", "credits", "nexus"]
ProvisionView = Literal["provision", "rate_reconciliation", "deferred"]
ExpenseView = Literal["part_ix", "allocation_basis"]
Severity = Literal["blocking", "warning", "clear"]
Section754 = Literal["open", "sent_to_client", "decided"]
Ptet = Literal["elected", "recommend", "not_elected"]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


# --- TXP-03 fixed assets -----------------------------------------------------------------------


class TaxDepthAssetRowOut(BaseModel):
    model_config = _cfg()

    asset_id: Annotated[UUID, Internal]
    description: Annotated[str, Field(max_length=200), Tri]
    property_key: Annotated[str, Field(max_length=60), Internal]
    placed_in_service: Annotated[date, Tri]
    cost: Money
    recovery_class: Annotated[Literal["3", "5", "7", "10", "15", "20", "27.5", "39"], Internal]
    method: Annotated[Literal["SL", "200DB", "150DB"], Internal]
    convention: Annotated[Literal["MM", "HY", "MQ"], Internal]
    bonus_pct: Percent
    prior: Money
    current: Money
    accumulated: Money
    bonus_check: Annotated[Literal["tie", "check", "not_eligible"], Internal]
    flags: Annotated[int, Field(ge=0), Internal] = 0
    cell_ref: Annotated[str | None, Field(max_length=40), Internal] = None  # "02 Fixed Assets!F12"


class TaxDepthPropertyOut(BaseModel):
    """By property (TXP-03 b; Form 8825): Elm Street 169,500 · Larimer 360,000 · Bergen 204,000."""

    model_config = _cfg()

    property_key: Annotated[str, Field(max_length=60), Internal]
    name: Annotated[str, Field(max_length=200), Tri]
    land: Money
    depreciation: Money


class TaxDepthFixedAssetsOut(BaseModel):
    """TXP-03 a: cost 15,752,000; accumulated 1,891,667 + 733,500 = 2,625,167."""

    model_config = _cfg()

    view: Annotated[AssetView, Internal]
    rows: Annotated[list[TaxDepthAssetRowOut], Internal]
    by_property: Annotated[list[TaxDepthPropertyOut], Internal] = []
    depreciable_cost: Money
    land: Money
    current: Money
    accumulated: Money
    ties_to_tb: Annotated[Tally, Internal]
    book_equals_tax: Annotated[Tally, Internal]
    bonus_eligibility: Annotated[Tally, Internal]
    dispositions: Annotated[int, Field(ge=0), Internal]
    engine_version: Annotated[str, Field(max_length=20), Internal]
    inputs_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), Internal]


class TaxDepthAssetIn(BaseModel):
    model_config = _cfg()

    description: Annotated[str, Field(min_length=1, max_length=200), Tri]
    property_key: Annotated[str, Field(min_length=1, max_length=60), Internal]
    placed_in_service: Annotated[date, Tri]
    cost: Money
    recovery_class: Annotated[Literal["3", "5", "7", "10", "15", "20", "27.5", "39"], Internal]


class TaxDepthAssetChangeIn(BaseModel):
    """A C3 proposal (ghost value); applied only on a reviewer's approval."""

    model_config = _cfg()

    recovery_class: Annotated[
        Literal["3", "5", "7", "10", "15", "20", "27.5", "39"] | None, Internal
    ] = None
    convention: Annotated[Literal["MM", "HY", "MQ"] | None, Internal] = None
    bonus_pct: Annotated[Decimal | None, Field(ge=0, le=100), Tri] = None
    sec179: Annotated[Decimal | None, Field(ge=0), Tri] = None
    acquired_on: Annotated[date | None, Tri] = None
    binding_contract_on: Annotated[date | None, Tri] = None
    citation_ids: Annotated[list[UUID], Field(max_length=10), Internal] = []
    expected_version: Annotated[int, Field(ge=1), Internal]


class TaxDepthProposalOut(BaseModel):
    model_config = _cfg()

    proposal_id: Annotated[UUID, Internal]
    kind: Annotated[Literal["fixed_asset_change", "sourcing_position"], Internal]
    version: Annotated[int, Field(ge=1), Internal]


# --- TXP-04 book-tax ---------------------------------------------------------------------------


class TaxDepthM3RowOut(BaseModel):
    """(a) + (b) + (c) = (d) on every row."""

    model_config = _cfg()

    line: Annotated[str, Field(max_length=20), Internal]
    label: Annotated[str, Field(max_length=200), Internal]
    income_per_books: Money
    temporary: Money
    permanent: Money
    per_return: Money
    note: Annotated[str | None, Field(max_length=200), Tri] = None


class TaxDepthScheduleOut(BaseModel):
    model_config = _cfg()

    schedule: Annotated[Literal["m3", "m1"], Internal]
    required: Annotated[bool, Internal]
    total_assets: Money
    book_income: Money
    rows: Annotated[list[TaxDepthM3RowOut], Internal]
    filed: Annotated[bool, Internal]  # the M-1 reference is never filed beside an M-3


# --- TXP-08 basis and the §754 card ------------------------------------------------------------


class TaxDepthPartnerBasisOut(BaseModel):
    model_config = _cfg()

    partner_id: Annotated[UUID, Internal]
    name: Annotated[str, Field(max_length=200), Tri]
    inside: Money
    outside: Money
    tally: Annotated[Tally, Internal]
    qualified_nonrecourse: Money | None = None
    other_nonrecourse: Money | None = None


class TaxDepthBasisOut(BaseModel):
    """TXP-08 a: 4 of 5 reconcile; inside 17,914,500 vs outside 17,943,095."""

    model_config = _cfg()

    view: Annotated[BasisView, Internal]
    partners: Annotated[list[TaxDepthPartnerBasisOut], Internal]
    reconciled: Annotated[int, Field(ge=0), Internal]
    inside_total: Money
    outside_total: Money
    section_754: Annotated[Section754, Internal]


class TaxDepthDecisionCardIn(BaseModel):
    model_config = _cfg()

    kind: Annotated[Literal["section_754"], Internal]
    subject_partner_id: Annotated[UUID, Internal]


class TaxDepthSendToClientIn(BaseModel):
    model_config = _cfg()

    contact_id: Annotated[UUID, Internal]
    template_version_id: Annotated[UUID, Internal]


class TaxDepthDecisionOut(BaseModel):
    model_config = _cfg()

    card_id: Annotated[UUID, Internal]
    status: Annotated[Section754, Internal]
    deadline: Annotated[date | None, Internal] = None


# --- TXP-09 states and PTET --------------------------------------------------------------------


class TaxDepthStateOut(BaseModel):
    model_config = _cfg()

    state: Annotated[str, Field(pattern=r"^[A-Z]{2}$"), Internal]
    apportionment_pct: Percent
    ptet: Annotated[Ptet, Internal]
    ptet_paid: Money | None = None
    ptet_paid_on: Annotated[date | None, Tri] = None
    mapped: Annotated[bool, Internal]
    nexus_conclusion: Annotated[str | None, Field(max_length=200), Tri] = None


class TaxDepthStatesOut(BaseModel):
    """TXP-09 a: IL 46.0 + CO 31.5 + NY 22.5 = 100.0; PTET 64,096 paid Mar 12, 2026."""

    model_config = _cfg()

    view: Annotated[StatesView, Internal]
    states: Annotated[list[TaxDepthStateOut], Internal]
    apportionment_tally: Annotated[Tally, Internal]
    sourcing: Annotated[Literal["proposed", "approved", "rejected", "undone"] | None, Internal]
    paid_count: Annotated[int, Field(ge=0), Internal]
    payable_count: Annotated[int, Field(ge=0), Internal]


class TaxDepthPtetIn(BaseModel):
    model_config = _cfg()

    election: Annotated[Ptet, Internal]
    payment_amount: Money | None = None
    payment_on: Annotated[date | None, Tri] = None
    expected_version: Annotated[int, Field(ge=1), Internal]


class TaxDepthUndoIn(BaseModel):
    model_config = _cfg()

    decision_id: Annotated[UUID, Internal]


# --- TXP-13 other entity workpapers ------------------------------------------------------------


class TaxDepthAaaOut(BaseModel):
    """TXP-13 a: AAA 1,488,200; allocation 70/30 per share per day; read-only once Accepted."""

    model_config = _cfg()

    aaa: Money
    pti: Money
    e_and_p: Money
    oaa: Money
    shareholder_pcts: Annotated[list[Percent], Internal]
    locked: Annotated[bool, Internal]


class TaxDepthProvisionOut(BaseModel):
    """TXP-13 b: current 2,134,650 + deferred 122,550 = 2,257,200 at an ETR of 28.9%."""

    model_config = _cfg()

    view: Annotated[ProvisionView, Internal]
    current: Money
    deferred: Money
    total: Money
    effective_rate: Percent
    rate_reconciliation_tally: Annotated[Tally, Internal]
    unclassified: Money | None = None


class TaxDepthFunctionalExpensesOut(BaseModel):
    """TXP-13 c: Part IX 3,210,000 + 486,000 + 318,000 = 4,014,000; program 80.0%; public
    support 87.4%."""

    model_config = _cfg()

    view: Annotated[ExpenseView, Internal]
    program: Money
    management: Money
    fundraising: Money
    total: Money
    program_ratio: Percent
    public_support: Percent


class TaxDepthRunOut(BaseModel):
    model_config = _cfg()

    run_id: Annotated[UUID, Internal]


# --- TAX-11 form pages -------------------------------------------------------------------------


class TaxDepthFormPageOut(BaseModel):
    model_config = _cfg()

    page_key: Annotated[str, Field(pattern=r"^[a-z0-9_]{2,40}$"), Internal]
    caption: Annotated[str, Field(max_length=120), Internal]
    blocking: Annotated[int, Field(ge=0), Internal]
    rendered: Annotated[bool, Internal]


class TaxDepthFormPagesOut(BaseModel):
    """Watermarked "Draft — not for filing" from an approved checkpoint (DEC-78)."""

    model_config = _cfg()

    checkpoint_id: Annotated[UUID, Internal]
    pages: Annotated[list[TaxDepthFormPageOut], Internal]
    watermark: Annotated[Literal["Draft — not for filing"], Internal]


class TaxDepthFieldOut(BaseModel):
    model_config = _cfg()

    field_key: Annotated[str, Field(max_length=80), Internal]
    label: Annotated[str, Field(max_length=120), Internal]
    value: Annotated[str | None, Field(max_length=200), Tri] = None
    rect: Annotated[list[Decimal], Field(min_length=4, max_length=4), Internal]


class TaxDepthFieldsOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[TaxDepthFieldOut], Internal]


class TaxDepthTraceOut(BaseModel):
    """Form field → workbook cell → TB line (SHL-09)."""

    model_config = _cfg()

    field_key: Annotated[str, Internal]
    cell_ref: Annotated[str | None, Internal] = None
    tb_lines: Annotated[list[str], Internal] = []


class TaxDepthDiagnosticOut(BaseModel):
    model_config = _cfg()

    rule_key: Annotated[str, Field(max_length=80), Internal]
    severity: Annotated[Severity, Internal]
    issue_id: Annotated[UUID | None, Internal] = None


class TaxDepthDiagnosticsOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[TaxDepthDiagnosticOut], Internal]
    blocking: Annotated[int, Field(ge=0), Internal]


class TaxDepthK1PreviewOut(BaseModel):
    model_config = _cfg()

    partner_id: Annotated[UUID, Internal]
    name: Annotated[str, Field(max_length=200), Tri]
    box_2: Money


class TaxDepthK1PreviewsOut(BaseModel):
    """Σ box 2 = 1,231,600 = Schedule K line 2 (TAX-11 c)."""

    model_config = _cfg()

    items: Annotated[list[TaxDepthK1PreviewOut], Internal]
    box_2_total: Money
    schedule_k_line_2: Money
    tally: Annotated[Tally, Internal]


# --- routes (each 501, one action) -------------------------------------------------------------

entity_depth_router = AbacusRouter(prefix="/v1", tags=["tax"])
_R = "/tax-returns/{return_id}"


async def _on(ctx: AuthContext, flag: Flag) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)


async def _human(ctx: AuthContext, flag: Flag, action: str) -> None:
    await _on(ctx, flag)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


_D = TAX_ENTITY_DEPTH
_W = TAX_OTHER_ENTITY_WORKPAPERS
_F = TAX_FORM_PREVIEW


@entity_depth_router.get(
    f"{_R}/fixed-assets",
    action="fixed_asset.read",
    response_model=TaxDepthFixedAssetsOut,
    errors=(501,),
)
async def fixed_assets_route(
    return_id: UUID, ctx: Ctx, view: AssetView = "register"
) -> TaxDepthFixedAssetsOut:
    await _on(ctx, _D)
    raise NotImplementedYet


@entity_depth_router.get(
    f"{_R}/fixed-assets/{{asset_id}}",
    action="fixed_asset.read",
    response_model=TaxDepthAssetRowOut,
    errors=(501,),
)
async def fixed_asset_route(return_id: UUID, asset_id: UUID, ctx: Ctx) -> TaxDepthAssetRowOut:
    await _on(ctx, _D)
    raise NotImplementedYet


@entity_depth_router.post(
    f"{_R}/fixed-assets",
    action="fixed_asset.create",
    response_model=TaxDepthAssetRowOut,
    status_code=201,
    errors=(409, 501),
)
async def fixed_asset_create_route(
    return_id: UUID, body: TaxDepthAssetIn, ctx: Ctx
) -> TaxDepthAssetRowOut:
    """409 `return_locked` once Accepted."""
    await _human(ctx, _D, "fixed_asset.create")
    raise NotImplementedYet


@entity_depth_router.post(
    f"{_R}/fixed-assets/{{asset_id}}/changes",
    action="fixed_asset.propose_change",
    response_model=TaxDepthProposalOut,
    status_code=201,
    errors=(409, 501),
)
async def fixed_asset_change_route(
    return_id: UUID, asset_id: UUID, body: TaxDepthAssetChangeIn, ctx: Ctx
) -> TaxDepthProposalOut:
    """A ghost value; nothing changes until a reviewer approves (C3)."""
    await _on(ctx, _D)
    raise NotImplementedYet


@entity_depth_router.get(
    f"{_R}/schedules/m3", action="book_tax.read", response_model=TaxDepthScheduleOut, errors=(501,)
)
async def m3_route(return_id: UUID, ctx: Ctx) -> TaxDepthScheduleOut:
    await _on(ctx, _D)
    raise NotImplementedYet


@entity_depth_router.get(
    f"{_R}/schedules/m1", action="book_tax.read", response_model=TaxDepthScheduleOut, errors=(501,)
)
async def m1_route(return_id: UUID, ctx: Ctx) -> TaxDepthScheduleOut:
    """The M-1 reference: never filed beside an M-3."""
    await _on(ctx, _D)
    raise NotImplementedYet


@entity_depth_router.get(
    f"{_R}/basis", action="basis.read", response_model=TaxDepthBasisOut, errors=(501,)
)
async def basis_route(
    return_id: UUID, ctx: Ctx, view: BasisView = "basis", partner: UUID | None = None
) -> TaxDepthBasisOut:
    await _on(ctx, _D)
    raise NotImplementedYet


@entity_depth_router.post(
    f"{_R}/decision-cards",
    action="decision.raise",
    response_model=TaxDepthDecisionOut,
    status_code=201,
    errors=(409, 501),
)
async def raise_decision_route(
    return_id: UUID, body: TaxDepthDecisionCardIn, ctx: Ctx
) -> TaxDepthDecisionOut:
    """The §754 card with options computed by code."""
    await _human(ctx, _D, "decision.raise")
    raise NotImplementedYet


@entity_depth_router.post(
    "/decision-cards/{card_id}/send-to-client",
    action="decision.send_to_client",
    response_model=TaxDepthDecisionOut,
    errors=(409, 501),
)
async def send_decision_route(
    card_id: UUID, body: TaxDepthSendToClientIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> TaxDepthDecisionOut:
    """One POR-04 request from the firm's template; 409 `decision_already_sent`."""
    await _human(ctx, _D, "decision.send_to_client")
    raise NotImplementedYet


@entity_depth_router.get(
    f"{_R}/states", action="states.read", response_model=TaxDepthStatesOut, errors=(501,)
)
async def states_route(
    return_id: UUID, ctx: Ctx, view: StatesView = "apportionment"
) -> TaxDepthStatesOut:
    await _on(ctx, _D)
    raise NotImplementedYet


@entity_depth_router.post(
    f"{_R}/states/sourcing:propose",
    action="sourcing.propose",
    response_model=TaxDepthProposalOut,
    status_code=201,
    errors=(409, 501),
)
async def sourcing_propose_route(return_id: UUID, ctx: Ctx) -> TaxDepthProposalOut:
    await _on(ctx, _D)
    raise NotImplementedYet


@entity_depth_router.post(
    f"{_R}/states/sourcing/undo",
    action="sourcing.approve",
    response_model=TaxDepthProposalOut,
    errors=(409, 501),
)
async def sourcing_undo_route(
    return_id: UUID, body: TaxDepthUndoIn, ctx: Ctx
) -> TaxDepthProposalOut:
    """`sourcing.undone` inside the 10-second window (DEC-24)."""
    await _human(ctx, _D, "sourcing.approve")
    raise NotImplementedYet


@entity_depth_router.patch(
    f"{_R}/states/{{state}}/ptet",
    action="ptet.update",
    response_model=TaxDepthStateOut,
    errors=(409, 501),
)
async def ptet_route(
    return_id: UUID, state: str, body: TaxDepthPtetIn, ctx: Ctx
) -> TaxDepthStateOut:
    await _human(ctx, _D, "ptet.update")
    raise NotImplementedYet


@entity_depth_router.get(
    f"{_R}/schedules/aaa",
    action="other_workpapers.read",
    response_model=TaxDepthAaaOut,
    errors=(501,),
)
async def aaa_route(return_id: UUID, ctx: Ctx) -> TaxDepthAaaOut:
    await _on(ctx, _W)
    raise NotImplementedYet


@entity_depth_router.get(
    f"{_R}/provision",
    action="other_workpapers.read",
    response_model=TaxDepthProvisionOut,
    errors=(501,),
)
async def provision_route(
    return_id: UUID, ctx: Ctx, view: ProvisionView = "provision"
) -> TaxDepthProvisionOut:
    await _on(ctx, _W)
    raise NotImplementedYet


@entity_depth_router.post(
    f"{_R}/provision/items/{{item_id}}/explain",
    action="issue.create",
    response_model=TaxDepthRunOut,
    status_code=202,
    errors=(409, 501),
)
async def provision_explain_route(return_id: UUID, item_id: UUID, ctx: Ctx) -> TaxDepthRunOut:
    """An SHL-15 issue; the classification arrives as a proposal (zero gateway calls without
    consent)."""
    await _human(ctx, _W, "issue.create")
    raise NotImplementedYet


@entity_depth_router.get(
    f"{_R}/functional-expenses",
    action="other_workpapers.read",
    response_model=TaxDepthFunctionalExpensesOut,
    errors=(501,),
)
async def functional_expenses_route(
    return_id: UUID, ctx: Ctx, view: ExpenseView = "part_ix"
) -> TaxDepthFunctionalExpensesOut:
    await _on(ctx, _W)
    raise NotImplementedYet


@entity_depth_router.post(
    f"{_R}/functional-expenses/allocation-runs",
    action="allocation_run.start",
    response_model=TaxDepthRunOut,
    status_code=202,
    errors=(409, 501),
)
async def allocation_run_route(
    return_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> TaxDepthRunOut:
    await _human(ctx, _W, "allocation_run.start")
    raise NotImplementedYet


@entity_depth_router.get(
    f"{_R}/form-pages",
    action="form_preview.read",
    response_model=TaxDepthFormPagesOut,
    errors=(409, 501),
)
async def form_pages_route(
    return_id: UUID, ctx: Ctx, checkpoint: UUID | None = None
) -> TaxDepthFormPagesOut:
    """409 `form_template_missing` for forms without a face template (DV-9)."""
    await _on(ctx, _F)
    raise NotImplementedYet


@entity_depth_router.get(
    f"{_R}/form-pages/{{page_key}}/fields",
    action="form_preview.read",
    response_model=TaxDepthFieldsOut,
    errors=(501,),
)
async def form_fields_route(return_id: UUID, page_key: str, ctx: Ctx) -> TaxDepthFieldsOut:
    await _on(ctx, _F)
    raise NotImplementedYet


@entity_depth_router.get(
    f"{_R}/fields/{{field_key}}/trace",
    action="form_preview.read",
    response_model=TaxDepthTraceOut,
    errors=(501,),
)
async def field_trace_route(return_id: UUID, field_key: str, ctx: Ctx) -> TaxDepthTraceOut:
    await _on(ctx, _F)
    raise NotImplementedYet


@entity_depth_router.get(
    f"{_R}/diagnostics",
    action="form_preview.read",
    response_model=TaxDepthDiagnosticsOut,
    errors=(501,),
)
async def diagnostics_route(return_id: UUID, ctx: Ctx) -> TaxDepthDiagnosticsOut:
    await _on(ctx, _F)
    raise NotImplementedYet


@entity_depth_router.get(
    f"{_R}/k1-previews",
    action="k1_package.read",
    response_model=TaxDepthK1PreviewsOut,
    errors=(501,),
)
async def k1_previews_route(return_id: UUID, ctx: Ctx) -> TaxDepthK1PreviewsOut:
    await _on(ctx, _F)
    raise NotImplementedYet


@entity_depth_router.post(
    f"{_R}/form-pages:download-draft",
    action="form_preview.download_draft",
    response_model=bytes,
    errors=(501,),
)
async def download_draft_route(return_id: UUID, ctx: Ctx) -> bytes:
    """Watermarked PDF; fresh MFA; one `form_preview.downloaded` audit event (DEC-60)."""
    await _human(ctx, _F, "form_preview.download_draft")
    raise NotImplementedYet

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
from typing import Annotated, Any, Literal, cast
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
# An optional figure keeps its tag on the outside of the union (classification is field-level).
MaybeMoney = Annotated[Decimal | None, Field(max_digits=20, decimal_places=2), Tri]
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
    qualified_nonrecourse: MaybeMoney = None
    other_nonrecourse: MaybeMoney = None


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
    ptet_paid: MaybeMoney = None
    ptet_paid_on: Annotated[date | None, Tri] = None
    mapped: Annotated[bool, Internal]
    nexus_conclusion: Annotated[str | None, Field(max_length=200), Tri] = None
    # T-06-T32 (additive; DEC-5837): the row TXP-09 a draws, every figure the server's.
    name: Annotated[str | None, Field(max_length=60), Internal] = None
    property_name: Annotated[str | None, Field(max_length=200), Tri] = None
    numerator: MaybeMoney = None
    denominator: MaybeMoney = None
    nexus_basis: Annotated[str | None, Field(max_length=200), Tri] = None
    rate_pct: Annotated[Decimal | None, Field(ge=0, le=100), Tri] = None
    ptet_amount: MaybeMoney = None
    return_form: Annotated[str | None, Field(max_length=60), Internal] = None
    status: Annotated[Literal["in_review", "approved"] | None, Internal] = None
    approved_by_initials: Annotated[str | None, Field(max_length=4), Internal] = None
    approved_on: Annotated[date | None, Internal] = None


class TaxDepthCreditOut(BaseModel):
    """TXP-09 a's Partner PTET credits: one partner's credit by state (to the state K-1s)."""

    model_config = _cfg()

    partner_id: Annotated[UUID, Internal]
    name: Annotated[str, Field(max_length=200), Tri]
    note: Annotated[str | None, Field(max_length=60), Tri] = None
    by_state: Annotated[dict[str, Decimal], Tri]
    total: Money


class TaxDepthNexusOut(BaseModel):
    """TXP-09 d: a state's nexus fact, its evidence, conclusion and owner."""

    model_config = _cfg()

    state: Annotated[str, Field(max_length=60), Internal]
    fact: Annotated[str, Field(max_length=500), Tri]
    evidence_name: Annotated[str | None, Field(max_length=200), Tri] = None
    evidence_version_id: Annotated[UUID | None, Internal] = None
    conclusion: Annotated[str, Field(max_length=200), Tri]
    owner_initials: Annotated[str | None, Field(max_length=4), Internal] = None


class TaxDepthOpportunityOut(BaseModel):
    """TXP-09 a's opportunity row (NYC): a recommendation only; nothing is elected here."""

    model_config = _cfg()

    jurisdiction: Annotated[str, Field(max_length=60), Internal]
    subject: Annotated[str, Field(max_length=200), Tri]
    basis: Annotated[str, Field(max_length=200), Tri]
    deadline_note: Annotated[str, Field(max_length=200), Tri]


class TaxDepthStatesOut(BaseModel):
    """TXP-09 a: IL 46.0 + CO 31.5 + NY 22.5 = 100.0; PTET 64,096 paid Mar 12, 2026."""

    model_config = _cfg()

    view: Annotated[StatesView, Internal]
    states: Annotated[list[TaxDepthStateOut], Internal]
    apportionment_tally: Annotated[Tally, Internal]
    sourcing: Annotated[Literal["proposed", "approved", "rejected", "undone"] | None, Internal]
    paid_count: Annotated[int, Field(ge=0), Internal]
    payable_count: Annotated[int, Field(ge=0), Internal]
    # T-06-T32 (additive; DEC-5837): TXP-09's tallies, credits, nexus and opportunity rows.
    base: MaybeMoney = None
    ptet_total: MaybeMoney = None
    credits: Annotated[list[TaxDepthCreditOut], Internal] = []
    nexus: Annotated[list[TaxDepthNexusOut], Internal] = []
    opportunities: Annotated[list[TaxDepthOpportunityOut], Internal] = []


class TaxDepthPtetIn(BaseModel):
    model_config = _cfg()

    election: Annotated[Ptet, Internal]
    payment_amount: MaybeMoney = None
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
    unclassified: MaybeMoney = None


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


def _asset_row(facts: object, computed: object, asset: object) -> TaxDepthAssetRowOut:
    from abacus.modules.tax import fixed_assets_service as fa

    f, c, a = cast(fa.Facts, facts), cast(fa.Computed, computed), cast(fa.AssetRecord, asset)
    row = c.by_asset.get(str(a.id))
    prior = Decimal(row.prior if row else 0)
    current = Decimal(row.current if row else 0)
    cls = a.recovery_class if a.recovery_class in _CLASSES else "39"
    return TaxDepthAssetRowOut(
        asset_id=a.id, description=a.description, property_key=a.property_key,
        placed_in_service=a.placed_in_service_on, cost=a.cost,
        recovery_class=cast(Any, cls), method=cast(Any, a.method),
        convention=cast(Any, a.convention),
        bonus_pct=a.bonus_pct, prior=prior, current=current, accumulated=prior + current,
        bonus_check=c.bonus.get(str(a.id), "not_eligible"),
        flags=1 if a.status == "flag" else 0, cell_ref=f.cells.get(a.asset_no),
    )  # fmt: skip


_CLASSES = ("3", "5", "7", "10", "15", "20", "27.5", "39")


@entity_depth_router.get(
    f"{_R}/fixed-assets",
    action="fixed_asset.read",
    response_model=TaxDepthFixedAssetsOut,
    errors=(),
)
async def fixed_assets_route(
    return_id: UUID, ctx: Ctx, view: AssetView = "register"
) -> TaxDepthFixedAssetsOut:
    """TXP-03 a, b, d from E3 (T-06-T33): register, by property, dispositions."""
    await _on(ctx, _D)
    from abacus.modules.tax import fixed_assets_service as fa

    facts, computed = await fa.read(ctx, return_id)
    to_tb, book, bonus = fa.tallies(facts, computed)
    shown = [a for a in facts.assets if a.disposed == (view == "dispositions")]
    rows = [_asset_row(facts, computed, a) for a in shown if a.recovery_class in _CLASSES]
    by_property = [
        TaxDepthPropertyOut(
            property_key=p.code, name=p.name, land=p.land,
            depreciation=Decimal(computed.register.by_property.get(p.code, 0)),
        )
        for p in facts.properties
    ]  # fmt: skip
    return TaxDepthFixedAssetsOut(
        view=view,
        rows=[] if view == "by_property" else rows,
        by_property=by_property if view == "by_property" else [],
        depreciable_cost=Decimal(computed.register.cost),
        land=sum((p.land for p in facts.properties), Decimal(0)),
        current=Decimal(computed.register.current),
        accumulated=Decimal(computed.register.accumulated),
        ties_to_tb=to_tb,
        book_equals_tax=book,
        bonus_eligibility=bonus,
        dispositions=sum(1 for a in facts.assets if a.disposed),
        engine_version=computed.register.engine_version,
        inputs_hash=computed.inputs_hash,
    )


@entity_depth_router.get(
    f"{_R}/fixed-assets/{{asset_id}}",
    action="fixed_asset.read",
    response_model=TaxDepthAssetRowOut,
    errors=(),
)
async def fixed_asset_route(return_id: UUID, asset_id: UUID, ctx: Ctx) -> TaxDepthAssetRowOut:
    """TXP-03 a2's drawer (T-06-T33)."""
    await _on(ctx, _D)
    from abacus.modules.tax import fixed_assets_service as fa

    facts, computed = await fa.read(ctx, return_id)
    asset = next((a for a in facts.assets if a.id == asset_id), None)
    if asset is None:
        raise NotFound("fixed_asset")
    return _asset_row(facts, computed, asset)


@entity_depth_router.post(
    f"{_R}/fixed-assets",
    action="fixed_asset.create",
    response_model=TaxDepthAssetRowOut,
    status_code=201,
    errors=(409,),
)
async def fixed_asset_create_route(
    return_id: UUID, body: TaxDepthAssetIn, ctx: Ctx
) -> TaxDepthAssetRowOut:
    """409 `return_locked` once Accepted."""
    await _human(ctx, _D, "fixed_asset.create")
    from abacus.modules.tax import fixed_assets_service as fa

    asset_id = await fa.create(
        ctx, return_id, description=body.description, property_key=body.property_key,
        placed_in_service=body.placed_in_service, cost=body.cost,
        recovery_class=body.recovery_class,
    )  # fmt: skip
    return await fixed_asset_route(return_id, asset_id, ctx)


@entity_depth_router.post(
    f"{_R}/fixed-assets/{{asset_id}}/changes",
    action="fixed_asset.propose_change",
    response_model=TaxDepthProposalOut,
    status_code=201,
    errors=(409,),
)
async def fixed_asset_change_route(
    return_id: UUID, asset_id: UUID, body: TaxDepthAssetChangeIn, ctx: Ctx
) -> TaxDepthProposalOut:
    """A ghost value; nothing changes until a reviewer approves (T-06-T33, DEC-5833)."""
    await _human(ctx, _D, "fixed_asset.propose_change")
    from abacus.modules.tax import fixed_assets_service as fa

    change = body.model_dump(exclude={"citation_ids", "expected_version"})
    request_id = await fa.propose_change(
        ctx, return_id, asset_id, change=change, expected_version=body.expected_version,
        citation_ids=list(body.citation_ids),
    )  # fmt: skip
    return TaxDepthProposalOut(
        proposal_id=request_id, kind="fixed_asset_change", version=body.expected_version + 1
    )


class TaxDepthChangeDecisionIn(BaseModel):
    """T-06-T33: a reviewer's decision on a person's asset change (reason when rejecting)."""

    model_config = _cfg()

    reason: Annotated[str | None, Field(max_length=500), Tri] = None


class TaxDepthChangeDecidedOut(BaseModel):
    model_config = _cfg()

    proposal_id: Annotated[UUID, Internal]
    decision: Annotated[Literal["approved", "rejected"], Internal]
    current: Money  # the register's depreciation after the decision (733,500)
    checkpoint_id: Annotated[UUID | None, Internal] = None


async def _decide(
    return_id: UUID, change_id: UUID, ctx: AuthContext, approve: bool, reason: str | None
) -> TaxDepthChangeDecidedOut:
    await _human(ctx, _D, "fixed_asset.approve_change")
    from abacus.modules.tax import fixed_assets_service as fa

    done = await fa.decide(ctx, return_id, change_id, approve=approve, reason=reason)
    return TaxDepthChangeDecidedOut(
        proposal_id=done.request_id, decision=done.decision, current=Decimal(done.current),
        checkpoint_id=done.checkpoint_id,
    )  # fmt: skip


@entity_depth_router.post(
    f"{_R}/fixed-asset-changes/{{change_id}}:approve",
    action="fixed_asset.approve_change",
    response_model=TaxDepthChangeDecidedOut,
    errors=(409,),
)
async def fixed_asset_change_approve_route(
    return_id: UUID, change_id: UUID, ctx: Ctx
) -> TaxDepthChangeDecidedOut:
    """A reviewer other than the requester; 409 `proposal_changed` when the asset moved."""
    return await _decide(return_id, change_id, ctx, True, None)


@entity_depth_router.post(
    f"{_R}/fixed-asset-changes/{{change_id}}:reject",
    action="fixed_asset.approve_change",
    response_model=TaxDepthChangeDecidedOut,
    errors=(409,),
)
async def fixed_asset_change_reject_route(
    return_id: UUID, change_id: UUID, body: TaxDepthChangeDecisionIn, ctx: Ctx
) -> TaxDepthChangeDecidedOut:
    return await _decide(return_id, change_id, ctx, False, body.reason)


@entity_depth_router.get(
    f"{_R}/schedules/m3", action="book_tax.read", response_model=TaxDepthScheduleOut, errors=()
)
async def m3_route(return_id: UUID, ctx: Ctx) -> TaxDepthScheduleOut:
    """TXP-04 a (T-06-T34): Parts II and III from E4; filed when required."""
    await _on(ctx, _D)
    return await _schedule(ctx, return_id, "m3")


async def _schedule(
    ctx: AuthContext, return_id: UUID, which: Literal["m3", "m1"]
) -> TaxDepthScheduleOut:
    from abacus.modules.tax.book_tax_service import schedule

    found = await schedule(ctx, return_id, which)
    return TaxDepthScheduleOut(
        schedule=found.schedule, required=found.required, total_assets=found.total_assets,
        book_income=found.book_income, filed=found.filed,
        rows=[
            TaxDepthM3RowOut(
                line=r.line[:20], label=r.label, income_per_books=r.a, temporary=r.b,
                permanent=r.c, per_return=r.d,
            )
            for r in found.rows
        ],
    )  # fmt: skip


@entity_depth_router.get(
    f"{_R}/schedules/m1", action="book_tax.read", response_model=TaxDepthScheduleOut, errors=()
)
async def m1_route(return_id: UUID, ctx: Ctx) -> TaxDepthScheduleOut:
    """The M-1 reference: never filed beside an M-3 (T-06-T34)."""
    await _on(ctx, _D)
    return await _schedule(ctx, return_id, "m1")


@entity_depth_router.get(
    f"{_R}/basis", action="basis.read", response_model=TaxDepthBasisOut, errors=()
)
async def basis_route(
    return_id: UUID, ctx: Ctx, view: BasisView = "basis", partner: UUID | None = None
) -> TaxDepthBasisOut:
    """TXP-08 a to c, e (T-06-T35): basis and §752 shares as E8 stored them."""
    await _on(ctx, _D)
    from abacus.modules.tax.basis_service import basis

    found = await basis(ctx, return_id, partner)
    return TaxDepthBasisOut(
        view=view,
        partners=[
            TaxDepthPartnerBasisOut(
                partner_id=p.partner_id, name=p.name, inside=p.inside, outside=p.outside,
                tally="tie" if p.reconciled else "off",
                qualified_nonrecourse=p.qualified_nonrecourse if view == "s752" else None,
                other_nonrecourse=p.other_nonrecourse if view == "s752" else None,
            )
            for p in found.partners
        ],
        reconciled=found.reconciled, inside_total=found.inside_total,
        outside_total=found.outside_total, section_754=found.section_754,
    )  # fmt: skip


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
    """The §754 card with options computed by code (T-06-T35); the open card answers again."""
    await _human(ctx, _D, "decision.raise")
    from abacus.modules.tax.basis_service import raise_card, section_754_state

    card_id = await raise_card(ctx, return_id)
    return TaxDepthDecisionOut(
        card_id=card_id, status=await section_754_state(ctx.tenant, return_id)
    )


@entity_depth_router.post(
    "/decision-cards/{card_id}/send-to-client",
    action="decision.send_to_client",
    response_model=TaxDepthDecisionOut,
    errors=(409, 501),
)
async def send_decision_route(
    card_id: UUID, body: TaxDepthSendToClientIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> TaxDepthDecisionOut:
    """The client owner's decision (C18 `section_754`, POR-08; DEC-5835); 409
    `decision_already_sent` on a second send."""
    await _human(ctx, _D, "decision.send_to_client")
    from abacus.modules.tax.basis_service import send_to_client

    del idempotency_key  # one send per card is the table's own rule (UNIQUE card_id)
    await send_to_client(ctx, card_id, contact_id=body.contact_id)
    return TaxDepthDecisionOut(card_id=card_id, status="sent_to_client")


@entity_depth_router.get(
    f"{_R}/states", action="states.read", response_model=TaxDepthStatesOut, errors=()
)
async def states_route(
    return_id: UUID, ctx: Ctx, view: StatesView = "apportionment"
) -> TaxDepthStatesOut:
    """TXP-09 a to c (T-06-T36): apportionment, credits and nexus."""
    await _on(ctx, _D)
    from abacus.modules.tax.states_service import view as states_view

    found = await states_view(ctx, return_id)
    return TaxDepthStatesOut(
        view=view,
        states=[_state_out(r) for r in found.states],
        apportionment_tally=found.tally,
        sourcing=cast(Any, found.sourcing),
        paid_count=found.paid_count,
        payable_count=found.payable_count,
        base=found.states[0].denominator if found.states else None,
        ptet_total=sum((r.ptet_amount or Decimal(0) for r in found.states), Decimal(0)),
        credits=[
            TaxDepthCreditOut(
                partner_id=pid, name=found.partner_names.get(pid, ""), by_state=by_state,
                total=sum(by_state.values(), Decimal(0)),
            )
            for pid, by_state in found.credits.items()
        ],
        nexus=[
            TaxDepthNexusOut(
                state=n.state, fact=n.fact, evidence_version_id=n.evidence_version_id,
                conclusion=n.conclusion,
            )
            for n in found.nexus_rows
        ],
    )  # fmt: skip


def _state_out(r: object) -> TaxDepthStateOut:
    row = cast(Any, r)
    return TaxDepthStateOut(
        state=row.state, apportionment_pct=row.share, ptet=row.ptet, ptet_paid=row.paid,
        ptet_paid_on=row.paid_on, mapped=row.mapped, nexus_conclusion=row.nexus,
        numerator=row.numerator, denominator=row.denominator, nexus_basis=row.nexus_basis,
        rate_pct=row.rate, ptet_amount=row.ptet_amount, return_form=row.return_form,
        status=row.status,
    )  # fmt: skip


@entity_depth_router.post(
    f"{_R}/states/sourcing:propose",
    action="sourcing.propose",
    response_model=TaxDepthProposalOut,
    status_code=201,
    errors=(409, 501),
)
async def sourcing_propose_route(return_id: UUID, ctx: Ctx) -> TaxDepthProposalOut:
    """A person's sourcing position; the TXP-10 review point is raised once (T-06-T36)."""
    await _human(ctx, _D, "sourcing.propose")
    from abacus.modules.tax.states_service import propose_sourcing

    row_id = await propose_sourcing(ctx, return_id)
    return TaxDepthProposalOut(proposal_id=row_id, kind="sourcing_position", version=1)


@entity_depth_router.post(
    f"{_R}/states/sourcing:approve",
    action="sourcing.approve",
    response_model=TaxDepthProposalOut,
    errors=(409,),
)
async def sourcing_approve_route(return_id: UUID, ctx: Ctx) -> TaxDepthProposalOut:
    """A reviewer's approval; the review point resolves once (T-06-T36, DEC-5836)."""
    await _human(ctx, _D, "sourcing.approve")
    from abacus.modules.tax.states_service import _latest, approve_sourcing

    await approve_sourcing(ctx, return_id)
    latest = await _latest(ctx.tenant, return_id)
    return TaxDepthProposalOut(proposal_id=latest.id, kind="sourcing_position", version=2)


@entity_depth_router.post(
    f"{_R}/states/sourcing/undo",
    action="sourcing.approve",
    response_model=TaxDepthProposalOut,
    errors=(409, 501),
)
async def sourcing_undo_route(
    return_id: UUID, body: TaxDepthUndoIn, ctx: Ctx
) -> TaxDepthProposalOut:
    """`sourcing.undone` inside the 10-second window (DEC-24); 409 `undo_window_closed`."""
    await _human(ctx, _D, "sourcing.approve")
    from abacus.modules.tax.states_service import _latest, undo_sourcing

    del body
    await undo_sourcing(ctx, return_id)
    latest = await _latest(ctx.tenant, return_id)
    return TaxDepthProposalOut(proposal_id=latest.id, kind="sourcing_position", version=3)


@entity_depth_router.patch(
    f"{_R}/states/{{state}}/ptet",
    action="ptet.update",
    response_model=TaxDepthStateOut,
    errors=(409, 501),
)
async def ptet_route(
    return_id: UUID, state: str, body: TaxDepthPtetIn, ctx: Ctx
) -> TaxDepthStateOut:
    """The election and a payment on its version (T-06-T36); 409 `ptet_changed`."""
    await _human(ctx, _D, "ptet.update")
    from abacus.modules.tax.states_service import update_ptet
    from abacus.modules.tax.states_service import view as states_view

    await update_ptet(
        ctx, return_id, state.upper(), election=body.election,
        payment_amount=body.payment_amount, payment_on=body.payment_on,
        expected_version=body.expected_version,
    )  # fmt: skip
    found = await states_view(ctx, return_id)
    row = next((r for r in found.states if r.state == state.upper()), None)
    if row is None:
        raise NotFound("ptet_election")
    return _state_out(row)


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

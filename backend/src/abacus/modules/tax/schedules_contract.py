"""The tax schedules contract stub: extensions, estimates and the payments union (T-03-T02;
T-03 §4.3; DEC-2201). Contract: `docs/contracts/tax-extensions-estimates.md`; screen TAX-13;
consumers T-08 (HOME-03), R-03 (POR-10), T-04 (TAX-12 estimate reminders).

Every return's extension of time to file per jurisdiction, with its projected liability, what was
paid by the original due date against the safe-harbor target (computed by `tax.compute.payments`,
never a model; ADR-050, DEC-77) and the client's confirmation; every client's estimate schedule
and its quarterly installments. Accrued never transmits a filing (DEC-49): "Mark filed" records
what a person filed in the engine. Payment methods are labels, never instruments (DEC-89).

Every route answers, in order: a client principal 404 (POR-10 reads confirmation requests through
its own request grant, never these routes); the matrix action at the firm (the service narrows to
the return's engagement and function); 404 with `tax.extensions_estimates` off. Only a reminder's
follow-up draft still answers 501 (DEC-2327). Amounts and reject codes are tax return information
(`tri`); client and contact names are confidential.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Header, Path, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import TAX_EXTENSIONS_ESTIMATES
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)
from abacus.modules.requests.api import RequestItemView

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
IfMatch = Annotated[int, Header(alias="If-Match", ge=1)]
Tri = classified("restricted", tri=True)
Money = Annotated[Decimal, Field(max_digits=18, decimal_places=2), Tri]
Pct = Annotated[Decimal, Field(max_digits=5, decimal_places=2), classified("internal")]
Name = Annotated[str, classified("confidential")]
# Optional forms keep the classification on the field (a `Name | None` union drops it).
OptName = Annotated[str | None, classified("confidential")]
OptMoney = Annotated[Decimal | None, Field(max_digits=18, decimal_places=2), Tri]
OptPct = Annotated[Decimal | None, Field(max_digits=5, decimal_places=2), classified("internal")]
Internal = classified("internal")

ExtensionStatus = Literal["not_filed", "prepared", "filed", "accepted", "rejected"]
InstallmentStatus = Literal[
    "not_confirmed", "confirmation_requested", "scheduled", "paid", "not_required"
]
Segment = Literal["open", "filed", "likely"]
ExtensionTile = Literal["extended", "open", "filed", "likely", "acks_pending"]
EstimateTile = Literal["due", "paid", "scheduled", "confirmation_requested", "not_required"]
LikelyReason = Literal[
    "k1_outstanding", "binder_incomplete", "engagement_not_accepted", "preparer_flag"
]
LiabilitySource = Literal["engine_import", "preparer_entry"]
PaymentKind = Literal["extension_payment", "ptet"]
EstimateMethod = Literal[
    "prior_year_100",
    "prior_year_110",
    "current_year_90",
    "not_required_withholding",
    "not_required_estate_first_years",
    "prospect",
]
PaymentMethodLabel = Literal[
    "irs_direct_pay", "eftps", "ny_online_services", "state_portal", "check", "other"
]
PaymentSourceKind = Literal["extension_payment", "ptet", "estimate_installment"]
ExtensionAction = Literal[
    "filing_extension.prepare",
    "filing_extension.approve_payment",
    "filing_extension.mark_filed",
    "filing_extension.flag_likely",
    "filing_extension.confirmation_send",
    "tax_schedule.export",
]
EstimateAction = Literal[
    "estimate_schedule.update", "estimate_schedule.confirmation_send", "tax_schedule.export"
]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True)


def _strict() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


# --- shared facts -------------------------------------------------------------------------------


class EngineStampOut(BaseModel):
    """Every computed figure carries the engine that computed it (chapter 03 §10.1)."""

    model_config = _frozen()

    engine_name: Annotated[str, Internal]
    engine_version: Annotated[str, Internal]
    inputs_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), Internal]


class TaxConfirmationOut(BaseModel):
    """ "✓ Claire Feld Apr 13" or "○ (confirmation request sent Sep 8)": a request item, never a
    task (R-03 reads POR-10 from the same item)."""

    model_config = _frozen()

    confirmed: Annotated[bool, Internal]
    contact_name: OptName = None
    confirmed_on: Annotated[date | None, Internal] = None
    request_item_id: Annotated[UUID | None, Internal] = None
    requested_on: Annotated[date | None, Internal] = None


class ExtensionPaymentOut(BaseModel):
    """One proposed or approved payment; an approved payment never changes (a later change is a
    new row that supersedes it). "PTET Mar 12: IL 28,044" is a `ptet` row per state."""

    model_config = _frozen()

    id: Annotated[UUID, Internal]
    kind: Annotated[PaymentKind, Internal]
    jurisdiction: Annotated[str, Internal]
    amount: Money
    paid_on: Annotated[date | None, Internal] = None
    proposed_by_name: Name
    approved_by_name: OptName = None
    approved_at: Annotated[datetime | None, Internal] = None
    supersedes_id: Annotated[UUID | None, Internal] = None
    confirmation_evidence_version_id: Annotated[UUID | None, Internal] = None


class JurisdictionLineOut(BaseModel):
    """A grouped line under a return (Feld: "4868 + IT-370"; "10,000 · NY 6,000")."""

    model_config = _frozen()

    extension_id: Annotated[UUID, Internal]
    jurisdiction: Annotated[str, Internal]
    form: Annotated[str, Internal]
    status: Annotated[ExtensionStatus, Internal]
    filed_on: Annotated[date | None, Internal] = None
    ack_received_at: Annotated[datetime | None, Internal] = None
    reject_code: Annotated[str | None, Tri] = None
    paid_with_extension: OptMoney = None


# --- extensions ---------------------------------------------------------------------------------


class ExtensionRowOut(BaseModel):
    """One TAX-13 a row per return with its jurisdiction lines. Projected liability, the
    safe-harbor target and the paid figures are code's; cells carry no "$"."""

    model_config = _frozen()

    tax_return_id: Annotated[UUID, Internal]
    work_item_id: Annotated[UUID, Internal]
    client_id: Annotated[UUID | None, Internal] = None  # CLI-07's link (DEC-2325)
    engagement_id: Annotated[UUID | None, Internal] = None
    client_name: Name
    client_note: OptName = None  # "(Walter's 2025 Form 1040)"
    return_form: Annotated[str, Internal]  # "1040", "1065", "2025 Form 990 (FYE Jun 30, 2026)"
    tax_year: Annotated[int, Internal]
    lines: Annotated[list[JurisdictionLineOut], Internal]
    projected_liability: OptMoney = None
    projected_liability_source: Annotated[LiabilitySource | None, Internal] = None
    projected_liability_note: OptName = None  # "— (pass-through)", "Not started — …"
    withholding_plus_estimates: OptMoney = None
    safe_harbor_target: OptMoney = None
    safe_harbor_pct: OptPct = None
    paid_by_original_due: OptMoney = None
    meets_safe_harbor: Annotated[bool | None, Internal] = None
    payments: Annotated[list[ExtensionPaymentOut], Internal]
    confirmation: Annotated[TaxConfirmationOut | None, classified("confidential")] = None
    original_due_on: Annotated[date, Internal]
    extended_due_on: Annotated[date, Internal]
    days_to_extended_due: Annotated[int | None, Internal] = None
    likely_to_extend: Annotated[bool, Internal]
    likely_reasons: Annotated[list[LikelyReason], Internal]
    likely_note: OptName = None
    prepare_blocked_reason: Annotated[str | None, Internal] = None  # G1/G3 tooltip key
    stamp: Annotated[EngineStampOut | None, Internal] = None
    row_version: Annotated[int, Internal]
    allowed_actions: Annotated[list[ExtensionAction], Internal]


class ExtensionOut(ExtensionRowOut):
    """The detail: rule and engine versions, the approval trail and evidence refs."""

    due_rules_version_id: Annotated[UUID | None, Internal] = None
    filed_form_evidence_version_id: Annotated[UUID | None, Internal] = None
    filed_recorded_by_name: OptName = None


class ProposedPaymentIn(BaseModel):
    model_config = _strict()

    return_id: Annotated[UUID, Internal]
    jurisdiction: Annotated[str, Field(min_length=2, max_length=12), Internal]
    kind: Annotated[PaymentKind, Internal] = "extension_payment"
    amount: Money


class ExtensionLineIn(BaseModel):
    """A preparer's line: Accrued never computes the projected tax (T-03 US-4.2). A state line
    names its form; a federal line's follows from the return."""

    model_config = _strict()

    return_id: Annotated[UUID, Internal]
    jurisdiction: Annotated[str, Field(min_length=2, max_length=12), Internal] = "US"
    form: Annotated[str | None, Field(max_length=12), Internal] = None
    projected_liability: OptMoney = None
    projected_liability_source: Annotated[LiabilitySource | None, Internal] = None
    withholding_plus_estimates: OptMoney = None


class ExtensionPrepareIn(BaseModel):
    """409 `gate_unmet` with the G1/G3 facts for a return whose engagement is not accepted."""

    model_config = _strict()

    return_ids: Annotated[list[UUID], Field(min_length=1, max_length=200), Internal]
    lines: Annotated[list[ExtensionLineIn], Field(max_length=400), Internal] = Field(
        default_factory=list[ExtensionLineIn]
    )
    payments: Annotated[list[ProposedPaymentIn], Field(max_length=400), Internal] = Field(
        default_factory=list[ProposedPaymentIn]
    )


class ExtensionSubmitIn(BaseModel):
    model_config = _strict()

    extension_ids: Annotated[list[UUID], Field(min_length=1, max_length=200), Internal]


class ApproveAndRequestIn(BaseModel):
    """Either prepared extensions, or returns with payments (prepared in the same unit of work);
    `send_confirmations` sends one confirmation request per client ("Send confirmation
    requests")."""

    model_config = _strict()

    extension_ids: Annotated[list[UUID], Field(max_length=200), Internal] = Field(
        default_factory=list[UUID]
    )
    return_ids: Annotated[list[UUID], Field(max_length=200), Internal] = Field(
        default_factory=list[UUID]
    )
    payments: Annotated[list[ProposedPaymentIn], Field(max_length=400), Internal] = Field(
        default_factory=list[ProposedPaymentIn]
    )
    send_confirmations: Annotated[bool, Internal] = True


class SafeHarborCheckOut(BaseModel):
    model_config = _frozen()

    tax_return_id: Annotated[UUID, Internal]
    jurisdiction: Annotated[str, Internal]
    projected_liability: OptMoney = None
    safe_harbor_target: OptMoney = None
    paid_by_original_due: OptMoney = None
    meets_safe_harbor: Annotated[bool | None, Internal] = None
    stamp: Annotated[EngineStampOut | None, Internal] = None


class ExtensionBatchOut(BaseModel):
    model_config = _frozen()

    extensions: Annotated[list[ExtensionRowOut], Internal]
    checks: Annotated[list[SafeHarborCheckOut], Internal]
    gate_id: Annotated[UUID | None, Internal] = None  # submit-for-approval's C13 gate


class ApproveAndRequestOut(ExtensionBatchOut):
    approved_payment_ids: Annotated[list[UUID], Internal]
    confirmation_request_item_ids: Annotated[list[UUID], Internal]


class ExtensionPatchIn(BaseModel):
    """`filed_on` (+ `form`) records the filing in the engine (`filing_extension.mark_filed`);
    `likely_to_extend` with a reason is `filing_extension.flag_likely`. One or the other."""

    model_config = _strict()

    filed_on: Annotated[date | None, Internal] = None
    form: Annotated[str | None, Field(max_length=12), Internal] = None
    filed_form_evidence_version_id: Annotated[UUID | None, Internal] = None
    likely_to_extend: Annotated[bool | None, Internal] = None
    reason: Annotated[LikelyReason | None, Internal] = None
    note: Annotated[str | None, Field(max_length=500), classified("confidential")] = None


class ConfirmationRequestIn(BaseModel):
    model_config = _strict()

    contact_id: Annotated[UUID | None, Internal] = None


class ConfirmationRequestOut(BaseModel):
    model_config = _frozen()

    request_item_id: Annotated[UUID, Internal]
    request_list_id: Annotated[UUID, Internal]
    sent_at: Annotated[datetime, Internal]
    contact_name: Name


# --- estimates ----------------------------------------------------------------------------------


class EstimateInstallmentOut(BaseModel):
    model_config = _frozen()

    quarter: Annotated[int, Field(ge=1, le=4), Internal]
    due_on: Annotated[date, Internal]
    amount: OptMoney = None
    jurisdiction_amounts: Annotated[dict[str, Decimal], Tri] = Field(
        default_factory=dict[str, Decimal]
    )  # "19,990 · NY 7,824"
    status: Annotated[InstallmentStatus, Internal]
    scheduled_for: Annotated[date | None, Internal] = None
    paid_on: Annotated[date | None, Internal] = None
    confirmation: Annotated[TaxConfirmationOut | None, classified("confidential")] = None


class EstimateRowOut(BaseModel):
    """One TAX-13 b row: the schedule and the selected quarter's installment."""

    model_config = _frozen()

    schedule_id: Annotated[UUID, Internal]
    client_entity_id: Annotated[UUID, Internal]
    client_name: Name
    client_note: OptName = None
    tax_year: Annotated[int, Internal]
    forms: Annotated[list[str], Internal]  # ["1040-ES", "IT-2105"]
    method: Annotated[EstimateMethod, Internal]
    method_note: Annotated[str | None, Tri] = None  # the code-written explanation of the figure
    annual_required: OptMoney = None
    jurisdiction_annual: Annotated[dict[str, Decimal], Tri] = Field(
        default_factory=dict[str, Decimal]
    )
    payment_method_labels: Annotated[list[PaymentMethodLabel], Internal]
    installment: Annotated[EstimateInstallmentOut | None, classified("internal")] = None
    stamp: Annotated[EngineStampOut | None, Internal] = None
    row_version: Annotated[int, Internal]
    allowed_actions: Annotated[list[EstimateAction], Internal]


class EstimateOut(EstimateRowOut):
    installments: Annotated[list[EstimateInstallmentOut], Internal]
    prior_year_tax: OptMoney = None
    prior_agi_over_threshold: Annotated[bool | None, Internal] = None
    projected_withholding: OptMoney = None


class EstimateCreateIn(BaseModel):
    """A schedule for one client, year and jurisdiction; code computes the figures."""

    model_config = _strict()

    client_entity_id: Annotated[UUID, Internal]
    basis_tax_return_id: Annotated[UUID | None, Internal] = None
    tax_year: Annotated[int, Field(ge=2000, le=2100), Internal]
    jurisdiction: Annotated[str, Field(min_length=2, max_length=12), Internal] = "US"
    form: Annotated[str, Field(min_length=2, max_length=16), Internal]
    method: Annotated[EstimateMethod, Internal]
    prior_year_tax: OptMoney = None
    prior_agi_over_threshold: Annotated[bool | None, Internal] = None
    projected_withholding: OptMoney = None
    payment_method_label: Annotated[PaymentMethodLabel | None, Internal] = None


class EstimatePatchIn(BaseModel):
    model_config = _strict()

    method: Annotated[EstimateMethod | None, Internal] = None
    prior_year_tax: OptMoney = None
    prior_year_tax_source: Annotated[LiabilitySource | None, Internal] = None
    prior_agi_over_threshold: Annotated[bool | None, Internal] = None
    projected_withholding: OptMoney = None
    payment_method_label: Annotated[PaymentMethodLabel | None, Internal] = None


class InstallmentPatchIn(BaseModel):
    model_config = _strict()

    scheduled_for: Annotated[date | None, Internal] = None
    paid_on: Annotated[date | None, Internal] = None
    evidence_version_id: Annotated[UUID | None, Internal] = None


class FollowUpDraftOut(BaseModel):
    """A follow-up drafted from the approved Reminder template; a person sends it through the
    existing `follow_up.send` (DEC-74)."""

    model_config = _frozen()

    follow_up_id: Annotated[UUID, Internal]
    request_item_id: Annotated[UUID, Internal]
    template_key: Annotated[str, Internal]


# --- payments union (DF-08) ---------------------------------------------------------------------


class PaymentRowOut(BaseModel):
    model_config = _frozen()

    source_kind: Annotated[PaymentSourceKind, Internal]
    source_id: Annotated[UUID, Internal]
    tax_return_id: Annotated[UUID | None, Internal] = None
    client_name: Name
    jurisdiction: Annotated[str, Internal]
    amount: Money
    paid_on: Annotated[date | None, Internal] = None
    confirmation_evidence_version_id: Annotated[UUID | None, Internal] = None


# --- gates --------------------------------------------------------------------------------------


async def _gate(ctx: AuthContext, action: str) -> None:
    if ctx.client:
        raise NotFound("filing_extension")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, TAX_EXTENSIONS_ESTIMATES):
        raise NotFound(TAX_EXTENSIONS_ESTIMATES.name)


async def _gate_on_return(ctx: AuthContext) -> None:
    """Actions held by a function on the return (`function_in`) can't be decided at the firm: no
    firm-level check meets them. The service authorises each return before it acts (DEC-2327)."""
    if ctx.client:
        raise NotFound("filing_extension")
    if not await flag_enabled(ctx.tenant, TAX_EXTENSIONS_ESTIMATES):
        raise NotFound(TAX_EXTENSIONS_ESTIMATES.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


def _check_out(c: object) -> SafeHarborCheckOut:
    from abacus.modules.tax.extensions import Check

    found = cast(Check, c)
    return SafeHarborCheckOut(
        tax_return_id=found.tax_return_id,
        jurisdiction=found.jurisdiction,
        projected_liability=found.projected_liability,
        safe_harbor_target=found.safe_harbor_target,
        paid_by_original_due=found.paid_by_original_due,
        meets_safe_harbor=found.meets_safe_harbor,
        stamp=EngineStampOut(
            engine_name=found.engine_name,
            engine_version=found.engine_version or "",
            inputs_hash=found.inputs_hash or "",
        )
        if found.engine_name
        else None,
    )


async def _rows_for(
    ctx: AuthContext, tax_year: int, return_ids: set[UUID] | None = None
) -> list[ExtensionRowOut]:
    from abacus.modules.tax import extensions

    found = await extensions.rows(ctx, tax_year)
    return [
        await _row_out(r) for r in found if return_ids is None or r.tax_return_id in return_ids
    ]


async def _row_out(found: object) -> ExtensionRowOut:
    """A TAX-13 a row from the stored lines and payments (T-03-T07, DEC-2243)."""
    from abacus.modules.identity.api import names_of
    from abacus.modules.tax.extensions import ReturnRow, money

    r = cast(ReturnRow, found)
    people = {p["proposed_by"] for p in r.payments} | {
        p["approved_by"] for p in r.payments if p["approved_by"]
    }
    names = await names_of(sorted(people, key=str)) if people else {}
    first = r.lines[0]
    return ExtensionRowOut(
        tax_return_id=r.tax_return_id,
        work_item_id=r.work_item_id,
        client_id=r.client_id,
        engagement_id=r.engagement_id,
        client_name=r.client_name,
        return_form=str(first["form"]),
        tax_year=r.tax_year,
        lines=[
            JurisdictionLineOut(
                extension_id=x["id"],
                jurisdiction=x["jurisdiction"],
                form=x["form"],
                status=cast(ExtensionStatus, x["status"]),
                filed_on=x["filed_on"],
                ack_received_at=x["ack_received_at"],
                reject_code=x["reject_code"],
            )
            for x in r.lines
        ],
        projected_liability=money(first.get("projected_liability")),
        projected_liability_source=first.get("projected_liability_source"),
        withholding_plus_estimates=money(first.get("withholding_plus_estimates")),
        safe_harbor_target=money(first.get("safe_harbor_target")),
        safe_harbor_pct=money(first.get("safe_harbor_pct")),
        payments=[
            ExtensionPaymentOut(
                id=p["id"],
                kind=cast(PaymentKind, p["kind"]),
                jurisdiction=p["jurisdiction"],
                amount=Decimal(str(p["amount"])),
                paid_on=p["paid_on"],
                proposed_by_name=names.get(p["proposed_by"], ""),
                approved_by_name=names.get(p["approved_by"]) if p["approved_by"] else None,
                approved_at=p["approved_at"],
                supersedes_id=p["supersedes_id"],
                confirmation_evidence_version_id=p["confirmation_evidence_version_id"],
            )
            for p in r.payments
        ],
        original_due_on=min(x["original_due_on"] for x in r.lines),
        extended_due_on=min(x["extended_due_on"] for x in r.lines),
        likely_to_extend=r.likely,
        likely_reasons=sorted(
            {
                c
                for x in r.lines
                for c in cast(list[Any], x["likely_reasons"] or [])  # Any: JSON from the database
            }  # Any: JSON from the database or the document
        ),
        likely_note=next((x["likely_note"] for x in r.lines if x["likely_note"]), None),
        confirmation=TaxConfirmationOut(
            confirmed=False,
            request_item_id=next(
                x["confirmation_request_item_id"]
                for x in r.lines
                if x["confirmation_request_item_id"]
            ),
        )
        if any(x["confirmation_request_item_id"] for x in r.lines)
        else None,
        row_version=max(x["row_version"] for x in r.lines),
        allowed_actions=[],
    )


schedules_router = AbacusRouter(prefix="/v1", tags=["tax"])
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_X = "/tax/extensions/{extension_id}"
_E = "/tax/estimates/{schedule_id}"
_Q = f"{_E}/installments/{{quarter}}"
Quarter = Annotated[int, Path(ge=1, le=4)]


# Exports come before `/{extension_id}` so the literal path wins.
@schedules_router.get(
    "/tax/extensions/export.xlsx",
    action="tax_schedule.export",
    response_model=bytes,
    errors=(501,),
)
async def extensions_export_route(
    ctx: Ctx,
    tax_year: Annotated[int, Query(ge=2000, le=2100)],
    segment: Annotated[Segment | None, Query()] = None,
) -> Response:
    """The visible rows of the current segment; fresh MFA; audited with the row count only."""
    await _gate(ctx, "tax_schedule.export")
    from abacus.modules.tax import schedule_exports

    return Response(
        await schedule_exports.extensions_workbook(ctx, tax_year, segment),
        media_type=_XLSX,
    )


@schedules_router.get(
    "/tax/estimates/export.xlsx", action="tax_schedule.export", response_model=bytes, errors=(501,)
)
async def estimates_export_route(
    ctx: Ctx,
    tax_year: Annotated[int, Query(ge=2000, le=2100)],
    quarter: Annotated[int | None, Query(ge=1, le=4)] = None,
) -> Response:
    await _gate(ctx, "tax_schedule.export")
    from abacus.modules.tax import schedule_exports

    return Response(
        await schedule_exports.estimates_workbook(ctx, tax_year, quarter),
        media_type=_XLSX,
    )


@schedules_router.get(
    "/tax/extensions",
    action="filing_extension.read",
    response_model=ListPage[ExtensionRowOut],
    errors=(501,),
)
async def extensions_route(
    ctx: Ctx,
    tax_year: Annotated[int, Query(ge=2000, le=2100)],
    segment: Annotated[Segment | None, Query()] = None,
    tile: Annotated[ExtensionTile | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> ListPage[ExtensionRowOut]:
    """Rows grouped per return; `counts` {extended, open, filed, likely, acks_pending} from the
    viewer's visible rows only (DEC-43)."""
    await _gate(ctx, "filing_extension.read")
    from abacus.modules.tax import extensions

    found = await extensions.rows(ctx, tax_year)
    # The tiles count every visible row; the segment and search only narrow what is listed.
    counts = extensions.counts(found)
    if segment:
        found = [r for r in found if extensions.segment_of(r) == segment]
    if q:
        found = [r for r in found if q.lower() in r.client_name.lower()]
    return ListPage[ExtensionRowOut](
        items=[await _row_out(r) for r in found],
        total=len(found),
        counts=counts,
    )


@schedules_router.post(
    "/tax/extensions:prepare",
    action="filing_extension.prepare",
    response_model=ExtensionBatchOut,
    errors=(409, 501),
)
async def extensions_prepare_route(
    body: ExtensionPrepareIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ExtensionBatchOut:
    """Extensions `prepared` with proposed payments and per-row safe-harbor checks; 409
    `gate_unmet` with the G1/G3 facts."""
    await _gate_on_return(ctx)
    from abacus.modules.tax import extensions

    checks = await extensions.prepare(
        ctx,
        body.return_ids,
        lines=[extensions.LineIn(**x.model_dump()) for x in body.lines],
        payments=[
            extensions.PaymentIn(p.return_id, p.jurisdiction, p.kind, p.amount)
            for p in body.payments
        ],
    )
    wanted = {c.tax_return_id for c in checks}
    years = await extensions.years_of(ctx, wanted)
    return ExtensionBatchOut(
        extensions=[row for year in sorted(years) for row in await _rows_for(ctx, year, wanted)],
        checks=[_check_out(c) for c in checks],
    )


@schedules_router.post(
    "/tax/extensions:submit-for-approval",
    action="filing_extension.prepare",
    response_model=ExtensionBatchOut,
    errors=(409, 501),
)
async def extensions_submit_route(
    body: ExtensionSubmitIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ExtensionBatchOut:
    """The proposer's path: registers the C13 payment-approval gate for the return's reviewers."""
    await _gate_on_return(ctx)
    from abacus.modules.tax import extensions

    year = await extensions.submit(ctx, body.extension_ids)
    return ExtensionBatchOut(extensions=await _rows_for(ctx, year), checks=[])


@schedules_router.post(
    "/tax/extensions:approve-and-request",
    action="filing_extension.approve_payment",
    response_model=ApproveAndRequestOut,
    errors=(409, 501),
)
async def extensions_approve_route(
    body: ApproveAndRequestIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ApproveAndRequestOut:
    """One unit of work: prepare any unprepared rows, approve the proposed payments as the
    caller (human only), then create and send the confirmation requests (the service also
    checks `filing_extension.confirmation_send`)."""
    await _gate_on_return(ctx)
    from abacus.modules.tax import extensions

    # One click from the sheet: prepare the rows it names, then approve them.
    extension_ids = list(body.extension_ids)
    if body.return_ids or body.payments:
        await extensions.prepare(
            ctx,
            body.return_ids or [p.return_id for p in body.payments],
            payments=[
                extensions.PaymentIn(p.return_id, p.jurisdiction, p.kind, p.amount)
                for p in body.payments
            ],
        )
        extension_ids += await extensions.extensions_of(
            ctx, {*body.return_ids, *(p.return_id for p in body.payments)}
        )
    # The service authorises `filing_extension.confirmation_send` on the caller (AGENT-001).
    approved, requested = await extensions.approve_and_request(
        ctx, extension_ids, send_confirmations=body.send_confirmations
    )
    return ApproveAndRequestOut(
        extensions=[],
        checks=[],
        approved_payment_ids=approved,
        confirmation_request_item_ids=requested,
    )


@schedules_router.get(
    _X, action="filing_extension.read", response_model=ExtensionOut, errors=(501,)
)
async def extension_route(extension_id: UUID, ctx: Ctx) -> ExtensionOut:
    await _gate(ctx, "filing_extension.read")
    from abacus.modules.tax import extensions

    return await _detail_out(ctx, await extensions.year_of(ctx, extension_id), extension_id)


async def _detail_out(ctx: AuthContext, tax_year: int, extension_id: UUID) -> ExtensionOut:
    from abacus.modules.identity.api import names_of
    from abacus.modules.tax import extensions

    for row in await extensions.rows(ctx, tax_year):
        line = next((x for x in row.lines if x["id"] == extension_id), None)
        if line is None:
            continue
        recorded = line["filed_recorded_by"]
        names = await names_of([recorded]) if recorded else {}
        return ExtensionOut(
            **(await _row_out(row)).model_dump(),
            due_rules_version_id=line["due_rules_version_id"],
            filed_form_evidence_version_id=line["filed_form_evidence_version_id"],
            filed_recorded_by_name=names.get(recorded) if recorded else None,
        )
    raise NotFound("filing_extension")


@schedules_router.patch(
    _X, action="filing_extension.mark_filed", response_model=ExtensionOut, errors=(409, 501)
)
async def extension_patch_route(
    extension_id: UUID, body: ExtensionPatchIn, ctx: Ctx, if_match: IfMatch
) -> ExtensionOut:
    """`filing_extension.flag_likely` for `likely_to_extend` alone, `mark_filed` otherwise."""
    await _gate_on_return(ctx)
    from abacus.modules.tax import extensions

    tax_year = await extensions.patch(
        ctx,
        extension_id,
        action=_patch_action(body),
        expected_version=if_match,
        filed_on=body.filed_on,
        form=body.form,
        filed_form_evidence_version_id=body.filed_form_evidence_version_id,
        likely_to_extend=body.likely_to_extend,
        reason=body.reason,
        note=body.note,
    )
    return await _detail_out(ctx, tax_year, extension_id)


def _patch_action(body: ExtensionPatchIn) -> str:
    likely_only = body.likely_to_extend is not None and body.filed_on is None
    return "filing_extension.flag_likely" if likely_only else "filing_extension.mark_filed"


@schedules_router.post(
    f"{_X}/confirmation-requests",
    action="filing_extension.confirmation_send",
    status_code=201,
    response_model=ConfirmationRequestOut,
    errors=(409, 501),
)
async def extension_confirmation_route(
    extension_id: UUID, body: ConfirmationRequestIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ConfirmationRequestOut:
    """One confirmation request, sent on the click, in the return's binder."""
    await _gate(ctx, "filing_extension.confirmation_send")
    from abacus.modules.tax import extensions

    item, _ = await extensions.request_confirmation(ctx, extension_id)
    return _confirmation_out(item)


def _confirmation_out(item: RequestItemView) -> ConfirmationRequestOut:
    return ConfirmationRequestOut(
        request_item_id=item.id,
        request_list_id=cast(UUID, item.request_list_id),
        sent_at=item.created_at,
        contact_name="",
    )


@schedules_router.get(
    "/tax/estimates",
    action="estimate_schedule.read",
    response_model=ListPage[EstimateRowOut],
    errors=(501,),
)
async def tax_estimates_route(
    ctx: Ctx,
    tax_year: Annotated[int, Query(ge=2000, le=2100)],
    quarter: Annotated[int | None, Query(ge=1, le=4)] = None,
    tile: Annotated[EstimateTile | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> ListPage[EstimateRowOut]:
    """Schedules by the quarter's installment; `counts` {due, paid, scheduled,
    confirmation_requested, not_required} from visible rows."""
    await _gate(ctx, "estimate_schedule.read")
    from abacus.modules.tax import estimates

    found = await estimates.schedules(ctx, tax_year)
    shown = await estimates.quarter_of(ctx, found, quarter)
    counts = estimates.tile_counts(found, shown)
    if q:
        found = [s for s in found if q.lower() in s.client_name.lower()]
    items = [_estimate_row(s, shown) for s in found]
    return ListPage[EstimateRowOut](items=items, total=len(items), counts=counts)


def _installment_out(q: object) -> EstimateInstallmentOut:
    from abacus.modules.tax.estimates import Installment

    found = cast(Installment, q)
    return EstimateInstallmentOut(
        quarter=found.quarter,
        due_on=found.due_on,
        amount=found.amount,
        status=cast(InstallmentStatus, found.status),
        scheduled_for=found.scheduled_for,
        paid_on=found.paid_on,
        confirmation=TaxConfirmationOut(
            confirmed=found.status == "paid",
            request_item_id=found.confirmation_request_item_id,
        )
        if found.confirmation_request_item_id
        else None,
    )


def _estimate_row(s: object, quarter: int) -> EstimateRowOut:
    from abacus.modules.tax.estimates import Schedule

    found = cast(Schedule, s)
    now = next((q for q in found.installments if q.quarter == quarter), None)
    return EstimateRowOut(
        schedule_id=found.id,
        client_entity_id=found.client_entity_id,
        client_name=found.client_name,
        tax_year=found.tax_year,
        forms=[found.form],
        method=cast(EstimateMethod, found.method),
        annual_required=found.annual_required,
        payment_method_labels=[cast(PaymentMethodLabel, found.payment_method_label)]
        if found.payment_method_label
        else [],
        installment=_installment_out(now) if now else None,
        stamp=EngineStampOut(
            engine_name="annual_required",
            engine_version=found.engine_version,
            inputs_hash=found.inputs_hash or "",
        )
        if found.engine_version
        else None,
        row_version=found.row_version,
        allowed_actions=[],
    )


def _estimate_out(s: object, quarter: int | None = None) -> EstimateOut:
    from abacus.modules.tax.estimates import Schedule

    found = cast(Schedule, s)
    return EstimateOut(
        **_estimate_row(found, quarter or 1).model_dump(),
        installments=[_installment_out(q) for q in found.installments],
        prior_year_tax=found.prior_year_tax,
        prior_agi_over_threshold=found.prior_agi_over_threshold,
        projected_withholding=found.projected_withholding,
    )


@schedules_router.post(
    "/tax/estimates",
    action="estimate_schedule.update",
    status_code=201,
    response_model=EstimateOut,
    errors=(409, 501),
)
async def estimate_create_route(
    body: EstimateCreateIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> EstimateOut:
    """A schedule's inputs; code computes the annual payment and the quarters."""
    await _gate(ctx, "estimate_schedule.update")
    from abacus.modules.tax import estimates

    made = await estimates.create(ctx, **body.model_dump())
    return _estimate_out(await estimates.one(ctx, made))


@schedules_router.patch(
    _E, action="estimate_schedule.update", response_model=EstimateOut, errors=(409, 501)
)
async def estimate_patch_route(
    schedule_id: UUID, body: EstimatePatchIn, ctx: Ctx, if_match: IfMatch
) -> EstimateOut:
    """Inputs, then code recomputes the annual payment and the installments."""
    await _gate(ctx, "estimate_schedule.update")
    from abacus.modules.tax import estimates

    return _estimate_out(
        await estimates.patch(
            ctx,
            schedule_id,
            expected_version=if_match,
            changes=body.model_dump(exclude_unset=True),
        )
    )


@schedules_router.patch(
    _Q, action="estimate_schedule.update", response_model=EstimateInstallmentOut, errors=(409, 501)
)
async def installment_patch_route(
    schedule_id: UUID, quarter: Quarter, body: InstallmentPatchIn, ctx: Ctx, if_match: IfMatch
) -> EstimateInstallmentOut:
    await _gate(ctx, "estimate_schedule.update")
    from abacus.modules.tax import estimates

    found = await estimates.patch_installment(
        ctx,
        schedule_id,
        quarter,
        expected_version=if_match,
        scheduled_for=body.scheduled_for,
        paid_on=body.paid_on,
    )
    return _installment_out(next(q for q in found.installments if q.quarter == quarter))


@schedules_router.post(
    f"{_Q}/confirmation-requests",
    action="estimate_schedule.confirmation_send",
    status_code=201,
    response_model=ConfirmationRequestOut,
    errors=(409, 501),
)
async def installment_confirmation_route(
    schedule_id: UUID,
    quarter: Quarter,
    body: ConfirmationRequestIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> ConfirmationRequestOut:
    """In the basis return's binder (a prospect has none: 409 `no_basis_return`)."""
    await _gate(ctx, "estimate_schedule.confirmation_send")
    from abacus.modules.tax import estimates

    item, _ = await estimates.request_confirmation(ctx, schedule_id, quarter)
    return _confirmation_out(item)


@schedules_router.post(
    f"{_Q}/follow-ups",
    action="follow_up.draft",
    status_code=201,
    response_model=FollowUpDraftOut,
    errors=(409, 501),
)
async def installment_follow_up_route(
    schedule_id: UUID, quarter: Quarter, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FollowUpDraftOut:
    """A draft from the approved Reminder template; a person sends it (`follow_up.send`)."""
    await _gate(ctx, "follow_up.draft")
    _not_yet()


@schedules_router.get(
    "/tax/payments",
    action="filing_extension.read",
    response_model=ListPage[PaymentRowOut],
    errors=(501,),
)
async def payments_route(
    ctx: Ctx,
    tax_year: Annotated[int, Query(ge=2000, le=2100)],
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> ListPage[PaymentRowOut]:
    """DF-08's union, read only: extension payments, PTET and paid installments."""
    await _gate(ctx, "filing_extension.read")
    from abacus.modules.tax import estimates, extensions

    items: list[PaymentRowOut] = [
        PaymentRowOut(
            source_kind=cast(PaymentSourceKind, p["kind"]),
            source_id=p["id"],
            tax_return_id=r.tax_return_id,
            client_name=r.client_name,
            jurisdiction=p["jurisdiction"],
            amount=Decimal(str(p["amount"])),
            paid_on=p["paid_on"],
            confirmation_evidence_version_id=p["confirmation_evidence_version_id"],
        )
        for r in await extensions.rows(ctx, tax_year)
        for p in r.payments
        if p["approved_by"]
    ]
    items += [
        PaymentRowOut(
            source_kind="estimate_installment",
            source_id=s.id,
            tax_return_id=s.basis_tax_return_id,
            client_name=s.client_name,
            jurisdiction=s.jurisdiction,
            amount=q.amount,
            paid_on=q.paid_on,
        )
        for s in await estimates.schedules(ctx, tax_year)
        for q in s.installments
        if q.status == "paid" and q.amount is not None
    ]
    return ListPage[PaymentRowOut](items=items, total=len(items))

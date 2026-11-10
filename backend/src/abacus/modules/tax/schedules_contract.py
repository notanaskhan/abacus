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
the return's engagement and function, and for a write holding `function_in` the firm check is the
service's alone, on the return); 404 without the `tax_returns` entitlement
(`tax.extensions_estimates` retired at T-03-T18, DEC-2605). Amounts and reject codes are tax
return information (`tri`); client and contact names are confidential.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import Depends, Header, Path, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.listing import ListPage, Position, decode_cursor, encode_cursor, query_hash
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    allowed_actions,
    authorise,
    current_context,
)
from abacus.modules.platform.api import entitlement

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
    # T-03-T16: a line's own version; the row's `row_version` is their max, so a second line's
    # If-Match would otherwise fail once the first has moved.
    row_version: Annotated[int, Internal] = 1


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
    # A state line's first payment names its form (IT-370); the federal form is the rules'.
    form: Annotated[str | None, Field(max_length=12), Internal] = None


class ExtensionPrepareIn(BaseModel):
    """409 `gate_unmet` with the G1/G3 facts for a return whose engagement is not accepted."""

    model_config = _strict()

    return_ids: Annotated[list[UUID], Field(min_length=1, max_length=200), Internal]
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
    gate_id: Annotated[UUID | None, Internal] = None  # C13's row, when T-08 / I-01 register it


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
    # T-03-T07 (DEC-2350): the preparer's figures, with their source (DEC-77, INV-2).
    projected_liability: OptMoney = None
    projected_liability_source: Annotated[LiabilitySource | None, Internal] = None
    projected_liability_ref: Annotated[dict[str, str] | None, Internal] = None
    withholding_plus_estimates: OptMoney = None


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
    # T-03-T07: an If-Match needs it, and the Paid cell opens the evidence in SHL-08 (US-5.3).
    row_version: Annotated[int, Internal] = 1
    paid_evidence_version_id: Annotated[UUID | None, Internal] = None


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
    # T-03-T18 (DEC-2605): the `tax_returns` entitlement replaces the retired flag.
    if await entitlement(ctx.tenant, "tax_returns") is None:
        raise NotFound("tax_returns")


async def _gate_on_return(ctx: AuthContext) -> None:
    """A write holding `function_in`: the firm can't answer it (the condition reads the caller's
    function on the work item, and at the firm it fails closed), so the service authorises on each
    return. Here only the client principal and the entitlement."""
    if ctx.client:
        raise NotFound("filing_extension")
    # T-03-T18 (DEC-2605): the `tax_returns` entitlement replaces the retired flag.
    if await entitlement(ctx.tenant, "tax_returns") is None:
        raise NotFound("tax_returns")


def _xlsx(data: bytes, name: str) -> Response:
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


_PAGE = 100


def _offset(ctx: AuthContext, cursor: str | None, resource: str, query: str) -> int:
    """A sealed position (kernel.listing): anything this list did not issue answers 422."""
    if not cursor:
        return 0
    found = decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=resource, query=query)
    return int(cast(int, found.key))


def _next(ctx: AuthContext, at: int, total: int, resource: str, query: str) -> str | None:
    if at + _PAGE >= total:
        return None
    return encode_cursor(
        Position(at + _PAGE, str(at + _PAGE)),
        tenant_id=ctx.tenant_id,
        resource=resource,
        query=query,
    )


def _stamp(version: object, inputs_hash: object) -> EngineStampOut | None:
    from abacus.modules.tax.compute.payments import ENGINE_NAME

    if not version or not inputs_hash:
        return None
    return EngineStampOut(
        engine_name=ENGINE_NAME, engine_version=str(version), inputs_hash=str(inputs_hash)
    )


_EXT_ACTIONS: tuple[ExtensionAction, ...] = (
    "filing_extension.prepare",
    "filing_extension.approve_payment",
    "filing_extension.mark_filed",
    "filing_extension.flag_likely",
    "filing_extension.confirmation_send",
    "tax_schedule.export",
)
_EST_ACTIONS: tuple[EstimateAction, ...] = (
    "estimate_schedule.update",
    "estimate_schedule.confirmation_send",
    "tax_schedule.export",
)


async def _confirmation(ctx: AuthContext, item_id: UUID | None) -> TaxConfirmationOut | None:
    if item_id is None:
        return None
    from abacus.modules.requests.api import request_item_state

    state = await request_item_state(ctx.tenant, item_id)
    if state is None:
        return None
    return TaxConfirmationOut(
        confirmed=state.confirmed,
        contact_name=state.contact_name,
        confirmed_on=state.confirmed_on,
        request_item_id=item_id,
        requested_on=state.requested_on,
    )


async def _row_out(ctx: AuthContext, found: object) -> ExtensionRowOut:
    """A TAX-13 a row from the stored lines and payments (T-03-T07, DEC-2243, DEC-2350)."""
    from abacus.kernel.clock import today
    from abacus.modules.identity.api import names_of
    from abacus.modules.tax import extensions
    from abacus.modules.tax.extensions import ReturnRow, money

    r = cast(ReturnRow, found)
    first = r.primary
    resource = await extensions.on_return(ctx, r.engagement_id, r.tax_return_id)
    allowed = await allowed_actions(ctx, resource, _EXT_ACTIONS)
    check = extensions.line_check(r.tax_return_id, first, r.payments, r.tax_year)
    extended_due = min(x["extended_due_on"] for x in r.lines)
    open_line = any(x["status"] == "not_filed" for x in r.lines)
    people = {p["proposed_by"] for p in r.payments} | {
        p["approved_by"] for p in r.payments if p["approved_by"]
    }
    names = await names_of(sorted(people, key=str)) if people else {}
    return ExtensionRowOut(
        tax_return_id=r.tax_return_id,
        work_item_id=r.work_item_id,
        client_id=r.client_id,
        engagement_id=r.engagement_id,
        client_name=r.client_name,
        return_form=r.return_form or str(first["form"]),
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
                row_version=x["row_version"],
            )
            for x in r.lines
        ],
        projected_liability=money(first.get("projected_liability")),
        projected_liability_source=first.get("projected_liability_source"),
        withholding_plus_estimates=money(first.get("withholding_plus_estimates")),
        safe_harbor_target=money(first.get("safe_harbor_target")),
        safe_harbor_pct=money(first.get("safe_harbor_pct")),
        paid_by_original_due=check.paid,
        meets_safe_harbor=check.meets,
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
        extended_due_on=extended_due,
        days_to_extended_due=(extended_due - await today(ctx.tenant)).days,
        confirmation=await _confirmation(ctx, first.get("confirmation_request_item_id")),
        prepare_blocked_reason=(
            await extensions.blocked_reason(ctx.tenant, r.engagement_id) if open_line else None
        ),
        stamp=_stamp(first.get("engine_version"), first.get("inputs_hash")),
        likely_to_extend=r.likely,
        likely_reasons=sorted(
            {
                c
                for x in r.lines
                for c in cast(list[Any], x["likely_reasons"] or [])  # Any: JSON from the database
            }  # Any: JSON from the database or the document
        ),
        likely_note=next((x["likely_note"] for x in r.lines if x["likely_note"]), None),
        row_version=max(x["row_version"] for x in r.lines),
        allowed_actions=[a for a in _EXT_ACTIONS if a in allowed],
    )


def _checks(found: object) -> list[SafeHarborCheckOut]:
    from abacus.modules.tax.compute.payments import ENGINE_NAME, ENGINE_VERSION
    from abacus.modules.tax.extensions import LineCheck

    return [
        SafeHarborCheckOut(
            tax_return_id=c.tax_return_id,
            jurisdiction=c.jurisdiction,
            projected_liability=c.projected_liability,
            safe_harbor_target=c.target,
            paid_by_original_due=c.paid,
            meets_safe_harbor=c.meets,
            stamp=(
                EngineStampOut(
                    engine_name=ENGINE_NAME,
                    engine_version=ENGINE_VERSION,
                    inputs_hash=c.inputs_hash,
                )
                if c.inputs_hash
                else None
            ),
        )
        for c in cast(list[LineCheck], found)
    ]


async def _rows_for_extensions(
    ctx: AuthContext, extension_ids: list[UUID]
) -> list[ExtensionRowOut]:
    from abacus.modules.tax import extensions

    seen: dict[UUID, ExtensionRowOut] = {}
    for extension_id in dict.fromkeys(extension_ids):
        row = await extensions.row_of(ctx, extension_id)
        if row.tax_return_id not in seen:
            seen[row.tax_return_id] = await _row_out(ctx, row)
    return list(seen.values())


def _proposed(payments: list[ProposedPaymentIn]) -> list[Any]:  # Any: the service's dataclass
    from abacus.modules.tax.extensions import ProposedPayment

    return [
        ProposedPayment(p.return_id, p.jurisdiction, p.kind, p.amount, p.form) for p in payments
    ]


def _installment_out(
    i: dict[str, Any],  # Any: a database row
    confirmation: TaxConfirmationOut | None,
) -> EstimateInstallmentOut:
    from abacus.modules.tax.estimates import money

    return EstimateInstallmentOut(
        quarter=i["quarter"],
        due_on=i["due_on"],
        amount=money(i["amount"]),
        status=cast(InstallmentStatus, i["status"]),
        scheduled_for=i["scheduled_for"],
        paid_on=i["paid_on"],
        confirmation=confirmation,
        row_version=i["row_version"],
        paid_evidence_version_id=i["paid_evidence_version_id"],
    )


async def _estimate_fields(ctx: AuthContext, found: object) -> dict[str, Any]:  # Any: model kwargs
    from abacus.modules.tax import estimates
    from abacus.modules.tax.estimates import ScheduleRow

    r = cast(ScheduleRow, found)
    s = r.schedule
    allowed = await allowed_actions(ctx, await estimates.resource_of(ctx, s), _EST_ACTIONS)
    label = s["payment_method_label"]
    return {
        "schedule_id": s["id"],
        "client_entity_id": s["client_entity_id"],
        "client_name": r.client_name,
        "tax_year": s["tax_year"],
        "forms": [s["form"]],
        "method": cast(EstimateMethod, s["method"]),
        "annual_required": estimates.money(s["annual_required"]),
        "payment_method_labels": [cast(PaymentMethodLabel, label)] if label else [],
        "stamp": _stamp(s["engine_version"], s["inputs_hash"]),
        "row_version": s["row_version"],
        "allowed_actions": [a for a in _EST_ACTIONS if a in allowed],
    }


async def _estimate_out(ctx: AuthContext, schedule_id: UUID) -> EstimateOut:
    from abacus.modules.tax import estimates

    r = await estimates.row_of(ctx, schedule_id)
    s = r.schedule
    return EstimateOut(
        **await _estimate_fields(ctx, r),
        installments=[
            _installment_out(i, await _confirmation(ctx, i["confirmation_request_item_id"]))
            for i in r.installments
        ],
        prior_year_tax=estimates.money(s["prior_year_tax"]),
        prior_agi_over_threshold=s["prior_agi_over_threshold"],
        projected_withholding=estimates.money(s["projected_withholding"]),
    )


def _sent_out(sent: object) -> ConfirmationRequestOut:
    from abacus.modules.tax.extensions import ConfirmationSent

    done = cast(ConfirmationSent, sent)
    return ConfirmationRequestOut(
        request_item_id=done.request_item_id,
        request_list_id=done.request_list_id,
        sent_at=cast(datetime, done.sent_at),
        contact_name=done.contact_name,
    )


schedules_router = AbacusRouter(prefix="/v1", tags=["tax"])
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

    return _xlsx(*await schedule_exports.extensions(ctx, tax_year, segment))


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

    return _xlsx(*await schedule_exports.estimates(ctx, tax_year, quarter))


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
    return_id: Annotated[list[UUID] | None, Query(max_length=200)] = None,
) -> ListPage[ExtensionRowOut]:
    """Rows grouped per return; `counts` {extended, open, filed, likely, acks_pending} from the
    viewer's visible rows only (DEC-43). `return_id` narrows to the returns the Extend sheet
    opened on (T-03-T16; TAX-01's bulk Extend…)."""
    await _gate(ctx, "filing_extension.read")
    from abacus.modules.tax import extensions

    visible = await extensions.rows(ctx, tax_year)
    found = [
        r
        for r in visible
        if extensions.in_segment(r, segment)
        and extensions.on_tile(r, tile)
        and (not q or q.lower() in r.client_name.lower())
        and (not return_id or r.tax_return_id in return_id)
    ]
    query = query_hash(tax_year=tax_year, segment=segment, tile=tile, q=q)
    at = _offset(ctx, cursor, "tax.extensions", query)
    page = found[at : at + _PAGE]
    return ListPage[ExtensionRowOut](
        items=[await _row_out(ctx, r) for r in page],
        total=len(found),
        counts=extensions.counts(visible),
        next_cursor=_next(ctx, at, len(found), "tax.extensions", query),
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
    `gate_unmet` with the G1/G3 facts. Authorised per return by the service."""
    await _gate_on_return(ctx)
    from abacus.modules.tax import extensions

    async def run() -> tuple[int, dict[str, object]]:
        ids, checks = await extensions.prepare(ctx, body.return_ids, _proposed(body.payments))
        out = ExtensionBatchOut(
            extensions=await _rows_for_extensions(ctx, ids), checks=_checks(checks)
        )
        return 200, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="filing_extension.prepare",
        key=idempotency_key,
        body=body.model_dump(mode="json"),
        run=run,
    )
    return ExtensionBatchOut.model_validate(stored.body)


@schedules_router.post(
    "/tax/extensions:submit-for-approval",
    action="filing_extension.prepare",
    response_model=ExtensionBatchOut,
    errors=(409, 501),
)
async def extensions_submit_route(
    body: ExtensionSubmitIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ExtensionBatchOut:
    """The proposer's path: the return's reviewers hear and approve (DEC-2350). Authorised per
    return by the service. `gate_id` stays empty until C13's row (T-03's cut list, T-08 / I-01)."""
    await _gate_on_return(ctx)
    from abacus.modules.tax import extensions

    async def run() -> tuple[int, dict[str, object]]:
        await extensions.submit_for_approval(ctx, body.extension_ids)
        out = ExtensionBatchOut(
            extensions=await _rows_for_extensions(ctx, body.extension_ids), checks=[]
        )
        return 200, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="filing_extension.submit_for_approval",
        key=idempotency_key,
        body=body.model_dump(mode="json"),
        run=run,
    )
    return ExtensionBatchOut.model_validate(stored.body)


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

    async def run() -> tuple[int, dict[str, object]]:
        # The service authorises the approval per return and the send on the caller (AGENT-001).
        approved, requested, checks = await extensions.approve_and_request(
            ctx,
            body.extension_ids,
            send_confirmations=body.send_confirmations,
            return_ids=body.return_ids,
            payments=_proposed(body.payments),
        )
        out = ApproveAndRequestOut(
            extensions=[],
            checks=_checks(checks),
            approved_payment_ids=approved,
            confirmation_request_item_ids=requested,
        )
        return 200, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="filing_extension.approve_and_request",
        key=idempotency_key,
        body=body.model_dump(mode="json"),
        run=run,
    )
    return ApproveAndRequestOut.model_validate(stored.body)


@schedules_router.get(
    _X, action="filing_extension.read", response_model=ExtensionOut, errors=(501,)
)
async def extension_route(extension_id: UUID, ctx: Ctx) -> ExtensionOut:
    await _gate(ctx, "filing_extension.read")
    return await _extension_out(ctx, extension_id)


@schedules_router.patch(
    _X, action="filing_extension.mark_filed", response_model=ExtensionOut, errors=(409, 501)
)
async def extension_patch_route(
    extension_id: UUID, body: ExtensionPatchIn, ctx: Ctx, if_match: IfMatch
) -> ExtensionOut:
    """`flag_likely` for `likely_to_extend` alone, `prepare` for the figures, else `mark_filed`.
    Authorised on the return by the service."""
    await _gate_on_return(ctx)
    from abacus.modules.tax import extensions

    await extensions.patch(
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
        projected_liability=body.projected_liability,
        projected_liability_source=body.projected_liability_source,
        projected_liability_ref=body.projected_liability_ref,
        withholding_plus_estimates=body.withholding_plus_estimates,
    )
    return await _extension_out(ctx, extension_id)


async def _extension_out(ctx: AuthContext, extension_id: UUID) -> ExtensionOut:
    from abacus.modules.identity.api import names_of
    from abacus.modules.tax import extensions

    row = await extensions.row_of(ctx, extension_id)
    line = next(x for x in row.lines if x["id"] == extension_id)
    out = await _row_out(ctx, row)
    filed_by = line["filed_recorded_by"]
    names = await names_of([filed_by]) if filed_by else {}
    return ExtensionOut(
        **out.model_dump(),
        due_rules_version_id=line["due_rules_version_id"],
        filed_form_evidence_version_id=line["filed_form_evidence_version_id"],
        filed_recorded_by_name=names.get(filed_by) if filed_by else None,
    )


def _patch_action(body: ExtensionPatchIn) -> str:
    if body.projected_liability is not None or body.withholding_plus_estimates is not None:
        return "filing_extension.prepare"
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

    async def run() -> tuple[int, dict[str, object]]:
        sent = await extensions.request_one(ctx, extension_id, body.contact_id)
        return 201, _sent_out(sent).model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="filing_extension.confirmation_request",
        key=idempotency_key,
        body={"id": str(extension_id), **body.model_dump(mode="json")},
        run=run,
    )
    return ConfirmationRequestOut.model_validate(stored.body)


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
    confirmation_requested, not_required} from visible rows; no `quarter`: the next one due."""
    await _gate(ctx, "estimate_schedule.read")
    from abacus.modules.tax import estimates

    visible = await estimates.rows(ctx, tax_year)
    chosen = quarter or await estimates.current_quarter(ctx.tenant, visible)
    found = [
        r
        for r in visible
        if estimates.on_tile(r, chosen, tile) and (not q or q.lower() in r.client_name.lower())
    ]
    query = query_hash(tax_year=tax_year, quarter=chosen, tile=tile, q=q)
    at = _offset(ctx, cursor, "tax.estimates", query)
    page = found[at : at + _PAGE]
    items: list[EstimateRowOut] = []
    for r in page:
        shown = r.installment(chosen)
        items.append(
            EstimateRowOut(
                **await _estimate_fields(ctx, r),
                installment=(
                    _installment_out(
                        shown, await _confirmation(ctx, shown["confirmation_request_item_id"])
                    )
                    if shown
                    else None
                ),
            )
        )
    return ListPage[EstimateRowOut](
        items=items,
        total=len(found),
        counts=estimates.counts(visible, chosen),
        next_cursor=_next(ctx, at, len(found), "tax.estimates", query),
    )


@schedules_router.patch(
    _E, action="estimate_schedule.update", response_model=EstimateOut, errors=(409, 501)
)
async def estimate_patch_route(
    schedule_id: UUID, body: EstimatePatchIn, ctx: Ctx, if_match: IfMatch
) -> EstimateOut:
    """Inputs, then code recomputes the annual payment and the installments."""
    await _gate(ctx, "estimate_schedule.update")
    from abacus.modules.tax import estimates

    await estimates.patch_schedule(
        ctx,
        schedule_id,
        expected_version=if_match,
        values=body.model_dump(exclude_unset=True),
    )
    return await _estimate_out(ctx, schedule_id)


@schedules_router.patch(
    _Q, action="estimate_schedule.update", response_model=EstimateInstallmentOut, errors=(409, 501)
)
async def installment_patch_route(
    schedule_id: UUID, quarter: Quarter, body: InstallmentPatchIn, ctx: Ctx, if_match: IfMatch
) -> EstimateInstallmentOut:
    await _gate(ctx, "estimate_schedule.update")
    from abacus.modules.tax import estimates

    await estimates.patch_installment(
        ctx,
        schedule_id,
        quarter,
        expected_version=if_match,
        scheduled_for=body.scheduled_for,
        paid_on=body.paid_on,
        evidence_version_id=body.evidence_version_id,
    )
    r = await estimates.row_of(ctx, schedule_id)
    found = r.installment(quarter)
    if found is None:
        raise NotFound("estimate_installment")
    return _installment_out(found, await _confirmation(ctx, found["confirmation_request_item_id"]))


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
    """In the basis return's binder, or a "{year} estimated payments" binder part (DEC-31)."""
    await _gate(ctx, "estimate_schedule.confirmation_send")
    from abacus.modules.tax import estimates

    async def run() -> tuple[int, dict[str, object]]:
        sent = await estimates.request_confirmation(ctx, schedule_id, quarter, body.contact_id)
        return 201, _sent_out(sent).model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="estimate_schedule.confirmation_request",
        key=idempotency_key,
        body={"id": str(schedule_id), "quarter": quarter, **body.model_dump(mode="json")},
        run=run,
    )
    return ConfirmationRequestOut.model_validate(stored.body)


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
    from abacus.modules.tax import estimates

    async def run() -> tuple[int, dict[str, object]]:
        follow_up_id, item_id, key = await estimates.draft_follow_up(ctx, schedule_id, quarter)
        out = FollowUpDraftOut(
            follow_up_id=follow_up_id, request_item_id=item_id, template_key=key
        )
        return 201, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="estimate_schedule.follow_up",
        key=idempotency_key,
        body={"id": str(schedule_id), "quarter": quarter},
        run=run,
    )
    return FollowUpDraftOut.model_validate(stored.body)


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
    from abacus.modules.tax import estimates

    found = await estimates.payments(ctx, tax_year)
    query = query_hash(tax_year=tax_year)
    at = _offset(ctx, cursor, "tax.payments", query)
    return ListPage[PaymentRowOut](
        items=[
            PaymentRowOut(
                source_kind=cast(PaymentSourceKind, p.source_kind),
                source_id=p.source_id,
                tax_return_id=p.tax_return_id,
                client_name=p.client_name,
                jurisdiction=p.jurisdiction,
                amount=p.amount,
                paid_on=p.paid_on,
                confirmation_evidence_version_id=p.confirmation_evidence_version_id,
            )
            for p in found[at : at + _PAGE]
        ],
        total=len(found),
        next_cursor=_next(ctx, at, len(found), "tax.payments", query),
    )

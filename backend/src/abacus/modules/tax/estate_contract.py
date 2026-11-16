"""EW-1 · estate workpapers, contract stub (T-07-T05; TASK-8019; SPEC-656; T-07 §4.3; DEC-5009).
Contract: `docs/contracts/estate-workpapers.md`.

TXT-04: the Form 706 inventory, deductions, the computation (an Accrued tie-out labelled
"Accrued tie-out (shadow)" until a CCH 706 import exists; DEC-77), the Form 709 gift history and
the derivation popovers. Every route declares one matrix action (T-07-T03) and answers 501 until
T-07-T22 lands; `tax.estate_workpapers` answers 404 while off. Return values are TRI. The
Illinois Form 700 card carries a status, never a figure (AC-13.3).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Path
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import TAX_ESTATE_WORKPAPERS
from abacus.kernel._statuses import (
    EstateComputationLabelStatus,
    EstateDeductionElectionStatus,
    EstateInventoryItemStatus,
    GiftForm709Status,
    TieOutTallyStatus,
)
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
Internal = classified("internal")
Confidential = classified("confidential")
Tri = classified("restricted", tri=True)
Money = Annotated[Decimal, Field(max_digits=20, decimal_places=2), Tri]
MaybeMoney = Annotated[Decimal | None, Field(max_digits=20, decimal_places=2), Tri]

Schedule = Literal["A", "B", "C", "D", "E", "F", "G", "H", "I"]
BasisRule = Literal["stepped_up", "ird_no_step_up", "non_probate_excluded"]
DeductionSchedule = Literal["J_funeral", "J_administration", "K", "L", "M", "O"]
Form709Status = GiftForm709Status  # the `gift_form_709` registry object (DEC-5018)
EstateSection = Literal["inventory", "deductions", "computation", "gifts"]
EstateAction = Literal["estate_workpaper.edit", "sign_off.l4", "request_item.send"]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True)


def _strict() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


async def _flag_on(ctx: AuthContext) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, TAX_ESTATE_WORKPAPERS):
        raise NotFound(TAX_ESTATE_WORKPAPERS.name)


class EstateDueChipOut(BaseModel):
    """From the practice due-date engine (AC-14.1): "Due Nov 2, 2026 · 4768 to May 3, 2027"."""

    model_config = _frozen()

    due_on: Annotated[date, Internal]
    extension_to: Annotated[date, Internal]
    extended: Annotated[bool, Internal]
    form_8971_due_on: Annotated[date | None, Internal]


class EstateTallyOut(BaseModel):
    model_config = _frozen()

    key: Annotated[str, Internal]
    label: Annotated[str, Internal]
    value: MaybeMoney
    state: Annotated[TieOutTallyStatus | None, Internal]


class EstateHeaderOut(BaseModel):
    model_config = _frozen()

    return_id: Annotated[UUID, Internal]
    client_entity_id: Annotated[UUID, Internal]
    decedent_name: Annotated[str, Confidential]
    date_of_death: Annotated[date, Confidential]
    due: Annotated[EstateDueChipOut, Internal]
    tallies: Annotated[list[EstateTallyOut], Internal]
    values_signed_by_initials: Annotated[str | None, Internal]  # L4 (c1)
    values_sign_off_stale: Annotated[bool, Internal]
    allowed_actions: Annotated[list[EstateAction], Internal]


class EstateAssetOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    schedule: Annotated[Schedule, Internal]
    description: Annotated[str, Confidential]
    dod_value: Money
    avd_value: MaybeMoney
    basis_to_1041: MaybeMoney  # None for IRD and non-probate life insurance, by rule
    basis_rule: Annotated[BasisRule, Internal]
    support_text: Annotated[str | None, Confidential]
    status: Annotated[EstateInventoryItemStatus, Internal]
    request_item_id: Annotated[UUID | None, Internal]
    citation_ids: Annotated[list[UUID], Internal]
    version: Annotated[int, Internal]


class EstateInventoryTotalsOut(BaseModel):
    model_config = _frozen()

    dod_value: Money
    avd_value: Money
    basis_to_1041: Money


class EstateInventoryOut(BaseModel):
    """TXT-04 a: six schedules foot 16,400,000 / 15,993,000 / 12,688,000 (AC-12.1)."""

    model_config = _frozen()

    header: Annotated[EstateHeaderOut, Internal]
    assets: Annotated[list[EstateAssetOut], Internal]
    totals: Annotated[EstateInventoryTotalsOut, Internal]


class EstateDeductionOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    schedule: Annotated[DeductionSchedule, Internal]
    description: Annotated[str, Confidential]
    amount: Money
    estimated: Annotated[bool, Internal]
    election: Annotated[EstateDeductionElectionStatus, Internal]
    citation_ids: Annotated[list[UUID], Internal]
    version: Annotated[int, Internal]


class EstateDeductionsOut(BaseModel):
    """TXT-04 b: 28,500 + 240,000 + 131,500 + 500,000 = 900,000 (AC-12.4)."""

    model_config = _frozen()

    header: Annotated[EstateHeaderOut, Internal]
    deductions: Annotated[list[EstateDeductionOut], Internal]
    total: Money


class EstateComputationLineOut(BaseModel):
    model_config = _frozen()

    key: Annotated[str, Internal]
    label: Annotated[str, Internal]
    value: MaybeMoney  # None renders "—" (net estate tax with DSUE)
    derivation_tile: Annotated[str | None, Internal]  # opens …/derivations/{tile} (f)


class EstateWithoutDsueOut(BaseModel):
    model_config = _frozen()

    credit: Money
    tax: Money


class EstateStateCardOut(BaseModel):
    """Illinois Form 700: a status and a review point, never a figure (AC-13.3; OQ-10)."""

    model_config = _frozen()

    jurisdiction: Annotated[str, Internal]  # the US state, "IL" (not a status; DEC-5018)
    required: Annotated[bool, Internal]
    status: Annotated[Literal["pending"], Internal]
    issue_id: Annotated[UUID | None, Internal]


class EstateComputationOut(BaseModel):
    """TXT-04 c (AC-13.1, AC-13.2)."""

    model_config = _frozen()

    header: Annotated[EstateHeaderOut, Internal]
    computation_id: Annotated[UUID, Internal]
    version_no: Annotated[int, Internal]
    engine_version: Annotated[str, Internal]
    inputs_hash: Annotated[str, Internal]
    parameter_set: Annotated[str, Internal]
    label: Annotated[EstateComputationLabelStatus, Internal]
    lines: Annotated[list[EstateComputationLineOut], Internal]
    without_dsue: Annotated[EstateWithoutDsueOut, Internal]
    state_card: Annotated[EstateStateCardOut, Internal]
    filing_required: Annotated[bool, Internal]
    filing_banner: Annotated[str | None, Tri]
    avd_available: Annotated[bool, Internal]


class GiftHistoryRowOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    year: Annotated[int, Internal]
    donee_name: Annotated[str, Confidential]
    asset: Annotated[str, Confidential]
    gift_amount: Money
    annual_exclusion: Money  # computed from the parameter file, never stored
    taxable_gift: Money  # computed
    form_709_status: Annotated[Form709Status, Internal]
    filed_on: Annotated[date | None, Internal]
    evidence_version_id: Annotated[UUID | None, Internal]
    version: Annotated[int, Internal]


class EstateGiftsOut(BaseModel):
    """TXT-04 d (AC-13.4)."""

    model_config = _frozen()

    header: Annotated[EstateHeaderOut, Internal]
    gifts: Annotated[list[GiftHistoryRowOut], Internal]
    adjusted_taxable_gifts: Money
    tie: Annotated[TieOutTallyStatus, Internal]


class EstateDerivationRowOut(BaseModel):
    model_config = _frozen()

    label: Annotated[str, Internal]
    value: MaybeMoney


class EstateDerivationOut(BaseModel):
    """TXT-04 f: rows, a note and the Provenance link to SHL-09 (AC-13.5)."""

    model_config = _frozen()

    tile: Annotated[str, Internal]
    rows: Annotated[list[EstateDerivationRowOut], Internal]
    note: Annotated[str | None, Tri]
    provenance_id: Annotated[UUID | None, Internal]


class EstateAssetIn(BaseModel):
    model_config = _strict()

    schedule: Annotated[Schedule, Internal]
    description: Annotated[str, Field(min_length=1, max_length=200), Confidential]
    dod_value: Money
    avd_value: MaybeMoney = None
    basis_rule: Annotated[BasisRule, Internal]
    support_text: Annotated[str | None, Field(max_length=300), Confidential] = None
    citation_ids: Annotated[list[UUID], Field(max_length=10), Internal] = []


class EstateAssetEditIn(BaseModel):
    """`valued` needs ≥ 1 citation and a human setter (service and DB)."""

    model_config = _strict()

    dod_value: Money
    avd_value: MaybeMoney = None
    status: Annotated[EstateInventoryItemStatus, Internal]
    support_text: Annotated[str | None, Field(max_length=300), Confidential] = None
    citation_ids: Annotated[list[UUID], Field(max_length=10), Internal] = []
    reason: Annotated[str, Field(min_length=1, max_length=1000), Confidential]
    expected_version: Annotated[int, Field(ge=1), Internal]


class EstateDeductionIn(BaseModel):
    model_config = _strict()

    schedule: Annotated[DeductionSchedule, Internal]
    description: Annotated[str, Field(min_length=1, max_length=200), Confidential]
    amount: Money
    estimated: Annotated[bool, Internal] = False
    election: Annotated[EstateDeductionElectionStatus, Internal] = (
        EstateDeductionElectionStatus.NONE
    )
    citation_ids: Annotated[list[UUID], Field(max_length=10), Internal] = []


class EstateDeductionEditIn(BaseModel):
    model_config = _strict()

    amount: Money
    estimated: Annotated[bool, Internal]
    election: Annotated[EstateDeductionElectionStatus, Internal]
    citation_ids: Annotated[list[UUID], Field(max_length=10), Internal] = []
    reason: Annotated[str, Field(min_length=1, max_length=1000), Confidential]
    expected_version: Annotated[int, Field(ge=1), Internal]


class GiftHistoryIn(BaseModel):
    model_config = _strict()

    year: Annotated[int, Field(ge=1976, le=2100), Internal]
    donee_name: Annotated[str, Field(min_length=1, max_length=200), Confidential]
    asset: Annotated[str, Field(min_length=1, max_length=200), Confidential]
    gift_amount: Money
    form_709_status: Annotated[Form709Status, Internal]
    filed_on: Annotated[date | None, Internal] = None
    evidence_version_id: Annotated[UUID | None, Internal] = None


class GiftHistoryEditIn(BaseModel):
    model_config = _strict()

    gift_amount: Money
    form_709_status: Annotated[Form709Status, Internal]
    filed_on: Annotated[date | None, Internal] = None
    evidence_version_id: Annotated[UUID | None, Internal] = None
    reason: Annotated[str, Field(min_length=1, max_length=1000), Confidential]
    expected_version: Annotated[int, Field(ge=1), Internal]


# --- routes (each 501 behind the flag, one action) -----------------------------------------------

estate_router = AbacusRouter(prefix="/v1/tax", tags=["estate workpapers"])
_R = "/returns/{return_id}/estate"


@estate_router.get(
    f"{_R}/inventory",
    action="estate_workpaper.read",
    response_model=EstateInventoryOut,
    errors=(),
)
async def estate_inventory_route(return_id: UUID, ctx: Ctx) -> EstateInventoryOut:
    await _flag_on(ctx)
    from abacus.modules.tax import (
        estate_service as es,
    )

    return await es.inventory(ctx, return_id)


@estate_router.get(
    f"{_R}/deductions",
    action="estate_workpaper.read",
    response_model=EstateDeductionsOut,
    errors=(),
)
async def estate_deductions_route(return_id: UUID, ctx: Ctx) -> EstateDeductionsOut:
    await _flag_on(ctx)
    from abacus.modules.tax import (
        estate_service as es,
    )

    return await es.deductions(ctx, return_id)


@estate_router.get(
    f"{_R}/computation",
    action="estate_workpaper.read",
    response_model=EstateComputationOut,
    errors=(),
)
async def estate_computation_route(return_id: UUID, ctx: Ctx) -> EstateComputationOut:
    await _flag_on(ctx)
    from abacus.modules.tax import (
        estate_service as es,
    )

    return await es.computation(ctx, return_id)


@estate_router.get(
    f"{_R}/gifts", action="estate_workpaper.read", response_model=EstateGiftsOut, errors=()
)
async def estate_gifts_route(return_id: UUID, ctx: Ctx) -> EstateGiftsOut:
    await _flag_on(ctx)
    from abacus.modules.tax import (
        estate_service as es,
    )

    return await es.gifts(ctx, return_id)


@estate_router.get(
    f"{_R}/derivations/{{tile}}",
    action="estate_workpaper.read",
    response_model=EstateDerivationOut,
    errors=(),
)
async def estate_derivation_route(
    return_id: UUID, tile: Annotated[str, Path(pattern=r"^[a-z_]{1,40}$")], ctx: Ctx
) -> EstateDerivationOut:
    await _flag_on(ctx)
    from abacus.modules.tax import (
        estate_service as es,
    )

    return await es.derivation(ctx, return_id, tile)


@estate_router.post(
    f"{_R}/assets",
    action="estate_workpaper.edit",
    response_model=EstateAssetOut,
    status_code=201,
    errors=(),
)
async def estate_asset_add_route(return_id: UUID, body: EstateAssetIn, ctx: Ctx) -> EstateAssetOut:
    await _flag_on(ctx)
    from abacus.modules.tax import (
        estate_service as es,
    )

    return await es.add_asset(ctx, return_id, body)


@estate_router.patch(
    "/estate-assets/{asset_id}",
    action="estate_workpaper.edit",
    response_model=EstateAssetOut,
    errors=(409,),
)
async def estate_asset_edit_route(
    asset_id: UUID, body: EstateAssetEditIn, ctx: Ctx
) -> EstateAssetOut:
    await _flag_on(ctx)
    from abacus.modules.tax import (
        estate_service as es,
    )

    return await es.edit_asset(ctx, asset_id, body)


@estate_router.post(
    f"{_R}/deductions",
    action="estate_workpaper.edit",
    response_model=EstateDeductionOut,
    status_code=201,
    errors=(),
)
async def estate_deduction_add_route(
    return_id: UUID, body: EstateDeductionIn, ctx: Ctx
) -> EstateDeductionOut:
    await _flag_on(ctx)
    from abacus.modules.tax import (
        estate_service as es,
    )

    return await es.add_deduction(ctx, return_id, body)


@estate_router.patch(
    "/estate-deductions/{deduction_id}",
    action="estate_workpaper.edit",
    response_model=EstateDeductionOut,
    errors=(409,),
)
async def estate_deduction_edit_route(
    deduction_id: UUID, body: EstateDeductionEditIn, ctx: Ctx
) -> EstateDeductionOut:
    await _flag_on(ctx)
    from abacus.modules.tax import (
        estate_service as es,
    )

    return await es.edit_deduction(ctx, deduction_id, body)


@estate_router.post(
    "/client-entities/{client_entity_id}/gift-history",
    action="estate_workpaper.edit",
    response_model=GiftHistoryRowOut,
    status_code=201,
    errors=(),
)
async def gift_history_add_route(
    client_entity_id: UUID, body: GiftHistoryIn, ctx: Ctx
) -> GiftHistoryRowOut:
    await _flag_on(ctx)
    from abacus.modules.tax import (
        estate_service as es,
    )

    return await es.add_gift(ctx, client_entity_id, body)


@estate_router.patch(
    "/gift-history-items/{gift_id}",
    action="estate_workpaper.edit",
    response_model=GiftHistoryRowOut,
    errors=(409,),
)
async def gift_history_edit_route(
    gift_id: UUID, body: GiftHistoryEditIn, ctx: Ctx
) -> GiftHistoryRowOut:
    await _flag_on(ctx)
    from abacus.modules.tax import (
        estate_service as es,
    )

    return await es.edit_gift(ctx, gift_id, body)

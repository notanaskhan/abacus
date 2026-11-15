"""FW-1 · fiduciary workpapers, contract stub (T-07-T05; TASK-8019; SPEC-656; T-07 §4.3; DEC-5009).
Contract: `docs/contracts/fiduciary-workpapers.md`.

TXT-01 (governing instrument and its interpretation), TXT-02 (the trust calculation) and TXT-03
(beneficiaries, K-1 (1041) packages and the 65-day election). Every route declares exactly one
matrix action (T-07-T03's rows) and answers 501 until its build row lands (T-07-T12, T14, T16,
T23); `tax.fiduciary_workpapers` (TXT-01, TXT-02) and `tax.fiduciary_k1_release` (TXT-03) answer
404 while off, and a client principal never reaches them.

Every model is classified; return values are TRI (§7216) and the EIN is sealed (last four only).
No route returns instrument text: a clause carries its label, heading, pages, regions and a text
hash, and the reader face re-reads the sealed layer through `evidence.api.text_layer`'s masked
projection (AC-15.3). Figures are code's (ADR-050): the browser never sums.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header, Path, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import TAX_FIDUCIARY_K1_RELEASE, TAX_FIDUCIARY_WORKPAPERS
from abacus.kernel._statuses import (
    InstrumentInterpretationStatus,
    InstrumentSegmentationStatus,
    K1PackageStatus,
    SixtyFiveDayElectionStatus,
    TieOutTallyStatus,
)
from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict, NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    current_context,
    mask_tins_for,
)
from abacus.modules.organisations.api import MaskedTinOut

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")
Confidential = classified("confidential")
Tri = classified("restricted", tri=True)  # tax return information (§7216)
Money = Annotated[Decimal, Field(max_digits=20, decimal_places=2), Tri]
# An optional figure keeps its tag: Optional[Money] would drop it at the field (ADR-031).
MaybeMoney = Annotated[Decimal | None, Field(max_digits=20, decimal_places=2), Tri]
Share = Annotated[Decimal, Field(max_digits=9, decimal_places=6), Tri]

DeterminationKey = Literal[
    "grantor_status",
    "trust_type",
    "fai_definition",
    "trustee_fees",
    "principal_invaded",
    "exemption",
    "election_65_day",
]
# AC-3.1: these keys rest on a clause; a save without one answers 422 `uncited_change`.
CLAUSE_GOVERNED: frozenset[str] = frozenset(
    {"grantor_status", "trust_type", "fai_definition", "trustee_fees", "principal_invaded"}
)
SetByKind = Literal["agent", "human"]
ReaderAvailability = Literal[
    "available", "agents_off", "consent_required", "capability_unavailable"
]
Scenario = Literal["base", "principal_invaded"]
FaiKind = Literal[
    "interest",
    "ordinary_dividends",
    "qualified_dividends",
    "tax_exempt_interest",
    "capital_gain",
    "rents",
    "other_income",
]
ExpenseKind = Literal["trustee_fee", "legal", "accounting", "tax_preparation", "other"]
ChargedTo = Literal["income", "principal"]
DistributionSource = Literal["income", "principal"]
DistributionForm = Literal["cash", "in_kind"]
ComputationView = Literal["tree", "character"]
ReleaseStepKey = Literal["final_approval", "form_8879_f"]
Delivery = Literal["portal_k1_recipient", "firm_1040_client"]
FiduciaryAction = Literal[
    "instrument.attach",
    "instrument.read_run",
    "instrument_determination.edit",
    "instrument_interpretation.reopen",
    "fai_line.edit",
    "trust_distribution.edit",
    "fiduciary_computation.recompute",
    "fiduciary_computation.export",
    "fiduciary_election.record",
    "sign_off.l1",
    "sign_off.l2",
    "sign_off.l3",
    "k1_package.release",
    "k1_package.resend",
]


# --- refusals (codes in docs/architecture/error-codes.yaml) --------------------------------------


class InterpretationNotApproved(DomainConflict):
    """AC-6.5: no approved instrument interpretation, so the trust calculation cannot compute."""

    code = "interpretation_not_approved"


class NotSegmented(DomainConflict):
    """AC-1.3: the instrument's clauses need checking before a reader run (manual marking)."""

    code = "not_segmented"


class InterpretationLocked(DomainConflict):
    """AC-4.2: approved determinations are locked; a manager reopens them with a reason."""

    code = "interpretation_locked"


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True)


def _strict() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


async def _flag_on(ctx: AuthContext, flag: Flag) -> None:
    """Off for the firm, the route is absent (404); a client principal never reaches it."""
    if ctx.client or not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)


def _stub(route: str) -> NotImplementedYet:
    return NotImplementedYet(route)


async def _instrument_read(ctx: AuthContext, return_id: UUID) -> InstrumentOut:
    """The TXT-01 read model (T-07-T12). Callers pass it through `mask_tins_for`."""
    from abacus.modules.tax.instruments import service

    return await service.instrument_read(ctx, return_id)


async def _instrument_attach(ctx: AuthContext, return_id: UUID, body: InstrumentAttachIn) -> None:
    """Record and segment the governing instrument (AC-1.2, AC-1.3; T-07-T12)."""
    from abacus.modules.tax.instruments import service

    await service.attach(ctx, return_id, body)


# --- TXT-01 models -------------------------------------------------------------------------------


class TrustProfileOut(BaseModel):
    model_config = _frozen()

    client_entity_id: Annotated[UUID, Internal]
    fiduciary_kind: Annotated[Literal["trust", "estate"], Internal]
    agreement_date: Annotated[date | None, Confidential]
    revocable: Annotated[bool, Confidential]
    irrevocable_since: Annotated[date | None, Confidential]
    settlor_name: Annotated[str | None, Confidential]
    settlor_died_year: Annotated[int | None, Confidential]
    residency_state: Annotated[str | None, Confidential]
    state_form: Annotated[str | None, Confidential]
    ein: Annotated[
        MaskedTinOut | None, Internal
    ]  # sealed TIN: kind and last four only (P-12; C-clients AC-22)


class GoverningInstrumentOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    evidence_version_id: Annotated[UUID, Internal]
    file_name: Annotated[str, Confidential]
    page_count: Annotated[int, Internal]
    supersedes_instrument_id: Annotated[UUID | None, Internal]
    attached_by_name: Annotated[str, Confidential]
    attached_at: Annotated[datetime, Internal]


class InstrumentSegmentationOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    status: Annotated[InstrumentSegmentationStatus, Internal]
    text_source: Annotated[Literal["text_layer", "ocr"], Internal]
    confidence: Annotated[Decimal, Field(max_digits=5, decimal_places=4), Internal]
    clause_count: Annotated[int, Internal]


class InstrumentInterpretationOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    status: Annotated[InstrumentInterpretationStatus, Internal]
    scenario: Annotated[Scenario, Internal]
    version_no: Annotated[int, Internal]
    content_hash: Annotated[str, Internal]
    read_run_id: Annotated[UUID | None, Internal]
    adopted_by_name: Annotated[str | None, Confidential]
    adopted_on: Annotated[date | None, Internal]
    approved_by_name: Annotated[str | None, Confidential]
    approved_on: Annotated[date | None, Internal]
    clause_citation_count: Annotated[int, Internal]
    # T-07-T15 (TXT-01 c): the principal-invaded scenario's banner and note, composed by code
    # from the engine's figures (T-07-T16 fills them); the browser never composes a figure.
    scenario_banner: Annotated[str | None, Tri] = None
    scenario_note: Annotated[str | None, Tri] = None


class InstrumentDeterminationOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    key: Annotated[DeterminationKey, Internal]
    value_code: Annotated[str, Tri]
    value_text: Annotated[str, Tri]
    rationale_ref: Annotated[str | None, Internal]  # an AgentText block id or a human note id
    citation_ids: Annotated[list[UUID], Internal]
    clause_labels: Annotated[list[str], Internal]  # display titles of the verified citations
    set_by_kind: Annotated[SetByKind, Internal]
    set_by_name: Annotated[str, Confidential]  # "Kevin Osei via Agent" for a run's proposal
    suggestion_id: Annotated[UUID | None, Internal]
    version: Annotated[int, Internal]
    clause_required: Annotated[bool, Internal]


class InstrumentCitedByOut(BaseModel):
    model_config = _frozen()

    target: Annotated[Literal["trust_calculation", "return_field"], Internal]
    target_ref: Annotated[str, Internal]  # TXT-02 `?row=` node key or a TAX-05 field key
    label: Annotated[str, Tri]
    clause_labels: Annotated[list[str], Internal]


class InstrumentReaderOut(BaseModel):
    model_config = _frozen()

    availability: Annotated[ReaderAvailability, Internal]
    consents_signed: Annotated[int, Internal]
    consents_required: Annotated[int, Internal]
    run_id: Annotated[UUID | None, Internal]
    progress_label: Annotated[str | None, Internal]


class InstrumentOut(BaseModel):
    """GET …/instrument: TXT-01's whole read (AC-1.1 to AC-5.2)."""

    model_config = _frozen()

    return_id: Annotated[UUID, Internal]
    profile: Annotated[TrustProfileOut, Internal]
    instrument: Annotated[GoverningInstrumentOut | None, Internal]
    segmentation: Annotated[InstrumentSegmentationOut | None, Internal]
    interpretation: Annotated[InstrumentInterpretationOut | None, Internal]
    determinations: Annotated[list[InstrumentDeterminationOut], Internal]
    cited_by: Annotated[list[InstrumentCitedByOut], Internal]
    reader: Annotated[InstrumentReaderOut, Internal]
    allowed_actions: Annotated[list[FiduciaryAction], Internal]


class ClauseRegionOut(BaseModel):
    model_config = _frozen()

    page: Annotated[int, Field(ge=1), Internal]
    bbox: Annotated[list[float], Field(min_length=4, max_length=4), Internal]


class InstrumentClauseOut(BaseModel):
    """A clause: label, heading, pages, regions and a hash. Never its text (AC-15.3)."""

    model_config = _frozen()

    id: Annotated[UUID, Internal]
    label: Annotated[str, Internal]
    heading: Annotated[str | None, Confidential]
    ordinal: Annotated[int, Internal]
    parent_clause_id: Annotated[UUID | None, Internal]
    page_from: Annotated[int, Internal]
    page_to: Annotated[int, Internal]
    regions: Annotated[list[ClauseRegionOut], Internal]
    text_sha256: Annotated[str, Internal]


class InstrumentClausesOut(BaseModel):
    model_config = _frozen()

    instrument_id: Annotated[UUID, Internal]
    segmentation_id: Annotated[UUID, Internal]
    status: Annotated[InstrumentSegmentationStatus, Internal]
    clauses: Annotated[list[InstrumentClauseOut], Internal]


class InstrumentAttachIn(BaseModel):
    model_config = _strict()

    evidence_version_id: Annotated[UUID, Internal]


class ClauseRegionIn(BaseModel):
    model_config = _strict()

    page: Annotated[int, Field(ge=1), Internal]
    bbox: Annotated[list[float], Field(min_length=4, max_length=4), Internal]


class ClauseMarkIn(BaseModel):
    """Manual clause marking when segmentation `needs_review` (label and regions picked in the
    reader)."""

    model_config = _strict()

    label: Annotated[str, Field(min_length=1, max_length=40), Internal]
    heading: Annotated[str | None, Field(max_length=200), Confidential] = None
    parent_clause_id: Annotated[UUID | None, Internal] = None
    regions: Annotated[list[ClauseRegionIn], Field(min_length=1, max_length=50), Internal]


class ReaderRunAcceptedOut(BaseModel):
    model_config = _frozen()

    run_id: Annotated[UUID, Internal]


class DeterminationRecordIn(BaseModel):
    """The agents-off path: a person records a determination (AC-1.6, AC-3.1)."""

    model_config = _strict()

    key: Annotated[DeterminationKey, Internal]
    value_code: Annotated[str, Field(min_length=1, max_length=60), Tri]
    value_text: Annotated[str, Field(min_length=1, max_length=300), Tri]
    citation_ids: Annotated[list[UUID], Field(max_length=10), Internal]
    note: Annotated[str | None, Field(max_length=1000), Confidential] = None


class DeterminationEditIn(BaseModel):
    """A human edit: a new version with a reason; a clause for governed keys (AC-3.1 to 3.3)."""

    model_config = _strict()

    value_code: Annotated[str, Field(min_length=1, max_length=60), Tri]
    value_text: Annotated[str, Field(min_length=1, max_length=300), Tri]
    citation_ids: Annotated[list[UUID], Field(max_length=10), Internal]
    reason: Annotated[str, Field(min_length=1, max_length=1000), Confidential]
    expected_version: Annotated[int, Field(ge=1), Internal]


class InterpretationReopenIn(BaseModel):
    model_config = _strict()

    reason: Annotated[str, Field(min_length=1, max_length=1000), Confidential]


# --- TXT-02 models -------------------------------------------------------------------------------


class FiduciaryTreeNodeOut(BaseModel):
    model_config = _frozen()

    key: Annotated[str, Internal]
    parent_key: Annotated[str | None, Internal]
    level: Annotated[int, Field(ge=0), Internal]
    label: Annotated[str, Internal]
    value: MaybeMoney
    box_label: Annotated[str | None, Internal]  # "Box 1 · 2a · 2b" on allocation rows
    clause_labels: Annotated[list[str], Internal]
    provenance_id: Annotated[UUID | None, Internal]  # SHL-09
    changed: Annotated[bool, Internal]  # against the last signed version (DEC-84)
    prior_value: MaybeMoney  # the struck value on a Changed row
    highlighted: Annotated[bool, Internal]


class FiduciaryCharacterAmountOut(BaseModel):
    model_config = _frozen()

    party: Annotated[str, Internal]  # a beneficiary contact id or "trust"
    amount: Money


class FiduciaryCharacterRowOut(BaseModel):
    model_config = _frozen()

    kind: Annotated[
        Literal["interest", "ordinary_dividends", "qualified_dividends", "total"], Internal
    ]
    total: Money
    by_party: Annotated[list[FiduciaryCharacterAmountOut], Internal]


class FiduciaryTallyOut(BaseModel):
    model_config = _frozen()

    key: Annotated[str, Internal]
    label: Annotated[str, Internal]
    value: MaybeMoney
    state: Annotated[TieOutTallyStatus | None, Internal]


class FiduciaryComputationOut(BaseModel):
    """GET …/fiduciary-computation: every figure, share and tie from the engine (AC-6.1 to 7.2)."""

    model_config = _frozen()

    return_id: Annotated[UUID, Internal]
    computation_id: Annotated[UUID, Internal]
    version_no: Annotated[int, Internal]
    view: Annotated[ComputationView, Internal]
    engine_name: Annotated[Literal["fiduciary"], Internal]
    engine_version: Annotated[str, Internal]
    inputs_hash: Annotated[str, Internal]
    parameter_set: Annotated[str, Internal]
    computed_at: Annotated[datetime, Internal]
    nodes: Annotated[list[FiduciaryTreeNodeOut], Internal]
    by_character: Annotated[list[FiduciaryCharacterRowOut], Internal]
    tallies: Annotated[list[FiduciaryTallyOut], Internal]
    notes: Annotated[list[str], Tri]  # engine-built sentences with code values
    banner: Annotated[str | None, Tri]  # "Theo's Dec 15 distribution edited · re-approval needed"
    signed_by_initials: Annotated[str | None, Internal]
    sign_off_stale: Annotated[bool, Internal]
    allowed_actions: Annotated[list[FiduciaryAction], Internal]


class FiduciaryRecomputeOut(BaseModel):
    model_config = _frozen()

    computation_id: Annotated[UUID, Internal]
    version_no: Annotated[int, Internal]
    created: Annotated[bool, Internal]  # False when `inputs_hash` matched the current version


class FaiLineOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    kind: Annotated[FaiKind, Internal]
    parent_line_id: Annotated[UUID | None, Internal]
    description: Annotated[str, Confidential]
    amount: Money
    citation_ids: Annotated[list[UUID], Internal]
    version: Annotated[int, Internal]


class FaiLinesOut(BaseModel):
    model_config = _frozen()

    lines: Annotated[list[FaiLineOut], Internal]


class FaiLineIn(BaseModel):
    model_config = _strict()

    kind: Annotated[FaiKind, Internal]
    parent_line_id: Annotated[UUID | None, Internal] = None
    description: Annotated[str, Field(min_length=1, max_length=200), Confidential]
    amount: Money
    citation_ids: Annotated[list[UUID], Field(min_length=1, max_length=10), Internal]


class FaiLineEditIn(BaseModel):
    model_config = _strict()

    amount: Money
    citation_ids: Annotated[list[UUID], Field(min_length=1, max_length=10), Internal]
    reason: Annotated[str, Field(min_length=1, max_length=1000), Confidential]
    expected_version: Annotated[int, Field(ge=1), Internal]


class FaiImportIn(BaseModel):
    model_config = _strict()

    evidence_version_id: Annotated[UUID, Internal]


class TrustExpenseOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    kind: Annotated[ExpenseKind, Internal]
    charged_to: Annotated[ChargedTo, Internal]
    amount: Money
    deductible: Annotated[bool, Internal]
    clause_id: Annotated[UUID | None, Internal]
    citation_ids: Annotated[list[UUID], Internal]
    version: Annotated[int, Internal]


class TrustExpensesOut(BaseModel):
    model_config = _frozen()

    expenses: Annotated[list[TrustExpenseOut], Internal]


class TrustExpenseIn(BaseModel):
    model_config = _strict()

    kind: Annotated[ExpenseKind, Internal]
    charged_to: Annotated[ChargedTo, Internal]
    amount: Money
    deductible: Annotated[bool, Internal]
    clause_id: Annotated[UUID | None, Internal] = None
    citation_ids: Annotated[list[UUID], Field(min_length=1, max_length=10), Internal]


class TrustExpenseEditIn(BaseModel):
    model_config = _strict()

    charged_to: Annotated[ChargedTo, Internal]
    amount: Money
    deductible: Annotated[bool, Internal]
    clause_id: Annotated[UUID | None, Internal] = None
    citation_ids: Annotated[list[UUID], Field(min_length=1, max_length=10), Internal]
    reason: Annotated[str, Field(min_length=1, max_length=1000), Confidential]
    expected_version: Annotated[int, Field(ge=1), Internal]


class TrustDistributionOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    beneficiary_contact_id: Annotated[UUID, Internal]
    beneficiary_name: Annotated[str, Confidential]
    paid_on: Annotated[date, Tri]
    amount: Money
    form: Annotated[DistributionForm, Internal]
    source: Annotated[DistributionSource, Internal]
    clause_id: Annotated[UUID | None, Internal]
    sixty_five_day_election_id: Annotated[UUID | None, Internal]
    version: Annotated[int, Internal]
    prior_amount: MaybeMoney  # the struck value against the last signed version


class TrustDistributionsOut(BaseModel):
    model_config = _frozen()

    distributions: Annotated[list[TrustDistributionOut], Internal]


class TrustDistributionIn(BaseModel):
    model_config = _strict()

    beneficiary_contact_id: Annotated[UUID, Internal]
    paid_on: Annotated[date, Tri]
    amount: Money
    form: Annotated[DistributionForm, Internal] = "cash"
    source: Annotated[DistributionSource, Internal] = "income"
    clause_id: Annotated[UUID | None, Internal] = None


class TrustDistributionEditIn(BaseModel):
    model_config = _strict()

    paid_on: Annotated[date, Tri]
    amount: Money
    source: Annotated[DistributionSource, Internal]
    clause_id: Annotated[UUID | None, Internal] = None
    reason: Annotated[str, Field(min_length=1, max_length=1000), Confidential]
    expected_version: Annotated[int, Field(ge=1), Internal]


# --- TXT-03 models -------------------------------------------------------------------------------


class BeneficiaryPaymentOut(BaseModel):
    model_config = _frozen()

    paid_on: Annotated[date, Tri]
    amount: Money


class BeneficiaryRowOut(BaseModel):
    model_config = _frozen()

    contact_id: Annotated[UUID, Internal]
    name: Annotated[str, Confidential]
    payments: Annotated[list[BeneficiaryPaymentOut], Internal]
    distributions: Money
    share: Share
    dni_allocated: Money
    box_1: Money  # interest
    box_2a: Money  # total ordinary dividends
    box_2b: Money  # qualified dividends
    delivery: Annotated[Delivery, Internal]
    package_id: Annotated[UUID | None, Internal]
    package_status: Annotated[K1PackageStatus | None, Internal]  # T-02's `k1_package` code


class BeneficiaryTotalsOut(BaseModel):
    model_config = _frozen()

    distributions: Money
    share: Share
    dni_allocated: Money
    box_1: Money
    box_2a: Money
    box_2b: Money
    income_distribution_deduction: Money  # Form 1041 line 18
    tie: Annotated[TieOutTallyStatus, Internal]


class SixtyFiveDayCardOut(BaseModel):
    model_config = _frozen()

    tax_year: Annotated[int, Internal]
    window_start: Annotated[date, Internal]
    window_end: Annotated[date, Internal]  # from the engine: the 65th day after year-end
    closed: Annotated[bool, Internal]
    distributions_in_window: MaybeMoney
    decision_owner_name: Annotated[str | None, Confidential]
    status: Annotated[SixtyFiveDayElectionStatus, Internal]
    amount: MaybeMoney
    paid_on: Annotated[date | None, Tri]
    next_tax_year: Annotated[int, Internal]
    next_window_end: Annotated[date, Internal]
    paragraph: Annotated[str | None, Tri]  # the firm's template with code values (DV-5)


class ReleaseStepOut(BaseModel):
    model_config = _frozen()

    key: Annotated[ReleaseStepKey, Internal]
    met: Annotated[bool, Internal]
    by_name: Annotated[str | None, Confidential]
    at: Annotated[datetime | None, Internal]
    superseded_by_change: Annotated[bool, Internal]  # DEC-85 drift relock (a3)


class BeneficiariesOut(BaseModel):
    """GET …/beneficiaries: TXT-03 (AC-9.1 to AC-11.3)."""

    model_config = _frozen()

    return_id: Annotated[UUID, Internal]
    computation_id: Annotated[UUID | None, Internal]  # None before a signed computation (e)
    rows: Annotated[list[BeneficiaryRowOut], Internal]
    totals: Annotated[BeneficiaryTotalsOut | None, Internal]
    election: Annotated[SixtyFiveDayCardOut, Internal]
    release_steps: Annotated[list[ReleaseStepOut], Internal]
    release_reason: Annotated[str | None, Internal]  # the accessible reason when disabled
    allowed_actions: Annotated[list[FiduciaryAction], Internal]


class SixtyFiveDayElectionIn(BaseModel):
    """The trustee's decision, recorded by a person (human-only; AC-11.2)."""

    model_config = _strict()

    status: Annotated[SixtyFiveDayElectionStatus, Internal]
    amount: MaybeMoney = None
    paid_on: Annotated[date | None, Tri] = None
    decision_owner_contact_id: Annotated[UUID, Internal]
    evidence_version_id: Annotated[UUID | None, Internal] = None


class SixtyFiveDayElectionOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    client_entity_id: Annotated[UUID, Internal]
    tax_year: Annotated[int, Internal]
    status: Annotated[SixtyFiveDayElectionStatus, Internal]
    amount: MaybeMoney
    paid_on: Annotated[date | None, Tri]
    window_end: Annotated[date, Internal]
    recorded_by_name: Annotated[str, Confidential]
    seq: Annotated[int, Internal]


class TrusteeQuestionIn(BaseModel):
    model_config = _strict()

    template_id: Annotated[UUID, Internal]
    options: Annotated[list[str], Field(max_length=6), Confidential] = []


class TrusteeQuestionDraftOut(BaseModel):
    """A C5 question draft for the trustee contact; sending is C5's `request_item.send` (Undo)."""

    model_config = _frozen()

    request_item_id: Annotated[UUID, Internal]
    recipient_contact_id: Annotated[UUID, Internal]
    body: Annotated[str, Confidential]  # the firm template with code values; never model text


# --- routes (each 501 behind its flag, one action) -----------------------------------------------

fiduciary_router = AbacusRouter(prefix="/v1/tax", tags=["fiduciary workpapers"])
_R = "/returns/{return_id}"


@fiduciary_router.get(
    f"{_R}/instrument", action="instrument.read", response_model=InstrumentOut, errors=()
)
async def instrument_route(return_id: UUID, ctx: Ctx) -> InstrumentOut:
    """TXT-01: profile, instrument, segmentation, determinations, cited-by, reader (T-07-T12).
    The profile's EIN is TIN-tagged: the read goes through the one central mask (AC9.4)."""
    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    return await mask_tins_for(ctx, await _instrument_read(ctx, return_id))


@fiduciary_router.post(
    f"{_R}/instrument", action="instrument.attach", response_model=InstrumentOut,
    status_code=201, errors=(409,),
)  # fmt: skip
async def instrument_attach_route(
    return_id: UUID, body: InstrumentAttachIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> InstrumentOut:
    """Attach a client-level file as the governing instrument (AC-1.2; T-07-T12); answers the
    read, masked for an offshore reader (AC9.4)."""
    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    await _instrument_attach(ctx, return_id, body)
    return await mask_tins_for(ctx, await _instrument_read(ctx, return_id))


@fiduciary_router.get(
    "/governing-instruments/{instrument_id}/clauses", action="instrument.read",
    response_model=InstrumentClausesOut, errors=(),
)  # fmt: skip
async def instrument_clauses_route(instrument_id: UUID, ctx: Ctx) -> InstrumentClausesOut:
    """The clause tree: labels, headings, pages, regions, hashes; no text (AC-1.3, AC-15.3)."""
    from abacus.modules.tax.instruments import service

    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    return await service.clauses(ctx, instrument_id)


@fiduciary_router.post(
    "/governing-instruments/{instrument_id}/clauses", action="instrument.attach",
    response_model=InstrumentClauseOut, status_code=201, errors=(409,),
)  # fmt: skip
async def instrument_clause_mark_route(
    instrument_id: UUID, body: ClauseMarkIn, ctx: Ctx
) -> InstrumentClauseOut:
    """Manual clause marking while segmentation `needs_review` (AC-1.3; T-07-T12)."""
    from abacus.modules.tax.instruments import service

    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    return await service.mark_clause(ctx, instrument_id, body)


@fiduciary_router.post(
    f"{_R}/instrument/read", action="instrument.read_run", response_model=ReaderRunAcceptedOut,
    status_code=202, errors=(409,),
)  # fmt: skip
async def instrument_read_route(
    return_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ReaderRunAcceptedOut:
    """Start `InstrumentReaderWorkflow`: 409 `consent_required`, `capability_unavailable`,
    `not_segmented` before any model call (AC-1.4, AC-1.5; T-07-T13)."""
    from abacus.modules.tax.instrument_reader import start_read

    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    return ReaderRunAcceptedOut(run_id=await start_read(ctx, return_id))


@fiduciary_router.post(
    f"{_R}/instrument/determinations", action="instrument_determination.edit",
    response_model=InstrumentDeterminationOut, status_code=201, errors=(409,),
)  # fmt: skip
async def determination_record_route(
    return_id: UUID, body: DeterminationRecordIn, ctx: Ctx
) -> InstrumentDeterminationOut:
    """The agents-off path (AC-1.6): 422 `uncited_change` for a governed key without a clause."""
    from abacus.modules.tax.instruments import service

    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    return await service.record_determination(ctx, return_id, body)


@fiduciary_router.patch(
    "/instrument-determinations/{determination_id}", action="instrument_determination.edit",
    response_model=InstrumentDeterminationOut, errors=(409,),
)  # fmt: skip
async def determination_edit_route(
    determination_id: UUID, body: DeterminationEditIn, ctx: Ctx
) -> InstrumentDeterminationOut:
    """A new version: 422 `uncited_change`; 409 `version_conflict`, `interpretation_locked`."""
    from abacus.modules.tax.instruments import service

    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    return await service.edit_determination(ctx, determination_id, body)


@fiduciary_router.post(
    "/instrument-interpretations/{interpretation_id}/reopen",
    action="instrument_interpretation.reopen", response_model=InstrumentInterpretationOut,
    errors=(409,),
)  # fmt: skip
async def interpretation_reopen_route(
    interpretation_id: UUID, body: InterpretationReopenIn, ctx: Ctx
) -> InstrumentInterpretationOut:
    """Unlock after L3; stales the TXT-02 sign-off (AC-5.2; T-07-T12)."""
    from abacus.modules.tax.instruments import service

    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    return await service.reopen(ctx, interpretation_id, body)


@fiduciary_router.get(
    f"{_R}/instrument/cited-by", action="instrument.read",
    response_model=list[InstrumentCitedByOut], errors=(),
)  # fmt: skip
async def instrument_cited_by_route(return_id: UUID, ctx: Ctx) -> list[InstrumentCitedByOut]:
    """Computation rows and return fields citing each clause (AC-2.4)."""
    from abacus.modules.tax.instruments import service

    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    return (await service.instrument_read(ctx, return_id)).cited_by


@fiduciary_router.get(
    f"{_R}/fiduciary-computation", action="fiduciary_computation.read",
    response_model=FiduciaryComputationOut, errors=(409, 501),
)  # fmt: skip
async def fiduciary_computation_route(
    return_id: UUID,
    ctx: Ctx,
    view: Annotated[ComputationView, Query()] = "tree",
    version: Annotated[int | None, Query(ge=1)] = None,
) -> FiduciaryComputationOut:
    """TXT-02's read model; 409 `interpretation_not_approved` before an approved reading (f1)."""
    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    raise _stub("fiduciary_computation")


@fiduciary_router.post(
    f"{_R}/fiduciary-computation/recompute", action="fiduciary_computation.recompute",
    response_model=FiduciaryRecomputeOut, errors=(409, 501),
)  # fmt: skip
async def fiduciary_recompute_route(
    return_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FiduciaryRecomputeOut:
    """Idempotent by `inputs_hash` (AC-6.4); 409 `interpretation_not_approved` (T-07-T16)."""
    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    raise _stub("fiduciary_recompute")


@fiduciary_router.get(
    f"{_R}/fiduciary-computation.xlsx", action="fiduciary_computation.export",
    response_model=bytes, errors=(501,),
)  # fmt: skip
async def fiduciary_export_route(
    return_id: UUID, ctx: Ctx, version: Annotated[int | None, Query(ge=1)] = None
) -> Response:
    """The deterministic XLSX of a version, byte-identical per version (AC-8.1; T-07-T16)."""
    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    raise _stub("fiduciary_export")


@fiduciary_router.get(
    f"{_R}/fai-lines", action="fiduciary_computation.read", response_model=FaiLinesOut,
    errors=(501,),
)  # fmt: skip
async def fai_lines_route(return_id: UUID, ctx: Ctx) -> FaiLinesOut:
    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    raise _stub("fai_lines")


@fiduciary_router.post(
    f"{_R}/fai-lines", action="fai_line.edit", response_model=FaiLineOut, status_code=201,
    errors=(501,),
)  # fmt: skip
async def fai_line_add_route(return_id: UUID, body: FaiLineIn, ctx: Ctx) -> FaiLineOut:
    """A cited FAI line; a qualified line never exceeds its ordinary parent (service-enforced)."""
    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    raise _stub("fai_line_add")


@fiduciary_router.post(
    f"{_R}/fai-lines/import-from-statement", action="fai_line.edit", response_model=FaiLinesOut,
    errors=(409, 501),
)  # fmt: skip
async def fai_lines_import_route(return_id: UUID, body: FaiImportIn, ctx: Ctx) -> FaiLinesOut:
    """Lines from P-11's extracted tables on the custodial statement (code, no model)."""
    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    raise _stub("fai_lines_import")


@fiduciary_router.patch(
    "/fai-lines/{line_id}", action="fai_line.edit", response_model=FaiLineOut,
    errors=(409, 501),
)  # fmt: skip
async def fai_line_edit_route(line_id: UUID, body: FaiLineEditIn, ctx: Ctx) -> FaiLineOut:
    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    raise _stub("fai_line_edit")


@fiduciary_router.get(
    f"{_R}/trust-expenses", action="fiduciary_computation.read", response_model=TrustExpensesOut,
    errors=(501,),
)  # fmt: skip
async def trust_expenses_route(return_id: UUID, ctx: Ctx) -> TrustExpensesOut:
    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    raise _stub("trust_expenses")


@fiduciary_router.post(
    f"{_R}/trust-expenses", action="fai_line.edit", response_model=TrustExpenseOut,
    status_code=201, errors=(501,),
)  # fmt: skip
async def trust_expense_add_route(
    return_id: UUID, body: TrustExpenseIn, ctx: Ctx
) -> TrustExpenseOut:
    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    raise _stub("trust_expense_add")


@fiduciary_router.patch(
    "/trust-expenses/{expense_id}", action="fai_line.edit", response_model=TrustExpenseOut,
    errors=(409, 501),
)  # fmt: skip
async def trust_expense_edit_route(
    expense_id: UUID, body: TrustExpenseEditIn, ctx: Ctx
) -> TrustExpenseOut:
    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    raise _stub("trust_expense_edit")


@fiduciary_router.get(
    f"{_R}/trust-distributions", action="fiduciary_computation.read",
    response_model=TrustDistributionsOut, errors=(501,),
)  # fmt: skip
async def trust_distributions_route(return_id: UUID, ctx: Ctx) -> TrustDistributionsOut:
    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    raise _stub("trust_distributions")


@fiduciary_router.post(
    f"{_R}/trust-distributions", action="trust_distribution.edit",
    response_model=TrustDistributionOut, status_code=201, errors=(501,),
)  # fmt: skip
async def trust_distribution_add_route(
    return_id: UUID, body: TrustDistributionIn, ctx: Ctx
) -> TrustDistributionOut:
    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    raise _stub("trust_distribution_add")


@fiduciary_router.patch(
    "/trust-distributions/{distribution_id}", action="trust_distribution.edit",
    response_model=TrustDistributionOut, errors=(409, 501),
)  # fmt: skip
async def trust_distribution_edit_route(
    distribution_id: UUID, body: TrustDistributionEditIn, ctx: Ctx
) -> TrustDistributionOut:
    """A new version with a reason; the L2 sign-off goes stale (AC-7.1; T-07-T16)."""
    await _flag_on(ctx, TAX_FIDUCIARY_WORKPAPERS)
    raise _stub("trust_distribution_edit")


@fiduciary_router.get(
    f"{_R}/beneficiaries", action="beneficiary_allocation.read", response_model=BeneficiariesOut,
    errors=(501,),
)  # fmt: skip
async def beneficiaries_route(return_id: UUID, ctx: Ctx) -> BeneficiariesOut:
    """TXT-03: allocation, tie-out, delivery, election card, release steps (T-07-T23)."""
    await _flag_on(ctx, TAX_FIDUCIARY_K1_RELEASE)
    raise _stub("beneficiaries")


@fiduciary_router.put(
    "/client-entities/{client_entity_id}/sixty-five-day-elections/{tax_year}",
    action="fiduciary_election.record", response_model=SixtyFiveDayElectionOut,
    errors=(409, 501),
)  # fmt: skip
async def sixty_five_day_election_route(
    client_entity_id: UUID,
    tax_year: Annotated[int, Path(ge=2000, le=2100)],
    body: SixtyFiveDayElectionIn,
    ctx: Ctx,
) -> SixtyFiveDayElectionOut:
    """Inserts a new row (latest wins); human-only by DB CHECK too (AC-11.2; T-07-T23)."""
    await _flag_on(ctx, TAX_FIDUCIARY_K1_RELEASE)
    raise _stub("sixty_five_day_election")


@fiduciary_router.post(
    f"{_R}/trustee-questions", action="fiduciary_election.read",
    response_model=TrusteeQuestionDraftOut, status_code=201, errors=(409, 501),
)  # fmt: skip
async def trustee_question_route(
    return_id: UUID, body: TrusteeQuestionIn, ctx: Ctx
) -> TrusteeQuestionDraftOut:
    """A C5 question draft from the firm template; a person sends it (AC-11.3; T-07-T23)."""
    await _flag_on(ctx, TAX_FIDUCIARY_K1_RELEASE)
    raise _stub("trustee_question")

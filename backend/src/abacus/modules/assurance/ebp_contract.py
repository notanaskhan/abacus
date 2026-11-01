"""The A-05 EBP workpapers contract stub, ebp-workpapers v1 (A-05-T04; TASK-2810; DEC-1859).
Contract: `docs/contracts/ebp-workpapers.md`; screens EBP-01 to EBP-09 and AUD-27; SPEC-640.

Every route is under `/v1/audits/{work_item_id}` and has one matrix action. Each answers, in
order: a non-person or a client principal 403 or 404 (INV-4: no portal scope admits an EBP table);
the action on the work item's engagement (walls 404, independence 403); 404 with its flag off
(`ebp.modules`, `ebp.form5500_tieout` for EBP-07, `assurance.estimates_rp` for AUD-27). Then a
read answers the Northwind Robotics 401(k) Plan PY2025 seed's figures (the examples below, so the
generated client and fixture mode agree) and a write is 501 `not_implemented` until its task.

Classification: a participant's SSN and date of birth are Restricted and never leave the server
unmasked (`ssn` as `MaskedTinOut`, `dob_masked`, DEC-1858); compensation and balances are
Confidential.
Every figure is code's (ADR-050). Verify, adopt, record a correction, evaluate the certification
and conclude are a person's acts; no agent or system principal holds them (INV-1).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Header, Path, Query
from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict

from abacus.kernel._flags import ASSURANCE_ESTIMATES_RP, EBP_FORM5500_TIEOUT, EBP_MODULES
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.engagements.api import assurance_item, get_ref
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Forbidden,
    allowed_actions,
    authorise,
    current_context,
    mask_tins_for,
)
from abacus.modules.organisations.api import MaskedTinOut, entity_name

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Money = Annotated[Decimal, classified("confidential")]
MaybeMoney = Annotated[Decimal | None, classified("confidential")]
Label = Annotated[str, Field(max_length=300), classified("internal")]
Note = Annotated[str, Field(min_length=1, max_length=2000), classified("confidential")]
MaybeNote = Annotated[str | None, Field(min_length=1, max_length=2000), classified("confidential")]
EbpAction = Literal[
    "ebp_plan.edit",
    "ebp_provider.manage",
    "ebp_provider.invite",
    "ebp_provider.request",
    "ebp_import.create",
    "ebp_correction.record",
    "ebp_schedule.draft",
    "ebp_certification.evaluate",
    "ebp_form5500.key",
    "ebp_schedule.render",
    "ebp_form5500.send_note",
    "ebp_form5500.remind",
    "test.create",
    "test.mark",
    "field.sign_off",
    "estimate.evaluate",
    "estimate.request_conclusion",
    "related_party.manage",
    "related_party.screen_out",
    "party_in_interest.manage",
    "pii.reveal",
]
Actions = Annotated[list[EbpAction], classified("internal")]
# The human-only acts (INV-1), named in the contract doc.
HUMAN_ONLY: tuple[str, ...] = (
    "verify (field.sign_off on an ebp_provision)",
    "adopt (ledger_snapshot.create_from_document; test.mark)",
    "record correction (ebp_correction.record)",
    "evaluate certification (ebp_certification.evaluate)",
    "conclude (decision.decide on an estimate or finding; estimate.request_conclusion raises it)",
)


def _ex(body: JsonDict) -> ConfigDict:
    return ConfigDict(frozen=True, json_schema_extra={"examples": [body]})


class FigureRowOut(BaseModel):
    """A labelled figure as a statement row: an amount with no "$", from code."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Field(pattern=r"^[a-z0-9_.]{1,64}$"), classified("internal")]
    label: Label
    amount: MaybeMoney
    # A Schedule H line's tie-out (status vocabulary `ebp_form5500_line`); a statement row: none.
    status: Annotated[
        Literal["tie", "reconciling_item", "inconsistent"] | None, classified("internal")
    ] = None
    note: Annotated[str | None, Field(max_length=500), classified("confidential")] = None


# --- EBP-01 plan profile and providers ----------------------------------------------------------

_PLAN: JsonDict = {
    "plan_name": "Northwind Robotics 401(k) Plan",
    "plan_number": "001",
    "sponsor_ein": {"kind": "ein", "presence": "on_file", "last4": "6620"},
    "plan_year_start": "2025-01-01",
    "plan_year_end": "2025-12-31",
    "plan_type": "401k",
    "safe_harbor": "qaca",
    "recordkeeper_id": "58217",
    "participants_boy": 286,
    "participants_eoy": 301,
    "filer_status": "large_plan",
    "form5500_due_on": "2026-10-15",
    "audit_kind": "103a3c",
    "version": 1,
    "allowed_actions": ["ebp_plan.edit"],
}


class PlanOut(BaseModel):
    """EBP-01's plan facts; the PN lives on `client_entities.plan_number` (A-05 §2.1)."""

    model_config = _ex(_PLAN)

    plan_name: Label
    plan_number: Annotated[str | None, Field(pattern=r"^[0-9]{3}$"), classified("internal")]
    # The platform's masked shape (kind and last four; Restricted, P-12): never a plain EIN.
    # None until the sponsor's EIN is captured (A-05-T18; DEC-1955).
    sponsor_ein: Annotated[MaskedTinOut | None, classified("restricted", pii_kind="tin")] = None
    plan_year_start: Annotated[date, classified("internal")]
    plan_year_end: Annotated[date, classified("internal")]
    plan_type: Annotated[Literal["401k"], classified("internal")]
    safe_harbor: Annotated[Literal["none", "qaca", "basic", "nonelective"], classified("internal")]
    # The recordkeeper's ID is never a plan number (EBP-01 b).
    recordkeeper_id: Annotated[str | None, Field(max_length=20), classified("internal")]
    participants_boy: Annotated[int, Field(ge=0), classified("confidential")]
    participants_eoy: Annotated[int, Field(ge=0), classified("confidential")]
    filer_status: Annotated[Literal["large_plan", "small_plan"], classified("internal")]
    form5500_due_on: Annotated[date, classified("internal")]
    # "§103(a)(3)(C) audit", never "limited scope" (DEC-1857).
    audit_kind: Annotated[Literal["103a3c", "full_scope"], classified("internal")]
    # The row's version: the next edit's `seen_version` (409 `version_conflict` otherwise).
    version: Annotated[int, Field(ge=1), classified("internal")]
    allowed_actions: Actions


class PlanEditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: Annotated[dict[str, str], classified("confidential")]
    citation_note: Note
    seen_version: Annotated[int, Field(ge=1), classified("internal")]


ProviderStatus = Literal["received", "waiting_on_inputs", "correction_requested"]

_PROVIDER: JsonDict = {
    "id": "00000000-0000-4000-8000-000000000501",
    "name": "Example Recordkeeper LLC",
    "role": "recordkeeper",
    "ein": {"kind": "ein", "presence": "on_file", "last4": "4420"},
    "status": "correction_requested",
    "soc_report": "SOC 1 Type 2, Jan 1 to Sep 30, 2025",
    "check_note": "Summit's draft Schedule C lists EIN ending 4402; the agreement shows 4420",
}


class ProviderOut(BaseModel):
    model_config = _ex(_PROVIDER)

    id: Annotated[UUID, classified("internal")]
    name: Label
    role: Annotated[
        Literal["recordkeeper", "trustee", "custodian", "tpa", "investment_adviser", "other"],
        classified("internal"),
    ]
    ein: Annotated[MaskedTinOut | None, classified("restricted", pii_kind="tin")] = None
    status: Annotated[ProviderStatus, classified("internal")]
    soc_report: Annotated[str | None, Field(max_length=200), classified("internal")]
    check_note: Annotated[str | None, Field(max_length=500), classified("confidential")]


class ProvidersOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ProviderOut], Field(max_length=50), classified("confidential")]
    allowed_actions: Actions


class ProviderIn(BaseModel):
    """A-05-T10 (additive): the SOC report's period and, last four digits only, the service
    agreement's and the draft Schedule C's EIN (the full EIN waits for A-05-T18; DEC-1955)."""

    model_config = ConfigDict(extra="forbid")

    name: Label
    role: Annotated[str, Field(max_length=40), classified("internal")]
    soc_type: Annotated[
        Literal["soc1_type1", "soc1_type2", "none"] | None, classified("internal")
    ] = None
    soc_period_start: Annotated[date | None, classified("internal")] = None
    soc_period_end: Annotated[date | None, classified("internal")] = None
    certifies: Annotated[bool, classified("internal")] = False
    agreement_ein_last4: Annotated[
        str | None, Field(pattern=r"^[0-9]{4}$"), classified("restricted", pii_kind="tin")
    ] = None
    schedule_c_ein_last4: Annotated[
        str | None, Field(pattern=r"^[0-9]{4}$"), classified("restricted", pii_kind="tin")
    ] = None


class InviteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_id: Annotated[UUID, classified("internal")]


# --- EBP-02 provisions ---------------------------------------------------------------------------

_PROVISION: JsonDict = {
    "key": "entry_dates",
    "label": "Entry dates",
    "value": "First of month following",
    "verified": False,
    "conflict": "SPD: quarterly",
    "amended_on": None,
    "citation_count": 2,
}


class ProvisionOut(BaseModel):
    model_config = _ex(_PROVISION)

    key: Annotated[str, Field(pattern=r"^[a-z0-9_]{1,64}$"), classified("internal")]
    label: Label
    value: Annotated[str, Field(max_length=500), classified("confidential")]
    verified: Annotated[bool, classified("internal")]
    conflict: Annotated[str | None, Field(max_length=200), classified("confidential")]
    amended_on: Annotated[date | None, classified("internal")]
    citation_count: Annotated[int, Field(ge=0), classified("internal")]


class PlanReviewOut(BaseModel):
    """EBP-02: the provisions of a workpaper version ("0 of 20 verified" in b)."""

    model_config = ConfigDict(frozen=True)

    version_no: Annotated[int, Field(ge=1), classified("internal")]
    verified: Annotated[int, Field(ge=0), classified("internal")]
    total: Annotated[int, Field(ge=0), classified("internal")]
    provisions: Annotated[list[ProvisionOut], Field(max_length=200), classified("confidential")]
    allowed_actions: Actions


class PlanReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_version_ids: Annotated[
        list[UUID], Field(min_length=1, max_length=20), classified("internal")
    ]


# --- census and participants (DEC-1858) ----------------------------------------------------------

_PARTICIPANT: JsonDict = {
    "id": "00000000-0000-4000-8000-000000000601",
    "name": "Participant 22",
    "ssn": {"kind": "ssn", "presence": "on_file", "last4": "4417"},
    "dob_masked": "••/••/••••",
    "status": "active",
    "compensation": "84200.00",
}


class ParticipantOut(BaseModel):
    """A census row as every surface shows it: SSN and DOB masked (Restricted; DEC-1858)."""

    model_config = _ex(_PARTICIPANT)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, Field(max_length=200), classified("confidential")]
    ssn: Annotated[MaskedTinOut, classified("restricted", pii_kind="tin")]
    dob_masked: Annotated[Literal["••/••/••••"], classified("internal")]
    status: Annotated[
        Literal["active", "terminated", "retired", "deceased"], classified("internal")
    ]
    compensation: Money


class ParticipantsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ParticipantOut], Field(max_length=500), classified("confidential")]
    next_cursor: Annotated[str | None, classified("internal")]
    total: Annotated[int, Field(ge=0), classified("internal")]


class RevealIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: Annotated[Literal["ssn", "dob"], classified("internal")]
    reason: Note


class ImportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_version_id: Annotated[UUID, classified("internal")]
    kind: Annotated[Literal["census", "hr", "payroll", "w3"], classified("internal")]
    column_map: Annotated[dict[str, str], classified("internal")]


# --- EBP-04 contributions and the late remittance ------------------------------------------------

_LATE: JsonDict = {
    "id": "00000000-0000-4000-8000-000000000701",
    "payroll_date": "2025-12-26",
    "deposited_on": "2026-01-09",
    "amount": "33540.00",
    "business_days": 9,
    "calendar_days": 10,
    "established_practice_days": 2,
    "lost_earnings": "64.38",
    "status": "pending_vfcp_scc",
    "form_5330": "exposure",
}


class LateRemittanceOut(BaseModel):
    """The single late remittance with both day counts (DF-34): 9 business days from the pay date
    against the plan's established practice, 10 calendar days for lost earnings."""

    model_config = _ex(_LATE)

    id: Annotated[UUID, classified("internal")]
    payroll_date: Annotated[date, classified("internal")]
    deposited_on: Annotated[date, classified("internal")]
    amount: Money
    business_days: Annotated[int, Field(ge=0), classified("internal")]
    calendar_days: Annotated[int, Field(ge=0), classified("internal")]
    established_practice_days: Annotated[int, Field(ge=0), classified("internal")]
    lost_earnings: Money
    status: Annotated[Literal["found", "pending_vfcp_scc", "corrected"], classified("internal")]
    form_5330: Annotated[Literal["exposure", "not_required", "filed"], classified("internal")]


class CorrectionIn(BaseModel):
    """A person records a correction (EBP-04 f); time alone never corrects."""

    model_config = ConfigDict(extra="forbid")

    lost_earnings_deposited_on: Annotated[date, classified("internal")]
    scc_notice_on: Annotated[date | None, classified("internal")] = None
    form_5330_status: Annotated[Literal["not_required", "filed"], classified("internal")]
    evidence_version_ids: Annotated[list[UUID], Field(max_length=20), classified("internal")]


# --- EBP-07 Part IV ------------------------------------------------------------------------------

_PART_IV: JsonDict = {
    "line": "4a",
    "draft_answer": "yes",
    "draft_amount": "33540.00",
    "consistency": "consistent",
    "basis": "the late remittance on EBP-04",
}


class PartIvLineOut(BaseModel):
    model_config = _ex(_PART_IV)

    line: Annotated[Literal["4a", "4b", "4d", "4i", "4j"], classified("internal")]
    draft_answer: Annotated[Literal["yes", "no"] | None, classified("internal")]
    draft_amount: MaybeMoney
    consistency: Annotated[Literal["consistent", "inconsistent"], classified("internal")]
    basis: Label


class Form5500Out(BaseModel):
    model_config = ConfigDict(frozen=True)

    draft_received: Annotated[bool, classified("internal")]
    lines: Annotated[list[FigureRowOut], Field(max_length=200), classified("confidential")]
    part_iv: Annotated[list[PartIvLineOut], Field(max_length=20), classified("confidential")]
    allowed_actions: Actions


class LineValueIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Annotated[Decimal, classified("confidential")]
    citation_note: Note


# --- the tabular reads (EBP-03..09) --------------------------------------------------------------

_NET_ASSETS: JsonDict = {
    "title": "Net assets available for benefits",
    "rows": [
        {"key": "investments", "label": "Investments", "amount": "16500000.00"},
        {
            "key": "notes_receivable",
            "label": "Notes receivable from participants",
            "amount": "312400.00",
        },
        {
            "key": "contributions_receivable",
            "label": "Contributions receivable",
            "amount": "48600.00",
        },
    ],
    "total": "16861000.00",
    "allowed_actions": [],
}


class FiguresOut(BaseModel):
    """A screen's code figures as statement rows (the v1 stub's shape for EBP-03 to EBP-09; each
    screen's task widens it additively)."""

    model_config = _ex(_NET_ASSETS)

    title: Label
    rows: Annotated[list[FigureRowOut], Field(max_length=500), classified("confidential")]
    total: MaybeMoney
    allowed_actions: Actions


class TestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant: Annotated[
        Literal["eligibility", "deferral", "match", "distribution", "loan"], classified("internal")
    ]
    sample_set_id: Annotated[UUID, classified("internal")]


class ResultIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Annotated[Literal["pass", "exception", "no_effect"], classified("internal")]
    note: MaybeNote = None


class CertificationPointIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: Annotated[Literal["evaluated", "not_evaluated"], classified("internal")]
    note: Note


class TrustAdoptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_version_id: Annotated[UUID, classified("internal")]
    citation_ids: Annotated[list[UUID], Field(max_length=200), classified("internal")]


# --- AUD-27 --------------------------------------------------------------------------------------

AudItemStatus = Literal["unevaluated", "evaluated", "exception", "screened_out"]

_ESTIMATE: JsonDict = {
    "id": "00000000-0000-4000-8000-000000000801",
    "name": "Inventory obsolescence reserve",
    "amount": "412000.00",
    "status": "evaluated",
    "pending_ep": True,
}


class Aud27ItemOut(BaseModel):
    model_config = _ex(_ESTIMATE)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, Field(max_length=300), classified("confidential")]
    amount: MaybeMoney
    status: Annotated[AudItemStatus, classified("internal")]
    # "Evaluated · pending EP" is a display variant of evaluated.
    pending_ep: Annotated[bool, classified("internal")]


class Aud27ListOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[Aud27ItemOut], Field(max_length=200), classified("confidential")]
    allowed_actions: Actions


class Aud27ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=300), classified("confidential")]


class ScreenOutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Note


class MethodIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class AcceptedOut(BaseModel):
    """A write's answer once live (its task widens it): the record's id."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]


# --- the gate and the routes ---------------------------------------------------------------------


async def _gate(ctx: AuthContext, work_item_id: UUID, action: str, flag: Flag) -> None:
    """A person only, never a client principal; the action on the work item's engagement; the
    flag. Authorised before the flag, so no one learns a flag state they may not use."""
    if ctx.client:
        raise NotFound("ebp")
    if ctx.tenant.actor_kind != "human" and not action.endswith(".read") and action != "ebp.read":
        raise Forbidden(action, "role")
    item = await assurance_item(ctx.tenant, work_item_id)
    ref = await get_ref(ctx, item.engagement_id)
    await authorise(ctx, action, ref.resource())
    if not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


def _example[M: BaseModel](model: type[M], body: JsonDict) -> M:
    return model.model_validate(body)


def _figures(title: str, rows: list[tuple[str, str, str | None]], total: str | None) -> FiguresOut:
    return FiguresOut(
        title=title,
        rows=[
            FigureRowOut(key=k, label=label, amount=None if a is None else Decimal(a))
            for k, label, a in rows
        ],
        total=None if total is None else Decimal(total),
        allowed_actions=[],
    )


router = AbacusRouter(prefix="/v1/audits/{work_item_id}", tags=["assurance"])
_E = EBP_MODULES
_F = EBP_FORM5500_TIEOUT
_A = ASSURANCE_ESTIMATES_RP


# EBP-01
async def _plan_out(ctx: AuthContext, work_item_id: UUID) -> PlanOut:
    from abacus.modules.assurance import ebp_plan

    found = await ebp_plan.plan_view(
        ctx,
        work_item_id,
        plan_name=await _plan_name(ctx, work_item_id),
        holidays=frozenset(),  # K-02's holiday set joins with its read API (DEC-1955)
    )
    p, status = found.plan, found.status
    item = await assurance_item(ctx.tenant, work_item_id)
    ref = await get_ref(ctx, item.engagement_id)
    can = await allowed_actions(ctx, ref.resource(), ("ebp_plan.edit",))
    return await mask_tins_for(
        ctx,
        PlanOut(
            plan_name=found.plan_name,
            plan_number=found.plan_number,
            plan_year_start=p.plan_year_start,
            plan_year_end=p.plan_year_end,
            plan_type="401k",
            safe_harbor=cast(Literal["none", "qaca", "basic", "nonelective"], p.safe_harbor),
            recordkeeper_id=p.recordkeeper_plan_id,
            participants_boy=p.participants_boy_with_balances or 0,
            participants_eoy=p.participants_eoy or 0,
            filer_status=status.filer_status if status is not None else "small_plan",
            form5500_due_on=status.form5500_due_on if status is not None else p.plan_year_end,
            audit_kind=found.audit_kind,
            version=p.version,
            allowed_actions=cast(list[EbpAction], list(can)),
        ),
    )


async def _plan_name(ctx: AuthContext, work_item_id: UUID) -> str:
    item = await assurance_item(ctx.tenant, work_item_id)
    ref = await get_ref(ctx, item.engagement_id)
    return await entity_name(ctx.tenant, ref.client_entity_id) or "Plan"


@router.get("/ebp/plan", action="ebp.read", response_model=PlanOut)
async def ebp_plan_route(work_item_id: UUID, ctx: Ctx) -> PlanOut:
    """Plan facts and the filer status card (EBP-01; T10); 404 `ebp_plan` until recorded."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    # The sponsor's masked EIN reaches an offshore reader null (DEC-52): the one central mask.
    return await _plan_out(ctx, work_item_id)


@router.patch("/ebp/plan", action="ebp_plan.edit", response_model=PlanOut, errors=(409,))
async def ebp_plan_edit_route(
    work_item_id: UUID, body: PlanEditIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> PlanOut:
    """A person's edit through `review.api.record_value`; the first save records the plan; 422
    `citation_note_required`, `plan_number_invalid` (with the Form 5500 helper); 409
    `version_conflict` (T10)."""
    await _gate(ctx, work_item_id, "ebp_plan.edit", _E)
    from abacus.modules.assurance import ebp_plan

    item = await assurance_item(ctx.tenant, work_item_id)
    ref = await get_ref(ctx, item.engagement_id)
    await ebp_plan.edit_plan(
        ctx,
        work_item_id,
        fields=body.fields,
        citation_note=body.citation_note,
        seen_version=body.seen_version,
        plan_entity_id=ref.client_entity_id,
    )
    return await _plan_out(ctx, work_item_id)


_ROLE_OUT: dict[str, str] = {
    "trustee_custodian": "trustee",
    "payroll": "other",
    "sdba_broker": "other",
}


@router.get("/ebp/providers", action="ebp.read", response_model=ProvidersOut)
async def ebp_providers_route(work_item_id: UUID, ctx: Ctx) -> ProvidersOut:
    """The plan's providers with their checks' notes, by code (T10)."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_plan

    rows = await ebp_plan.providers(ctx.tenant, work_item_id)
    notes = ebp_plan.check_notes(
        await ebp_plan.checks(ctx.tenant, work_item_id), {p.id: p.org_name for p in rows}
    )
    item = await assurance_item(ctx.tenant, work_item_id)
    ref = await get_ref(ctx, item.engagement_id)
    can = await allowed_actions(
        ctx, ref.resource(), ("ebp_provider.manage", "ebp_provider.invite")
    )
    return await mask_tins_for(
        ctx,
        ProvidersOut(
            items=[
                ProviderOut(
                    id=p.id,
                    name=p.org_name,
                    role=cast(
                        Literal[
                            "recordkeeper",
                            "trustee",
                            "custodian",
                            "tpa",
                            "investment_adviser",
                            "other",
                        ],
                        _ROLE_OUT.get(p.role, p.role),
                    ),
                    ein=None,
                    status=cast(ProviderStatus, p.status),
                    soc_report=_soc_text(p.soc_type, p.soc_period_start, p.soc_period_end),
                    check_note=notes.get(p.id),
                )
                for p in rows
            ],
            allowed_actions=cast(list[EbpAction], list(can)),
        ),
    )


def _soc_text(kind: str | None, start: date | None, end: date | None) -> str | None:
    if kind not in ("soc1_type1", "soc1_type2"):
        return None
    label = "SOC 1 Type 2" if kind == "soc1_type2" else "SOC 1 Type 1"
    if start is None or end is None:
        return label
    return f"{label}, {start:%b} {start.day} to {end:%b} {end.day}, {end.year}"


@router.post(
    "/ebp/providers",
    action="ebp_provider.manage",
    response_model=AcceptedOut,
    status_code=201,
    errors=(409,),
)
async def ebp_provider_create_route(
    work_item_id: UUID, body: ProviderIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AcceptedOut:
    """Add a provider; code runs its checks (SOC gap; Schedule C EIN ending against the
    agreement's, routed to the TPA) (T10)."""
    await _gate(ctx, work_item_id, "ebp_provider.manage", _E)
    from abacus.modules.assurance import ebp_plan

    created = await ebp_plan.add_provider(
        ctx,
        work_item_id,
        ebp_plan.NewProvider(
            org_name=body.name,
            role=body.role,
            soc_type=body.soc_type,
            soc_period_start=body.soc_period_start,
            soc_period_end=body.soc_period_end,
            certifies=body.certifies,
            agreement_ein_last4=body.agreement_ein_last4,
            schedule_c_ein_last4=body.schedule_c_ein_last4,
        ),
    )
    return AcceptedOut(id=created.id)


@router.post(
    "/ebp/providers/{provider_id}/invite",
    action="ebp_provider.invite",
    response_model=AcceptedOut,
    status_code=201,
    errors=(501,),
)
async def ebp_provider_invite_route(
    work_item_id: UUID,
    provider_id: UUID,
    body: InviteIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> AcceptedOut:
    """A C5 delegation to a named provider contact, scope `request_item` (T08)."""
    await _gate(ctx, work_item_id, "ebp_provider.invite", _E)
    _not_yet()


# EBP-02
@router.get("/ebp/plan-reviews/current", action="ebp.read", response_model=PlanReviewOut)
async def ebp_plan_review_route(
    work_item_id: UUID, ctx: Ctx, version: Annotated[int | None, Query(ge=1)] = None
) -> PlanReviewOut:
    """Provisions with conflicts and amendment tags (EBP-02; `?version=` is b2; T10)."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    return PlanReviewOut(
        version_no=version or 2,
        verified=0,
        total=20,
        provisions=[_example(ProvisionOut, _PROVISION)],
        allowed_actions=["field.sign_off"],
    )


@router.post(
    "/ebp/plan-reviews",
    action="workpaper.draft",
    response_model=AcceptedOut,
    status_code=202,
    errors=(501,),
)
async def ebp_plan_review_start_route(
    work_item_id: UUID, body: PlanReviewIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AcceptedOut:
    """Start a provisions read (A-04's `workpapers.drafting` gate; T12)."""
    await _gate(ctx, work_item_id, "workpaper.draft", _E)
    _not_yet()


# census
@router.get("/ebp/participants", action="ebp.read", response_model=ParticipantsOut)
async def ebp_participants_route(
    work_item_id: UUID,
    ctx: Ctx,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> ParticipantsOut:
    """Masked participants, tokens only (DEC-1858; T15)."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    return await mask_tins_for(
        ctx,
        ParticipantsOut(
            items=[_example(ParticipantOut, _PARTICIPANT)], next_cursor=None, total=301
        ),
    )


@router.post(
    "/ebp/participants/{participant_id}/reveals",
    action="pii.reveal",
    response_model=AcceptedOut,
    status_code=201,
    errors=(501,),
)
async def ebp_participant_reveal_route(
    work_item_id: UUID,
    participant_id: UUID,
    body: RevealIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> AcceptedOut:
    """A logged reveal (fresh MFA, onshore, 20 an hour, `no-store`; DEC-1858; T15)."""
    await _gate(ctx, work_item_id, "pii.reveal", _E)
    _not_yet()


@router.post(
    "/ebp/imports",
    action="ebp_import.create",
    response_model=AcceptedOut,
    status_code=201,
    errors=(501,),
)
async def ebp_import_route(
    work_item_id: UUID, body: ImportIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AcceptedOut:
    """A code import that foots or is refused `import_not_footing` (T15)."""
    await _gate(ctx, work_item_id, "ebp_import.create", _E)
    _not_yet()


# tests grid (EBP-03, 04 testing tab, 05)
@router.post(
    "/tests", action="test.create", response_model=AcceptedOut, status_code=201, errors=(501,)
)
async def ebp_test_create_route(
    work_item_id: UUID, body: TestIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AcceptedOut:
    await _gate(ctx, work_item_id, "test.create", _E)
    _not_yet()


@router.put(
    "/tests/{test_id}/items/{item_id}/results/{attribute}",
    action="test.mark",
    response_model=AcceptedOut,
    errors=(409, 501),
)
async def ebp_test_mark_route(
    work_item_id: UUID,
    test_id: UUID,
    item_id: UUID,
    attribute: Annotated[str, Path(pattern=r"^[a-z0-9_]{1,40}$")],
    body: ResultIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> AcceptedOut:
    """A person's pass, exception or no effect (never the agent's; INV-1)."""
    await _gate(ctx, work_item_id, "test.mark", _E)
    _not_yet()


@router.get("/ebp/eligibility", action="ebp.read", response_model=FiguresOut)
async def ebp_eligibility_route(work_item_id: UUID, ctx: Ctx) -> FiguresOut:
    await _gate(ctx, work_item_id, "ebp.read", _E)
    return _figures(
        "Eligibility",
        [
            ("eligible_boy", "Eligible participants, beginning of year", "286"),
            ("eligible_eoy", "Eligible participants, end of year", "301"),
        ],
        None,
    )


# EBP-04
@router.get("/ebp/contributions/reconciliation", action="ebp.read", response_model=FiguresOut)
async def ebp_contributions_route(work_item_id: UUID, ctx: Ctx) -> FiguresOut:
    await _gate(ctx, work_item_id, "ebp.read", _E)
    return _figures(
        "Contributions receivable",
        [
            ("receivable_regular", "Regular payroll", "15060.00"),
            ("receivable_late", "Late deposit", "33540.00"),
        ],
        "48600.00",
    )


@router.get("/ebp/late-remittances", action="ebp.read", response_model=list[LateRemittanceOut])
async def ebp_late_remittances_route(work_item_id: UUID, ctx: Ctx) -> list[LateRemittanceOut]:
    """The one late remittance (DF-34)."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    return [_example(LateRemittanceOut, _LATE)]


@router.post(
    "/ebp/late-remittances/{remittance_id}/corrections",
    action="ebp_correction.record",
    response_model=AcceptedOut,
    status_code=201,
    errors=(409, 501),
)
async def ebp_correction_route(
    work_item_id: UUID,
    remittance_id: UUID,
    body: CorrectionIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> AcceptedOut:
    """A person records the correction (EBP-04 f; T21)."""
    await _gate(ctx, work_item_id, "ebp_correction.record", _E)
    _not_yet()


# EBP-05, 06, 08, 09
@router.get("/ebp/loans/rollforward", action="ebp.read", response_model=FiguresOut)
async def ebp_loans_route(work_item_id: UUID, ctx: Ctx) -> FiguresOut:
    await _gate(ctx, work_item_id, "ebp.read", _E)
    return _figures(
        "Notes receivable from participants",
        [("notes_eoy", "End of year", "312400.00")],
        "312400.00",
    )


@router.get("/ebp/investments", action="ebp.read", response_model=FiguresOut)
async def ebp_investments_route(
    work_item_id: UUID,
    ctx: Ctx,
    layer: Annotated[Literal["unadjusted", "aje", "rje", "final"], Query()] = "final",
) -> FiguresOut:
    """Lines by layer (C9/C8); Final is 409 `layer_unavailable` until A-06 registers (T26)."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    return _example(FiguresOut, _NET_ASSETS)


@router.post(
    "/ebp/trust-tb/adopt",
    action="ledger_snapshot.create_from_document",
    response_model=AcceptedOut,
    status_code=201,
    errors=(501,),
)
async def ebp_trust_adopt_route(
    work_item_id: UUID, body: TrustAdoptIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AcceptedOut:
    """A person adopts the trust report's lines as the plan TB (ADR-400; T28)."""
    await _gate(ctx, work_item_id, "ledger_snapshot.create_from_document", _E)
    _not_yet()


@router.put(
    "/ebp/certification/points/{point_key}",
    action="ebp_certification.evaluate",
    response_model=AcceptedOut,
    errors=(501,),
)
async def ebp_certification_route(
    work_item_id: UUID,
    point_key: Annotated[str, Path(pattern=r"^[a-z0-9_]{1,40}$")],
    body: CertificationPointIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> AcceptedOut:
    """A person evaluates a certification point (29 CFR 2520.103-8; T27)."""
    await _gate(ctx, work_item_id, "ebp_certification.evaluate", _E)
    _not_yet()


@router.get("/ebp/participant-accounts/rollforward", action="ebp.read", response_model=FiguresOut)
async def ebp_participant_accounts_route(work_item_id: UUID, ctx: Ctx) -> FiguresOut:
    await _gate(ctx, work_item_id, "ebp.read", _E)
    return _figures(
        "Participant accounts",
        [("active", "Active", "13640900.00"), ("terminated", "Terminated", "3171500.00")],
        "16812400.00",
    )


@router.get("/ebp/plan-expenses", action="ebp.read", response_model=FiguresOut)
async def ebp_plan_expenses_route(work_item_id: UUID, ctx: Ctx) -> FiguresOut:
    await _gate(ctx, work_item_id, "ebp.read", _E)
    return _figures("Administrative expenses", [], None)


# EBP-07
@router.get("/ebp/form-5500", action="ebp_form5500.read", response_model=Form5500Out)
async def ebp_form5500_route(work_item_id: UUID, ctx: Ctx) -> Form5500Out:
    """Draft status, Schedule H lines with tallies and Part IV (EBP-07; T36)."""
    await _gate(ctx, work_item_id, "ebp_form5500.read", _F)
    return Form5500Out(
        draft_received=True,
        lines=[
            FigureRowOut(
                key="h.1c",
                label="Receivables",
                amount=Decimal("48600.00"),
                status="reconciling_item",
            )
        ],
        part_iv=[_example(PartIvLineOut, _PART_IV)],
        allowed_actions=["ebp_form5500.key", "ebp_form5500.send_note"],
    )


@router.post(
    "/ebp/form-5500/lines/{line_id}/value",
    action="ebp_form5500.key",
    response_model=AcceptedOut,
    errors=(501,),
)
async def ebp_form5500_key_route(
    work_item_id: UUID, line_id: UUID, body: LineValueIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AcceptedOut:
    await _gate(ctx, work_item_id, "ebp_form5500.key", _F)
    _not_yet()


@router.post(
    "/ebp/form-5500/reconciliation-note",
    action="ebp_form5500.send_note",
    response_model=AcceptedOut,
    status_code=201,
    errors=(501,),
)
async def ebp_form5500_note_route(
    work_item_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AcceptedOut:
    """Note 8 to AUD-20 (A-06's receiving endpoint; T38)."""
    await _gate(ctx, work_item_id, "ebp_form5500.send_note", _F)
    _not_yet()


# AUD-27
@router.get("/estimates", action="estimate.read", response_model=Aud27ListOut)
async def estimates_route(work_item_id: UUID, ctx: Ctx) -> Aud27ListOut:
    await _gate(ctx, work_item_id, "estimate.read", _A)
    return Aud27ListOut(
        items=[_example(Aud27ItemOut, _ESTIMATE)], allowed_actions=["estimate.evaluate"]
    )


@router.put(
    "/estimates/{estimate_id}/method",
    action="estimate.evaluate",
    response_model=AcceptedOut,
    errors=(409, 501),
)
async def estimate_method_route(
    work_item_id: UUID,
    estimate_id: UUID,
    body: MethodIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> AcceptedOut:
    await _gate(ctx, work_item_id, "estimate.evaluate", _A)
    _not_yet()


@router.post(
    "/estimates/{estimate_id}/request-conclusion",
    action="estimate.request_conclusion",
    response_model=AcceptedOut,
    status_code=201,
    errors=(409, 501),
)
async def estimate_conclusion_route(
    work_item_id: UUID, estimate_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AcceptedOut:
    """Raise the EP's decision card; deciding is `decision.decide` (INV-1; T52)."""
    await _gate(ctx, work_item_id, "estimate.request_conclusion", _A)
    _not_yet()


@router.get("/related-parties", action="related_party.read", response_model=Aud27ListOut)
async def related_parties_route(work_item_id: UUID, ctx: Ctx) -> Aud27ListOut:
    await _gate(ctx, work_item_id, "related_party.read", _A)
    return Aud27ListOut(items=[], allowed_actions=["related_party.manage"])


@router.post(
    "/related-parties",
    action="related_party.manage",
    response_model=AcceptedOut,
    status_code=201,
    errors=(501,),
)
async def related_party_create_route(
    work_item_id: UUID, body: Aud27ItemIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AcceptedOut:
    await _gate(ctx, work_item_id, "related_party.manage", _A)
    _not_yet()


@router.post(
    "/related-parties/{party_id}/screen-out",
    action="related_party.screen_out",
    response_model=AcceptedOut,
    errors=(501,),
)
async def related_party_screen_out_route(
    work_item_id: UUID,
    party_id: UUID,
    body: ScreenOutIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> AcceptedOut:
    await _gate(ctx, work_item_id, "related_party.screen_out", _A)
    _not_yet()


@router.get("/parties-in-interest", action="ebp.read", response_model=Aud27ListOut)
async def parties_in_interest_route(work_item_id: UUID, ctx: Ctx) -> Aud27ListOut:
    """AUD-27 c (Northwind); the prohibited transaction reads the late remittance (T52)."""
    await _gate(ctx, work_item_id, "ebp.read", _A)
    return Aud27ListOut(items=[], allowed_actions=["party_in_interest.manage"])


@router.post(
    "/parties-in-interest",
    action="party_in_interest.manage",
    response_model=AcceptedOut,
    status_code=201,
    errors=(501,),
)
async def party_in_interest_create_route(
    work_item_id: UUID, body: Aud27ItemIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AcceptedOut:
    await _gate(ctx, work_item_id, "party_in_interest.manage", _A)
    _not_yet()

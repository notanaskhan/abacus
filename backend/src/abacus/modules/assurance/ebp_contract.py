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

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Header, Path, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict

from abacus.kernel._flags import (
    ASSURANCE_ESTIMATES_RP,
    EBP_FORM5500_TIEOUT,
    EBP_MODULES,
    WORKPAPERS_DRAFTING,
)
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.assurance import ebp_provisions
from abacus.modules.assurance.ebp_imports import ImportView, Ties, import_of, import_source
from abacus.modules.assurance.ebp_participants import DOB_MASK, participants_of
from abacus.modules.assurance.ebp_participants import reveal as reveal_participant_field
from abacus.modules.assurance.tb_mapping_contract import SignOffChipOut
from abacus.modules.engagements.api import assurance_item, get_ref
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Forbidden,
    allowed_actions,
    authorise,
    current_context,
    mask_tins_for,
    names_of,
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
    # A-05-T17 (DEC-2071): what the screen ticks and shows beside the value.
    reference: Annotated[str | None, Field(max_length=300), classified("confidential")] = None
    cell: Annotated[
        str | None, Field(pattern=r"^[A-Z]{1,3}[0-9]{1,5}$"), classified("internal")
    ] = None
    value_hash: Annotated[str | None, Field(max_length=80), classified("internal")] = None


class PlanReviewOut(BaseModel):
    """EBP-02: the provisions of a workpaper version ("0 of 20 verified" in b)."""

    model_config = ConfigDict(frozen=True)

    version_no: Annotated[int, Field(ge=1), classified("internal")]
    verified: Annotated[int, Field(ge=0), classified("internal")]
    total: Annotated[int, Field(ge=0), classified("internal")]
    provisions: Annotated[list[ProvisionOut], Field(max_length=200), classified("confidential")]
    allowed_actions: Actions
    # A-05-T17 (DEC-2071): the paper the ticks are on (`workpaper_cell` fields) and its
    # sign-offs ("✓ HL", "Reviewed · HL Sep 17").
    workpaper_id: Annotated[UUID | None, classified("internal")] = None
    sign_offs: Annotated[list[SignOffChipOut], Field(max_length=10), classified("internal")] = (
        Field(default_factory=list[SignOffChipOut])
    )


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
    ssn: Annotated[MaskedTinOut | None, classified("restricted", pii_kind="tin")]
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


class ParticipantRevealOut(BaseModel):
    """The only payload that carries a participant's SSN or date of birth in the clear, for 30
    seconds; `Cache-Control: no-store`, never logged (DEC-60, DEC-1858; A-05-T18)."""

    model_config = ConfigDict(frozen=True)

    value: Annotated[str, classified("restricted")]
    field: Annotated[Literal["ssn", "dob"], classified("internal")]
    expires_in: Annotated[int, Field(ge=1, le=60), classified("internal")]
    revealed_by: Annotated[str, classified("confidential")]
    revealed_at: Annotated[datetime, classified("internal")]


ImportKind = Literal[
    "census",
    "payroll_register",
    "loan_report",
    "account_balances",
    "sdba_detail",
    "trust_receipts",
    "hr_roster",
]


class ImportIn(BaseModel):
    """A code import (A-05-T19; DEC-2068): the column map is `{field: header}`; the W-3 boxes
    and a register's printed control totals are keyed from the PDF with the import."""

    model_config = ConfigDict(extra="forbid")

    evidence_version_id: Annotated[UUID, classified("internal")]
    kind: Annotated[ImportKind, classified("internal")]
    column_map: Annotated[
        dict[
            Annotated[str, Field(pattern=r"^[a-z_]{1,40}$")],
            Annotated[str, Field(min_length=1, max_length=120)],
        ],
        Field(max_length=30),
        classified("internal"),
    ]
    w3_box1: Annotated[
        Decimal | None, Field(ge=0, decimal_places=2), classified("confidential")
    ] = None
    w3_box12d: Annotated[
        Decimal | None, Field(ge=0, decimal_places=2), classified("confidential")
    ] = None
    control_totals: Annotated[
        dict[Annotated[str, Field(pattern=r"^[a-z_]{1,40}$")], Decimal],
        Field(max_length=10),
        classified("confidential"),
    ] = Field(default_factory=dict)


class EbpImportOut(BaseModel):
    """An import as the import sheet shows it: its totals, or why it was refused (the
    differences, never a cell value)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]
    kind: Annotated[ImportKind, classified("internal")]
    row_count: Annotated[int | None, Field(ge=0), classified("internal")]
    totals: Annotated[dict[str, object], classified("confidential")]
    status: Annotated[Literal["mapped", "imported", "refused"], classified("internal")]
    refusal_code: Annotated[str | None, Field(max_length=60), classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


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


class PayrollOut(BaseModel):
    """One payroll on the remittance timeline (EBP-04 b and the 26-dot timeline; A-05-T31): the
    deposit and its lag as code recorded them, and the payroll's total by code."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    pay_date: Annotated[date, classified("internal")]
    deposit_date: Annotated[date | None, classified("internal")]
    deferrals_pretax: Money
    deferrals_roth: Money
    match: Money
    deferrals: Money  # pre-tax + Roth, by code
    total: Money
    business_day_lag: Annotated[int | None, Field(ge=0), classified("internal")]
    calendar_lag: Annotated[int | None, Field(ge=0), classified("internal")]
    late: Annotated[bool, classified("internal")]


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


class InvestmentRowOut(BaseModel):
    """One certified line against the plan TB at the layer (EBP-06)."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Field(max_length=80), classified("internal")]
    label: Label
    level: Annotated[Literal["level1", "nav", "not_certified", "other"], classified("internal")]
    trust_eoy: MaybeMoney = None
    trust_boy: MaybeMoney = None
    tb_eoy: MaybeMoney = None
    tb_boy: MaybeMoney = None
    ties: Annotated[bool | None, classified("internal")] = None
    off_by: MaybeMoney = None


class CertificationPointOut(BaseModel):
    """A person's evaluation of a point; the agent's answer is only ever `proposed_answer`."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Field(max_length=40), classified("internal")]
    proposed_answer: Annotated[str | None, Field(max_length=500), classified("confidential")] = None
    citation_id: Annotated[UUID | None, classified("internal")] = None
    answer: Annotated[Literal["evaluated", "not_evaluated"], classified("internal")]
    note: Annotated[str | None, Field(max_length=1000), classified("confidential")] = None


class InvestmentsOut(BaseModel):
    """EBP-06 by layer: agreement rows, the certified footing, chips and the sign-off hold."""

    model_config = ConfigDict(frozen=True)

    layer: Annotated[Literal["unadjusted", "aje", "rje", "final"], classified("internal")]
    rows: Annotated[list[InvestmentRowOut], Field(max_length=500), classified("confidential")]
    investments_eoy: MaybeMoney = None
    investments_boy: MaybeMoney = None
    level1_eoy: MaybeMoney = None
    nav_eoy: MaybeMoney = None
    net_assets: MaybeMoney = None
    tb_balanced: Annotated[bool, classified("internal")]
    py_ties: Annotated[bool, classified("internal")]
    points: Annotated[list[CertificationPointOut], classified("confidential")]
    hold_reason: Annotated[Literal["certification_unevaluated"] | None, classified("internal")] = (
        None
    )
    unevaluated: Annotated[int, classified("internal")]
    engine_version: Annotated[str, Field(max_length=40), classified("internal")]
    inputs_hash: Annotated[str, Field(max_length=64), classified("internal")]
    allowed_actions: Actions


class TestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant: Annotated[
        Literal["eligibility", "deferral", "match", "distribution", "loan"], classified("internal")
    ]
    sample_set_id: Annotated[UUID, classified("internal")]
    # A-05-T22 (additive): the approved sample version and the paper (default: the variant's
    # EBP workpaper on the work item).
    sample_version: Annotated[int, Field(ge=1), classified("internal")] = 1
    workpaper_id: Annotated[UUID | None, classified("internal")] = None


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


class TestGridCellOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    attribute_key: Annotated[str, classified("internal")]
    result: Annotated[
        Literal["not_started", "agent_tested", "needs_human", "pass", "exception", "no_effect"],
        classified("internal"),
    ]
    by: Annotated[Literal["human", "agent", "system", "policy"], classified("internal")]
    citation_ids: Annotated[list[UUID], classified("internal")]
    # EBP-04 c (A-05-T32; DEC-2258): a recalculation cell's figure as recorded and code's own
    # recalculation; None on a pure attribute (EBP-03).
    value: MaybeMoney = None
    expected: MaybeMoney = None


class TestGridRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: Annotated[int, classified("internal")]
    item_id: Annotated[UUID, classified("internal")]
    record_key: Annotated[str, classified("confidential")]
    state: Annotated[str, classified("internal")]
    cells: Annotated[list[TestGridCellOut], classified("internal")]
    # EBP-04 c: the EBP-03 sample item the same participant's exception traces to.
    linked_item_id: Annotated[UUID | None, classified("internal")] = None


class TestGridOut(BaseModel):
    """EBP-03 a/b, EBP-04 c, EBP-05: rows in sample order with each attribute's newest result."""

    model_config = ConfigDict(frozen=True)

    test_id: Annotated[UUID, classified("internal")]
    variant: Annotated[str, classified("internal")]
    attributes: Annotated[list[str], classified("internal")]
    rows: Annotated[list[TestGridRowOut], classified("confidential")]
    counts: Annotated[dict[str, int], classified("internal")]
    version_no: Annotated[int, classified("internal")]


class AcceptedOut(BaseModel):
    """A write's answer once live (its task widens it): the record's id."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]


# --- the gate and the routes ---------------------------------------------------------------------


# --- EBP-03 sample (A-05-T23, DEC-2225): the eligibility test's 25 rows with the facts the grid
# shows. The date of birth stays masked (A-05-T18's sealing; reveal is the logged per-field route),
# so the screen's computation line names eligibility and entry, never the 21st birthday.

EligibilityResult = Literal[
    "not_started", "agent_tested", "needs_human", "pass", "exception", "no_effect"
]


class EligibilitySampleRowOut(BaseModel):
    """One sampled participant in A-03's order: census against HR, and code's entry date."""

    model_config = ConfigDict(frozen=True)

    position: Annotated[int, Field(ge=1), classified("internal")]
    item_id: Annotated[UUID, classified("internal")]
    participant_id: Annotated[UUID, classified("internal")]
    record_key: Annotated[str, Field(max_length=40), classified("internal")]  # "NW-1184"
    census_name: Annotated[str, Field(max_length=200), classified("confidential")]
    hr_first_name: Annotated[str | None, Field(max_length=100), classified("confidential")]
    dob_masked: Annotated[Literal["••/••/••••"], classified("internal")]
    census_hire: Annotated[date, classified("confidential")]
    hr_hire: Annotated[date | None, classified("confidential")]
    eligible_on: Annotated[date | None, classified("confidential")]
    entry_on: Annotated[date | None, classified("confidential")]
    recordkeeper_entry_on: Annotated[date | None, classified("confidential")]
    rate_label: Annotated[str, Field(max_length=120), classified("confidential")]
    result: Annotated[EligibilityResult, classified("internal")]
    note: Annotated[str | None, Field(max_length=300), classified("confidential")] = None
    hr_record_version_id: Annotated[UUID | None, classified("internal")] = None
    missed_deferral: Annotated[Decimal | None, classified("confidential")] = None
    missed_match: Annotated[Decimal | None, classified("confidential")] = None


class EligibilitySampleOut(BaseModel):
    """EBP-03's sample read: the rows, the tallies and the rungs the header shows."""

    model_config = ConfigDict(frozen=True)

    test_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    rows: Annotated[list[EligibilitySampleRowOut], classified("confidential")]
    exceptions: Annotated[int, Field(ge=0), classified("internal")]
    needs_human: Annotated[int, Field(ge=0), classified("internal")]
    prepared_by: Annotated[str | None, Field(max_length=4), classified("internal")] = None
    reviewed_by: Annotated[str | None, Field(max_length=4), classified("internal")] = None
    allowed_actions: Annotated[list[str], classified("internal")]


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
    """Unmasked: each route masks it itself (`mask_tins_for`, the offshore contract)."""
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
    return PlanOut(
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
    return await mask_tins_for(ctx, await _plan_out(ctx, work_item_id))


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
    return await mask_tins_for(ctx, await _plan_out(ctx, work_item_id))


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
    """EBP-02 (A-05-T16; DEC-2069): the latest review's provisions (`?version=` is b2, an earlier
    review, read-only), each with its adopted value and reference and whether it is verified (a
    current field tick on its value cell)."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    found = await ebp_provisions.review_of(ctx, work_item_id, version)
    actions: list[EbpAction] = ["field.sign_off"] if version is None else []
    return PlanReviewOut(
        version_no=max(found.review_no, 1),
        verified=found.verified,
        total=len(found.provisions),
        provisions=[
            ProvisionOut(
                key=p.provision.key,
                label=p.provision.label,
                value=p.value or "",
                verified=p.verified,
                conflict=None,
                amended_on=None,
                citation_count=p.citation_count,
                reference=p.reference,
                cell=p.provision.value_cell,
                value_hash=p.value_hash,
            )
            for p in found.provisions
        ],
        allowed_actions=actions,
        workpaper_id=found.workpaper_id,
        sign_offs=await _chips(found.sign_offs),
    )


@router.post(
    "/ebp/plan-reviews",
    action="workpaper.draft",
    response_model=AcceptedOut,
    status_code=202,
)
async def ebp_plan_review_start_route(
    work_item_id: UUID, body: PlanReviewIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AcceptedOut:
    """Start a provisions read (A-05-T16): the review is recorded and an `ebp_provisions` run
    starts on EBP-02 over the chosen versions, in order; the answer is the run's id. A-04's
    `workpapers.drafting` gate and the EBP flag both apply."""
    await _gate(ctx, work_item_id, "workpaper.draft", _E)
    await _gate(ctx, work_item_id, "workpaper.draft", WORKPAPERS_DRAFTING)
    run_id = await ebp_provisions.start_review(
        ctx, work_item_id, body.document_version_ids, idempotency_key
    )
    return AcceptedOut(id=run_id)


# census
@router.get("/ebp/participants", action="ebp.read", response_model=ParticipantsOut)
async def ebp_participants_route(
    work_item_id: UUID,
    ctx: Ctx,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> ParticipantsOut:
    """Masked participants of the latest imported census, tokens only (DEC-1858; T15, T19)."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    rows, total = await participants_of(ctx, work_item_id, q)
    return await mask_tins_for(
        ctx,
        ParticipantsOut(
            items=[
                ParticipantOut(
                    id=r.id,
                    name=r.name,
                    ssn=None
                    if r.ssn_last4 is None
                    else MaskedTinOut(kind="ssn", presence="on_file", last4=r.ssn_last4),
                    dob_masked=DOB_MASK,
                    status=cast(Literal["active", "terminated"], r.status),
                    compensation=r.compensation or Decimal("0.00"),
                )
                for r in rows
            ],
            next_cursor=None,
            total=total,
        ),
    )


@router.post(
    "/ebp/participants/{participant_id}/reveals",
    action="pii.reveal",
    response_model=ParticipantRevealOut,
    status_code=201,
    errors=(429,),
)
async def ebp_participant_reveal_route(
    work_item_id: UUID,
    participant_id: UUID,
    body: RevealIn,
    ctx: Ctx,
    response: Response,
    idempotency_key: IdempotencyKey,
) -> ParticipantRevealOut:
    """A logged reveal (A-05-T18; DEC-1858, DEC-2067): one field for 30 seconds, `no-store`. The
    gate reads the work item (`ebp.read`, then the flag); `pii.reveal` itself is authorised by the
    reveal, so stale MFA answers 403 `mfa_required` (the shell steps up), and offshore members,
    agents, support sessions and client principals get 403 before anything opens; 429 past twenty
    reveals an hour across every reveal. One `pii_reveals` row and one `pii.revealed` audit event,
    never the value."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    revealed = await reveal_participant_field(
        ctx, work_item_id, participant_id, body.field, body.reason
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return ParticipantRevealOut(
        value=revealed.value,
        field=body.field,
        expires_in=revealed.expires_in,
        revealed_by=revealed.revealed_by,
        revealed_at=revealed.revealed_at,
    )


@router.post(
    "/ebp/imports",
    action="ebp_import.create",
    response_model=EbpImportOut,
    status_code=201,
)
async def ebp_import_route(
    work_item_id: UUID, body: ImportIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> EbpImportOut:
    """A code import (A-05-T19; DEC-2068): parsed from the version's isolated extraction, footed
    and tied by code, census SSNs and dates of birth sealed. 422 `import_map_invalid` for a map
    that misses a field or names a header the file lacks; 422 `import_refused` (recorded, with
    `facts.reason` `import_not_footing`, `import_not_tying`, `import_no_control_total` or
    `import_bad_value` and the differences) for a file that reads but does not foot or tie."""
    await _gate(ctx, work_item_id, "ebp_import.create", _E)
    view = await import_source(
        ctx,
        work_item_id,
        body.evidence_version_id,
        body.kind,
        body.column_map,
        Ties(body.w3_box1, body.w3_box12d, body.control_totals),
    )
    return _import_out(view)


@router.get("/ebp/imports/{import_id}", action="ebp.read", response_model=EbpImportOut)
async def ebp_import_read_route(work_item_id: UUID, import_id: UUID, ctx: Ctx) -> EbpImportOut:
    """An import and its totals or refusal (A-05-T19)."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    return _import_out(await import_of(ctx, work_item_id, import_id))


async def _chips(signed: Sequence[ebp_provisions.SignedLevel]) -> list[SignOffChipOut]:
    names = await names_of([s.user_id for s in signed])
    return [
        SignOffChipOut(
            level=s.level,
            initials="".join(part[0] for part in names.get(s.user_id, "").split()[:2]).upper(),
            name=names.get(s.user_id, ""),
            at=s.at,
            stale=s.stale,
        )
        for s in signed
    ]


def _import_out(view: ImportView) -> EbpImportOut:
    return EbpImportOut(
        id=view.id,
        evidence_version_id=view.evidence_version_id,
        kind=cast(ImportKind, view.kind),
        row_count=view.row_count,
        totals=dict(view.totals),
        status=cast(Literal["mapped", "imported", "refused"], view.status),
        refusal_code=view.refusal_code,
        created_at=view.created_at,
    )


# tests grid (EBP-03, 04 testing tab, 05)
@router.post(
    "/tests", action="test.create", response_model=AcceptedOut, status_code=201, errors=(501,)
)
async def ebp_test_create_route(
    work_item_id: UUID, body: TestIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AcceptedOut:
    await _gate(ctx, work_item_id, "test.create", _E)
    from abacus.modules.assurance import ebp_tests

    test_id = await ebp_tests.create(ctx, work_item_id, body)
    return AcceptedOut(id=test_id)


@router.get("/tests/{test_id}", action="test.read", response_model=TestGridOut)
async def ebp_test_grid_route(work_item_id: UUID, test_id: UUID, ctx: Ctx) -> TestGridOut:
    """The shared grid (A-05-T22)."""
    await _gate(ctx, work_item_id, "test.read", _E)
    from abacus.modules.assurance import ebp_tests

    return await ebp_tests.grid_out(ctx, work_item_id, test_id)


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
    from abacus.modules.assurance import ebp_tests

    await ebp_tests.mark(ctx, work_item_id, test_id, item_id, attribute, body)
    return AcceptedOut(id=test_id)


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


@router.get(
    "/ebp/eligibility/sample",
    action="ebp.read",
    response_model=EligibilitySampleOut,
    errors=(501,),
)
async def ebp_eligibility_sample_route(work_item_id: UUID, ctx: Ctx) -> EligibilitySampleOut:
    """EBP-03's grid (A-05-T23 contract first, DEC-2225): 501 until the sample service lands."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    _not_yet()


# EBP-04
@router.get("/ebp/contributions/reconciliation", action="ebp.read", response_model=FiguresOut)
async def ebp_contributions_route(work_item_id: UUID, ctx: Ctx) -> FiguresOut:
    """Contributions receivable at year end by code from the payroll register (A-05-T30)."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_remittances
    from abacus.modules.engagements.api import engagement_metadata

    item = await assurance_item(ctx.tenant, work_item_id)
    year_end = (await engagement_metadata(ctx, item.engagement_id)).engagement.fiscal_period_end
    found = await ebp_remittances.reconciliation(ctx.tenant, work_item_id, year_end)
    return _figures(
        "Contributions receivable",
        [
            ("receivable_regular", "Regular payroll", str(found.regular)),
            ("receivable_late", "Late deposit", str(found.late)),
        ],
        str(found.total),
    )


@router.get("/ebp/contributions/payrolls", action="ebp.read", response_model=list[PayrollOut])
async def ebp_payrolls_route(work_item_id: UUID, ctx: Ctx) -> list[PayrollOut]:
    """The plan year's payrolls in pay-date order with their deposit lags (A-05-T31; DEC-2257)."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_remittances

    return [
        PayrollOut(
            id=p.id,
            pay_date=p.pay_date,
            deposit_date=p.deposit_date,
            deferrals_pretax=p.deferrals_pretax,
            deferrals_roth=p.deferrals_roth,
            match=p.match,
            deferrals=p.deferrals,
            total=p.total,
            business_day_lag=p.business_day_lag,
            calendar_lag=p.calendar_lag,
            late=p.late,
        )
        for p in await ebp_remittances.payrolls(ctx.tenant, work_item_id)
    ]


@router.get(
    "/ebp/contributions/test", action="ebp.read", response_model=TestGridOut, errors=(501,)
)
async def ebp_contributions_test_route(work_item_id: UUID, ctx: Ctx) -> TestGridOut:
    """EBP-04 c: the 25-participant deferral and match recalculation on the shared grid (A-05-T32
    contract first, DEC-2258): 501 until the recalculation service lands."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    _not_yet()


@router.get("/ebp/late-remittances", action="ebp.read", response_model=list[LateRemittanceOut])
async def ebp_late_remittances_route(work_item_id: UUID, ctx: Ctx) -> list[LateRemittanceOut]:
    """The late remittances (DF-34): one row per late payroll, as code computed it (A-05-T30)."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_remittances

    return [_late_out(r) for r in await ebp_remittances.late_remittances(ctx.tenant, work_item_id)]


def _late_out(r: object) -> LateRemittanceOut:
    from abacus.modules.assurance.ebp_remittances import LateRemittance

    found = cast(LateRemittance, r)
    return LateRemittanceOut(
        id=found.id,
        payroll_date=found.payroll_date,
        deposited_on=found.deposited_on or found.payroll_date,
        amount=found.principal,
        business_days=found.business_days,
        calendar_days=found.calendar_days,
        # The practice is the due date's lag: the payroll's lag less the days it ran late.
        established_practice_days=max(found.business_days - found.business_days_late, 0),
        lost_earnings=found.lost_earnings or Decimal(0),
        status=cast(Any, found.status),  # Any: 0658's CHECK holds the words
        form_5330=cast(Any, found.form_5330),  # Any: mapped from 0658's words
    )


@router.get("/ebp/schedule-h-4a", action="ebp.read", response_model=FiguresOut)
async def ebp_schedule_4a_route(work_item_id: UUID, ctx: Ctx) -> FiguresOut:
    """The line 4a preview: the late deferrals by code, one row per late remittance (A-05-T30)."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_remittances

    rows = await ebp_remittances.late_remittances(ctx.tenant, work_item_id)
    return _figures(
        "Schedule H line 4a",
        [
            (
                f"late_{r.payroll_date:%Y%m%d}",
                f"Payroll {r.payroll_date:%b %-d, %Y}",
                str(r.principal),
            )
            for r in rows
        ],
        str(ebp_remittances.schedule_h_4a(rows)),
    )


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
    """A person records the correction with evidence (EBP-04 f; A-05-T30): 422
    `correction_evidence_required`, 409 `already_corrected`."""
    await _gate(ctx, work_item_id, "ebp_correction.record", _E)
    from abacus.modules.assurance import ebp_remittances

    event_id = await ebp_remittances.record_correction(
        ctx,
        work_item_id,
        remittance_id,
        lost_earnings_deposited_on=body.lost_earnings_deposited_on,
        scc_notice_on=body.scc_notice_on,
        form_5330_status=body.form_5330_status,
        evidence_version_ids=body.evidence_version_ids,
    )
    return AcceptedOut(id=event_id)


# EBP-05, 06, 08, 09
@router.get("/ebp/loans/rollforward", action="ebp.read", response_model=FiguresOut)
async def ebp_loans_route(work_item_id: UUID, ctx: Ctx) -> FiguresOut:
    await _gate(ctx, work_item_id, "ebp.read", _E)
    return _figures(
        "Notes receivable from participants",
        [("notes_eoy", "End of year", "312400.00")],
        "312400.00",
    )


@router.get("/ebp/investments", action="ebp.read", response_model=InvestmentsOut, errors=(409,))
async def ebp_investments_route(
    work_item_id: UUID,
    ctx: Ctx,
    layer: Annotated[Literal["unadjusted", "aje", "rje", "final"], Query()] = "final",
) -> InvestmentsOut:
    """Lines by layer (C9/C8); Final is 409 `layer_unavailable` until A-06 registers."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_investments

    item = await assurance_item(ctx.tenant, work_item_id)
    view = await ebp_investments.investments(ctx.tenant, item.engagement_id, work_item_id, layer)
    found = view.agreement
    rows = [
        InvestmentRowOut(
            key=a.line_key,
            label=a.fund_name,
            level=cast(Any, a.level),  # Any: the column's CHECK holds the three levels
            trust_eoy=a.trust_eoy,
            trust_boy=a.trust_boy,
            tb_eoy=a.tb_eoy,
            tb_boy=a.tb_boy,
            ties=a.ties,
            off_by=a.off_by,
        )
        for a in found.lines
    ] + [
        InvestmentRowOut(key=code, label=name, level="other", tb_eoy=amount)
        for code, name, amount in view.extra
    ]
    return InvestmentsOut(
        layer=layer,
        rows=rows,
        investments_eoy=found.investments_eoy,
        investments_boy=found.investments_boy,
        level1_eoy=found.level1_eoy,
        nav_eoy=found.nav_eoy,
        net_assets=view.net_assets,
        tb_balanced=view.tb_balanced,
        py_ties=found.py_ties,
        points=[_point_out(p) for p in view.points],
        hold_reason="certification_unevaluated" if view.unevaluated else None,
        unevaluated=view.unevaluated,
        engine_version=found.engine_version,
        inputs_hash=found.inputs_hash,
        allowed_actions=[],
    )


def _point_out(p: object) -> CertificationPointOut:
    point = cast(Any, p)  # Any: ebp_investments.Point, imported where the route runs
    return CertificationPointOut(
        key=point.key,
        proposed_answer=point.proposed_answer,
        citation_id=point.citation_id,
        answer=point.answer,
        note=point.note,
    )


@router.get(
    "/ebp/certification",
    action="ebp.read",
    response_model=list[CertificationPointOut],
)
async def ebp_certification_read_route(
    work_item_id: UUID, ctx: Ctx
) -> list[CertificationPointOut]:
    """The six points in order; a point nobody evaluated reads `not_evaluated`."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_investments

    return [_point_out(p) for p in await ebp_investments.points(ctx.tenant, work_item_id)]


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
    errors=(409,),
)
async def ebp_certification_route(
    work_item_id: UUID,
    point_key: Annotated[str, Path(pattern=r"^[a-z0-9_]{1,40}$")],
    body: CertificationPointIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> AcceptedOut:
    """A person evaluates a certification point (29 CFR 2520.103-8; A-05-T39)."""
    await _gate(ctx, work_item_id, "ebp_certification.evaluate", _E)
    from abacus.modules.assurance import ebp_investments

    return AcceptedOut(
        id=await ebp_investments.evaluate_point(
            ctx, work_item_id, point_key, body.answer, body.note
        )
    )


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

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

import re
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
from abacus.modules.assurance import (
    aud27,  # A-05-T53: the AUD-27 service
    ebp_provisions,
    ebp_schedule_render,  # A-05-T58 remainder: the 4i schedule through C11
)
from abacus.modules.assurance.compute.ebp.accounts import Group as AccountGroup
from abacus.modules.assurance.ebp_form5500 import (
    form5500_view,
    key_line_value,
    schedule_4i_view,
)
from abacus.modules.assurance.ebp_imports import ImportView, Ties, import_of, import_source
from abacus.modules.assurance.ebp_participants import DOB_MASK, participants_of
from abacus.modules.assurance.ebp_participants import reveal as reveal_participant_field
from abacus.modules.assurance.tb_mapping_contract import SignOffChipOut
from abacus.modules.engagements.api import assurance_item, get_ref, work_item_period
from abacus.modules.evidence.api import citation_display
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
from abacus.modules.platform.api import entitlement

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


class ConflictSourceOut(BaseModel):
    """EBP-02 c: the document that disagrees (A-05-T17; DEC-2487): the viewer opens on it."""

    model_config = ConfigDict(frozen=True)

    evidence_version_id: Annotated[UUID, classified("internal")]
    # "The SPD (2025, p. 6) says entry is on the first day of each calendar quarter."
    note: Annotated[str, Field(max_length=500), classified("confidential")]


class PlanReviewDiffOut(BaseModel):
    """EBP-02 b2's ribbon: what the current version adds to this earlier one, from code."""

    model_config = ConfigDict(frozen=True)

    current_version_no: Annotated[int, Field(ge=1), classified("internal")]
    added_labels: Annotated[list[str], Field(max_length=200), classified("internal")]


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
    conflict_source: Annotated[ConflictSourceOut | None, classified("confidential")] = None


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
    version_diff: Annotated[PlanReviewDiffOut | None, classified("internal")] = None


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

    # A-05-T58 close (DEC-2820): every Part IV line 4a to 4m, additively; code checks 4a against
    # the late remittances, and a line no check covers reads `not_checked`.
    line: Annotated[
        Literal["4a", "4b", "4c", "4d", "4e", "4f", "4g", "4h", "4i", "4j", "4k", "4l", "4m"],
        classified("internal"),
    ]
    draft_answer: Annotated[Literal["yes", "no"] | None, classified("internal")]
    draft_amount: MaybeMoney
    consistency: Annotated[
        Literal["consistent", "inconsistent", "not_checked"], classified("internal")
    ]
    basis: Label


class Form5500RowOut(BaseModel):
    """A-05-T58 (DEC-2814): one Schedule H line with both sides, the code's difference and its
    classification; `match_id` lights the row and the draft's form field together."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    line_code: Annotated[str, Field(max_length=20), classified("internal")]
    caption: Label
    fs_amount: MaybeMoney
    f5500_amount: MaybeMoney
    difference: MaybeMoney
    classification: Annotated[
        Literal["tie", "reconciling_item", "inconsistent"] | None, classified("internal")
    ]
    note_ref: Annotated[str | None, Field(max_length=40), classified("internal")] = None
    match_id: Annotated[str | None, classified("internal")] = None


class Form5500Out(BaseModel):
    model_config = ConfigDict(frozen=True)

    draft_received: Annotated[bool, classified("internal")]
    lines: Annotated[list[FigureRowOut], Field(max_length=200), classified("confidential")]
    part_iv: Annotated[list[PartIvLineOut], Field(max_length=20), classified("confidential")]
    allowed_actions: Actions
    # A-05-T58 (DEC-2814), additive: the tie-out rows with both sides, and the draft's id.
    rows: Annotated[list[Form5500RowOut], Field(max_length=200), classified("confidential")] = (
        Field(default_factory=list[Form5500RowOut])
    )
    draft_id: Annotated[UUID | None, classified("internal")] = None
    evidence_version_id: Annotated[UUID | None, classified("internal")] = None


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


class AccountGroupOut(BaseModel):
    """EBP-08's statement row; `crossfoots` by code."""

    model_config = ConfigDict(frozen=True)

    status: Label
    participants: Annotated[int, classified("internal")]
    beginning: Money
    contributions: Money
    earnings: Money
    distributions: Money
    fees: Money
    transfers: Money
    ending: Money
    crossfoots: Annotated[bool, classified("internal")]


class AccountTieOut(BaseModel):
    """A tie to another screen; `ties` is None when that side can't be read yet."""

    model_config = ConfigDict(frozen=True)

    key: Label
    expected: MaybeMoney
    actual: Money
    ties: Annotated[bool | None, classified("internal")]


class AccountRollforwardOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    groups: Annotated[list[AccountGroupOut], Field(max_length=20), classified("confidential")]
    total: Annotated[AccountGroupOut, classified("confidential")]
    transfers_net_zero: Annotated[bool, classified("internal")]
    ties: Annotated[list[AccountTieOut], Field(max_length=20), classified("confidential")]
    forfeiture_account: Money
    inputs_hash: Annotated[str, classified("internal")]
    engine_version: Annotated[str, classified("internal")]
    allowed_actions: Actions


class AccountRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    participant_key: Annotated[str, classified("internal")]
    name: Annotated[str, classified("confidential")]
    identifier_mask: Annotated[str | None, classified("confidential")]
    beginning: Money
    contributions: Money
    earnings: Money
    distributions: Money
    fees: Money
    transfers: Money
    ending: Money


class AccountRowsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[AccountRowOut], Field(max_length=5000), classified("confidential")]


class SdbaRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    security_type: Label
    market_value: Money


class SdbaOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    rows: Annotated[list[SdbaRowOut], Field(max_length=100), classified("confidential")]
    total: Money
    per_trust: MaybeMoney


class VestingRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    participant_key: Annotated[str, classified("internal")]
    name: Annotated[str, classified("confidential")]
    identifier_mask: Annotated[str | None, classified("confidential")]
    termination_on: Annotated[date, classified("internal")]
    years_of_service: Annotated[Decimal | None, classified("confidential")]
    vested_pct: Annotated[Decimal | None, classified("confidential")]
    agrees: Annotated[bool | None, classified("internal")]


class VestingOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    rows: Annotated[list[VestingRowOut], Field(max_length=500), classified("confidential")]
    forfeitures_arising: Money


class EbpRunStartedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: Annotated[UUID, classified("internal")]


class ExpenseRowOut(BaseModel):
    """One expense with Sheet!Cell-citable amounts; `exception` by code (no 408(b)(2) on file)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    provider_id: Annotated[UUID | None, classified("internal")] = None
    line_key: Annotated[str, Field(max_length=80), classified("internal")]
    description: Label
    disclosure_citation_id: Annotated[UUID | None, classified("internal")] = None
    citation_id: Annotated[UUID | None, classified("internal")] = None
    invoiced: MaybeMoney = None
    credits: MaybeMoney = None
    paid_from_plan: MaybeMoney = None
    schedule_h_line: Annotated[Literal["2i(1)", "2i(2)", "2i(3)", "2i(4)"], classified("internal")]
    exception: Annotated[bool, classified("internal")] = False
    # A-05-T45 (additive): the grid's Provider and 408(b)(2) words, and each cell's citations.
    provider_name: Annotated[str | None, classified("confidential")] = None
    disclosure_text: Annotated[str | None, classified("confidential")] = None
    citation_labels: Annotated[list[str], Field(max_length=20), classified("confidential")] = (
        Field(default_factory=list[str])
    )


class ExpensesOut(BaseModel):
    """EBP-09 a: 38,400 = 2i(1) 6,000 + 2i(2) 32,400; 41,500 - 3,100."""

    model_config = ConfigDict(frozen=True)

    rows: Annotated[list[ExpenseRowOut], Field(max_length=500), classified("confidential")]
    invoiced: MaybeMoney = None
    credits: MaybeMoney = None
    paid_from_plan: MaybeMoney = None
    line_2i1: MaybeMoney = None
    line_2i2: MaybeMoney = None
    line_2i3: MaybeMoney = None
    line_2i4: MaybeMoney = None
    invoices_tie: Annotated[bool, classified("internal")]
    exceptions: Annotated[int, classified("internal")]
    engine_version: Annotated[str, Field(max_length=40), classified("internal")]
    inputs_hash: Annotated[str, Field(max_length=64), classified("internal")]


class ComplianceTestOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    test_key: Annotated[str, Field(max_length=80), classified("internal")]
    plan_year: Annotated[int, classified("internal")]
    limit: MaybeMoney = None
    limit_ref: Annotated[str | None, Field(max_length=120), classified("internal")] = None
    result: Annotated[Literal["pass", "exception", "exempt", "proposed"], classified("internal")]
    accepted: Annotated[bool, classified("internal")]


class QualificationFactOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    fact_key: Annotated[str, Field(max_length=80), classified("internal")]
    value: Annotated[str | None, Field(max_length=500), classified("confidential")] = None
    result: Annotated[Literal["consistent", "exception", "not_evaluated"], classified("internal")]
    citation_id: Annotated[UUID | None, classified("internal")] = None
    accepted: Annotated[bool, classified("internal")]


class SupportPrefillOut(BaseModel):
    """SHL-14's prefill: identifiers only. Nothing is sent by this route."""

    model_config = ConfigDict(frozen=True)

    provider_id: Annotated[UUID | None, classified("internal")] = None
    expense_line_key: Annotated[str, Field(max_length=80), classified("internal")]
    request_kind: Annotated[Literal["tpa_support"], classified("internal")]


class LoanRowOut(BaseModel):
    """One participant loan with its rollforward and, for a new loan, its IRC 72(p) limit."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    participant_key: Annotated[str, Field(max_length=40), classified("confidential")]
    loan_ref: Annotated[str, Field(max_length=40), classified("internal")]
    status: Annotated[Literal["active", "new", "paid_off", "offset"], classified("internal")]
    originated_on: Annotated[date | None, classified("confidential")] = None
    term_months: Annotated[int | None, classified("internal")] = None
    is_residence: Annotated[bool, classified("internal")] = False
    vested_balance: MaybeMoney = None
    beginning: MaybeMoney = None
    new: MaybeMoney = None
    repayments: MaybeMoney = None
    offsets: MaybeMoney = None
    ending: MaybeMoney = None
    limit: MaybeMoney = None
    within_limit: Annotated[bool | None, classified("internal")] = None
    # A-05-T44 (additive): the name the recordkeeper reports; the census's SSN stays masked.
    participant_name: Annotated[str | None, classified("confidential")] = None


class LoansOut(BaseModel):
    """EBP-05 a: 288,500 + 96,200 - 57,450 - 14,850 = 312,400; 41 + 5 - 7 - 3 = 36."""

    model_config = ConfigDict(frozen=True)

    beginning: MaybeMoney = None
    new: MaybeMoney = None
    repayments: MaybeMoney = None
    offsets: MaybeMoney = None
    ending: MaybeMoney = None
    foots: Annotated[bool, classified("internal")]
    count_beginning: Annotated[int, classified("internal")]
    count_new: Annotated[int, classified("internal")]
    count_paid_off: Annotated[int, classified("internal")]
    count_offset: Annotated[int, classified("internal")]
    count_ending: Annotated[int, classified("internal")]
    comparative_agrees: Annotated[bool, classified("internal")]
    comparative_off_by: MaybeMoney = None
    part_iv_4b: Annotated[Literal["no"], classified("internal")]
    rows: Annotated[list[LoanRowOut], Field(max_length=2000), classified("confidential")]
    engine_version: Annotated[str, Field(max_length=40), classified("internal")]
    inputs_hash: Annotated[str, Field(max_length=64), classified("internal")]


class LoanOffsetOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    loan_ref: Annotated[str, Field(max_length=40), classified("internal")]
    offset_on: Annotated[date, classified("confidential")]
    amount: MaybeMoney = None
    form_1099r_code: Annotated[str | None, Field(max_length=2), classified("internal")] = None
    reported_line: Annotated[Literal["2e(1)"], classified("internal")]
    # A-05-T44 (additive).
    participant_name: Annotated[str | None, classified("confidential")] = None
    terminated_on: Annotated[date | None, classified("confidential")] = None


class LoanOffsetsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    rows: Annotated[list[LoanOffsetOut], Field(max_length=2000), classified("confidential")]
    total: MaybeMoney = None


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
    proposed_answer: Annotated[str | None, Field(max_length=500), classified("confidential")] = (
        None
    )
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
    # DEC-2319: "Total mutual funds & CITs", code's, so the screen does no arithmetic.
    funds_eoy: MaybeMoney = None
    funds_boy: MaybeMoney = None
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


class Aud27MethodOut(BaseModel):
    """The method card's tie: components against the balance, code's (A-05-T53)."""

    model_config = ConfigDict(frozen=True)

    components_total: Money
    difference: Money
    ties: Annotated[bool, classified("internal")]


class Aud27ComponentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: Annotated[str, Field(max_length=300), classified("confidential")]
    amount: Money


class Aud27RollforwardOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    opening: Money
    usage: Money
    additions: Money
    computed_closing: Money
    ties: Annotated[bool, classified("internal")]
    # S31 close (DV-AUD-27-3): the rollforward's period, the work item's start and end.
    opening_on: Annotated[date | None, classified("internal")] = None
    closing_on: Annotated[date | None, classified("internal")] = None


class Aud27TransactionOut(BaseModel):
    """S31 close (DV-AUD-27-2): one thing the plan did with a party in interest in the year, as a
    person recorded it."""

    model_config = ConfigDict(frozen=True)

    description: Annotated[str, Field(max_length=300), classified("confidential")]
    amount: MaybeMoney


class Aud27RetrospectiveOut(BaseModel):
    """A prior-year estimate against its outcome ("over by $14,000.00, 3.4%")."""

    model_config = ConfigDict(frozen=True)

    label: Annotated[str, Field(max_length=120), classified("confidential")]
    prior_estimate: Money
    outcome: Money
    difference: Money
    percent: Annotated[Decimal, classified("internal")]
    direction: Annotated[Literal["over", "under", "exact"], classified("internal")]


class Aud27RangeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    low: Money
    high: Money
    inside: Annotated[bool, classified("internal")]


class Aud27ItemOut(BaseModel):
    model_config = _ex(_ESTIMATE)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, Field(max_length=300), classified("confidential")]
    amount: MaybeMoney
    status: Annotated[AudItemStatus, classified("internal")]
    # "Evaluated · pending EP" is a display variant of evaluated.
    pending_ep: Annotated[bool, classified("internal")]
    # A-05-T57 (DEC-2813), additive: what AUD-27's rows and cards show, from A-05-T53's views.
    account_ref: Annotated[str | None, Field(max_length=40), classified("internal")] = None
    significant_risk: Annotated[bool, classified("internal")] = False
    method_text: Annotated[str | None, Field(max_length=500), classified("confidential")] = None
    disclosure_ref: Annotated[str | None, Field(max_length=200), classified("confidential")] = None
    components: Annotated[
        list[Aud27ComponentOut], Field(max_length=50), classified("confidential")
    ] = Field(default_factory=list[Aud27ComponentOut])
    method: Annotated[Aud27MethodOut | None, classified("confidential")] = None
    rollforward: Annotated[Aud27RollforwardOut | None, classified("confidential")] = None
    retrospectives: Annotated[
        list[Aud27RetrospectiveOut], Field(max_length=10), classified("confidential")
    ] = Field(default_factory=list[Aud27RetrospectiveOut])
    range: Annotated[Aud27RangeOut | None, classified("confidential")] = None
    # A possible bias: every retrospective difference points the same way (AU-C 540.A133).
    bias: Annotated[Literal["none", "possible"] | None, classified("internal")] = None
    # Related parties: where the candidate came from, the relationship, the finding it raised.
    source: Annotated[str | None, Field(max_length=40), classified("internal")] = None
    relationship: Annotated[str | None, Field(max_length=300), classified("confidential")] = None
    finding_id: Annotated[UUID | None, classified("internal")] = None
    # Parties in interest (EBP): the ERISA relationship, exemption and reporting line.
    exemption: Annotated[str | None, Field(max_length=200), classified("confidential")] = None
    reporting: Annotated[str | None, Field(max_length=200), classified("confidential")] = None
    transactions: Annotated[
        list[Aud27TransactionOut], Field(max_length=50), classified("confidential")
    ] = Field(default_factory=list[Aud27TransactionOut])
    # S31 close (A-05-T57, DV-AUD-27-2): a related party's disclosure as a person recorded it;
    # `disclosure_note` says it names a note in the statements (a link to AUD-20).
    disclosure: Annotated[str | None, Field(max_length=300), classified("confidential")] = None
    disclosure_note: Annotated[bool, classified("internal")] = False
    # A screened-out candidate's reason, as the person gave it (the Disclosure column reads it).
    screened_out_reason: Annotated[
        str | None, Field(max_length=1000), classified("confidential")
    ] = None


class Aud27ProhibitedOut(BaseModel):
    """AUD-27 c's card: the late remittance as a prohibited transaction, read from EBP-04."""

    model_config = ConfigDict(frozen=True)

    late_remittance_id: Annotated[UUID, classified("internal")]
    principal: MaybeMoney
    deposited_on: Annotated[date | None, classified("internal")] = None
    business_days_late: Annotated[int | None, classified("internal")] = None
    lost_earnings: MaybeMoney
    # The late remittance's own words (EBP-04's `LateRemittanceOut`; S31 end pass: enums).
    correction_status: Annotated[
        Literal["found", "pending_vfcp_scc", "corrected"] | None, classified("internal")
    ] = None
    form_5330_status: Annotated[
        Literal["exposure", "not_required", "filed"] | None, classified("internal")
    ] = None
    # S31 close (DV-AUD-27-6): EBP-04's code-computed excise exposure on the lost earnings.
    excise_exposure: MaybeMoney = None


class Aud27ListOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[Aud27ItemOut], Field(max_length=200), classified("confidential")]
    allowed_actions: Actions
    # A-05-T57 (DEC-2813): the parties-in-interest read carries the prohibited transactions.
    prohibited: Annotated[list[Aud27ProhibitedOut], classified("confidential")] = Field(
        default_factory=list[Aud27ProhibitedOut]
    )


class Aud27TransactionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: Annotated[str, Field(min_length=1, max_length=300), classified("confidential")]
    amount: MaybeMoney = None


class Aud27ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=300), classified("confidential")]
    # S31 close, additive: a party in interest's ERISA relationship (required for one), its
    # exemption, its Form 5500 reporting line and the year's transactions.
    relationship: Annotated[str | None, Field(max_length=200), classified("confidential")] = None
    exemption: Annotated[str | None, Field(max_length=200), classified("confidential")] = None
    reporting: Annotated[str | None, Field(max_length=200), classified("confidential")] = None
    transactions: Annotated[
        list[Aud27TransactionIn], Field(max_length=50), classified("confidential")
    ] = Field(default_factory=list[Aud27TransactionIn])


class RelatedPartyActivityIn(BaseModel):
    """S31 close (A-05-T57): a related party's year transactions and its disclosure, recorded by a
    person; recording again replaces them."""

    model_config = ConfigDict(extra="forbid")

    transactions: Annotated[
        list[Aud27TransactionIn], Field(max_length=50), classified("confidential")
    ] = Field(default_factory=list[Aud27TransactionIn])
    disclosure: Annotated[
        str | None, Field(min_length=1, max_length=300), classified("confidential")
    ] = None
    disclosure_note: Annotated[bool, classified("internal")] = False


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
    state: Annotated[
        Literal["not_started", "agent_tested", "needs_human", "pass", "exception", "no_effect"],
        classified("internal"),
    ]
    cells: Annotated[list[TestGridCellOut], classified("internal")]
    # EBP-04 c: the EBP-03 sample item the same participant's exception traces to.
    linked_item_id: Annotated[UUID | None, classified("internal")] = None
    # EBP-05 b (A-05-T44, additive): a distribution's type and its 1099-R code.
    detail: Annotated[str | None, classified("confidential")] = None
    code: Annotated[str | None, Field(max_length=20), classified("internal")] = None


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
    census_hire: Annotated[date | None, classified("confidential")]  # None: not on the census
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


class EntryRuleOut(BaseModel):
    """The entry rule EBP-03 computed from: the verified provisions' (A-05-T16; DEC-2482). While it
    is `unverified` or `unreadable` the ages and months are null and no row has an entry date."""

    model_config = ConfigDict(frozen=True)

    state: Annotated[Literal["verified", "unverified", "unreadable"], classified("internal")]
    minimum_age: Annotated[int | None, Field(ge=0, le=99), classified("internal")] = None
    service_months: Annotated[int | None, Field(ge=0, le=99), classified("internal")] = None


class EligibilitySampleOut(BaseModel):
    """EBP-03's sample read: the rows, the tallies and the rungs the header shows."""

    model_config = ConfigDict(frozen=True)

    test_id: Annotated[UUID | None, classified("internal")]  # None: no test yet, so no rows
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    rows: Annotated[list[EligibilitySampleRowOut], classified("confidential")]
    exceptions: Annotated[int, Field(ge=0), classified("internal")]
    needs_human: Annotated[int, Field(ge=0), classified("internal")]
    prepared_by: Annotated[str | None, Field(max_length=4), classified("internal")] = None
    reviewed_by: Annotated[str | None, Field(max_length=4), classified("internal")] = None
    allowed_actions: Annotated[list[str], classified("internal")]
    # DEC-2328: the paper an exception's AUD-15 draft finding sits on.
    workpaper_id: Annotated[UUID | None, classified("internal")] = None
    entry_rule: Annotated[EntryRuleOut, classified("internal")]


CorrectionWord = Literal["found", "pending_vfcp_scc", "corrected"]
Form5330Word = Literal["exposure", "not_required", "filed"]


def _correction_word(stored: str | None) -> CorrectionWord | None:
    """0658's CHECK holds exactly these words."""
    return cast("CorrectionWord | None", stored)


def _form_5330_word(stored: str | None) -> Form5330Word | None:
    """0658's words, mapped to the API's (PTE 2002-51 reads "not_required")."""
    found = "not_required" if stored == "not_required_pte_2002_51" else stored
    return cast("Form5330Word | None", found)


async def _gate(ctx: AuthContext, work_item_id: UUID, action: str, flag: Flag) -> None:
    """A person only, never a client principal; the action on the work item's engagement; the
    flag; the `ebp_audits` entitlement. Authorised first, so no one learns a flag or entitlement
    state they may not use."""
    if ctx.client:
        raise NotFound("ebp")
    if ctx.tenant.actor_kind != "human" and not action.endswith(".read") and action != "ebp.read":
        raise Forbidden(action, "role")
    item = await assurance_item(ctx.tenant, work_item_id)
    ref = await get_ref(ctx, item.engagement_id)
    await authorise(ctx, action, ref.resource())
    if not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)
    # A-05-T49 (ADR P-28): the EBP module is an entitlement; for a real firm it also needs the
    # signed CPA memo (DEC-2603).
    if await entitlement(ctx.tenant, "ebp_audits") is None:
        raise NotFound("ebp_audits")


def _not_yet() -> NoReturn:
    raise NotImplementedYet


def _account_group(group: AccountGroup) -> AccountGroupOut:
    return AccountGroupOut(
        status=group.status,
        participants=group.participants,
        beginning=group.beginning,
        contributions=group.contributions,
        earnings=group.earnings,
        distributions=group.distributions,
        fees=group.fees,
        transfers=group.transfers,
        ending=group.ending,
        crossfoots=group.crossfoots,
    )


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
        version_diff=(
            None
            if found.version_diff is None
            else PlanReviewDiffOut(
                current_version_no=found.version_diff.current_no,
                added_labels=list(found.version_diff.added_labels),
            )
        ),
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
)
async def ebp_eligibility_sample_route(work_item_id: UUID, ctx: Ctx) -> EligibilitySampleOut:
    """EBP-03's grid (A-05-T23, DEC-2225, DEC-2328): rows in A-03's order; none before a test."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_eligibility_sample

    return await ebp_eligibility_sample.sample(ctx, work_item_id)


# EBP-04
@router.get("/ebp/contributions/reconciliation", action="ebp.read", response_model=FiguresOut)
async def ebp_contributions_route(work_item_id: UUID, ctx: Ctx) -> FiguresOut:
    """EBP-04 a's waterfall by code, register to statements (A-05-T30, T31; DEC-2361). Keys are
    the screen's; `tie.*` rows appear only when the tie holds. W-3's waits on its figure."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_investments, ebp_remittances
    from abacus.modules.engagements.api import engagement_metadata

    item = await assurance_item(ctx.tenant, work_item_id)
    year_end = (await engagement_metadata(ctx, item.engagement_id)).engagement.fiscal_period_end
    per_statements = await ebp_investments.contributions_per_statements(
        ctx.tenant, item.engagement_id
    )
    found = await ebp_remittances.reconciliation(
        ctx.tenant, work_item_id, year_end, per_statements
    )

    def tie(key: str, label: str, holds: bool | None) -> list[FigureRowOut]:
        return [FigureRowOut(key=key, label=label, amount=None, status="tie")] if holds else []

    def row(key: str, label: str, amount: Decimal) -> FigureRowOut:
        return FigureRowOut(key=key, label=label, amount=amount)

    payroll = found.deferrals + found.match
    return FiguresOut(
        title="Contributions per financial statements",
        rows=[
            *tie("tie.payroll_trust", "Payroll → trust", found.trust_ties),
            *tie("tie.trust_fs", "Trust → FS", found.ties),
            row("deferrals", "Participant deferrals per payroll register", found.deferrals),
            row("match", "Employer match per payroll calculation", found.match),
            row("total_payroll", "Total per payroll", payroll),
            row("less_late", "Less deposited after year end", -found.total),
            row("trust_receipts", "Payroll-sourced receipts per trust", found.trust_receipts),
            row("rollovers", "Rollover contributions", found.rollovers),
            row(
                "total_trust",
                "Contributions per trust report",
                found.trust_receipts + found.rollovers,
            ),
            row("receivable_regular", "Contributions receivable: regular payroll", found.regular),
            row("receivable_late", "Contributions receivable: late deposit", found.late),
        ],
        total=found.reconciled,
        allowed_actions=[],
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
    contract first, DEC-2258; live with DEC-2356)."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_tests

    return await ebp_tests.contribution_recalc(ctx, work_item_id)


@router.get(
    "/ebp/distributions/test", action="ebp.read", response_model=TestGridOut, errors=(501,)
)
async def ebp_distributions_test_route(work_item_id: UUID, ctx: Ctx) -> TestGridOut:
    """EBP-05 b: the 10 sampled distributions on the shared grid (A-05-T44, contract first). Its
    service joins with the sampled-distributions read; until then 501 and the screen's fixture."""
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
@router.get("/ebp/loans/rollforward", action="ebp.read", response_model=LoansOut)
async def ebp_loans_route(work_item_id: UUID, ctx: Ctx) -> LoansOut:
    """EBP-05 by code: rollforward, counts, the PY comparative; offsets are line 2e(1)."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_loans

    py = await ebp_loans.py_notes_receivable(ctx.tenant, work_item_id)
    view = await ebp_loans.loans(ctx.tenant, work_item_id, py)
    rolled = view.rollforward
    return LoansOut(
        beginning=rolled.beginning,
        new=rolled.new,
        repayments=rolled.repayments,
        offsets=rolled.offsets,
        ending=rolled.ending,
        foots=rolled.foots,
        count_beginning=rolled.count_beginning,
        count_new=rolled.count_new,
        count_paid_off=rolled.count_paid_off,
        count_offset=rolled.count_offset,
        count_ending=rolled.count_ending,
        comparative_agrees=view.comparative.agrees,
        comparative_off_by=view.comparative.off_by,
        part_iv_4b="no",
        rows=[_loan_out(r) for r in view.rows],
        engine_version=rolled.engine_version,
        inputs_hash=rolled.inputs_hash,
    )


def _loan_out(r: object) -> LoanRowOut:
    row = cast(Any, r)  # Any: ebp_loans.LoanRow, imported where the route runs
    return LoanRowOut(
        participant_name=row.participant_name,
        id=row.id,
        participant_key=row.participant_key,
        loan_ref=row.loan_ref,
        status=row.status,
        originated_on=row.originated_on,
        term_months=row.term_months,
        is_residence=row.is_residence,
        vested_balance=row.vested_balance,
        beginning=row.loan.beginning,
        new=row.loan.new,
        repayments=row.loan.repayments,
        offsets=row.loan.offsets,
        ending=row.loan.ending,
        limit=row.limit.limit if row.limit else None,
        within_limit=row.limit.within if row.limit else None,
    )


@router.get("/ebp/loans/new", action="ebp.read", response_model=list[LoanRowOut])
async def ebp_loans_new_route(work_item_id: UUID, ctx: Ctx) -> list[LoanRowOut]:
    """The year's new loans, each with its IRC 72(p) limit by code."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_loans

    view = await ebp_loans.loans(ctx.tenant, work_item_id, None)
    return [_loan_out(r) for r in view.rows if r.loan.new > 0]


@router.get("/ebp/loans/offsets", action="ebp.read", response_model=LoanOffsetsOut)
async def ebp_loans_offsets_route(work_item_id: UUID, ctx: Ctx) -> LoanOffsetsOut:
    """Offsets: distributions on Schedule H line 2e(1), line 2g stays 0."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_loans

    view = await ebp_loans.loans(ctx.tenant, work_item_id, None)
    return LoanOffsetsOut(
        rows=[
            LoanOffsetOut(
                participant_name=o.participant_name,
                terminated_on=o.terminated_on,
                loan_ref=o.loan_ref,
                offset_on=o.offset_on,
                amount=o.amount,
                form_1099r_code=o.form_1099r_code,
                reported_line="2e(1)",
            )
            for o in view.offsets
        ],
        total=view.offsets_total,
    )


@router.get(
    "/ebp/participants/{participant_key}/loan",
    action="ebp.read",
    response_model=list[LoanRowOut],
)
async def ebp_participant_loan_route(
    work_item_id: UUID,
    participant_key: Annotated[str, Path(pattern=r"^[A-Za-z0-9-]{1,40}$")],
    ctx: Ctx,
) -> list[LoanRowOut]:
    """The EBP-05 drawer's loans."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_loans

    return [
        _loan_out(r)
        for r in await ebp_loans.participant_loan(ctx.tenant, work_item_id, participant_key)
    ]


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
        funds_eoy=found.funds_eoy,
        funds_boy=found.funds_boy,
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


@router.get(
    "/ebp/participant-accounts/rollforward",
    action="ebp.read",
    response_model=AccountRollforwardOut,
)
async def ebp_participant_accounts_route(work_item_id: UUID, ctx: Ctx) -> AccountRollforwardOut:
    """EBP-08 d: by status, crossfooted and footed by code, with ties to EBP-04, 05, 06, 09."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_accounts, ebp_expenses

    expenses = await ebp_expenses.plan_expenses(ctx.tenant, work_item_id)
    view = await ebp_accounts.accounts(ctx.tenant, work_item_id, fees_paid=expenses.tie.paid)
    roll = view.rollforward
    return AccountRollforwardOut(
        groups=[_account_group(g) for g in roll.groups],
        total=_account_group(roll.total),
        transfers_net_zero=roll.transfers_net_zero,
        ties=[
            AccountTieOut(key=t.key, expected=t.expected, actual=t.actual, ties=t.ties)
            for t in view.ties
        ],
        forfeiture_account=view.forfeiture_account,
        inputs_hash=roll.inputs_hash,
        engine_version=roll.engine_version,
        allowed_actions=[],
    )


@router.get(
    "/ebp/participant-accounts/groups/{group}/accounts",
    action="ebp.read",
    response_model=AccountRowsOut,
)
async def ebp_account_group_route(
    work_item_id: UUID, group: Annotated[str, Path(max_length=20)], ctx: Ctx
) -> AccountRowsOut:
    """The participant drill (O2). Masked SSNs only; an unknown group answers 404."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_accounts

    rows = await ebp_accounts.group_accounts(ctx.tenant, work_item_id, group)
    return AccountRowsOut(
        items=[
            AccountRowOut(
                participant_key=r.participant_key,
                name=r.name,
                identifier_mask=r.ssn_mask,
                beginning=r.account.beginning,
                contributions=r.account.contributions,
                earnings=r.account.earnings,
                distributions=r.account.distributions,
                fees=r.account.fees,
                transfers=r.account.transfers,
                ending=r.account.ending,
            )
            for r in rows
        ]
    )


@router.get("/ebp/participant-accounts/sdba", action="ebp.read", response_model=SdbaOut)
async def ebp_sdba_route(work_item_id: UUID, ctx: Ctx) -> SdbaOut:
    """EBP-08 b: 924,300 + 612,450 + 68,250 = 1,605,000 by code; ties to EBP-06."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_accounts

    by_type, total, trust = await ebp_accounts.sdba(ctx.tenant, work_item_id)
    return SdbaOut(
        rows=[SdbaRowOut(security_type=k, market_value=v) for k, v in sorted(by_type.items())],
        total=total,
        per_trust=trust,
    )


@router.get("/ebp/participant-accounts/vesting", action="ebp.read", response_model=VestingOut)
async def ebp_vesting_route(work_item_id: UUID, ctx: Ctx) -> VestingOut:
    """EBP-08 c: the plan year's terminations (DF-34) and the forfeitures arising."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_accounts

    rows, forfeitures = await ebp_accounts.vesting(
        ctx.tenant, work_item_id, await _plan_year(ctx, work_item_id)
    )
    return VestingOut(
        rows=[
            VestingRowOut(
                participant_key=r.participant_key,
                name=r.name,
                identifier_mask=r.ssn_mask,
                termination_on=r.termination_on,
                years_of_service=r.years_of_service,
                vested_pct=r.vested_pct,
                agrees=r.agrees,
            )
            for r in rows
        ],
        forfeitures_arising=forfeitures,
    )


@router.post(
    "/ebp/participant-accounts/run",
    action="agent_run.start",
    response_model=EbpRunStartedOut,
    status_code=202,
    errors=(409, 501),
)
async def ebp_participant_accounts_run_route(
    work_item_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> EbpRunStartedOut:
    """Begin…: the drafter's `ebp_reconcile` mode on this workpaper. A person's start; the agent
    drafts suggestions only, and sign-off stays L3 and L4 (SHL-12)."""
    await _gate(ctx, work_item_id, "agent_run.start", _E)
    from abacus.modules.agents.api import start_section_draft
    from abacus.modules.assurance import ebp_reconcile
    from abacus.modules.workpapers.api import paper_of_kind

    engagement_id = (await assurance_item(ctx.tenant, work_item_id)).engagement_id
    paper = await paper_of_kind(ctx, engagement_id, "ebp_participant_accounts")
    run_id = await start_section_draft(
        ctx, engagement_id, paper, ebp_reconcile.MODE, None, idempotency_key
    )
    return EbpRunStartedOut(run_id=run_id)


async def _plan_year(ctx: AuthContext, work_item_id: UUID) -> int:
    from abacus.modules.engagements.api import engagement_metadata

    item = await assurance_item(ctx.tenant, work_item_id)
    return (await engagement_metadata(ctx, item.engagement_id)).engagement.fiscal_period_end.year


@router.get("/ebp/plan-expenses", action="ebp.read", response_model=ExpensesOut)
async def ebp_plan_expenses_route(work_item_id: UUID, ctx: Ctx) -> ExpensesOut:
    """EBP-09 a: expenses foot to Schedule H 2i; invoices less credits by code."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_expenses

    view = await ebp_expenses.plan_expenses(ctx.tenant, work_item_id)
    tied = view.tie
    return ExpensesOut(
        rows=[
            ExpenseRowOut(
                id=r["id"],
                provider_id=r["provider_id"],
                line_key=r["line_key"],
                description=r["description"],
                disclosure_citation_id=r["disclosure_citation_id"],
                citation_id=r["citation_id"],
                invoiced=r["invoiced"],
                credits=r["credits"],
                paid_from_plan=r["paid_from_plan"],
                schedule_h_line=r["schedule_h_line"],
                exception=r["line_key"] in tied.exceptions,
            )
            for r in view.rows
        ],
        invoiced=tied.invoiced,
        credits=tied.credits,
        paid_from_plan=tied.paid,
        line_2i1=tied.by_line.get("2i(1)", Decimal(0)),
        line_2i2=tied.by_line.get("2i(2)", Decimal(0)),
        line_2i3=tied.by_line.get("2i(3)", Decimal(0)),
        line_2i4=tied.by_line.get("2i(4)", Decimal(0)),
        invoices_tie=tied.invoices_tie,
        exceptions=len(tied.exceptions),
        engine_version=tied.engine_version,
        inputs_hash=tied.inputs_hash,
    )


@router.get("/ebp/erisa-budget-account", action="ebp.read", response_model=FiguresOut)
async def ebp_budget_account_route(work_item_id: UUID, ctx: Ctx) -> FiguresOut:
    """1,200 + 2,650 - 3,100 = 750 by code."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_expenses

    roll = await ebp_expenses.budget_account(ctx.tenant, work_item_id)
    return _figures(
        "ERISA budget account",
        [
            ("beginning", "Jan 1", str(roll.beginning)),
            ("revenue_share", "Credits", str(roll.revenue_share)),
            ("applied", "Applied", str(roll.applied)),
        ],
        str(roll.ending),
    )


@router.get("/ebp/compliance-tests", action="ebp.read", response_model=list[ComplianceTestOut])
async def ebp_compliance_tests_route(work_item_id: UUID, ctx: Ctx) -> list[ComplianceTestOut]:
    """This plan year's tests and limits; an exemption is a proposal until a person accepts."""
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_expenses

    rows = await ebp_expenses.compliance_tests(
        ctx.tenant, work_item_id, await _plan_year(ctx, work_item_id)
    )
    return [
        ComplianceTestOut(
            id=r.id,
            test_key=r.test_key,
            plan_year=r.plan_year,
            limit=r.limit,
            limit_ref=r.limit_ref,
            result=cast(Any, r.result),  # Any: the column's CHECK plus `proposed`
            accepted=r.accepted_at is not None,
        )
        for r in rows
    ]


@router.get(
    "/ebp/plan-qualification", action="ebp.read", response_model=list[QualificationFactOut]
)
async def ebp_plan_qualification_route(work_item_id: UUID, ctx: Ctx) -> list[QualificationFactOut]:
    await _gate(ctx, work_item_id, "ebp.read", _E)
    from abacus.modules.assurance import ebp_expenses

    return [
        QualificationFactOut(
            id=r["id"],
            fact_key=r["fact_key"],
            value=r["value"],
            result=r["result"],
            citation_id=r["citation_id"],
            accepted=r["accepted_at"] is not None,
        )
        for r in await ebp_expenses.qualification(ctx.tenant, work_item_id)
    ]


@router.post(
    "/ebp/plan-expenses/{expense_id}/request-support",
    action="ebp_provider.request",
    response_model=SupportPrefillOut,
)
async def ebp_expense_support_route(
    work_item_id: UUID, expense_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SupportPrefillOut:
    """SHL-14's prefill for the provider of this expense; a person edits and sends (POR-14)."""
    await _gate(ctx, work_item_id, "ebp_provider.request", _E)
    from abacus.modules.assurance import ebp_expenses

    found = await ebp_expenses.support_prefill(ctx.tenant, work_item_id, expense_id)
    return SupportPrefillOut(
        provider_id=found.provider_id,
        expense_line_key=found.expense_line_key,
        request_kind="tpa_support",
    )


# EBP-07
async def _line_matches(ctx: AuthContext, ids: Sequence[UUID | None]) -> dict[UUID, str]:
    """Each cited line's region id (C4 §3.1), read from its citation; one that the reader can't
    see, or that has no region, lights nothing."""
    found: dict[UUID, str] = {}
    for citation_id in {i for i in ids if i is not None}:
        try:
            view = await citation_display(ctx, citation_id)
        except NotFound:
            continue
        if view.match_id is not None:
            found[citation_id] = view.match_id
    return found


@router.get("/ebp/form-5500", action="ebp_form5500.read", response_model=Form5500Out)
async def ebp_form5500_route(work_item_id: UUID, ctx: Ctx) -> Form5500Out:
    """Draft status, Schedule H lines with tallies and Part IV (EBP-07; T36; A-05-T58)."""
    await _gate(ctx, work_item_id, "ebp_form5500.read", _F)
    view = await form5500_view(ctx, work_item_id)
    matches = await _line_matches(ctx, [line.f5500_citation_id for line in view.lines])
    return Form5500Out(
        draft_received=view.draft_id is not None,
        draft_id=view.draft_id,
        evidence_version_id=view.evidence_version_id,
        lines=[
            FigureRowOut(
                # The v1 key's pattern is `[a-z0-9_.]`: "1b(2)" reads "h.1b_2_" (S31 end pass).
                key="h." + re.sub(r"[^a-z0-9_.]", "_", line.line_code.lower())[:62],
                label=line.caption,
                amount=line.f5500_amount,
                status=line.classification,  # type: ignore[arg-type]  # registry kind literal
                note=line.note_ref,
            )
            for line in view.lines
        ],
        rows=[
            Form5500RowOut(
                id=line.id,
                line_code=line.line_code,
                caption=line.caption,
                fs_amount=line.fs_amount,
                f5500_amount=line.f5500_amount,
                difference=line.difference,
                classification=line.classification,  # type: ignore[arg-type]  # CHECK literal
                note_ref=line.note_ref,
                match_id=None
                if line.f5500_citation_id is None
                else matches.get(line.f5500_citation_id),
            )
            for line in view.lines
        ],
        part_iv=[
            PartIvLineOut(
                line=answer.question,  # type: ignore[arg-type]  # 0665's CHECK `^4[a-m]$`
                draft_answer="yes"
                if answer.draft_answer == "yes"
                else ("no" if answer.draft_answer == "no" else None),
                draft_amount=answer.amount,
                consistency="inconsistent"
                if answer.result == "inconsistent"
                else ("consistent" if answer.result == "consistent" else "not_checked"),
                basis=answer.evidence_ref or "",
            )
            for answer in view.part_iv
        ],
        allowed_actions=[
            "ebp_form5500.key",
            "ebp_form5500.send_note",
            "ebp_form5500.remind",
            "ebp_schedule.render",
        ],
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
    """DV-EBP-07-1: a person keys the draft's value with where they read it; code re-ties."""
    await _gate(ctx, work_item_id, "ebp_form5500.key", _F)
    del idempotency_key  # the write is a set: keying the same value again changes nothing more
    draft_id = await key_line_value(ctx, work_item_id, line_id, body.value, body.citation_note)
    return AcceptedOut(id=draft_id)


class Schedule4iRowOut(BaseModel):
    """One line of Schedule H line 4i: "*" marks a party in interest; a participant-directed
    holding's cost is omitted ("**")."""

    model_config = ConfigDict(frozen=True)

    mark: Annotated[Literal["*", ""], classified("internal")]
    identity: Label
    description: Annotated[str, Field(max_length=200), classified("internal")]
    cost: MaybeMoney
    cost_omitted: Annotated[bool, classified("internal")]
    current_value: Money


class Schedule4iOut(BaseModel):
    """A-05-T58 close (DEC-2820): the 4i schedule by code (`compute.ebp.form5500.schedule_4i`)
    and the draft's line 1c total it must equal."""

    model_config = ConfigDict(frozen=True)

    rows: Annotated[list[Schedule4iRowOut], Field(max_length=500), classified("confidential")]
    total: Money
    draft_total: MaybeMoney
    ties: Annotated[bool, classified("internal")]
    inputs_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]


@router.get(
    "/ebp/form-5500/schedules/4i", action="ebp_form5500.read", response_model=Schedule4iOut
)
async def ebp_schedule_4i_route(work_item_id: UUID, ctx: Ctx) -> Schedule4iOut:
    """EBP-07 c: the schedule of assets held at year end."""
    await _gate(ctx, work_item_id, "ebp_form5500.read", _F)
    schedule, draft_total = await schedule_4i_view(ctx, work_item_id)
    return Schedule4iOut(
        rows=[
            Schedule4iRowOut(
                mark=r.mark,
                identity=r.identity,
                description=r.description,
                cost=r.cost,
                cost_omitted=r.cost_omitted,
                current_value=r.current_value,
            )
            for r in schedule.rows
        ],
        total=schedule.total,
        draft_total=draft_total,
        ties=schedule.ties,
        inputs_hash=schedule.inputs_hash,
    )


@router.post(
    "/ebp/form-5500/schedules/4i/render",
    action="ebp_schedule.render",
    response_model=AcceptedOut,
    status_code=201,
)
async def ebp_schedule_4i_render_route(
    work_item_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AcceptedOut:
    """A person's DRAFT render of the 4i schedule through C11 (A-05-T58 remainder, DEC-2828);
    answers the generated document. 404 until a Form 5500 draft arrives."""
    await _gate(ctx, work_item_id, "ebp_schedule.render", _F)
    del idempotency_key
    return AcceptedOut(id=await ebp_schedule_render.render_4i(ctx, work_item_id))


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
    found = await aud27.estimates(ctx, work_item_id)
    opening_on, closing_on = await work_item_period(ctx.tenant, work_item_id)
    return Aud27ListOut(
        items=[
            Aud27ItemOut(
                id=e.id,
                name=e.name,
                amount=e.balance,
                status=e.status,  # type: ignore[arg-type]  # registry kind literal
                pending_ep=e.pending_ep,
                account_ref=e.account_ref,
                significant_risk=e.significant_risk,
                method_text=e.method_text,
                disclosure_ref=e.disclosure_ref,
                components=[Aud27ComponentOut(label=lbl, amount=amt) for lbl, amt in e.components],
                method=None
                if e.footing is None
                else Aud27MethodOut(
                    components_total=e.footing.components_total,
                    difference=e.footing.difference,
                    ties=e.footing.difference == 0,
                ),
                rollforward=None
                if e.rollforward is None
                else Aud27RollforwardOut(
                    opening=e.rollforward.opening,
                    usage=e.rollforward.usage,
                    additions=e.rollforward.additions,
                    computed_closing=e.rollforward.computed_closing,
                    ties=e.rollforward.computed_closing == e.rollforward.balance,
                    opening_on=opening_on,
                    closing_on=closing_on,
                ),
                retrospectives=[
                    Aud27RetrospectiveOut(
                        label=r.label,
                        prior_estimate=r.prior_estimate,
                        outcome=r.outcome,
                        difference=r.difference,
                        percent=r.percent,
                        direction=r.direction,
                    )
                    for r in e.retrospectives
                ],
                range=None
                if e.range is None
                else Aud27RangeOut(low=e.range.low, high=e.range.high, inside=e.range.inside),
                bias=None
                if not e.retrospectives
                else ("possible" if e.bias.direction is not None else "none"),
            )
            for e in found
        ],
        allowed_actions=["estimate.evaluate", "estimate.request_conclusion"],
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
    await aud27.set_method(ctx, work_item_id, estimate_id, body.method, body.seen_version)
    return AcceptedOut(id=estimate_id)


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
    return AcceptedOut(id=await aud27.request_conclusion(ctx, work_item_id, estimate_id))


@router.get("/related-parties", action="related_party.read", response_model=Aud27ListOut)
async def related_parties_route(work_item_id: UUID, ctx: Ctx) -> Aud27ListOut:
    await _gate(ctx, work_item_id, "related_party.read", _A)
    parties = await aud27.related_parties(ctx, work_item_id)
    return Aud27ListOut(
        items=[
            Aud27ItemOut(
                id=p.id,
                name=p.name or "Related party",
                amount=None,
                status=p.status,  # type: ignore[arg-type]  # registry kind literal
                pending_ep=False,
                source=p.source,
                relationship=p.relationship,
                finding_id=p.finding_id,
                transactions=[
                    Aud27TransactionOut(description=d, amount=a) for d, a in p.transactions
                ],
                disclosure=p.disclosure,
                disclosure_note=p.disclosure_note,
                screened_out_reason=p.screened_out_reason,
            )
            for p in parties
        ],
        allowed_actions=["related_party.manage", "related_party.screen_out"],
    )


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
    return AcceptedOut(
        id=await aud27.add_related_party(
            ctx,
            work_item_id,
            body.name,
            relationship=body.relationship,
            activity=aud27.PartyRecord(
                transactions=[(t.description, t.amount) for t in body.transactions]
            ),
        )
    )


@router.put(
    "/related-parties/{party_id}/activity",
    action="related_party.manage",
    response_model=AcceptedOut,
)
async def related_party_activity_route(
    work_item_id: UUID,
    party_id: UUID,
    body: RelatedPartyActivityIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> AcceptedOut:
    """AUD-27 b: a person records the party's year transactions and disclosure (S31 close)."""
    await _gate(ctx, work_item_id, "related_party.manage", _A)
    del idempotency_key
    await aud27.record_activity(
        ctx,
        work_item_id,
        party_id,
        aud27.PartyRecord(
            transactions=[(t.description, t.amount) for t in body.transactions],
            disclosure=body.disclosure,
            disclosure_note=body.disclosure_note,
        ),
    )
    return AcceptedOut(id=party_id)


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
    await aud27.screen_out(ctx, work_item_id, party_id, body.reason)
    return AcceptedOut(id=party_id)


@router.get("/parties-in-interest", action="ebp.read", response_model=Aud27ListOut)
async def parties_in_interest_route(work_item_id: UUID, ctx: Ctx) -> Aud27ListOut:
    """AUD-27 c (Northwind); the prohibited transaction reads the late remittance (T52)."""
    await _gate(ctx, work_item_id, "ebp.read", _A)
    parties, prohibited = await aud27.parties_in_interest(ctx, work_item_id)
    return Aud27ListOut(
        items=[
            Aud27ItemOut(
                id=p.id,
                name=p.name,
                amount=None,
                # A late remittance is the sponsor's use of plan assets (ERISA §406), so the
                # sponsor's row carries the exception while one exists; the rest are unevaluated.
                status="exception"
                if prohibited and "sponsor" in p.relationship.lower()
                else "unevaluated",
                pending_ep=False,
                relationship=p.relationship,
                exemption=p.exemption,
                reporting=p.reporting,
                transactions=[
                    Aud27TransactionOut(description=d, amount=a) for d, a in p.transactions
                ],
            )
            for p in parties
        ],
        allowed_actions=["party_in_interest.manage"],
        prohibited=[
            Aud27ProhibitedOut(
                late_remittance_id=t.late_remittance_id,
                principal=t.principal,
                deposited_on=t.deposited_on if isinstance(t.deposited_on, date) else None,
                business_days_late=t.business_days_late,
                lost_earnings=t.lost_earnings,
                correction_status=_correction_word(t.correction_status),
                form_5330_status=_form_5330_word(t.form_5330_status),
                excise_exposure=t.excise_exposure,
            )
            for t in prohibited
        ],
    )


@router.post(
    "/parties-in-interest",
    action="party_in_interest.manage",
    response_model=AcceptedOut,
    status_code=201,
)
async def party_in_interest_create_route(
    work_item_id: UUID, body: Aud27ItemIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AcceptedOut:
    """AUD-27 c: a person records a party in interest (S31 close)."""
    await _gate(ctx, work_item_id, "party_in_interest.manage", _A)
    del idempotency_key
    party_id = await aud27.add_party_in_interest(
        ctx,
        work_item_id,
        body.name,
        relationship=body.relationship or "",
        exemption=body.exemption,
        reporting=body.reporting,
        transactions=[(t.description, t.amount) for t in body.transactions],
    )
    return AcceptedOut(id=party_id)

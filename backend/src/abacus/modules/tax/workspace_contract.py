"""RW-1 · the tax return review workspace, contract stub (T-04-T05; TASK-6320; SPEC-649; T-04
§4.3; DEC-3020). Contracts: `docs/contracts/tax-review-workspace.md` (RW-1) and
`docs/contracts/tax-worksheets.md` (WS-1).

Every route declares exactly one matrix action (T-04-T03's rows) and answers 501 until its build
row lands (T-04-T15 to T-04-T24); the flags `tax.review_workspace` and `tax.individual_workpapers`
arrive with T-04-T09. Every model is classified; return values are TRI (`restricted`, §7216) and
never leave as a model's text. Figures are code's (ADR-050) and the engine's (DEC-77): no route
computes tax.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._statuses import (
    AssistantAvailabilityStatus,
    DocumentApprovalStatus,
    K1ActivityStatus,
    K1TreatmentStatus,
    ResidencyDeterminationStatus,
    ReturnFieldViewStatus,
)
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotImplementedYet
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
Internal = classified("internal")
Confidential = classified("confidential")
Tri = classified("restricted")  # tax return information (§7216)
Money = Annotated[Decimal, Field(max_digits=20, decimal_places=2), Tri]
# An optional figure keeps its tag: Optional[Money] would drop it at the field (ADR-031).
MaybeMoney = Annotated[Decimal | None, Field(max_digits=20, decimal_places=2), Tri]
ApprovalLevel = Literal["preparer", "detail", "manager"]
WorkspaceAction = Literal[
    "document.approve",
    "tax_return.request_approval",
    "tax_return.draft_run",
    "k1_treatment.resolve",
    "k1_treatment.approve",
    "k1_treatment.override",
    "residency.request_proposal",
    "residency.confirm",
    "issue.explain",
]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True)


def _strict() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


def _not_yet() -> NoReturn:
    raise NotImplementedYet


# --- RW-1 models ---------------------------------------------------------------------------------


class WorkspaceSummaryOut(BaseModel):
    """The tabs' counts at the viewer's level, the K-1 dependency chip and availability."""

    model_config = _frozen()

    return_id: Annotated[UUID, Internal]
    review_count: Annotated[int, Field(ge=0), Internal]  # "Review 36" at the viewer's level
    viewer_level: Annotated[ApprovalLevel | None, Internal] = None
    issues_open: Annotated[int, Field(ge=0), Internal]
    checkpoints_proposed: Annotated[int, Field(ge=0), Internal] = 0
    k1_dependency: Annotated[K1ActivityStatus | None, Internal] = None
    assistant: Annotated[AssistantAvailabilityStatus, Internal]
    allowed_actions: Annotated[list[WorkspaceAction], Internal]


class ReviewDocumentOut(BaseModel):
    model_config = _frozen()

    evidence_version_id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    category: Annotated[str, Internal]
    sub_head: Annotated[str | None, Internal] = None
    approval: Annotated[DocumentApprovalStatus, Internal]
    approvals_count: Annotated[int, Field(ge=0), Internal] = 0  # the "✓ n" micro-pill
    flagged: Annotated[bool, Internal] = False
    mismatch_field_key: Annotated[str | None, Internal] = None
    version: Annotated[int, Internal]


class ReviewTreeOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[ReviewDocumentOut], Confidential]
    total: Annotated[int, Field(ge=0), Internal]
    review_count: Annotated[int, Field(ge=0), Internal]


class DocumentApprovalIn(BaseModel):
    model_config = _strict()

    evidence_version_id: Annotated[UUID, Internal]
    level: Annotated[ApprovalLevel, Internal]
    seen_version: Annotated[int, Field(ge=1), Internal]


class DocumentApprovalReverseIn(BaseModel):
    model_config = _strict()

    reason: Annotated[str | None, Field(max_length=500), Confidential] = None


class DocumentApprovalOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    evidence_version_id: Annotated[UUID, Internal]
    level: Annotated[ApprovalLevel, Internal]
    approved_by_name: Annotated[str, Confidential]
    approved_at: Annotated[datetime, Internal]
    reversed: Annotated[bool, Internal] = False


class LeadsheetLineOut(BaseModel):
    model_config = _frozen()

    line_key: Annotated[str, Internal]  # "1040.3b"
    label: Annotated[str, Internal]
    amount: MaybeMoney = None
    contributing_field_keys: Annotated[list[str], Internal]
    mismatch: Annotated[bool, Internal] = False


class ReturnLeadsheetOut(BaseModel):
    model_config = _frozen()

    form: Annotated[str, Internal]
    title: Annotated[str, Internal]
    lines: Annotated[list[LeadsheetLineOut], Tri]


class LeadsheetsOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[ReturnLeadsheetOut], Tri]


class K1MatrixRowOut(BaseModel):
    model_config = _frozen()

    activity_id: Annotated[UUID, Internal]
    label: Annotated[str, Confidential]
    current_year: MaybeMoney = None
    prior_year: MaybeMoney = None
    status: Annotated[K1ActivityStatus, Internal]


class K1MatrixOut(BaseModel):
    """Sch E - K-1: CY per K-1 activity and the PY column (TAX-05 a)."""

    model_config = _frozen()

    rows: Annotated[list[K1MatrixRowOut], Tri]
    tax_year: Annotated[int, Internal]
    prior_year: Annotated[int, Internal]


class FieldLinkOut(BaseModel):
    """`match_id` to region to field to line for MatchProvider: identifiers and locators only."""

    model_config = _frozen()

    match_id: Annotated[str, Internal]
    evidence_version_id: Annotated[UUID, Internal]
    page: Annotated[int, Field(ge=1), Internal]
    bbox: Annotated[list[float], Field(min_length=4, max_length=4), Internal]
    field_key: Annotated[str, Internal]
    line_key: Annotated[str | None, Internal] = None


class FieldLinksOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[FieldLinkOut], Internal]


class FinalApprovalRequestIn(BaseModel):
    model_config = _strict()

    assignee_user_id: Annotated[UUID, Internal]


class FinalApprovalRequestOut(BaseModel):
    model_config = _frozen()

    gate_id: Annotated[UUID, Internal]
    requested_at: Annotated[datetime, Internal]


class ReturnRunAcceptedOut(BaseModel):
    model_config = _frozen()

    agent_run_id: Annotated[UUID, Internal]


# --- WS-1 models ---------------------------------------------------------------------------------


class WorksheetNodeOut(BaseModel):
    model_config = _frozen()

    worksheet_id: Annotated[UUID, Internal]
    title: Annotated[str, Internal]  # "Sch E p2 — Ridgeline"
    group: Annotated[str, Internal]
    sub_head: Annotated[str | None, Internal] = None
    tsj: Annotated[Literal["T", "S", "J"] | None, Internal] = None
    new_this_year: Annotated[bool, Internal] = False
    edited: Annotated[bool, Internal] = False


class WorksheetsOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[WorksheetNodeOut], Internal]


class WorksheetFieldOut(BaseModel):
    model_config = _frozen()

    field_key: Annotated[str, Internal]
    label: Annotated[str, Internal]
    value: MaybeMoney = None
    state: Annotated[ReturnFieldViewStatus, Internal]
    provenance: Annotated[str | None, Internal] = None  # "0 → 1,550 · Samuel · K-1 box 18A"
    citations: Annotated[int, Field(ge=0), Internal] = 0
    signed_off_by: Annotated[list[str], Confidential] = Field(default_factory=list[str])
    engine_label: Annotated[str | None, Internal] = None
    seen_seq: Annotated[int, Internal]


class WorksheetSectionOut(BaseModel):
    model_config = _frozen()

    key: Annotated[str, Internal]
    title: Annotated[str, Internal]
    fields: Annotated[list[WorksheetFieldOut], Tri]
    signed_off: Annotated[bool, Internal] = False


class WorksheetFieldsOut(BaseModel):
    model_config = _frozen()

    worksheet_id: Annotated[UUID, Internal]
    sections: Annotated[list[WorksheetSectionOut], Tri]


class K1TreatmentOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    line: Annotated[str, Internal]  # "Box 18A"
    treatment: Annotated[str, Internal]  # "Passive", "Nonpassive", …
    status: Annotated[K1TreatmentStatus, Internal]
    changed_vs_year: Annotated[int | None, Internal] = None
    decided_by_name: Annotated[str | None, Confidential] = None
    version: Annotated[int, Internal]


class K1ActivityOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    label: Annotated[str, Confidential]
    status: Annotated[K1ActivityStatus, Internal]
    released_on: Annotated[date | None, Internal] = None
    treatments: Annotated[list[K1TreatmentOut], Internal]
    pending_proposal_id: Annotated[UUID | None, Internal] = None


class K1ActivitiesOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[K1ActivityOut], Confidential]


class K1OverrideIn(BaseModel):
    model_config = _strict()

    value: Annotated[str, Field(min_length=1, max_length=80), Internal]
    reason: Annotated[str, Field(min_length=1, max_length=1000), Confidential]
    seen_version: Annotated[int, Field(ge=1), Internal]


class ResidencyOptionOut(BaseModel):
    model_config = _frozen()

    key: Annotated[str, Internal]
    label: Annotated[str, Confidential]
    recommended: Annotated[bool, Internal] = False


class ReturnResidencyOut(BaseModel):
    model_config = _frozen()

    status: Annotated[ResidencyDeterminationStatus, Internal]
    facts: Annotated[list[str], Confidential]  # "150 NYC days", "Rhinebeck main home"
    options: Annotated[list[ResidencyOptionOut], Confidential]
    confirmed_by_name: Annotated[str | None, Confidential] = None
    confirmed_at: Annotated[datetime | None, Internal] = None


class AllocationRowOut(BaseModel):
    model_config = _frozen()

    jurisdiction: Annotated[str, Internal]
    income: MaybeMoney = None
    credits: MaybeMoney = None
    derivation: Annotated[str | None, Internal] = None


class StateAllocationOut(BaseModel):
    model_config = _frozen()

    rows: Annotated[list[AllocationRowOut], Tri]


# --- routes (each 501, one action) ---------------------------------------------------------------

workspace_router = AbacusRouter(prefix="/v1/tax", tags=["tax workspace"])
_R = "/returns/{return_id}"


@workspace_router.get(
    f"{_R}/workspace", action="tax_return.read", response_model=WorkspaceSummaryOut, errors=(501,)
)
async def workspace_route(return_id: UUID, ctx: Ctx) -> WorkspaceSummaryOut:
    _not_yet()


@workspace_router.get(
    f"{_R}/review-tree", action="tax_return.read", response_model=ReviewTreeOut, errors=(501,)
)
async def review_tree_route(
    return_id: UUID,
    ctx: Ctx,
    level: Annotated[ApprovalLevel | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    category: Annotated[str | None, Query(max_length=60)] = None,
) -> ReviewTreeOut:
    _not_yet()


@workspace_router.post(
    f"{_R}/document-approvals",
    action="document.approve",
    response_model=DocumentApprovalOut,
    status_code=201,
    errors=(409, 501),
)
async def document_approval_route(
    return_id: UUID, body: DocumentApprovalIn, ctx: Ctx
) -> DocumentApprovalOut:
    """409 `mismatch` (`facts.field_key`), 403 `level_not_permitted`, 409 `version_superseded`."""
    _not_yet()


@workspace_router.post(
    "/document-approvals/{approval_id}/reverse",
    action="document.approve",
    response_model=DocumentApprovalOut,
    errors=(409, 501),
)
async def document_approval_reverse_route(
    approval_id: UUID, body: DocumentApprovalReverseIn, ctx: Ctx
) -> DocumentApprovalOut:
    """Unapprove as a reversing row, own level only; nothing is deleted."""
    _not_yet()


@workspace_router.get(
    f"{_R}/leadsheets", action="return_worksheet.read", response_model=LeadsheetsOut, errors=(501,)
)
async def return_leadsheets_route(
    return_id: UUID, ctx: Ctx, form: Annotated[str, Query(max_length=20)] = "1040"
) -> LeadsheetsOut:
    _not_yet()


@workspace_router.get(
    f"{_R}/matrices/sch-e-k1",
    action="return_worksheet.read",
    response_model=K1MatrixOut,
    errors=(501,),
)
async def sch_e_k1_matrix_route(return_id: UUID, ctx: Ctx) -> K1MatrixOut:
    _not_yet()


@workspace_router.get(
    f"{_R}/links", action="return_worksheet.read", response_model=FieldLinksOut, errors=(501,)
)
async def field_links_route(
    return_id: UUID, ctx: Ctx, evidence_version_id: Annotated[UUID | None, Query()] = None
) -> FieldLinksOut:
    _not_yet()


@workspace_router.post(
    f"{_R}/final-approval-requests",
    action="tax_return.request_approval",
    response_model=FinalApprovalRequestOut,
    status_code=201,
    errors=(409, 501),
)
async def final_approval_request_route(
    return_id: UUID, body: FinalApprovalRequestIn, ctx: Ctx
) -> FinalApprovalRequestOut:
    """409 `{blockers: draft_k1 | blocking_issues | unapproved_documents}`."""
    _not_yet()


@workspace_router.post(
    f"{_R}/draft-runs",
    action="tax_return.draft_run",
    response_model=ReturnRunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def draft_run_route(return_id: UUID, ctx: Ctx) -> ReturnRunAcceptedOut:
    _not_yet()


@workspace_router.get(
    f"{_R}/worksheets", action="return_worksheet.read", response_model=WorksheetsOut, errors=(501,)
)
async def worksheets_route(return_id: UUID, ctx: Ctx) -> WorksheetsOut:
    _not_yet()


@workspace_router.get(
    "/worksheets/{worksheet_id}/fields",
    action="return_worksheet.read",
    response_model=WorksheetFieldsOut,
    errors=(501,),
)
async def worksheet_fields_route(
    worksheet_id: UUID, ctx: Ctx, q: Annotated[str | None, Query(max_length=120)] = None
) -> WorksheetFieldsOut:
    _not_yet()


@workspace_router.get(
    f"{_R}/k1-activities",
    action="k1_treatment.read",
    response_model=K1ActivitiesOut,
    errors=(501,),
)
async def k1_activities_route(return_id: UUID, ctx: Ctx) -> K1ActivitiesOut:
    _not_yet()


@workspace_router.get(
    "/k1-activities/{activity_id}",
    action="k1_treatment.read",
    response_model=K1ActivityOut,
    errors=(501,),
)
async def k1_activity_route(activity_id: UUID, ctx: Ctx) -> K1ActivityOut:
    _not_yet()


@workspace_router.post(
    "/k1-activities/{activity_id}/treatment-runs",
    action="k1_treatment.resolve",
    response_model=ReturnRunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def k1_treatment_run_route(activity_id: UUID, ctx: Ctx) -> ReturnRunAcceptedOut:
    _not_yet()


@workspace_router.post(
    "/k1-treatments/{treatment_id}/override",
    action="k1_treatment.override",
    response_model=K1TreatmentOut,
    errors=(409, 501),
)
async def k1_override_route(treatment_id: UUID, body: K1OverrideIn, ctx: Ctx) -> K1TreatmentOut:
    """422 `reason_required` when the reason is blank (the model enforces 1+ characters)."""
    _not_yet()


@workspace_router.get(
    f"{_R}/residency", action="residency.read", response_model=ReturnResidencyOut, errors=(501,)
)
async def residency_route(return_id: UUID, ctx: Ctx) -> ReturnResidencyOut:
    _not_yet()


@workspace_router.post(
    f"{_R}/residency/proposal-runs",
    action="residency.request_proposal",
    response_model=ReturnRunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def residency_proposal_route(return_id: UUID, ctx: Ctx) -> ReturnRunAcceptedOut:
    _not_yet()


@workspace_router.get(
    f"{_R}/state-allocation",
    action="residency.read",
    response_model=StateAllocationOut,
    errors=(501,),
)
async def state_allocation_route(return_id: UUID, ctx: Ctx) -> StateAllocationOut:
    _not_yet()

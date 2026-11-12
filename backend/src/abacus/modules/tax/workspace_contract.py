"""RW-1 · the tax return review workspace, contract stub (T-04-T05; TASK-6320; SPEC-649; T-04
§4.3; DEC-3020). Contracts: `docs/contracts/tax-review-workspace.md` (RW-1) and
`docs/contracts/tax-worksheets.md` (WS-1).

Every route declares exactly one matrix action (T-04-T03's rows) and answers 501 until its build
row lands (T-04-T15 to T-04-T24); the flags `tax.review_workspace`, `tax.individual_workpapers`
and `tax_agents.enabled` (T-04-T09) answer 404 while off. Every model is classified; return
values are TRI (`restricted`, §7216) and never leave as a model's text. Figures are code's
(ADR-050) and the engine's (DEC-77): no route computes tax.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import (
    TAX_AGENTS_ENABLED,
    TAX_INDIVIDUAL_WORKPAPERS,
    TAX_REVIEW_WORKSPACE,
)
from abacus.kernel._statuses import (
    K1ActivityStatus,
    K1TreatmentStatus,
    ResidencyDeterminationStatus,
    ReturnFieldViewStatus,
)
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.tax.k1_treatments import ActivityView, TreatmentView

Ctx = Annotated[AuthContext, Depends(current_context)]
Internal = classified("internal")
Confidential = classified("confidential")
Tri = classified("restricted")  # tax return information (§7216)
Money = Annotated[Decimal, Field(max_digits=20, decimal_places=2), Tri]
# An optional figure keeps its tag: Optional[Money] would drop it at the field (ADR-031).
MaybeMoney = Annotated[Decimal | None, Field(max_digits=20, decimal_places=2), Tri]
ApprovalLevel = Literal["preparer", "detail", "manager"]
# Derived codes, never stored, so `_statuses` generates them empty (as `due_risk` on HOME-02): the
# contract types them from the vocabulary's codes (`document_approval`, `assistant_availability`).
DocumentApproval = Literal["unapproved", "approved", "mismatch"]
AssistantAvailability = Literal["available", "ai_unavailable", "consent_required", "agents_off"]
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


async def _flag_on(ctx: AuthContext, flag: Flag) -> None:
    """T-04-T09 (DEC-3111): off for the firm, the route is absent (404); a client principal never
    reaches the workspace."""
    if ctx.client or not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)


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
    assistant: Annotated[AssistantAvailability, Internal]
    allowed_actions: Annotated[list[WorkspaceAction], Internal]
    # TASK-7322: BH-TAX-02's signer, named only to a viewer who may request final approval.
    final_approver_user_id: Annotated[UUID | None, Internal] = None


class ReviewDocumentOut(BaseModel):
    model_config = _frozen()

    evidence_version_id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    category: Annotated[str, Internal]
    sub_head: Annotated[str | None, Internal] = None
    approval: Annotated[DocumentApproval, Internal]
    approvals_count: Annotated[int, Field(ge=0), Internal] = 0  # the "✓ n" micro-pill
    flagged: Annotated[bool, Internal] = False
    mismatch_field_key: Annotated[str | None, Internal] = None
    version: Annotated[int, Internal]
    # TASK-7322: the live approval at the shown level (the latest), for Unapprove.
    approval_id: Annotated[UUID | None, Internal] = None


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
    # T-04-T29: the section's id, the `return_worksheet_section` sign-off target (SHL-12).
    section_id: Annotated[UUID | None, Internal] = None


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
    # T-04-T36 (DEC-88): only for a person who can read both engagements; else null.
    source_package_id: Annotated[UUID | None, Internal] = None


def _k1_treatment_out(t: TreatmentView) -> K1TreatmentOut:
    return K1TreatmentOut(
        id=t.id,
        line=t.line,
        treatment=t.treatment,
        status=K1TreatmentStatus(t.status),
        changed_vs_year=t.changed_vs_year,
        decided_by_name=t.decided_by_name,
        version=t.version,
    )


def _k1_out(a: ActivityView) -> K1ActivityOut:
    return K1ActivityOut(
        id=a.id,
        label=a.label,
        status=K1ActivityStatus(a.status),
        released_on=a.released_on.date() if a.released_on else None,
        treatments=[_k1_treatment_out(t) for t in a.treatments],
        pending_proposal_id=a.pending_proposal_id,
        source_package_id=a.source_package_id,
    )


class K1ActivitiesOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[K1ActivityOut], Confidential]


class K1OverrideIn(BaseModel):
    model_config = _strict()

    value: Annotated[
        str, Field(min_length=1, max_length=80), Confidential
    ]  # the client's treatment
    reason: Annotated[str, Field(min_length=1, max_length=1000), Confidential]
    seen_version: Annotated[int, Field(ge=1), Internal]


class ResidencyOptionOut(BaseModel):
    model_config = _frozen()

    key: Annotated[str, Internal]
    label: Annotated[str, Confidential]
    recommended: Annotated[bool, Internal] = False


class ResidencyFactOut(BaseModel):
    """T-04-T39 (additive): one cited fact as code states it (TRI)."""

    model_config = _frozen()

    key: Annotated[str, Internal]
    value: Annotated[dict[str, object], Tri]
    citation_ids: Annotated[list[UUID], Internal]
    source_kind: Annotated[str, Internal]


class ReturnResidencyOut(BaseModel):
    model_config = _frozen()

    status: Annotated[ResidencyDeterminationStatus, Internal]
    facts: Annotated[list[str], Confidential]  # "150 NYC days", "Rhinebeck main home"
    options: Annotated[list[ResidencyOptionOut], Confidential]
    confirmed_by_name: Annotated[str | None, Confidential] = None
    confirmed_at: Annotated[datetime | None, Internal] = None
    # T-04-T39 (additive): the determination, its conflict, cited facts, review point, tallies.
    determination_id: Annotated[UUID | None, Internal] = None
    conflict: Annotated[bool, Internal] = False
    fact_rows: Annotated[list[ResidencyFactOut], Tri] = []
    issue_id: Annotated[UUID | None, Internal] = None
    version: Annotated[int, Internal] = 1
    tallies: Annotated[dict[str, int], Internal] = {}


class AllocationRowOut(BaseModel):
    model_config = _frozen()

    jurisdiction: Annotated[str, Internal]
    income: MaybeMoney = None
    credits: MaybeMoney = None
    derivation: Annotated[str | None, Internal] = None


class StateAllocationOut(BaseModel):
    model_config = _frozen()

    rows: Annotated[list[AllocationRowOut], Tri]
    # T-04-T39 (additive): code's totals and what the return does not hold yet.
    federal_total: MaybeMoney = None
    ny_agi: MaybeMoney = None
    credit: MaybeMoney = None
    credit_limit: MaybeMoney = None
    addbacks: MaybeMoney = None
    missing: Annotated[list[str], Internal] = []


# --- routes (each 501, one action) ---------------------------------------------------------------

workspace_router = AbacusRouter(prefix="/v1/tax", tags=["tax workspace"])
_R = "/returns/{return_id}"


@workspace_router.get(
    f"{_R}/workspace", action="tax_return.read", response_model=WorkspaceSummaryOut, errors=(501,)
)
async def workspace_route(return_id: UUID, ctx: Ctx) -> WorkspaceSummaryOut:
    """TAX-04's tab counts at the viewer's level (T-04-T17)."""
    from abacus.modules.tax.return_issues import checkpoint_chip, issue_counts
    from abacus.modules.tax.review_tree import summary

    await _flag_on(ctx, TAX_REVIEW_WORKSPACE)
    found = await summary(ctx, return_id)
    issues = await issue_counts(ctx, return_id)  # T-04-T23: TAX-06's open count
    chip = await checkpoint_chip(ctx, return_id)  # T-04-T23: TAX-07's "☰ n proposed"
    return WorkspaceSummaryOut(
        return_id=return_id,
        review_count=found.review_count,
        viewer_level=found.viewer_level,
        issues_open=issues.open_total,
        checkpoints_proposed=chip.proposed,
        k1_dependency=None
        if found.k1_dependency is None
        else K1ActivityStatus(found.k1_dependency),
        assistant=cast(AssistantAvailability, found.assistant),
        allowed_actions=cast(list[WorkspaceAction], found.allowed),
        final_approver_user_id=found.final_approver_user_id,
    )


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
    """The documents at a level, "Review n" (T-04-T17)."""
    from abacus.modules.tax.review_tree import tree

    await _flag_on(ctx, TAX_REVIEW_WORKSPACE)
    docs, review, _ = await tree(ctx, return_id, level=level, q=q, category=category)
    return ReviewTreeOut(
        items=[
            ReviewDocumentOut(
                evidence_version_id=d.evidence_version_id,
                title=d.title,
                category=d.category,
                approval=d.approval,
                approvals_count=d.approvals_count,
                version=d.version,
                approval_id=d.approval_id,
                mismatch_field_key=d.mismatch_field_key,
            )
            for d in docs
        ],
        total=len(docs),
        review_count=review,
    )


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
    from abacus.modules.tax.review_tree import approve

    await _flag_on(ctx, TAX_REVIEW_WORKSPACE)
    return _approval_out(
        await approve(
            ctx,
            return_id,
            evidence_version_id=body.evidence_version_id,
            level=body.level,
            seen_version=body.seen_version,
        )
    )


def _approval_out(a: object) -> DocumentApprovalOut:
    return DocumentApprovalOut.model_validate(a, from_attributes=True)


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
    from abacus.modules.tax.review_tree import reverse

    await _flag_on(ctx, TAX_REVIEW_WORKSPACE)
    return _approval_out(await reverse(ctx, approval_id, body.reason))


@workspace_router.get(
    f"{_R}/leadsheets", action="return_worksheet.read", response_model=LeadsheetsOut, errors=(501,)
)
async def return_leadsheets_route(
    return_id: UUID, ctx: Ctx, form: Annotated[str, Query(max_length=20)] = "1040"
) -> LeadsheetsOut:
    await _flag_on(ctx, TAX_INDIVIDUAL_WORKPAPERS)
    from abacus.modules.tax.leadsheets import leadsheets

    return LeadsheetsOut(
        items=[
            ReturnLeadsheetOut(
                form=card.form,
                title=card.title,
                lines=[
                    LeadsheetLineOut(
                        line_key=line.line_key,
                        label=line.label,
                        amount=line.amount,
                        contributing_field_keys=list(line.contributing_field_keys),
                        mismatch=line.mismatch,
                    )
                    for line in card.lines
                ],
            )
            for card in await leadsheets(ctx, return_id, form)
        ]
    )


@workspace_router.get(
    f"{_R}/matrices/sch-e-k1",
    action="return_worksheet.read",
    response_model=K1MatrixOut,
    errors=(501,),
)
async def sch_e_k1_matrix_route(return_id: UUID, ctx: Ctx) -> K1MatrixOut:
    await _flag_on(ctx, TAX_INDIVIDUAL_WORKPAPERS)
    from abacus.modules.tax.leadsheets import k1_matrix

    found = await k1_matrix(ctx, return_id)
    return K1MatrixOut(
        rows=[
            K1MatrixRowOut(
                activity_id=r.activity_id,
                label=r.label,
                current_year=r.current_year,
                prior_year=r.prior_year,
                status=K1ActivityStatus(r.status),
            )
            for r in found.rows
        ],
        tax_year=found.tax_year,
        prior_year=found.prior_year,
    )


@workspace_router.get(
    f"{_R}/links", action="return_worksheet.read", response_model=FieldLinksOut, errors=(501,)
)
async def field_links_route(
    return_id: UUID, ctx: Ctx, evidence_version_id: Annotated[UUID | None, Query()] = None
) -> FieldLinksOut:
    await _flag_on(ctx, TAX_INDIVIDUAL_WORKPAPERS)
    from abacus.modules.tax.leadsheets import field_links

    return FieldLinksOut(
        items=[
            FieldLinkOut(
                match_id=link.match_id,
                evidence_version_id=link.evidence_version_id,
                page=link.page,
                bbox=list(link.bbox),
                field_key=link.field_key,
                line_key=link.line_key,
            )
            for link in await field_links(ctx, return_id, evidence_version_id)
        ]
    )


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
    from abacus.modules.tax.review_tree import request_final_approval

    await _flag_on(ctx, TAX_REVIEW_WORKSPACE)
    gate_id, at = await request_final_approval(ctx, return_id, body.assignee_user_id)
    return FinalApprovalRequestOut(gate_id=gate_id, requested_at=at)


@workspace_router.post(
    f"{_R}/draft-runs",
    action="tax_return.draft_run",
    response_model=ReturnRunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def draft_run_route(return_id: UUID, ctx: Ctx) -> ReturnRunAcceptedOut:
    await _flag_on(ctx, TAX_AGENTS_ENABLED)
    await _flag_on(ctx, TAX_REVIEW_WORKSPACE)
    _not_yet()


@workspace_router.get(
    f"{_R}/worksheets", action="return_worksheet.read", response_model=WorksheetsOut, errors=(501,)
)
async def worksheets_route(return_id: UUID, ctx: Ctx) -> WorksheetsOut:
    """TAX-05's tree (T-04-T16)."""
    from abacus.modules.tax.worksheets import tree

    await _flag_on(ctx, TAX_INDIVIDUAL_WORKPAPERS)
    return WorksheetsOut(
        items=[
            WorksheetNodeOut(
                worksheet_id=n.worksheet_id,
                title=n.title,
                group=n.group,
                sub_head=n.sub_head,
                tsj=cast(Literal["T", "S", "J"] | None, n.tsj),
                new_this_year=n.new_this_year,
                edited=n.edited,
            )
            for n in await tree(ctx, return_id)
        ]
    )


@workspace_router.get(
    "/worksheets/{worksheet_id}/fields",
    action="return_worksheet.read",
    response_model=WorksheetFieldsOut,
    errors=(501,),
)
async def worksheet_fields_route(
    worksheet_id: UUID, ctx: Ctx, q: Annotated[str | None, Query(max_length=120)] = None
) -> WorksheetFieldsOut:
    """TAX-05's fields with their provenance (T-04-T16); edits go through `PUT /v1/fields/…`."""
    from abacus.modules.tax.worksheets import fields

    await _flag_on(ctx, TAX_INDIVIDUAL_WORKPAPERS)
    return WorksheetFieldsOut(
        worksheet_id=worksheet_id,
        sections=[
            WorksheetSectionOut(
                key=s.key,
                title=s.title,
                section_id=s.section_id,
                fields=[
                    WorksheetFieldOut(
                        field_key=f.field_key,
                        label=f.label,
                        value=f.value,
                        state=ReturnFieldViewStatus(f.state),
                        provenance=f.provenance,
                        citations=f.citations,
                        engine_label=f.engine_label,
                        seen_seq=f.seen_seq,
                    )
                    for f in s.fields
                ],
            )
            for s in await fields(ctx, worksheet_id, q)
        ],
    )


@workspace_router.get(
    f"{_R}/k1-activities",
    action="k1_treatment.read",
    response_model=K1ActivitiesOut,
    errors=(501,),
)
async def k1_activities_route(return_id: UUID, ctx: Ctx) -> K1ActivitiesOut:
    from abacus.modules.tax.k1_treatments import list_k1_activities

    await _flag_on(ctx, TAX_REVIEW_WORKSPACE)
    return K1ActivitiesOut(items=[_k1_out(a) for a in await list_k1_activities(ctx, return_id)])


@workspace_router.get(
    "/k1-activities/{activity_id}",
    action="k1_treatment.read",
    response_model=K1ActivityOut,
    errors=(501,),
)
async def k1_activity_route(activity_id: UUID, ctx: Ctx) -> K1ActivityOut:
    from abacus.modules.tax.k1_treatments import get_k1_activity

    await _flag_on(ctx, TAX_REVIEW_WORKSPACE)
    return _k1_out(await get_k1_activity(ctx, activity_id))


@workspace_router.post(
    "/k1-activities/{activity_id}/treatment-runs",
    action="k1_treatment.resolve",
    response_model=ReturnRunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def k1_treatment_run_route(activity_id: UUID, ctx: Ctx) -> ReturnRunAcceptedOut:
    """T-04-T38: the analyst's `k1_treatments` mode on the activity's return (202), as the
    person's agent; its treatments come back as one proposal for SHL-10."""
    from abacus.modules.tax.analyst_modes import activity_return, return_facts, start_mode

    await _flag_on(ctx, TAX_AGENTS_ENABLED)
    await _flag_on(ctx, TAX_REVIEW_WORKSPACE)
    return_id = await activity_return(ctx, activity_id)
    engagement, entity, year = await return_facts(ctx, return_id)
    run = await start_mode(ctx, "k1_treatments", return_id, entity, year, engagement)
    return ReturnRunAcceptedOut(agent_run_id=run)


@workspace_router.post(
    "/k1-treatments/{treatment_id}/override",
    action="k1_treatment.override",
    response_model=K1TreatmentOut,
    errors=(409, 501),
)
async def k1_override_route(treatment_id: UUID, body: K1OverrideIn, ctx: Ctx) -> K1TreatmentOut:
    """422 `reason_required` when the reason is blank (the model enforces 1+ characters)."""
    from abacus.modules.tax.k1_treatments import get_k1_activity, override_treatment

    await _flag_on(ctx, TAX_REVIEW_WORKSPACE)
    await override_treatment(ctx, treatment_id, body.value, body.reason, body.seen_version)
    from abacus.modules.tax.k1_treatments import activity_of_treatment

    view = await get_k1_activity(ctx, await activity_of_treatment(ctx, treatment_id))
    row = next(t for t in view.treatments if t.id == treatment_id)
    return _k1_treatment_out(row)


@workspace_router.get(
    f"{_R}/residency", action="residency.read", response_model=ReturnResidencyOut, errors=(501,)
)
async def residency_route(return_id: UUID, ctx: Ctx) -> ReturnResidencyOut:
    """T-04-T39 (TXI-03 a to e): facts with citations, options with code's recommendation, the
    status and the review point. 404 before a determination is opened."""
    from abacus.modules.tax.residency_service import residency_view

    await _flag_on(ctx, TAX_REVIEW_WORKSPACE)
    view = await residency_view(ctx, return_id)
    return ReturnResidencyOut(
        status=ResidencyDeterminationStatus(view.status),
        facts=[_fact_text(f.key, f.value) for f in view.facts],
        options=[
            ResidencyOptionOut(key=o.key, label=o.label, recommended=o.recommended)
            for o in view.options
        ],
        confirmed_by_name=view.confirmed_by_name,
        confirmed_at=view.confirmed_at,
        determination_id=view.determination_id,
        conflict=view.conflict,
        fact_rows=[
            ResidencyFactOut(
                key=f.key,
                value=dict(f.value),
                citation_ids=list(f.citation_ids),
                source_kind=f.source_kind,
            )
            for f in view.facts
        ],
        issue_id=view.issue_id,
        version=view.version,
        tallies=dict(view.tallies),
    )


def _fact_text(key: str, value: Mapping[str, object]) -> str:
    """A fact's words from code's parts ("281 NYC days", "Main home: Rhinebeck")."""
    if key == "days":
        return f"{value.get('nyc', 0)} NYC days"
    if key == "main_home_answer":
        return f"Main home: {value.get('place', '')}"
    places = cast(object, value.get("places") or value.get("localities") or [])
    parts = cast(list[object], places) if isinstance(places, list) else []
    joined = ", ".join(str(p) for p in parts)
    return f"{key.replace('_', ' ').capitalize()}: {joined}".rstrip(": ")


@workspace_router.post(
    f"{_R}/residency/proposal-runs",
    action="residency.request_proposal",
    response_model=ReturnRunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def residency_proposal_route(return_id: UUID, ctx: Ctx) -> ReturnRunAcceptedOut:
    """T-04-T38: the analyst's `residency` mode on the return (202), as the person's agent; its
    recommendation comes back as one proposal, a conflict as Action required."""
    from abacus.modules.tax.analyst_modes import return_facts, start_mode

    await _flag_on(ctx, TAX_AGENTS_ENABLED)
    await _flag_on(ctx, TAX_REVIEW_WORKSPACE)
    engagement, entity, year = await return_facts(ctx, return_id)
    run = await start_mode(ctx, "residency", return_id, entity, year, engagement)
    return ReturnRunAcceptedOut(agent_run_id=run)


@workspace_router.get(
    f"{_R}/state-allocation",
    action="residency.read",
    response_model=StateAllocationOut,
    errors=(501,),
)
async def state_allocation_route(return_id: UUID, ctx: Ctx) -> StateAllocationOut:
    """T-04-T39 (TXI-03 allocation): income by jurisdiction, the IT-112-R credit and the IT-225
    add-backs, computed by code from the return's fields."""
    from abacus.modules.tax.residency_service import allocation_view

    await _flag_on(ctx, TAX_REVIEW_WORKSPACE)
    view = await allocation_view(ctx, return_id)
    return StateAllocationOut(
        rows=[
            AllocationRowOut(
                jurisdiction=ln.jurisdiction,
                income=ln.amount if "credit" not in ln.label else None,
                credits=ln.amount if "credit" in ln.label else None,
                derivation=f"{ln.label}: {ln.derivation}" if ln.derivation else ln.label,
            )
            for ln in view.lines
        ],
        federal_total=view.federal_total,
        ny_agi=view.ny_agi,
        credit=view.credit,
        credit_limit=view.credit_limit,
        addbacks=view.addbacks,
        missing=list(view.missing),
    )


@workspace_router.get(
    f"{_R}/state-allocation.xlsx", action="export.create", response_model=bytes, errors=(501,)
)
async def state_allocation_xlsx_route(return_id: UUID, ctx: Ctx) -> Response:
    """T-04-T39: the allocation as a deterministic xlsx; `export.create` needs a fresh MFA."""
    from abacus.modules.tax.residency_service import allocation_view, allocation_xlsx

    await _flag_on(ctx, TAX_REVIEW_WORKSPACE)
    content = allocation_xlsx(await allocation_view(ctx, return_id))
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="state-allocation-{return_id}.xlsx"',
            "Cache-Control": "no-store",
        },
    )


@workspace_router.get(
    f"{_R}/issues/export", action="export.create", response_model=bytes, errors=(501,)
)
async def return_issues_export_route(return_id: UUID, ctx: Ctx) -> Response:
    """T-04-T23 (AC-4.7): TAX-06's issues as CSV; `export.create` needs a fresh MFA (matrix
    `mfa_recent`), each cell is neutralised against formula injection, `export.created` records
    the row count."""
    from abacus.modules.tax.return_issues import issues_csv

    await _flag_on(ctx, TAX_REVIEW_WORKSPACE)
    content = await issues_csv(ctx, return_id)
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="issues-{return_id}.csv"',
            "Cache-Control": "no-store",
        },
    )

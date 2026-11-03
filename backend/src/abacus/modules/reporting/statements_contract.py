"""Statements v1, the stub (A-06-T19; A-06 §4.3; AUD-20; DEC-2209). Contract:
`docs/contracts/completion.md` §"Statements v1"; consumers AUD-20 (A-06-T25 onward), EBP-07
(A-05), A-07 (AUD-21 to AUD-24), A-10 (the shared `statement_documents` model).

DEC-80's canonical model: a statement document per audit and framework, insert-only versions
drafted by code from a TB snapshot and the approved entries, each line's value tied to its
source (TB-linked, formula or a person's override with its reason), code's tie-out, the
disclosure checklist (N/A needs a reason) and management's approval (a person's record, or the
client's through R-02's C18). The disclosure-checklist templates are firm content imported and
published by a person (methodology; licensed text only under ADR-056).

Every route answers, in order: a client principal 404; the matrix action on the engagement (or
the firm for template routes); 404 with `reporting.fs_disclosure` off; 501 until A-06-T25.
Amounts are confidential (no TRI and no TIN on any statement field).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import REPORTING_FS_DISCLOSURE
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
IfMatch = Annotated[int, Header(alias="If-Match", ge=1)]
Internal = classified("internal")
Amount = Annotated[Decimal, Field(max_digits=20, decimal_places=2), classified("confidential")]

DocumentStatus = Literal["draft", "in_review", "final", "signed_off"]
ManagementApproval = Literal["none", "sent_for_approval", "approved_by_management"]
ValueSource = Literal["tb_linked", "formula", "override", "stale_override"]
Answer = Literal["yes", "no", "na"]
AnswerState = Literal["empty", "suggested", "adopted", "answered", "reviewed"]
StatementAction = Literal[
    "statement.draft",
    "statement.tie_out",
    "statement.send_draft",
    "statement.record_management_approval",
    "disclosure_checklist.answer",
    "disclosure_checklist.review",
    "disclosure_checklist.export",
]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True)


def _strict() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class LinkedValueOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    year: Annotated[int, Internal]
    value: Amount
    source: Annotated[ValueSource, Internal]
    citation_ids: Annotated[list[UUID], Internal]
    override_reason: Annotated[str | None, classified("confidential")] = None
    ties: Annotated[bool | None, Internal] = None
    off_by: Annotated[
        Decimal | None, Field(max_digits=20, decimal_places=2), classified("confidential")
    ] = None


class LineItemOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    statement_key: Annotated[str, Internal]
    section_key: Annotated[str, Internal]
    line_key: Annotated[str, Internal]
    label: Annotated[str, classified("confidential")]
    position: Annotated[int, Internal]
    note_ref: Annotated[str | None, Internal] = None
    values: Annotated[list[LinkedValueOut], classified("confidential")]


class TieOutOut(BaseModel):
    """ "63 of 63 tie"; `off` names each value that does not, its difference and the cause."""

    model_config = _frozen()

    total: Annotated[int, Internal]
    tied: Annotated[int, Internal]
    off: Annotated[list[dict[str, str]], classified("confidential")]
    engine_version: Annotated[str, Internal]
    inputs_hash: Annotated[str, Internal]
    ran_at: Annotated[datetime, Internal]


class StatementVersionOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    version_no: Annotated[int, Internal]
    source_snapshot_id: Annotated[UUID, Internal]
    drafted_by_kind: Annotated[Literal["system", "human"], Internal]
    out_of_date: Annotated[bool, Internal]
    content_hash: Annotated[str, Internal]
    created_at: Annotated[datetime, Internal]
    lines: Annotated[list[LineItemOut], classified("confidential")]
    tie_out: Annotated[TieOutOut | None, classified("internal")] = None


class StatementsOut(BaseModel):
    model_config = _frozen()

    statement_document_id: Annotated[UUID | None, Internal] = None
    framework_key: Annotated[str | None, Internal] = None
    status: Annotated[DocumentStatus, Internal]
    management_approval: Annotated[ManagementApproval, Internal]
    current: Annotated[StatementVersionOut | None, classified("internal")] = None
    allowed_actions: Annotated[list[StatementAction], Internal]


class StatementDraftStartedOut(BaseModel):
    model_config = _frozen()

    run_id: Annotated[UUID, Internal]


class LineageOut(BaseModel):
    """The verified sources behind one line (TB accounts, entries, the formula)."""

    model_config = _frozen()

    line_item_id: Annotated[UUID, Internal]
    sources: Annotated[list[dict[str, str]], classified("confidential")]
    citation_ids: Annotated[list[UUID], Internal]


class DisclosureItemOut(BaseModel):
    model_config = _frozen()

    item_key: Annotated[str, Internal]
    section: Annotated[str, Internal]
    text: Annotated[str, Internal]
    answer: Annotated[Answer | None, Internal] = None
    reason: Annotated[str | None, classified("confidential")] = None
    note_ref: Annotated[str | None, Internal] = None
    state: Annotated[AnswerState, Internal]
    suggestion_id: Annotated[UUID | None, Internal] = None
    version: Annotated[int, Internal]


class ChecklistOut(BaseModel):
    model_config = _frozen()

    statement_document_id: Annotated[UUID, Internal]
    template_version_id: Annotated[UUID | None, Internal] = None
    items: Annotated[list[DisclosureItemOut], classified("confidential")]
    answered: Annotated[int, Internal]
    total: Annotated[int, Internal]


class ChecklistAnswerIn(BaseModel):
    """422 `reason_required` for N/A without a reason (the database refuses it too)."""

    model_config = _strict()

    answer: Annotated[Answer, Internal]
    reason: Annotated[str | None, Field(max_length=2000), classified("confidential")] = None
    note_ref: Annotated[str | None, Field(max_length=40), Internal] = None


class ChecklistReviewIn(BaseModel):
    model_config = _strict()

    item_keys: Annotated[list[str], Field(min_length=1, max_length=500), Internal]


class StatementSendDraftIn(BaseModel):
    model_config = _strict()

    recipient_contact_id: Annotated[UUID, Internal]
    watermark: Annotated[Literal[True], Internal] = True
    page_comments: Annotated[bool, Internal] = True


class SentDraftOut(BaseModel):
    model_config = _frozen()

    deliverable_ref: Annotated[str, Internal]
    approval_item_ref: Annotated[str, Internal]


class ManagementApprovalIn(BaseModel):
    """Record mode: the signed approval the firm received, as evidence."""

    model_config = _strict()

    evidence_version_id: Annotated[UUID, Internal]


class ApprovalRecordedOut(BaseModel):
    model_config = _frozen()

    management_approval: Annotated[ManagementApproval, Internal]
    recorded_at: Annotated[datetime, Internal]


class ChecklistImportOut(BaseModel):
    model_config = _frozen()

    template_id: Annotated[UUID | None, Internal] = None
    version: Annotated[int | None, Internal] = None
    dry_run: Annotated[bool, Internal]
    problems: Annotated[list[str], Internal]


class ChecklistTemplateVersionOut(BaseModel):
    model_config = _frozen()

    template_id: Annotated[UUID, Internal]
    version: Annotated[int, Internal]
    status: Annotated[Literal["draft", "published"], Internal]
    published_at: Annotated[datetime | None, Internal] = None


async def _gate(ctx: AuthContext, engagement_id: UUID | None, action: str) -> None:
    if ctx.client:
        raise NotFound("statement")
    if engagement_id is None:
        await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    else:
        await authorise(ctx, action, (await get_ref(ctx, engagement_id)).resource())
    if not await flag_enabled(ctx.tenant, REPORTING_FS_DISCLOSURE):
        raise NotFound(REPORTING_FS_DISCLOSURE.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


statements_router = AbacusRouter(prefix="/v1", tags=["statements"])
_WI = "/engagements/{engagement_id}/financial-statements"
_SV = "/statement-versions/{version_id}"
_SD = "/statement-documents/{document_id}/disclosure-checklist"


@statements_router.get(_WI, action="statement.read", response_model=StatementsOut, errors=(501,))
async def fs_statements_route(engagement_id: UUID, ctx: Ctx) -> StatementsOut:
    """The current version tree with tie counts."""
    await _gate(ctx, engagement_id, "statement.read")
    _not_yet()


@statements_router.post(
    f"{_WI}/draft",
    action="statement.draft",
    response_model=StatementDraftStartedOut,
    status_code=202,
    errors=(409, 501),
)
async def statements_draft_route(
    engagement_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> StatementDraftStartedOut:
    """Code drafts the statements from the final TB and the approved entries (deterministic)."""
    await _gate(ctx, engagement_id, "statement.draft")
    _not_yet()


@statements_router.get(
    f"{_SV}/line-items/{{line_id}}/lineage",
    action="statement.read",
    response_model=LineageOut,
    errors=(501,),
)
async def lineage_route(version_id: UUID, line_id: UUID, ctx: Ctx) -> LineageOut:
    await _gate(ctx, None, "statement.read")
    _not_yet()


@statements_router.post(
    f"{_SV}/tie-out", action="statement.tie_out", response_model=TieOutOut, status_code=202,
    errors=(501,),
)  # fmt: skip
async def tie_out_route(version_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey) -> TieOutOut:
    await _gate(ctx, None, "statement.tie_out")
    _not_yet()


@statements_router.get(
    f"{_SV}/tie-out", action="statement.read", response_model=TieOutOut, errors=(501,)
)
async def tie_out_result_route(version_id: UUID, ctx: Ctx) -> TieOutOut:
    await _gate(ctx, None, "statement.read")
    _not_yet()


@statements_router.post(
    f"{_SV}/send-draft", action="statement.send_draft", response_model=SentDraftOut,
    errors=(409, 501),
)  # fmt: skip
async def fs_send_draft_route(
    version_id: UUID, body: StatementSendDraftIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SentDraftOut:
    """A DRAFT-watermarked PDF as a C10 draft deliverable and a C18 `fs_draft` item."""
    await _gate(ctx, None, "statement.send_draft")
    _not_yet()


@statements_router.post(
    f"{_SV}/management-approval:record",
    action="statement.record_management_approval",
    response_model=ApprovalRecordedOut,
    errors=(409, 501),
)
async def management_approval_route(
    version_id: UUID, body: ManagementApprovalIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ApprovalRecordedOut:
    """Record mode: a person records management's signed approval."""
    await _gate(ctx, None, "statement.record_management_approval")
    _not_yet()


@statements_router.get(
    _SD, action="disclosure_checklist.read", response_model=ChecklistOut, errors=(501,)
)
async def checklist_route(document_id: UUID, ctx: Ctx) -> ChecklistOut:
    await _gate(ctx, None, "disclosure_checklist.read")
    _not_yet()


@statements_router.put(
    f"{_SD}/items/{{item_key}}",
    action="disclosure_checklist.answer",
    response_model=DisclosureItemOut,
    errors=(409, 501),
)
async def checklist_answer_route(
    document_id: UUID, item_key: str, body: ChecklistAnswerIn, ctx: Ctx, if_match: IfMatch
) -> DisclosureItemOut:
    await _gate(ctx, None, "disclosure_checklist.answer")
    _not_yet()


@statements_router.post(
    f"{_SD}/items/{{item_key}}/adopt",
    action="disclosure_checklist.answer",
    response_model=DisclosureItemOut,
    errors=(409, 501),
)
async def checklist_adopt_route(
    document_id: UUID, item_key: str, ctx: Ctx, if_match: IfMatch
) -> DisclosureItemOut:
    """A person adopts the agent's suggested answer (it becomes theirs)."""
    await _gate(ctx, None, "disclosure_checklist.answer")
    _not_yet()


@statements_router.post(
    f"{_SD}/items:review",
    action="disclosure_checklist.review",
    response_model=ChecklistOut,
    errors=(409, 501),
)
async def checklist_review_route(
    document_id: UUID, body: ChecklistReviewIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ChecklistOut:
    await _gate(ctx, None, "disclosure_checklist.review")
    _not_yet()


@statements_router.get(
    f"{_SD}/export.xlsx",
    action="disclosure_checklist.export",
    response_model=bytes,
    errors=(501,),
)
async def checklist_export_route(document_id: UUID, ctx: Ctx) -> Response:
    await _gate(ctx, None, "disclosure_checklist.export")
    _not_yet()


@statements_router.post(
    "/methodology/disclosure-checklists:import",
    action="disclosure_checklist_template.import",
    response_model=ChecklistImportOut,
    errors=(409, 501),
)
async def checklist_import_route(
    ctx: Ctx,
    name: Annotated[str, Query(min_length=1, max_length=200)],
    framework_key: Annotated[str, Query(pattern=r"^[a-z][a-z0-9_]{1,39}$")],
    dry_run: Annotated[bool, Query()] = True,
) -> ChecklistImportOut:
    """The firm's checklist file as the raw body (DEC-1369's import grammar); dry run first."""
    await _gate(ctx, None, "disclosure_checklist_template.import")
    _not_yet()


@statements_router.post(
    "/methodology/disclosure-checklists/{template_id}/versions/{version}/publish",
    action="disclosure_checklist_template.publish",
    response_model=ChecklistTemplateVersionOut,
    errors=(409, 501),
)
async def checklist_publish_route(
    template_id: UUID, version: int, ctx: Ctx
) -> ChecklistTemplateVersionOut:
    """A person publishes with fresh MFA; a published version never changes."""
    await _gate(ctx, None, "disclosure_checklist_template.publish")
    _not_yet()

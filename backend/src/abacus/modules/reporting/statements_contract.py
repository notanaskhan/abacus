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
from typing import TYPE_CHECKING, Annotated, Any, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import REPORTING_FS_DISCLOSURE
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.safe_xlsx import XLSX
from abacus.modules.engagements.api import assurance_item_id, get_ref
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)

if TYPE_CHECKING:
    from abacus.modules.reporting.statements import VersionView

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
    """The deterministic run's record: `FsDraftWorkflow` writes the version, and the screen shows
    its skeleton until `GET` reads it (AUD-20c)."""

    model_config = _frozen()

    run_id: Annotated[UUID, Internal]


class TieOutStartedOut(BaseModel):
    """`TieOutWorkflow` runs in the background; `GET` reads the result (AUD-20 c)."""

    model_config = _frozen()

    statement_version_id: Annotated[UUID, Internal]


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


async def _version_gate(ctx: AuthContext, version_id: UUID, action: str) -> None:
    """The version's own engagement decides (A-06-T25): an id alone reaches no other audit."""
    from abacus.modules.reporting import statements

    if ctx.client:
        raise NotFound("statement")
    await statements.authorise_version(ctx, action, version_id)
    if not await flag_enabled(ctx.tenant, REPORTING_FS_DISCLOSURE):
        raise NotFound(REPORTING_FS_DISCLOSURE.name)


async def _document_gate(ctx: AuthContext, document_id: UUID, action: str) -> None:
    from abacus.modules.reporting import statements

    if ctx.client:
        raise NotFound("statement")
    await statements.authorise_document(ctx, action, document_id)
    if not await flag_enabled(ctx.tenant, REPORTING_FS_DISCLOSURE):
        raise NotFound(REPORTING_FS_DISCLOSURE.name)


async def _work_item(ctx: AuthContext, engagement_id: UUID) -> UUID:
    """The engagement's assurance work item: the statements' scope (A-06 §4.2)."""
    found = await assurance_item_id(ctx.tenant, engagement_id)
    if found is None:
        raise NotFound("work_item")
    return found


def _tie_out_out(row: dict[str, Any]) -> TieOutOut:  # Any: a row from the database
    return TieOutOut(
        total=row["total"],
        tied=row["tied"],
        off=row["off"],
        engine_version=row["engine_version"],
        inputs_hash=row["inputs_hash"],
        ran_at=row["created_at"],
    )


def _version_out(view: VersionView) -> StatementVersionOut:
    lines: dict[UUID, list[dict[str, Any]]] = {}  # Any: rows from the database
    for row in view.lines:
        lines.setdefault(row["line_id"], []).append(row)
    runs = cast("list[dict[str, str]]", [] if view.tie_out is None else view.tie_out["off"])
    off = {(o["line_key"], o["year"]): o for o in runs}
    return StatementVersionOut(
        id=view.row["id"],
        version_no=view.row["version_no"],
        source_snapshot_id=view.row["source_snapshot_id"],
        drafted_by_kind=view.row["drafted_by_kind"],
        out_of_date=view.out_of_date,
        content_hash=view.row["content_hash"],
        created_at=view.row["created_at"],
        lines=[
            LineItemOut(
                id=line_id,
                statement_key=rows[0]["statement_key"],
                section_key=rows[0]["section_key"],
                line_key=rows[0]["line_key"],
                label=rows[0]["label"],
                position=rows[0]["position"],
                note_ref=rows[0]["note_ref"],
                values=[
                    LinkedValueOut(
                        id=r["value_id"],
                        year=r["year"],
                        value=r["value"],
                        source=r["source"],
                        citation_ids=list(r["citation_ids"]),
                        override_reason=r["override_reason"],
                        ties=None
                        if view.tie_out is None
                        else (r["line_key"], str(r["year"])) not in off,
                        off_by=Decimal(off[(r["line_key"], str(r["year"]))]["off_by"])
                        if (r["line_key"], str(r["year"])) in off
                        else None,
                    )
                    for r in rows
                ],
            )
            for line_id, rows in lines.items()
        ],
        tie_out=_tie_out_out(view.tie_out) if view.tie_out else None,
    )


async def _checklist_out(ctx: AuthContext, document_id: UUID) -> ChecklistOut:
    from abacus.modules.reporting import statements

    view = await statements.disclosure_view(ctx.tenant, document_id)
    return ChecklistOut(
        statement_document_id=view.document_id,
        template_version_id=view.template_version_id,
        items=[DisclosureItemOut(**item) for item in view.items],
        answered=view.answered,
        total=view.total,
    )


statements_router = AbacusRouter(prefix="/v1", tags=["statements"])
_WI = "/engagements/{engagement_id}/financial-statements"
_SV = "/statement-versions/{version_id}"
_SD = "/statement-documents/{document_id}/disclosure-checklist"


@statements_router.get(_WI, action="statement.read", response_model=StatementsOut, errors=(501,))
async def fs_statements_route(engagement_id: UUID, ctx: Ctx) -> StatementsOut:
    """The current version tree with tie counts."""
    await _gate(ctx, engagement_id, "statement.read")
    from abacus.modules.reporting import statements

    view = await statements.current_of(ctx.tenant, await _work_item(ctx, engagement_id))
    if view.document is None:
        return StatementsOut(status="draft", management_approval="none", allowed_actions=[])
    return StatementsOut(
        statement_document_id=view.document["id"],
        framework_key=view.document["framework_key"],
        status=view.document["status"],
        management_approval=view.document["management_approval"],
        current=_version_out(view.current) if view.current else None,
        allowed_actions=[],
    )


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
    from abacus.modules.reporting import statements

    run_id = await statements.start_draft(ctx, engagement_id, await _work_item(ctx, engagement_id))
    return StatementDraftStartedOut(run_id=run_id)


@statements_router.get(
    f"{_SV}/line-items/{{line_id}}/lineage",
    action="statement.read",
    response_model=LineageOut,
    errors=(501,),
)
async def lineage_route(version_id: UUID, line_id: UUID, ctx: Ctx) -> LineageOut:
    await _version_gate(ctx, version_id, "statement.read")
    from abacus.modules.reporting import statements

    sources, citations = await statements.lineage(ctx.tenant, version_id, line_id)
    return LineageOut(line_item_id=line_id, sources=sources, citation_ids=citations)


@statements_router.post(
    f"{_SV}/tie-out", action="statement.tie_out", response_model=TieOutStartedOut,
    status_code=202, errors=(501,),
)  # fmt: skip
async def tie_out_route(
    version_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> TieOutStartedOut:
    await _version_gate(ctx, version_id, "statement.tie_out")
    from abacus.modules.reporting import statements

    await statements.start_tie_out(ctx, version_id)
    return TieOutStartedOut(statement_version_id=version_id)


@statements_router.get(
    f"{_SV}/tie-out", action="statement.read", response_model=TieOutOut, errors=(501,)
)
async def tie_out_result_route(version_id: UUID, ctx: Ctx) -> TieOutOut:
    await _version_gate(ctx, version_id, "statement.read")
    from abacus.modules.reporting import statements

    return _tie_out_out(await statements.last_tie_out(ctx.tenant, version_id))


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
    await _version_gate(ctx, version_id, "statement.record_management_approval")
    from abacus.modules.reporting import statements

    state, at = await statements.record_management_approval(
        ctx, version_id, body.evidence_version_id
    )
    return ApprovalRecordedOut(management_approval=cast(ManagementApproval, state), recorded_at=at)


@statements_router.get(
    _SD, action="disclosure_checklist.read", response_model=ChecklistOut, errors=(501,)
)
async def checklist_route(document_id: UUID, ctx: Ctx) -> ChecklistOut:
    await _document_gate(ctx, document_id, "disclosure_checklist.read")
    return await _checklist_out(ctx, document_id)


@statements_router.put(
    f"{_SD}/items/{{item_key}}",
    action="disclosure_checklist.answer",
    response_model=DisclosureItemOut,
    errors=(409, 501),
)
async def checklist_answer_route(
    document_id: UUID, item_key: str, body: ChecklistAnswerIn, ctx: Ctx, if_match: IfMatch
) -> DisclosureItemOut:
    await _document_gate(ctx, document_id, "disclosure_checklist.answer")
    from abacus.modules.reporting import statements

    item = await statements.answer_item(
        ctx, document_id, item_key, body.answer, body.reason, body.note_ref, if_match
    )
    return DisclosureItemOut(**item)


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
    await _document_gate(ctx, document_id, "disclosure_checklist.answer")
    from abacus.modules.reporting import statements

    return DisclosureItemOut(**await statements.adopt_item(ctx, document_id, item_key, if_match))


@statements_router.post(
    f"{_SD}/items:review",
    action="disclosure_checklist.review",
    response_model=ChecklistOut,
    errors=(409, 501),
)
async def checklist_review_route(
    document_id: UUID, body: ChecklistReviewIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ChecklistOut:
    await _document_gate(ctx, document_id, "disclosure_checklist.review")
    from abacus.modules.reporting import statements

    await statements.review_items(ctx, document_id, body.item_keys)
    return await _checklist_out(ctx, document_id)


@statements_router.get(
    f"{_SD}/export.xlsx",
    action="disclosure_checklist.export",
    response_model=bytes,
    errors=(501,),
)
async def checklist_export_route(document_id: UUID, ctx: Ctx) -> Response:
    """Deterministic: the same answers give the same bytes. Client text can't run as a formula."""
    await _gate(ctx, None, "disclosure_checklist.export")
    from abacus.modules.reporting import statements

    await statements.authorise_document(ctx, "disclosure_checklist.export", document_id)
    view = await statements.disclosure_view(ctx.tenant, document_id)
    return Response(
        content=statements.checklist_workbook(view),
        media_type=XLSX,
        headers={"Content-Disposition": 'attachment; filename="disclosure-checklist.xlsx"'},
    )


@statements_router.post(
    "/methodology/disclosure-checklists:import",
    action="disclosure_checklist_template.import",
    status_code=201,
    response_model=ChecklistImportOut,
    errors=(409, 501),
)
async def checklist_import_route(
    request: Request,
    ctx: Ctx,
    name: Annotated[str, Query(min_length=1, max_length=200)],
    framework_key: Annotated[str, Query(pattern=r"^[a-z][a-z0-9_]{1,39}$")],
    dry_run: Annotated[bool, Query()] = True,
) -> ChecklistImportOut:
    """The firm's checklist file as the raw body (DEC-1369's import grammar); dry run first."""
    await _gate(ctx, None, "disclosure_checklist_template.import")
    from abacus.modules.methodology.api import CHECKLIST_MAX_BYTES, import_checklist

    content = bytearray()
    async for chunk in request.stream():
        content += chunk
        if len(content) > CHECKLIST_MAX_BYTES:
            break  # the parser refuses it as too large, without holding the rest
    found = await import_checklist(ctx, name, framework_key, bytes(content), dry_run=dry_run)
    return ChecklistImportOut(
        template_id=found.template_id,
        version=found.version,
        dry_run=found.dry_run,
        problems=list(found.problems),
    )


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
    from abacus.modules.methodology.api import publish_checklist

    found = await publish_checklist(ctx, template_id, version)
    return ChecklistTemplateVersionOut(
        template_id=found.template_id,
        version=found.version,
        status="published",
        published_at=cast(datetime, found.published_at),
    )

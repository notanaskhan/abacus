"""C11 renderer and templates v1, the stubs (P-11-T03; P-11 §4.3, §8.1; ADR-320; SPEC-520).
Contract: `docs/contracts/c11-renderer.md`.

Every route answers 404 for a client principal (clients never reach C11: INV-4; deliverables go
through C10 and envelopes through C7), then checks its one matrix action, then answers 404 with
`reporting.generated_documents` off and 501 `not_implemented` with it on until its task lands:
templates P-11-T06, generated-document reads and regenerate P-11-T11. Fixture mode serves the
same shapes from the Brightwater Hale seed (`apps/web/src/fixtures/handlers/reporting.ts`).

Rules the shapes carry:
- **DocBlocks are a closed union** (ADR-320 §2): no markup, no URL, no expression but
  `{"type": "var", "key": …}` naming a declared variable.
- **Tables carry decimal strings** from the snapshot: the renderer never sums (ADR-050).
- **People finalise**: `mode=final` needs a human `approval_ref` (`reporting.api.render_final`);
  regenerate and template publication deny the agent and the system.
- **No Restricted value** on any shape: variable values reach clients only rendered, and a
  masked change reads `masked: true`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import REPORTING_GENERATED_DOCUMENTS
from abacus.kernel._statuses import GeneratedDocumentStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]

GeneratedDocumentKind = Literal[
    "engagement_letter",
    "consent_7216",
    "representation_letter",
    "governance_letter",
    "audit_report",
    "review_report",
    "compilation_report",
    "notice_response",
    "delivery_cover_letter",
    "k1_cover_letter",
    "fs_package",
    "run_trace_export",
]
LayoutKey = Literal["letter", "consent_7216", "report", "notice_response", "package", "run_export"]
RenderMode = Literal["draft", "final", "sample"]
RenderFormat = Literal["pdf", "docx"]
RequesterKind = Literal["human", "agent", "system"]
VariableType = Literal["money", "date", "text", "percent", "count", "name", "address"]
# C11 §7: the refusal codes a consumer branches on.
C11ErrorCode = Literal[
    "document_locked",
    "approval_hash_mismatch",
    "already_published",
    "missing_variable",
    "final_requires_approval",
    "markup_not_allowed",
    "unknown_variable",
    "unknown_layout",
    "unknown_block",
    "clause_conflict",
    "too_large",
    "asset_not_allowed",
    "missing_glyph",
    "renderer_unavailable",
]
ImportErrorCode = Literal[
    "unknown_variable",
    "unknown_layout",
    "unknown_block",
    "markup_not_allowed",
    "clause_conflict",
    "too_large",
]

# C11 §5: the audit events the service writes (P-11-T08 onward); never a Restricted value.
AUDIT_EVENTS = (
    "report_template.imported",
    "report_template.published",
    "report_template.deprecated",
    "generated_document.rendered",
    "generated_document.finalised",
    "generated_document.regenerated",
    "generated_document.locked",
    "generated_document.marked_out_of_date",
)
# C11 §4: the human-only actions.
HUMAN_ONLY_ACTIONS = (
    "report_template.import",
    "report_template.publish",
    "generated_document.regenerate",
)

FIRM_ACTIONS = (
    "generated_document.read",
    "generated_document.regenerate",
    "report_template.read",
    "report_template.import",
    "report_template.publish",
)


async def _stub(ctx: AuthContext, action: str) -> NoReturn:
    """A client principal never reaches C11: 404. Then the action at the firm, then the flag,
    then 501."""
    if ctx.client:
        raise NotFound("generated documents")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, REPORTING_GENERATED_DOCUMENTS):
        raise NotFound(REPORTING_GENERATED_DOCUMENTS.name)
    raise NotImplementedYet


# --- DocBlocks (ADR-320 §2; P-11 §4.2) ---------------------------------------------------------


class TextRun(BaseModel):
    """Literal text: rendered escaped, never interpreted (AC-8)."""

    model_config = ConfigDict(frozen=True)

    type: Annotated[Literal["text"], classified("internal")] = "text"
    text: Annotated[str, Field(max_length=20_000), classified("confidential")]


class VarRun(BaseModel):
    """A declared variable, resolved server-side by the kind's provider (AC-10)."""

    model_config = ConfigDict(frozen=True)

    type: Annotated[Literal["var"], classified("internal")] = "var"
    key: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{0,79}$"), classified("internal")]


class CiteRun(BaseModel):
    """A citation marker: a verified citation id (INV-2), never text."""

    model_config = ConfigDict(frozen=True)

    type: Annotated[Literal["cite"], classified("internal")] = "cite"
    citation_id: Annotated[UUID, classified("internal")]


Run = Annotated[TextRun | VarRun | CiteRun, Field(discriminator="type")]


class HeadingBlock(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Annotated[Literal["heading"], classified("internal")] = "heading"
    level: Annotated[int, Field(ge=1, le=4), classified("internal")]
    text: Annotated[str, Field(max_length=500), classified("confidential")]


class ParagraphBlock(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Annotated[Literal["paragraph"], classified("internal")] = "paragraph"
    runs: Annotated[list[Run], Field(max_length=400), classified("confidential")]


class ListBlock(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Annotated[Literal["list"], classified("internal")] = "list"
    ordered: Annotated[bool, classified("internal")]
    items: Annotated[list[list[Run]], Field(max_length=200), classified("confidential")]


class TableBlock(BaseModel):
    """Cells are decimal strings from the snapshot; the renderer never sums (ADR-050)."""

    model_config = ConfigDict(frozen=True)

    type: Annotated[Literal["table"], classified("internal")] = "table"
    columns: Annotated[list[str], Field(max_length=20), classified("confidential")]
    rows: Annotated[list[list[str]], Field(max_length=500), classified("confidential")]


class KvRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Field(max_length=200), classified("confidential")]
    value: Annotated[list[Run], Field(max_length=50), classified("confidential")]


class KvBlock(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Annotated[Literal["kv"], classified("internal")] = "kv"
    rows: Annotated[list[KvRowOut], Field(max_length=200), classified("confidential")]


class SignerLineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: Annotated[str, Field(max_length=200), classified("confidential")]
    name: Annotated[list[Run], Field(max_length=20), classified("confidential")]


class SignatureBlock(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Annotated[Literal["signature_block"], classified("internal")] = "signature_block"
    signers: Annotated[list[SignerLineOut], Field(max_length=10), classified("confidential")]


class LegendBlock(BaseModel):
    """Repeats on every page (an AR-C 70 package's legend, AC-11)."""

    model_config = ConfigDict(frozen=True)

    type: Annotated[Literal["legend"], classified("internal")] = "legend"
    text: Annotated[str, Field(max_length=1000), classified("internal")]


class ImageBlock(BaseModel):
    """A firm asset stored as evidence (letterhead, signature image): never a URL (AC-9)."""

    model_config = ConfigDict(frozen=True)

    type: Annotated[Literal["image"], classified("internal")] = "image"
    asset_id: Annotated[UUID, classified("internal")]


class EnclosuresBlock(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Annotated[Literal["enclosures"], classified("internal")] = "enclosures"
    items: Annotated[list[str], Field(max_length=50), classified("confidential")]


class PageBreakBlock(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Annotated[Literal["page_break"], classified("internal")] = "page_break"


class SectionBlock(BaseModel):
    """A section; `override` marks paragraphs a person wrote in the consumer's editor."""

    model_config = ConfigDict(frozen=True)

    type: Annotated[Literal["section"], classified("internal")] = "section"
    id: Annotated[str, Field(pattern=r"^[a-z0-9_-]{1,64}$"), classified("internal")]
    title: Annotated[str, Field(max_length=500), classified("confidential")]
    blocks: Annotated[list[DocBlock], Field(max_length=500), classified("confidential")]
    override: Annotated[bool, classified("internal")] = False


class ClauseBlock(BaseModel):
    """A clause from the template's library; `non_standard` when it differs from the standard."""

    model_config = ConfigDict(frozen=True)

    type: Annotated[Literal["clause"], classified("internal")] = "clause"
    clause_id: Annotated[str, Field(pattern=r"^[a-z0-9_-]{1,64}$"), classified("internal")]
    enabled: Annotated[bool, classified("internal")]
    non_standard: Annotated[bool, classified("internal")]
    blocks: Annotated[list[DocBlock], Field(max_length=200), classified("confidential")]


DocBlock = Annotated[
    SectionBlock
    | HeadingBlock
    | ParagraphBlock
    | ClauseBlock
    | ListBlock
    | TableBlock
    | KvBlock
    | SignatureBlock
    | LegendBlock
    | ImageBlock
    | EnclosuresBlock
    | PageBreakBlock,
    Field(discriminator="type"),
]
SectionBlock.model_rebuild()
ClauseBlock.model_rebuild()


# --- Generated documents (P-11 §4.3) ------------------------------------------------------------


class OwnerRefOut(BaseModel):
    """The consumer record the document belongs to (an engagement letter, a notice response)."""

    model_config = ConfigDict(frozen=True)

    type: Annotated[str, Field(pattern=r"^[a-z_]{1,64}$"), classified("internal")]
    id: Annotated[UUID, classified("internal")]


class GeneratedFileOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    format: Annotated[RenderFormat, classified("internal")]
    # Null only for a `sample` render (never evidence).
    evidence_version_id: Annotated[UUID | None, classified("internal")]
    render_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]
    page_count: Annotated[int, Field(ge=1), classified("internal")]


class TemplateRefOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    name: Annotated[str, classified("internal")]


class RequesterOut(BaseModel):
    """Who asked for the version: "<person> via Agent" for an agent's draft (INV-5)."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[RequesterKind, classified("internal")]
    label: Annotated[str, classified("confidential")]


class ApprovalOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    by: Annotated[str, classified("confidential")]
    at: Annotated[datetime, classified("internal")]


class GeneratedVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    n: Annotated[int, Field(ge=1), classified("internal")]
    mode: Annotated[RenderMode, classified("internal")]
    files: Annotated[list[GeneratedFileOut], classified("internal")]
    content_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]
    template: Annotated[TemplateRefOut | None, classified("internal")]
    snapshot_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]
    engine_version: Annotated[str, classified("internal")]
    requested_by: Annotated[RequesterOut, classified("confidential")]
    approval: Annotated[ApprovalOut | None, classified("confidential")]
    created_at: Annotated[datetime, classified("internal")]


class GeneratedDocumentOut(BaseModel):
    """One generated document: its computed status (DF-31) and its insert-only versions."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[GeneratedDocumentKind, classified("internal")]
    owner_ref: Annotated[OwnerRefOut, classified("internal")]
    status: Annotated[GeneratedDocumentStatus, classified("internal")]
    out_of_date: Annotated[bool, classified("internal")]
    out_of_date_reasons: Annotated[list[str], classified("internal")]
    current_version: Annotated[int | None, classified("internal")]
    versions: Annotated[list[GeneratedVersionOut], classified("confidential")]
    allowed_actions: Annotated[list[str], classified("internal")]


class FieldRegionOut(BaseModel):
    """Where a variable or field sits on the rendered page (AC-22): PDF points, top-left origin."""

    model_config = ConfigDict(frozen=True)

    field_key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    page: Annotated[int, Field(ge=1), classified("internal")]
    rect_pt: Annotated[list[float], Field(min_length=4, max_length=4), classified("internal")]
    value_text: Annotated[str, classified("confidential")]
    match_id: Annotated[str, Field(pattern=r"^gd:"), classified("internal")]


class FieldRegionsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[FieldRegionOut], classified("confidential")]


class DiffOpOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    op: Annotated[Literal["equal", "insert", "delete"], classified("internal")]
    text: Annotated[str, classified("confidential")]


class BlockDiffOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    block_id: Annotated[str, classified("internal")]
    clause_id: Annotated[str | None, classified("internal")]
    ops: Annotated[list[DiffOpOut], classified("confidential")]


class CompareOut(BaseModel):
    """A deterministic word-level diff by block and clause id (AC-23)."""

    model_config = ConfigDict(frozen=True)

    to: Annotated[str, classified("internal")]  # "standard" or a version number
    blocks: Annotated[list[BlockDiffOut], classified("confidential")]


class ChangedVariableOut(BaseModel):
    """A variable whose current value differs from the snapshot (AC-17); a Restricted value is
    never shown: `masked` with both values null."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    was: Annotated[str | None, classified("confidential")]
    now: Annotated[str | None, classified("confidential")]
    masked: Annotated[bool, classified("internal")]


class ChangesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ChangedVariableOut], classified("confidential")]


class RenderTicketOut(BaseModel):
    """A render accepted: the new version is Drafting until its job finishes."""

    model_config = ConfigDict(frozen=True)

    generated_document_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    status: Annotated[Literal["drafting"], classified("internal")] = "drafting"


# --- Report templates (P-11 §4.3; P-11-T06 implements) -----------------------------------------


class VariableDeclOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{0,79}$"), classified("internal")]
    label: Annotated[str, Field(max_length=200), classified("internal")]
    value_type: Annotated[VariableType, classified("internal")]


class ClauseDefOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    clause_id: Annotated[str, Field(pattern=r"^[a-z0-9_-]{1,64}$"), classified("internal")]
    title: Annotated[str, Field(max_length=200), classified("internal")]
    standard: Annotated[list[DocBlock], classified("internal")]
    default_enabled: Annotated[bool, classified("internal")]


class PublicationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: Annotated[Literal["published", "deprecated"], classified("internal")]
    by: Annotated[str, classified("confidential")]
    at: Annotated[datetime, classified("internal")]


class ReportTemplateOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    family: Annotated[GeneratedDocumentKind, classified("internal")]
    name: Annotated[str, classified("internal")]
    description: Annotated[str, classified("internal")]
    current_version: Annotated[int | None, classified("internal")]
    published_at: Annotated[datetime | None, classified("internal")]


class ReportTemplateVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    layout_key: Annotated[LayoutKey, classified("internal")]
    body: Annotated[list[DocBlock], classified("internal")]
    clauses: Annotated[list[ClauseDefOut], classified("internal")]
    variables: Annotated[list[VariableDeclOut], classified("internal")]
    publications: Annotated[list[PublicationOut], classified("confidential")]
    content_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]


class TemplateImportIn(BaseModel):
    """A template bundle (AC-1): structured blocks, declared variables and synthetic sample data
    only (AC-2: no markup, no URL)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    family: Annotated[GeneratedDocumentKind, classified("internal")]
    name: Annotated[str, Field(min_length=1, max_length=200), classified("internal")]
    description: Annotated[str, Field(max_length=2000), classified("internal")] = ""
    layout_key: Annotated[str, Field(max_length=40), classified("internal")]
    body: Annotated[list[DocBlock], Field(max_length=500), classified("internal")]
    clauses: Annotated[list[ClauseDefOut], Field(max_length=200), classified("internal")] = []
    variables: Annotated[list[VariableDeclOut], Field(max_length=200), classified("internal")] = []
    sample_data: Annotated[dict[str, str], classified("internal")] = {}


class ImportErrorOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: Annotated[str, Field(max_length=500), classified("internal")]
    code: Annotated[ImportErrorCode, classified("internal")]


class ImportReportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: Annotated[bool, classified("internal")]
    errors: Annotated[list[ImportErrorOut], classified("internal")]
    warnings: Annotated[list[str], classified("internal")]
    draft_version_id: Annotated[UUID | None, classified("internal")]


class PreviewPageOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    n: Annotated[int, Field(ge=1), classified("internal")]
    width_pt: Annotated[float, classified("internal")]
    height_pt: Annotated[float, classified("internal")]


class TemplatePreviewOut(BaseModel):
    """A SAMPLE-watermarked render from the version's synthetic sample data; never evidence."""

    model_config = ConfigDict(frozen=True)

    pages: Annotated[list[PreviewPageOut], classified("internal")]
    expires_at: Annotated[datetime, classified("internal")]


# --- Routes ----------------------------------------------------------------------------------

templates_router = AbacusRouter(prefix="/v1/report-templates", tags=["reporting"])
documents_router = AbacusRouter(prefix="/v1/generated-documents", tags=["reporting"])


@templates_router.get(
    "",
    action="report_template.read",
    response_model=ListPage[ReportTemplateOut],
    errors=(501,),
)
async def list_report_templates_route(
    ctx: Ctx,
    family: Annotated[GeneratedDocumentKind | None, Query()] = None,
) -> ListPage[ReportTemplateOut]:
    """The firm's templates with their current published version (P-11-T06)."""
    await _stub(ctx, "report_template.read")


@templates_router.get(
    "/{template_id}/versions/{version_no}",
    action="report_template.read",
    response_model=ReportTemplateVersionOut,
    errors=(501,),
)
async def get_report_template_version_route(
    ctx: Ctx, template_id: UUID, version_no: int
) -> ReportTemplateVersionOut:
    """One version: layout, blocks, clauses, declared variables and publications."""
    await _stub(ctx, "report_template.read")


@templates_router.post(
    "/import",
    action="report_template.import",
    response_model=ImportReportOut,
    errors=(413, 501),
)
async def import_report_template_route(
    ctx: Ctx,
    body: TemplateImportIn,
    dry_run: Annotated[bool, Query()] = True,
) -> ImportReportOut:
    """Validate a bundle (dry run) or store it as a draft version; errors listed by path (AC-1)."""
    await _stub(ctx, "report_template.import")


@templates_router.post(
    "/{template_id}/versions/{version_no}/publish",
    action="report_template.publish",
    response_model=ReportTemplateVersionOut,
    errors=(409, 501),
)
async def publish_report_template_route(
    ctx: Ctx, template_id: UUID, version_no: int
) -> ReportTemplateVersionOut:
    """Human-only with a fresh second factor; 409 `already_published` (AC-3)."""
    await _stub(ctx, "report_template.publish")


@templates_router.post(
    "/{template_id}/versions/{version_no}/preview",
    action="report_template.read",
    response_model=TemplatePreviewOut,
    errors=(501, 503),
)
async def preview_report_template_route(
    ctx: Ctx, template_id: UUID, version_no: int
) -> TemplatePreviewOut:
    """A SAMPLE render from synthetic sample data; page images `no-store`; never evidence."""
    await _stub(ctx, "report_template.read")


@documents_router.get(
    "/{document_id}",
    action="generated_document.read",
    response_model=GeneratedDocumentOut,
    errors=(501,),
)
async def get_generated_document_route(ctx: Ctx, document_id: UUID) -> GeneratedDocumentOut:
    """The document, its computed status and its versions (AC-14)."""
    await _stub(ctx, "generated_document.read")


@documents_router.get(
    "/{document_id}/versions/{version_no}/fields",
    action="generated_document.read",
    response_model=FieldRegionsOut,
    errors=(501,),
)
async def get_generated_document_fields_route(
    ctx: Ctx, document_id: UUID, version_no: int
) -> FieldRegionsOut:
    """The field-region manifest (AC-22)."""
    await _stub(ctx, "generated_document.read")


@documents_router.get(
    "/{document_id}/versions/{version_no}/compare",
    action="generated_document.read",
    response_model=CompareOut,
    errors=(501,),
)
async def compare_generated_document_route(
    ctx: Ctx,
    document_id: UUID,
    version_no: int,
    to: Annotated[str, Query(pattern=r"^(standard|[1-9][0-9]{0,4})$")] = "standard",
) -> CompareOut:
    """A deterministic word diff against the standard text or another version (AC-23)."""
    await _stub(ctx, "generated_document.read")


@documents_router.get(
    "/{document_id}/changes",
    action="generated_document.read",
    response_model=ChangesOut,
    errors=(501,),
)
async def get_generated_document_changes_route(ctx: Ctx, document_id: UUID) -> ChangesOut:
    """Variables whose current value differs from the snapshot (AC-17)."""
    await _stub(ctx, "generated_document.read")


@documents_router.post(
    "/{document_id}/regenerate",
    action="generated_document.regenerate",
    response_model=RenderTicketOut,
    errors=(409, 501, 503),
)
async def regenerate_generated_document_route(
    ctx: Ctx, document_id: UUID, idempotency_key: IdempotencyKey
) -> RenderTicketOut:
    """Human-only: version n+1 as a new draft; 409 `document_locked` (AC-18, AC-19)."""
    await _stub(ctx, "generated_document.regenerate")

"""C21 part B, the routes: `/v1/standards` (K-02-T08; K-02 §4.4; rules-tables.md; KNW-04).

Every route answers 404 for a client principal (INV-4), then reads need `firm_standard.read`
(403), then 404 with `knowledge.firm_standards` off; the service checks each write's own action
(the owner's `owner_of_target`, fresh MFA by the matrix). Import and export stay 501 until
K-02-T11.
"""

from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Path, Query

from abacus.kernel._flags import KNOWLEDGE_FIRM_STANDARDS
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)
from abacus.modules.methodology import standards
from abacus.modules.methodology.standards_contract import (
    StandardCreateIn,
    StandardDetailOut,
    StandardDraftPatchIn,
    StandardExamplesOut,
    StandardImportIn,
    StandardImportResultOut,
    StandardKind,
    StandardOut,
    StandardOwnerIn,
    StandardPublishIn,
    StandardVersionDiffOut,
    StandardVersionOut,
    StandardVersionSummaryOut,
)

Ctx = Annotated[AuthContext, Depends(current_context)]

standards_router = AbacusRouter(prefix="/v1/standards", tags=["standards"])
StandardId = Annotated[UUID, Path()]
VersionId = Annotated[UUID, Path()]
IfMatch = Annotated[int, Header(alias="If-Match", ge=1)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]


async def _gate(ctx: AuthContext) -> None:
    """INV-4: a client principal gets 404. Then the matrix's read (403), then the flag (404)."""
    if ctx.client:
        raise NotFound("firm_standard")
    await authorise(ctx, standards.READ, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, KNOWLEDGE_FIRM_STANDARDS):
        raise NotFound(KNOWLEDGE_FIRM_STANDARDS.name)


async def _stub(ctx: AuthContext, action: str) -> NoReturn:
    """Import and export until K-02-T11: 404 for a client, the matrix, the flag, then 501."""
    if ctx.client:
        raise NotFound("firm_standard")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, KNOWLEDGE_FIRM_STANDARDS):
        raise NotFound(KNOWLEDGE_FIRM_STANDARDS.name)
    raise NotImplementedYet


@standards_router.get("", action="firm_standard.read", response_model=ListPage[StandardOut])
async def list_standards_route(
    ctx: Ctx, kind: Annotated[StandardKind | None, Query()] = None
) -> ListPage[StandardOut]:
    """KNW-04's section list and rows; drafts appear for partners only."""
    await _gate(ctx)
    items = await standards.list_standards(ctx, kind)
    return ListPage[StandardOut](items=items, total=len(items))


@standards_router.post(
    "",
    action="firm_standard.create",
    response_model=StandardOut,
    status_code=201,
    errors=(409,),
)
async def create_standard_route(body: StandardCreateIn, ctx: Ctx) -> StandardOut:
    """Create a standard (QM owner or practice leader, fresh MFA); the owner must be a partner
    member (422 `owner_not_partner`); 409 `standard_key_taken`."""
    await _gate(ctx)
    return await standards.create_standard(ctx, body)


@standards_router.get(
    "/{standard_id}", action="firm_standard.read", response_model=StandardDetailOut
)
async def standard_route(
    standard_id: StandardId, ctx: Ctx, version: Annotated[int | None, Query(ge=1)] = None
) -> StandardDetailOut:
    """The form pane: the version in effect (or `?version=`) and the Timeline."""
    await _gate(ctx)
    return await standards.standard_detail(ctx, standard_id, version)


@standards_router.put(
    "/{standard_id}/owner", action="firm_standard.assign_owner", response_model=StandardOut
)
async def assign_owner_route(
    standard_id: StandardId, body: StandardOwnerIn, ctx: Ctx
) -> StandardOut:
    """Assign the owner (a partner member; 422 `owner_not_partner`)."""
    await _gate(ctx)
    return await standards.assign_owner(ctx, standard_id, body.owner_id)


@standards_router.get(
    "/{standard_id}/versions/{version_id}",
    action="firm_standard.read",
    response_model=StandardVersionOut,
)
async def standard_version_route(
    standard_id: StandardId, version_id: VersionId, ctx: Ctx
) -> StandardVersionOut:
    """One version; a draft is 404 for anyone but a partner (US-3.4)."""
    await _gate(ctx)
    return await standards.version_detail(ctx, standard_id, version_id)


@standards_router.post(
    "/{standard_id}/versions",
    action="firm_standard.draft",
    response_model=StandardVersionOut,
    status_code=201,
    errors=(409,),
)
async def draft_version_route(standard_id: StandardId, ctx: Ctx) -> StandardVersionOut:
    """New version…: a draft from the current version (409 `draft_exists`,
    `no_current_version`; 403 `not_standard_owner` for a partner who is not the owner)."""
    await _gate(ctx)
    return await standards.draft_version(ctx, standard_id)


@standards_router.patch(
    "/{standard_id}/versions/{version_id}",
    action="firm_standard.draft",
    response_model=StandardVersionOut,
    errors=(409,),
)
async def edit_draft_route(
    standard_id: StandardId,
    version_id: VersionId,
    body: StandardDraftPatchIn,
    ctx: Ctx,
    if_match: IfMatch,
) -> StandardVersionOut:
    """Edit the draft (409 `stale_version` or `not_draft`, 422 `payload_invalid`)."""
    await _gate(ctx)
    return await standards.edit_draft(ctx, standard_id, version_id, body, if_match)


@standards_router.delete(
    "/{standard_id}/versions/{version_id}",
    action="firm_standard.draft",
    response_model=StandardVersionSummaryOut,
    errors=(409,),
)
async def standard_discard_draft_route(
    standard_id: StandardId, version_id: VersionId, ctx: Ctx, if_match: IfMatch
) -> StandardVersionSummaryOut:
    """Discard draft: status `discarded`; the row stays (never deleted)."""
    await _gate(ctx)
    return await standards.discard_draft(ctx, standard_id, version_id, if_match)


@standards_router.post(
    "/{standard_id}/versions/{version_id}/publish",
    action="firm_standard.publish",
    response_model=StandardVersionOut,
    errors=(409,),
)
async def publish_version_route(
    standard_id: StandardId,
    version_id: VersionId,
    body: StandardPublishIn,
    ctx: Ctx,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
) -> StandardVersionOut:
    """Publish vN…: the owner, a person, with fresh MFA (422 `effective_from_backdated`,
    `effective_from_not_after_current`). A retried key answers what the first publish did."""
    await _gate(ctx)

    async def run() -> tuple[int, dict[str, object]]:
        out = await standards.publish_version(ctx, standard_id, version_id, body, if_match)
        return 200, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="firm_standard.publish",
        key=idempotency_key,
        body={
            "version_id": str(version_id),
            "if_match": if_match,
            **body.model_dump(mode="json"),
        },
        run=run,
    )
    return StandardVersionOut.model_validate(stored.body)


@standards_router.get(
    "/{standard_id}/versions/{version_id}/diff",
    action="firm_standard.read",
    response_model=StandardVersionDiffOut,
)
async def version_diff_route(
    standard_id: StandardId,
    version_id: VersionId,
    ctx: Ctx,
    against: Annotated[UUID | None, Query()] = None,
) -> StandardVersionDiffOut:
    """Cell-level diff for KNW-04 i, against the version the draft came from by default."""
    await _gate(ctx)
    return await standards.version_diff(ctx, standard_id, version_id, against)


@standards_router.get(
    "/{standard_id}/versions/{version_id}/export.xlsx",
    action="firm_standard.read",
    response_model=bytes,
    errors=(501,),
)
async def standard_export_version_route(
    standard_id: StandardId, version_id: VersionId, ctx: Ctx
) -> bytes:
    """The version as a workbook; re-importing it gives an empty diff (US-5.1; K-02-T11)."""
    await _stub(ctx, "firm_standard.read")


@standards_router.get(
    "/{standard_id}/examples",
    action="firm_standard.read",
    response_model=StandardExamplesOut,
)
async def standard_examples_route(
    standard_id: StandardId,
    ctx: Ctx,
    period: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
) -> StandardExamplesOut:
    """Registered example providers' rows, `visible()`-filtered with no hidden counts."""
    await _gate(ctx)
    return await standards.examples(ctx, standard_id, period)


@standards_router.post(
    "/{standard_id}/imports",
    action="firm_standard.import",
    response_model=StandardImportResultOut,
    status_code=201,
    errors=(501,),
)
async def import_standard_route(
    standard_id: StandardId, body: StandardImportIn, ctx: Ctx
) -> StandardImportResultOut:
    """A workbook to a draft of this standard (its owner's; 422 `import_invalid` with
    problems). Never publishes (K-02-T11)."""
    await _stub(ctx, "firm_standard.import")


@standards_router.post(
    "/imports",
    action="firm_standard.import",
    response_model=StandardImportResultOut,
    status_code=201,
    errors=(501,),
)
async def import_standards_route(body: StandardImportIn, ctx: Ctx) -> StandardImportResultOut:
    """Onboarding: one sheet per kind, one draft per standard; an owner who is not a partner
    member is a row problem (`owner_not_partner`; K-02-T11)."""
    await _stub(ctx, "firm_standard.import")

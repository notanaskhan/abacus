"""C21 part B, the routes: `/v1/standards` (K-02-T08; K-02 §4.4; rules-tables.md; KNW-04).

Every route answers 404 for a client principal (INV-4), then reads need `firm_standard.read`
(403), then 404 with `knowledge.firm_standards` off; the service checks each write's own action
(the owner's `owner_of_target`, fresh MFA by the matrix). Import and export stay 501 until
K-02-T11.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from abacus.kernel._flags import KNOWLEDGE_FIRM_STANDARDS
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.isolation import IsolationFailed, run_isolated
from abacus.kernel.listing import ListPage
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
    emails_of,
    partner_members,
)
from abacus.modules.methodology import standards, standards_import
from abacus.modules.methodology.standards_contract import (
    StandardCreateIn,
    StandardDetailOut,
    StandardDraftPatchIn,
    StandardExamplesOut,
    StandardImportProblemOut,
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


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# K-02-T11 (DEC-1357): the workbook is the raw request body, as methodology's template import
# (no multipart dependency; the generated client posts the file as the body).


async def _import_gate(ctx: AuthContext) -> None:
    """404 for a client, the matrix's import action, then the flag."""
    if ctx.client:
        raise NotFound("firm_standard")
    await authorise(ctx, standards.IMPORT, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, KNOWLEDGE_FIRM_STANDARDS):
        raise NotFound(KNOWLEDGE_FIRM_STANDARDS.name)


async def _parsed[**P, T](
    parser: Callable[P, tuple[T, list[standards_import.Problem]]],
    *args: P.args,
    **kwargs: P.kwargs,
) -> tuple[T, list[standards_import.Problem]]:
    """A workbook parsed in the isolated child (hostile content; ADR-052): a child that crashes or
    runs out of time or memory is one `not_a_workbook` problem."""
    try:
        return await asyncio.to_thread(run_isolated, parser, *args, **kwargs)
    except IsolationFailed:
        _invalid([standards_import.Problem("", None, None, "not_a_workbook")])


async def _body(request: Request) -> bytes:
    """The workbook, refused past the limit before it is all read."""
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > standards_import.MAX_BYTES:
            _invalid([standards_import.Problem("", None, None, "too_large")])
    return bytes(data)


def _problem(
    sheet: str, row: int | None, column: str | None, code: str
) -> StandardImportProblemOut:
    return StandardImportProblemOut(sheet=sheet, row=row, column=column, code=code)


def _invalid(problems: Sequence[standards_import.Problem]) -> NoReturn:
    """422 `import_invalid`: where and what, never a cell (ADR-052), in the validation shape."""
    raise RequestValidationError(
        [
            {
                "loc": ("body", *(p for p in (p.sheet, p.row, p.column) if p is not None)),
                "msg": p.code,
                "type": "import_invalid",
            }
            for p in problems
        ]
    )


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
)
async def standard_export_version_route(
    standard_id: StandardId, version_id: VersionId, ctx: Ctx
) -> Response:
    """The version as a workbook; re-importing it gives an empty diff (US-5.1; K-02-T11)."""
    await _gate(ctx)
    kind, key, number, payload = await standards.version_payload(ctx, standard_id, version_id)
    body = standards_import.export_workbook(kind, f"{key} v{number}", payload)
    return Response(
        content=body,
        media_type=XLSX,
        headers={"Content-Disposition": f'attachment; filename="{key}-v{number}.xlsx"'},
    )


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
    errors=(409,),
)
async def import_standard_route(
    standard_id: StandardId,
    request: Request,
    ctx: Ctx,
    format: Annotated[Literal["xlsx", "csv"], Query()] = "xlsx",
) -> StandardImportResultOut:
    """A workbook to a draft of this standard (its owner's; 422 `import_invalid` with
    problems). Never publishes (K-02-T11). The workbook is the raw body (DEC-1357)."""
    await _import_gate(ctx)
    data = await _body(request)
    kind = (await standards.standard_detail(ctx, standard_id, None)).standard.kind
    payload, problems = await _parsed(
        standards_import.read_payload_isolated, kind, data, format == "csv"
    )
    if payload is None:
        _invalid(problems)
    draft = await standards.import_draft(ctx, standard_id, payload)
    return StandardImportResultOut(drafts=[draft], problems=[])


@standards_router.post(
    "/imports",
    action="firm_standard.import",
    response_model=StandardImportResultOut,
    status_code=201,
)
async def import_standards_route(request: Request, ctx: Ctx) -> StandardImportResultOut:
    """Onboarding: one sheet per kind, one draft per standard; an owner who is not a partner
    member is a row problem (`owner_not_partner`; K-02-T11). The other rows still import."""
    await _import_gate(ctx)
    rows, problems = await _parsed(standards_import.read_onboarding_isolated, await _body(request))
    if problems:
        _invalid(problems)
    owners = await partner_members(ctx.tenant_id)
    by_email = {e.lower(): u for u, e in (await emails_of(sorted(owners))).items()}
    drafts: list[StandardVersionSummaryOut] = []
    found: list[StandardImportProblemOut] = []
    for row in rows:
        owner = by_email.get(row.owner_email.lower())
        if owner is None:
            found.append(_problem(standards_import.STANDARDS, row.row, "D", "owner_not_partner"))
            continue
        try:
            created = await standards.create_standard(
                ctx,
                StandardCreateIn.model_validate(
                    {"key": row.key, "name": row.name, "kind": row.kind, "owner_id": owner}
                ),
            )
            drafts.append(await standards.import_draft(ctx, created.id, row.payload))
        except (DomainInvalid, DomainConflict, ValidationError) as refused:
            code = getattr(refused, "code", None) or "row_invalid"
            found.append(_problem(standards_import.STANDARDS, row.row, None, str(code)))
    return StandardImportResultOut(drafts=drafts, problems=found)

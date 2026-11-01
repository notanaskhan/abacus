"""Methodology import review routes (K-01-T18; K-01 §4.3; `docs/contracts/methodology-programs.md`
§import review; DEC-1755). Behind `methodology.import_review`: a client principal is 404, the
action is checked at the firm, then the flag (404 off). File bodies are raw (TASK-023 D3); storage
keys never leave the server.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, cast
from urllib.parse import quote
from uuid import UUID

from fastapi import Depends, Header, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import METHODOLOGY_IMPORT_REVIEW
from abacus.kernel.classification import classified
from abacus.kernel.config import settings
from abacus.kernel.listing import ListPage
from abacus.kernel.text import SingleLineText
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.methodology import extraction, imports
from abacus.modules.methodology.contract import VersionStateOut, require_live, version_state_out
from abacus.modules.methodology.service import EngagementType

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
ImportId = Annotated[UUID, Path()]
VersionId = Annotated[UUID, Path()]
MANAGE = "methodology.manage"
READ = "methodology.read"

methodology_import_router = AbacusRouter(prefix="/v1/methodology", tags=["methodology"])


class SourceFileOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    role: Annotated[imports.FileRole, classified("internal")]
    filename: Annotated[str, classified("internal")]
    media_type: Annotated[str, classified("internal")]
    bytes: Annotated[int, classified("internal")]
    sha256: Annotated[str, classified("internal")]
    scan_status: Annotated[Literal["clean"], classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


ImportStatus = Literal[
    "awaiting_files", "scanning", "parsing", "needs_review", "failed", "cancelled"
]


class MethodologyImportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    template_id: Annotated[UUID, classified("internal")]
    version_id: Annotated[UUID | None, classified("internal")]
    status: Annotated[ImportStatus, classified("internal")]
    pages_done: Annotated[int, classified("internal")]
    pages_total: Annotated[int | None, classified("internal")]
    failure_code: Annotated[str | None, classified("internal")]
    started_at: Annotated[datetime, classified("internal")]
    files: Annotated[list[SourceFileOut], classified("internal")]


class MethodologyImportIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    template_name: Annotated[
        SingleLineText, Field(min_length=1, max_length=100), classified("internal")
    ]
    engagement_types: Annotated[
        list[EngagementType], Field(max_length=5), classified("internal")
    ] = []


def _import_out(view: imports.ImportView) -> MethodologyImportOut:
    return MethodologyImportOut(
        id=view.id,
        template_id=view.template_id,
        version_id=view.version_id,
        status=cast("ImportStatus", view.status),
        pages_done=view.pages_done,
        pages_total=view.pages_total,
        failure_code=view.failure_code,
        started_at=view.started_at,
        files=[
            SourceFileOut(
                id=f.id,
                role=cast("imports.FileRole", f.role),
                filename=f.filename,
                media_type=f.media_type,
                bytes=f.bytes,
                sha256=f.sha256,
                scan_status="clean",
                created_at=f.created_at,
            )
            for f in view.files
        ],
    )


@methodology_import_router.post(
    "/imports",
    action=MANAGE,
    response_model=MethodologyImportOut,
    status_code=201,
)
async def create_import_route(
    body: MethodologyImportIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> MethodologyImportOut:
    """KNW-02 "+ Upload methodology…": an import for the named template, once per
    Idempotency-Key (the same key answers the same import)."""
    await require_live(ctx, METHODOLOGY_IMPORT_REVIEW, MANAGE)
    return _import_out(
        await imports.create_import(
            ctx,
            template_name=body.template_name,
            engagement_types=list(body.engagement_types),
            idempotency_key=idempotency_key,
        )
    )


@methodology_import_router.get(
    "/imports/{import_id}", action=MANAGE, response_model=MethodologyImportOut
)
async def get_import_route(import_id: ImportId, ctx: Ctx) -> MethodologyImportOut:
    """The import, its files and its progress (KNW-02 b polls it)."""
    await require_live(ctx, METHODOLOGY_IMPORT_REVIEW, MANAGE)
    return _import_out(await imports.import_view(ctx, import_id))


async def _body(request: Request) -> bytes:
    """The file, read up to the limit (a larger body is refused before it is all read)."""
    limit = settings().methodology_max_bytes
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > limit:
            raise imports.FileTooLarge(facts={"limit": limit})
    return bytes(data)


@methodology_import_router.put(
    "/imports/{import_id}/files/{role}",
    action=MANAGE,
    response_model=MethodologyImportOut,
    errors=(409,),
)
async def upload_file_route(
    import_id: ImportId,
    role: Annotated[imports.FileRole, Path()],
    request: Request,
    ctx: Ctx,
    filename: Annotated[SingleLineText, Query(min_length=1, max_length=255)],
) -> MethodologyImportOut:
    """One file for a role, as the raw request body (no multipart): scanned and typed before it
    is kept, written once. 409 `import_frozen`, `file_exists`; 422 `file_too_large` and the
    upload refusals (`file_refused`, …)."""
    await require_live(ctx, METHODOLOGY_IMPORT_REVIEW, MANAGE)
    return _import_out(
        await imports.upload_file(ctx, import_id, role, filename, await _body(request))
    )


@methodology_import_router.post(
    "/imports/{import_id}/start",
    action=MANAGE,
    response_model=MethodologyImportOut,
    errors=(409,),
)
async def start_import_route(import_id: ImportId, ctx: Ctx) -> MethodologyImportOut:
    """Read the files. A workbook alone lands its version in Needs review now; a document needs
    the Methodology importer (409 `importer_not_enabled`). 409 `import_frozen`, `files_missing`."""
    await require_live(ctx, METHODOLOGY_IMPORT_REVIEW, MANAGE)
    return _import_out(await imports.start_import(ctx, import_id))


@methodology_import_router.post(
    "/imports/{import_id}/cancel",
    action=MANAGE,
    response_model=MethodologyImportOut,
    errors=(409,),
)
async def cancel_import_route(import_id: ImportId, ctx: Ctx) -> MethodologyImportOut:
    """Stop an import that has not finished; 409 `import_frozen` otherwise."""
    await require_live(ctx, METHODOLOGY_IMPORT_REVIEW, MANAGE)
    return _import_out(await imports.cancel_import(ctx, import_id))


@methodology_import_router.get(
    "/versions/{version_id}/files/{file_id}/download",
    action=READ,
    response_model=bytes,
    errors=(),
)
async def methodology_file_download_route(
    version_id: VersionId, file_id: Annotated[UUID, Path()], ctx: Ctx
) -> Response:
    """The original file (audited)."""
    await require_live(ctx, METHODOLOGY_IMPORT_REVIEW, READ)
    found = await imports.download_file(ctx, version_id, file_id)
    return Response(
        content=found.content,
        media_type=found.media_type,
        headers={
            "Content-Disposition": _attachment(found.filename),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


# --- pages (K-01-T20) ----------------------------------------------------------------------------


class PageWordOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: Annotated[str, classified("confidential")]
    # x0, top, x1, bottom as fractions of the page.
    box: Annotated[tuple[float, float, float, float], classified("internal")]


class MethodologyPageWordsOut(BaseModel):
    """One page's words with their boxes for the KNW-02 viewer (TIN forms masked)."""

    model_config = ConfigDict(frozen=True)

    page: Annotated[int, classified("internal")]
    page_count: Annotated[int, classified("internal")]
    words: Annotated[list[PageWordOut], classified("confidential")]


PageNo = Annotated[int, Path(ge=1, le=extraction.MAX_PAGES)]


@methodology_import_router.get(
    "/versions/{version_id}/files/{file_id}/pages/{page_no}",
    action=READ,
    response_model=bytes,
    errors=(409,),
)
async def methodology_file_page_route(
    version_id: VersionId, file_id: Annotated[UUID, Path()], page_no: PageNo, ctx: Ctx
) -> Response:
    """One page of a PDF source as a PNG, read in the isolated child (audited; `no-store`): 409
    `page_preview_unavailable` for a DOCX, 422 `page_out_of_range`, `source_encrypted`,
    `source_malformed`."""
    await require_live(ctx, METHODOLOGY_IMPORT_REVIEW, READ)
    found = await extraction.page_image(ctx, version_id, file_id, page_no)
    return Response(
        content=found.png,
        media_type="image/png",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@methodology_import_router.get(
    "/versions/{version_id}/files/{file_id}/pages/{page_no}/words",
    action=READ,
    response_model=MethodologyPageWordsOut,
    errors=(409,),
)
async def methodology_file_page_words_route(
    version_id: VersionId,
    file_id: Annotated[UUID, Path()],
    page_no: PageNo,
    ctx: Ctx,
    response: Response,
) -> MethodologyPageWordsOut:
    """One page's words and their boxes, for the viewer's regions and MatchProvider tracing."""
    await require_live(ctx, METHODOLOGY_IMPORT_REVIEW, READ)
    found = await extraction.page_words(ctx, version_id, file_id, page_no)
    response.headers["Cache-Control"] = "no-store"
    return MethodologyPageWordsOut(
        page=found.page,
        page_count=found.page_count,
        words=[PageWordOut(text=w.text, box=w.box) for w in found.words],
    )


def _attachment(name: str) -> str:
    """A person's file name as a header: an ASCII fallback with no quote or backslash, and the
    UTF-8 name percent-encoded (RFC 6266, RFC 5987); a raw name breaks quoting or the header's
    Latin-1 encoding."""
    fallback = (
        "".join(ch if 0x20 <= ord(ch) < 0x7F and ch not in '"\\' else "_" for ch in name) or "file"
    )
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"


# --- diff ----------------------------------------------------------------------------------------


class DiffTilesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    added: Annotated[int, classified("internal")]
    changed: Annotated[int, classified("internal")]
    removed: Annotated[int, classified("internal")]
    unchanged: Annotated[int, classified("internal")]


class DiffRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[Literal["added", "changed", "removed"], classified("internal")]
    program_code: Annotated[str, classified("internal")]
    number: Annotated[int, classified("internal")]
    step_key: Annotated[str, classified("internal")]
    before_text: Annotated[str | None, classified("internal")]
    after_text: Annotated[str | None, classified("internal")]
    changed_fields: Annotated[list[str], classified("internal")]


class VersionDiffOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_id: Annotated[UUID, classified("internal")]
    against_version_id: Annotated[UUID | None, classified("internal")]
    against_label: Annotated[str | None, classified("internal")]
    tiles: Annotated[DiffTilesOut, classified("internal")]
    rows: Annotated[list[DiffRowOut], classified("internal")]


@methodology_import_router.get(
    "/versions/{version_id}/diff", action=READ, response_model=VersionDiffOut, errors=()
)
async def methodology_version_diff_route(
    version_id: VersionId,
    ctx: Ctx,
    against: Annotated[UUID | None, Query()] = None,
) -> VersionDiffOut:
    """KNW-02 c: the code-computed diff against another version of the template (default: the
    version drafted from, else the one numbered before)."""
    await require_live(ctx, METHODOLOGY_IMPORT_REVIEW, READ)
    view = await imports.version_diff(ctx, version_id, against)
    d = view.diff
    return VersionDiffOut(
        version_id=view.version_id,
        against_version_id=view.against_version_id,
        against_label=view.against_label,
        tiles=DiffTilesOut(
            added=d.added, changed=d.changed, removed=d.removed, unchanged=d.unchanged
        ),
        rows=[
            DiffRowOut(
                kind=r.kind,
                program_code=r.program_code,
                number=r.number,
                step_key=r.step_key,
                before_text=r.before_text,
                after_text=r.after_text,
                changed_fields=list(r.changed_fields),
            )
            for r in d.rows
        ],
    )


# --- standards mapping ---------------------------------------------------------------------------


# An engagement type code the version serves (the EBP subtypes as well as the SPEC-024 types;
# K-01 AC6.2 names three EBP types).
EngagementTypeCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,47}$")]


class StandardsMappingIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    standards_set_id: Annotated[UUID | None, classified("internal")]
    quality_management_ref: Annotated[
        SingleLineText | None, Field(max_length=120), classified("internal")
    ] = None
    engagement_types: Annotated[
        list[EngagementTypeCode], Field(max_length=10), classified("internal")
    ]
    default_for_new_engagements: Annotated[bool, classified("internal")]
    row_version: Annotated[int, Field(ge=1), classified("internal")]


@methodology_import_router.put(
    "/versions/{version_id}/standards-mapping",
    action=MANAGE,
    response_model=VersionStateOut,
    errors=(409,),
)
async def standards_mapping_route(
    version_id: VersionId, body: StandardsMappingIn, ctx: Ctx
) -> VersionStateOut:
    """KNW-02 d: the standards set (a published platform set; 422 `standards_set_invalid`), the
    QM reference, the engagement types and the default, on a draft or a version in review."""
    await require_live(ctx, METHODOLOGY_IMPORT_REVIEW, MANAGE)
    return await version_state_out(
        ctx,
        await imports.map_standards(
            ctx,
            version_id,
            standards_set_id=body.standards_set_id,
            quality_management_ref=body.quality_management_ref,
            engagement_types=list(body.engagement_types),
            default_for_new_engagements=body.default_for_new_engagements,
            row_version=body.row_version,
        ),
    )


# --- flag resolution and activity ----------------------------------------------------------------


class FlagResolutionIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Annotated[Literal["confirm", "edit"], classified("internal")]
    text: Annotated[str | None, Field(max_length=4000), classified("internal")] = None
    row_version: Annotated[int, Field(ge=1), classified("internal")]


class FlagResolutionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_id: Annotated[UUID, classified("internal")]
    step_key: Annotated[str, classified("internal")]
    parse_flag: Annotated[str, classified("internal")]
    resolution: Annotated[Literal["confirmed", "edited"], classified("internal")]
    text: Annotated[str, classified("internal")]
    row_version: Annotated[int, classified("internal")]


@methodology_import_router.post(
    "/versions/{version_id}/steps/{step_id}/flag-resolution",
    action=MANAGE,
    response_model=FlagResolutionOut,
    errors=(409,),
)
async def flag_resolution_route(
    version_id: VersionId,
    step_id: Annotated[UUID, Path()],
    body: FlagResolutionIn,
    ctx: Ctx,
) -> FlagResolutionOut:
    """KNW-02 a2: confirm the parse or edit the text (the step keeps its citation). 409
    `flag_not_open`, `stale_version`, `version_frozen`."""
    await require_live(ctx, METHODOLOGY_IMPORT_REVIEW, MANAGE)
    done = await imports.resolve_flag(
        ctx, version_id, step_id, action=body.action, text=body.text, row_version=body.row_version
    )
    return FlagResolutionOut(
        step_id=done.step_id,
        step_key=done.step_key,
        parse_flag=done.parse_flag,
        resolution="confirmed" if done.resolution == "confirmed" else "edited",
        text=done.text,
        row_version=done.row_version,
    )


ActorKind = Literal["human", "agent", "system"]


class VersionActivityOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    seq: Annotated[int, classified("internal")]
    kind: Annotated[str, classified("internal")]
    actor_kind: Annotated[ActorKind, classified("internal")]
    actor_user_id: Annotated[UUID | None, classified("internal")]
    actor_name: Annotated[str | None, classified("internal")]
    at: Annotated[datetime, classified("internal")]
    facts: Annotated[dict[str, object], classified("internal")]


@methodology_import_router.get(
    "/versions/{version_id}/activity",
    action=READ,
    response_model=ListPage[VersionActivityOut],
)
async def methodology_version_activity_route(
    version_id: VersionId, ctx: Ctx
) -> ListPage[VersionActivityOut]:
    """KNW-02's Activity tab: every version event with its named actor and time."""
    await require_live(ctx, METHODOLOGY_IMPORT_REVIEW, READ)
    entries = await imports.version_activity(ctx, version_id)
    return ListPage[VersionActivityOut](
        items=[
            VersionActivityOut(
                seq=e.seq,
                kind=e.kind,
                actor_kind=cast("ActorKind", e.actor_kind),
                actor_user_id=e.actor_user_id,
                actor_name=e.actor_name,
                at=e.at,
                facts=e.facts,
            )
            for e in entries
        ],
        total=len(entries),
    )


__all__ = ["methodology_import_router"]

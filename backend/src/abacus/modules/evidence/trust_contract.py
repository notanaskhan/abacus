"""C4 v1, the trust kit (P-03-T02; ADR-166 for P-48, ADR-066, ADR-110; P-36 contract first).

Citations v2, the source viewer, logged PII reveal and password unlock as a derivation. Each
family sits behind its own flag. Off, its routes answer 404; on, 501 `not_implemented` until its
service lands:
- `evidence.citations_v2`: citations; the two reads are served (P-03-T08), relink is P-03-T12;
- `evidence.viewer_v1`: the viewer; served (P-03-T09);
- `evidence.pii_reveal`: reveal; P-03-T12;
- `evidence.viewer_unlock`: unlock; P-03-T14.
`POST /v1/citations` is reserved: 501 until its first anchor consumer.

Shapes per P-03 §4.3 and `docs/contracts/c04-citations-viewer.md`. Hard rules:
- `title` and `loc` are rendered by code from the locator, never from model text (INV-2).
- A quote is re-read from the masked word layer; it is never stored.
- Viewer routes carry geometry and mask tokens only, never text.
- A revealed value leaves only in the reveal response, `no-store`, never logged (DEC-60).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Path, Query, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from abacus.kernel._flags import (
    EVIDENCE_CITATIONS_V2,
    EVIDENCE_PII_REVEAL,
    EVIDENCE_VIEWER_UNLOCK,
    EVIDENCE_VIEWER_V1,
)
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.evidence.citations.display import (
    CitationFilters,
    CitationView,
    citation_display,
    citation_list,
)
from abacus.modules.evidence.routes import (
    _png_response,  # pyright: ignore[reportPrivateUsage] -- the module's own PNG answer
)
from abacus.modules.evidence.viewer import (
    viewer_manifest,
    viewer_page,
    viewer_regions,
    viewer_search,
)
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]

CitationKind = Literal[
    "document_text",
    "sheet_cell",
    "ledger_line",
    "workpaper_cell",
    "methodology_step",
    "policy_rule",
    "record_field",
    "tax_form_line",
    "artifact_cell",
    "request_item",
]
VerificationReason = Literal[
    "page_not_found",
    "cell_not_found",
    "quote_not_found",
    "value_mismatch",
    "bbox_mismatch",
    "source_not_found",
    "source_not_visible",
    "locator_invalid",
]
CitationState = Literal["valid", "moved", "broken", "relinked"]
QuoteState = Literal["shown", "withheld", "changed"]
PiiKind = Literal["ssn", "itin", "ein", "bank_account", "routing_number", "dob"]
ViewerStatus = Literal[
    "processing", "ready", "password_protected", "unreadable", "not_previewable"
]
ViewerKind = Literal["pages", "image", "table", "none"]
AnchorType = Annotated[str, Field(pattern=r"^[a-z][a-z_]{0,39}$")]
# A page rect in page points, top-left origin: [x0, top, x1, bottom].
Rect = Annotated[list[float], Field(min_length=4, max_length=4)]

router = AbacusRouter(prefix="/v1", tags=["trust kit"])


async def _gate(ctx: AuthContext, gate: Flag) -> None:
    """A family's flag: off, its routes answer 404 (the repo's stub convention)."""
    if not await flag_enabled(ctx.tenant, gate):
        raise NotFound(gate.name)


async def _stub(ctx: AuthContext, gate: Flag) -> NoReturn:
    await _gate(ctx, gate)
    raise NotImplementedYet


# --- Citations ------------------------------------------------------------------------------


class CitationCreatorOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[Literal["agent", "human", "system"], classified("internal")]
    label: Annotated[str, classified("confidential")]  # "<person> via Agent", rendered by code


class CitationSourceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Annotated[str, classified("internal")]
    id: Annotated[UUID, classified("internal")]
    version: Annotated[str | None, classified("internal")]
    evidence_version_id: Annotated[UUID | None, classified("internal")]
    page: Annotated[int | None, Field(ge=1), classified("internal")]


class CitationMovedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    successor_ref: Annotated[str | None, classified("internal")]
    at: Annotated[datetime, classified("internal")]


class CitationV2Out(BaseModel):
    """The display contract: what a popover, chip or linked-figure row reads."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    n: Annotated[int, Field(ge=1), classified("internal")]
    kind: Annotated[CitationKind, classified("internal")]
    title: Annotated[str, classified("confidential")]
    loc: Annotated[str, classified("confidential")]
    quote: Annotated[str | None, classified("restricted")]  # re-read from the masked layer
    quote_state: Annotated[QuoteState, classified("internal")]
    value_text: Annotated[str | None, classified("confidential")]
    match_id: Annotated[str | None, classified("internal")]
    state: Annotated[CitationState, classified("internal")]
    verified: Annotated[bool, classified("internal")]
    verification_reason: Annotated[VerificationReason | None, classified("internal")]
    created_by: Annotated[CitationCreatorOut, classified("confidential")]
    retrieved_at: Annotated[datetime | None, classified("internal")]
    source: Annotated[CitationSourceOut, classified("internal")]
    used_in: Annotated[int, Field(ge=0), classified("internal")]
    moved: Annotated[CitationMovedOut | None, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]


class CitationLocatorIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_version_id: Annotated[UUID, classified("internal")]
    page: Annotated[int, Field(ge=1, le=5000), classified("internal")]
    bbox: Annotated[Rect, classified("internal")]


class CitationCreateIn(BaseModel):
    """Reserved (Cite selection): the server derives the quote from the layer and ignores any
    client text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cited_from_type: Annotated[AnchorType, classified("internal")]
    cited_from_id: Annotated[UUID, classified("internal")]
    cited_from_ref: Annotated[str, Field(min_length=1, max_length=120), classified("internal")]
    kind: Annotated[Literal["document_text"], classified("internal")]
    locator: Annotated[CitationLocatorIn, classified("internal")]


def _citation_out(view: CitationView) -> CitationV2Out:
    return CitationV2Out.model_validate(asdict(view))


@router.get(
    "/citations/{citation_id}",
    action="citation.read",
    response_model=CitationV2Out,
    errors=(501,),
)
async def get_citation_route(citation_id: UUID, ctx: Ctx) -> CitationV2Out:
    """AC1.5, AC2.1: one citation; walled or unknown answers 404, a client principal 403."""
    await _gate(ctx, EVIDENCE_CITATIONS_V2)
    return _citation_out(await citation_display(ctx, citation_id))


@router.get(
    "/citations",
    action="citation.read",
    response_model=ListPage[CitationV2Out],
    errors=(501,),
)
async def list_citations_route(
    ctx: Ctx,
    anchor_type: Annotated[AnchorType | None, Query()] = None,
    anchor_id: Annotated[UUID | None, Query()] = None,
    anchor_ref: Annotated[str | None, Query(max_length=120)] = None,
    host_ref: Annotated[str | None, Query(max_length=120)] = None,
    section_id: Annotated[str | None, Query(max_length=120)] = None,
    source_version_id: Annotated[UUID | None, Query()] = None,
    kind: Annotated[CitationKind | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ListPage[CitationV2Out]:
    """AC2.2, AC2.6, AC3.2, AC3.6: an anchor's stack (by `n`), a section's list, the rows a
    version's figures are cited by. Walled citations are omitted with no hidden count.
    `host_ref` is `<anchor_type>:<anchor_id>` (DEC-265)."""
    await _gate(ctx, EVIDENCE_CITATIONS_V2)
    found = await citation_list(
        ctx,
        CitationFilters(
            anchor_type, anchor_id, anchor_ref, host_ref, section_id, source_version_id, kind
        ),
        cursor=cursor,
        limit=limit,
    )
    return ListPage[CitationV2Out](
        items=[_citation_out(v) for v in found.items],
        next_cursor=found.next_cursor,
        total=found.total,
        total_capped=found.total_capped,
    )


@router.post(
    "/citations/{citation_id}/relink",
    action="citation.relink",
    response_model=CitationV2Out,
    status_code=201,
    errors=(409, 501),
)
async def relink_citation_route(citation_id: UUID, ctx: Ctx) -> CitationV2Out:
    """AC6.2: a person re-verifies a moved citation on its successor. 409 `not_moved`; 422
    `relink_unverified`."""
    await _stub(ctx, EVIDENCE_CITATIONS_V2)


@router.post(
    "/citations",
    action="citation.create",
    response_model=CitationV2Out,
    status_code=201,
    errors=(501,),
)
async def create_citation_route(body: CitationCreateIn, ctx: Ctx) -> CitationV2Out:
    """Reserved: answers 501 behind the flag until its first anchor consumer (P-03 §2.3)."""
    await _stub(ctx, EVIDENCE_CITATIONS_V2)


# --- Source viewer (geometry and mask tokens only, never text) ------------------------------


class ViewerPageOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    n: Annotated[int, Field(ge=1), classified("internal")]
    width_pt: Annotated[float, classified("internal")]
    height_pt: Annotated[float, classified("internal")]
    rotation: Annotated[Literal[0, 90, 180, 270], classified("internal")]
    image_w: Annotated[int, classified("internal")]
    image_h: Annotated[int, classified("internal")]
    text_layer: Annotated[bool, classified("internal")]
    pii_scan: Annotated[Literal["done", "not_scannable"], classified("internal")]


class PiiMaskOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    page: Annotated[int, Field(ge=1), classified("internal")]
    rect: Annotated[Rect, classified("internal")]
    kind: Annotated[PiiKind, classified("internal")]
    display: Annotated[str, classified("confidential")]  # "•••-••-6081": the mask token


class ViewerManifestOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_version_id: Annotated[UUID, classified("internal")]
    file_name: Annotated[str, classified("confidential")]
    media_type: Annotated[str, classified("internal")]
    status: Annotated[ViewerStatus, classified("internal")]
    reason: Annotated[str | None, classified("internal")]
    kind: Annotated[ViewerKind, classified("internal")]
    page_count: Annotated[int, Field(ge=0), classified("internal")]
    truncated: Annotated[bool, classified("internal")]
    pages: Annotated[list[ViewerPageOut], classified("internal")]
    pii_masks: Annotated[list[PiiMaskOut], classified("confidential")]
    derivation_id: Annotated[UUID | None, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]


class ViewerRegionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    match_id: Annotated[str, classified("internal")]
    page: Annotated[int | None, Field(ge=1), classified("internal")]
    rects: Annotated[list[Rect], classified("internal")]
    sheet: Annotated[str | None, classified("confidential")]  # a table cell instead of rects
    cell: Annotated[str | None, classified("internal")]
    citation_id: Annotated[UUID | None, classified("internal")]
    label: Annotated[str | None, classified("confidential")]


class ViewerRegionsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ViewerRegionOut], classified("internal")]


class ViewerSearchHitOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    page: Annotated[int, Field(ge=1), classified("internal")]
    rects: Annotated[list[Rect], classified("internal")]


class ViewerSearchOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ViewerSearchHitOut], classified("internal")]
    total: Annotated[int, Field(ge=0), classified("internal")]
    truncated: Annotated[bool, classified("internal")]


VersionId = Annotated[UUID, Path()]


@router.get(
    "/evidence-versions/{version_id}/viewer",
    action="evidence.read",
    response_model=ViewerManifestOut,
    errors=(501,),
)
async def viewer_manifest_route(version_id: VersionId, ctx: Ctx) -> ViewerManifestOut:
    """AC3.1, AC3.4, AC4.8, AC5.1: the manifest; walled or invisible versions answer 404. Until
    masked renditions exist (P-03-T15) a rendered version reads `processing`, reason
    `preview_outdated` (DEC-266)."""
    await _gate(ctx, EVIDENCE_VIEWER_V1)
    return ViewerManifestOut.model_validate(asdict(await viewer_manifest(ctx, version_id)))


@router.get(
    "/evidence-versions/{version_id}/pages/{page_no}",
    action="evidence.read",
    response_model=bytes,
    errors=(409, 501),
)
async def viewer_page_route(
    version_id: VersionId,
    page_no: Annotated[int, Path(ge=1, le=5000)],
    ctx: Ctx,
) -> Response:
    """AC4.2: the masked PNG (`no-store`, `nosniff`); 409 `preview_outdated` for a preview made
    before masking. The read leaves an access event first (Q-02-T20)."""
    await _gate(ctx, EVIDENCE_VIEWER_V1)
    return _png_response(await viewer_page(ctx, version_id, page_no))


@router.get(
    "/evidence-versions/{version_id}/regions",
    action="evidence.read",
    response_model=ViewerRegionsOut,
    errors=(501,),
)
async def viewer_regions_route(
    version_id: VersionId,
    ctx: Ctx,
    match_ids: Annotated[list[str] | None, Query(max_length=200)] = None,
) -> ViewerRegionsOut:
    """AC3.1, AC3.6: where the cited matches are, in page points."""
    await _gate(ctx, EVIDENCE_VIEWER_V1)
    found = await viewer_regions(ctx, version_id, match_ids)
    return ViewerRegionsOut.model_validate({"items": [asdict(r) for r in found]})


@router.get(
    "/evidence-versions/{version_id}/search",
    action="evidence.read",
    response_model=ViewerSearchOut,
    errors=(501,),
)
async def viewer_search_route(
    version_id: VersionId,
    ctx: Ctx,
    q: Annotated[str, Query(min_length=1, max_length=200)],
) -> ViewerSearchOut:
    """AC3.9: page rects only, at most 200; the query is never logged."""
    await _gate(ctx, EVIDENCE_VIEWER_V1)
    return ViewerSearchOut.model_validate(asdict(await viewer_search(ctx, version_id, q)))


# --- Logged reveal and unlock (human only) --------------------------------------------------


class PiiRevealIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    region_id: Annotated[UUID, classified("internal")]
    context_ref: Annotated[str | None, Field(max_length=120), classified("internal")] = None


class PiiRevealOut(BaseModel):
    """The only payload that carries a revealed value; `Cache-Control: no-store` (DEC-60)."""

    model_config = ConfigDict(frozen=True)

    mask_id: Annotated[UUID, classified("internal")]
    value: Annotated[str, classified("restricted")]
    kind: Annotated[PiiKind, classified("internal")]
    expires_in: Annotated[int, Field(ge=1, le=60), classified("internal")]
    revealed_by: Annotated[str, classified("confidential")]
    revealed_at: Annotated[datetime, classified("internal")]


class EvidenceUnlockIn(BaseModel):
    """AC5.4: the password is a secret; never logged, stored or echoed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    password: Annotated[SecretStr, Field(min_length=1, max_length=256), classified("restricted")]


class EvidenceUnlockOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Annotated[Literal["ready", "wrong_password"], classified("internal")]
    attempts_left: Annotated[int | None, Field(ge=0), classified("internal")]
    derivation_id: Annotated[UUID | None, classified("internal")]


@router.post(
    "/evidence-versions/{version_id}/pii-reveals",
    action="pii.reveal",
    response_model=PiiRevealOut,
    status_code=201,
    errors=(501,),
)
async def reveal_pii_route(version_id: VersionId, body: PiiRevealIn, ctx: Ctx) -> PiiRevealOut:
    """AC4.4 to AC4.7: 403 `offshore`, `mfa_required` or `role`; 429 `reveal_rate_limited`."""
    await _stub(ctx, EVIDENCE_PII_REVEAL)


@router.post(
    "/evidence-versions/{version_id}/unlock",
    action="evidence.unlock",
    response_model=EvidenceUnlockOut,
    errors=(409, 501),
)
async def unlock_version_route(
    version_id: VersionId, body: EvidenceUnlockIn, ctx: Ctx
) -> EvidenceUnlockOut:
    """AC5.2, AC5.3: a derivation, never a change to the evidence; 409 `not_password_protected`;
    429 `unlock_rate_limited` with `retry_after`."""
    await _stub(ctx, EVIDENCE_VIEWER_UNLOCK)

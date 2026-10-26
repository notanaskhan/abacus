"""Engagement export v1: the contract stub (A-01-T17; SPEC-344; ADR-036). Contract:
`docs/contracts/engagement-export-v1.md`.

For the export sheet (AUD-02, AUD-03; A-01-T24), Q-04's rollback path, G-02/Q-02's firm export
and A-07's archive seal. Behind `audits.binder_export` (off: 404; on: 501 `not_implemented` until
A-01-T18 creates, undoes and reads, and A-01-T22 downloads). The shapes are fixed here so the
consumers' tests and fixture mode run against them:

- `POST /v1/work-items/{work_item_id}/exports` (`export.create`: engagement partner or manager,
  fresh MFA, independence, not offshore; `Idempotency-Key`): 202 `queued` with `not_before` ten
  seconds on, a single-use approval grant behind it (P-35). A retried key returns the same export.
  422 `export_kind_unsupported` for a work item that is not an audit (fail closed until C19);
  422 `binder_not_in_work_item` for a binder id that is not one of the work item's (DEC-379).
- `POST /v1/exports/{export_id}/undo` (`export.create`): inside the window, `undone`; after it,
  409 `undo_window_closed`.
- `GET /v1/work-items/{work_item_id}/exports` and `GET /v1/exports/{export_id}` (`export.read`):
  the sheet's history and its 3-second poll.
- `GET /v1/exports/{export_id}/download` (`export.download`: fresh MFA, not offshore; the
  requester or an `export.create` holder on the engagement): the decrypted ZIP streamed by the API
  (no presigned link, ADR-104), resumable with `Range`; 409 `export_not_ready` before `ready`,
  410 `export_expired` after the 7 days or once voided.

Statuses are C2's `engagement_export` codes. No route is reachable by a client principal (INV-4)
and the agent holds none of the actions (INV-1). Sizes are bytes; counts and digests exist only
once the package is built. The stub checks the flag first, as every stub does; the implementing
tasks authorise first (404 behind a wall before anything else).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import AUDITS_BINDER_EXPORT
from abacus.kernel._statuses import EngagementExportStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.evidence.export_manifest import ExportKind
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
# ADR-139: a create starts a workflow and a single-use grant, so it carries a key.
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

# Why a build failed; the sheet words it (A-01-T24).
ExportFailure = Literal["integrity_mismatch", "export_section_missing", "build_error"]
# Why a ready export was voided before its 7 days (P-31: withdrawn content).
ExportVoidReason = Literal["withdrawn_content", "expired"]
# What the person may do with this export now; the sheet shows only these controls.
ExportAllowedAction = Literal["undo", "download"]


class ExportScopeIn(BaseModel):
    """The export sheet's options. No binder ids means every PBC binder of the work item."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    binder_ids: Annotated[list[UUID], Field(max_length=50), classified("internal")] = []
    include_unaccepted: Annotated[bool, classified("internal")] = False
    include_audit_trail: Annotated[bool, classified("internal")] = True


class ExportCreateIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[ExportKind, classified("internal")] = "binder"
    scope: Annotated[ExportScopeIn, classified("internal")] = ExportScopeIn()


class ExportScopeOut(BaseModel):
    """The scope as resolved at create: the binder ids are always listed."""

    model_config = ConfigDict(frozen=True)

    binder_ids: Annotated[list[UUID], classified("internal")]
    include_unaccepted: Annotated[bool, classified("internal")]
    include_audit_trail: Annotated[bool, classified("internal")]


class ExportPersonOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]


class EngagementExportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    kind: Annotated[ExportKind, classified("internal")]
    scope: Annotated[ExportScopeOut, classified("internal")]
    format_version: Annotated[Literal["1.0"], classified("public")]
    status: Annotated[EngagementExportStatus, classified("internal")]
    requested_by: Annotated[ExportPersonOut, classified("internal")]
    requested_at: Annotated[datetime, classified("internal")]
    # The end of the Undo window (P-35 grant `not_before`).
    not_before: Annotated[datetime, classified("internal")]
    ready_at: Annotated[datetime | None, classified("internal")] = None
    expires_at: Annotated[datetime | None, classified("internal")] = None
    request_count: Annotated[int | None, Field(ge=0), classified("internal")] = None
    file_count: Annotated[int | None, Field(ge=0), classified("internal")] = None
    size_bytes: Annotated[int | None, Field(ge=0), classified("internal")] = None
    manifest_sha256: Annotated[Sha256 | None, classified("internal")] = None
    bundle_sha256: Annotated[Sha256 | None, classified("internal")] = None
    failure_code: Annotated[ExportFailure | None, classified("internal")] = None
    void_reason: Annotated[ExportVoidReason | None, classified("internal")] = None
    allowed_actions: Annotated[list[ExportAllowedAction], classified("internal")] = []


class EngagementExportPageOut(BaseModel):
    """The work item's exports, newest first (P-36 envelope without facets)."""

    model_config = ConfigDict(frozen=True)

    items: Annotated[list[EngagementExportOut], Field(max_length=50), classified("internal")]
    next_cursor: Annotated[str | None, classified("internal")] = None


async def _stub(ctx: AuthContext) -> NoReturn:
    if not await flag_enabled(ctx.tenant, AUDITS_BINDER_EXPORT):
        raise NotFound(AUDITS_BINDER_EXPORT.name)
    raise NotImplementedYet


work_item_exports_router = AbacusRouter(
    prefix="/v1/work-items/{work_item_id}/exports", tags=["engagement export"]
)
exports_router = AbacusRouter(prefix="/v1/exports", tags=["engagement export"])


@work_item_exports_router.post(
    "",
    action="export.create",
    response_model=EngagementExportOut,
    status_code=202,
    errors=(409, 501),
)
async def create_export_route(
    work_item_id: UUID, body: ExportCreateIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> EngagementExportOut:
    """AUD-02/03 "Export binder…" (A-01-T18): `queued` with a 10-second Undo window; 422
    `export_kind_unsupported` for a non-audit work item; audited `engagement_export.requested`."""
    await _stub(ctx)


@work_item_exports_router.get(
    "", action="export.read", response_model=EngagementExportPageOut, errors=(501,)
)
async def list_exports_route(
    work_item_id: UUID,
    ctx: Ctx,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> EngagementExportPageOut:
    """The export sheet's history for the work item, newest first (A-01-T18)."""
    await _stub(ctx)


@exports_router.get(
    "/{export_id}", action="export.read", response_model=EngagementExportOut, errors=(501,)
)
async def get_export_route(export_id: UUID, ctx: Ctx) -> EngagementExportOut:
    """The sheet's poll: Queued, Packaging…, Ready, Export failed, Expired, Undone (A-01-T18)."""
    await _stub(ctx)


@exports_router.post(
    "/{export_id}/undo",
    action="export.create",
    response_model=EngagementExportOut,
    errors=(409, 501),
)
async def undo_export_route(export_id: UUID, ctx: Ctx) -> EngagementExportOut:
    """Undo inside the window voids the grant: `undone`, no package (A-01-T18); 409
    `undo_window_closed` after it. Audited `engagement_export.undone`."""
    await _stub(ctx)


@exports_router.get(
    "/{export_id}/download",
    action="export.download",
    response_model=bytes,
    errors=(409, 410, 501),
)
async def download_export_route(
    export_id: UUID,
    ctx: Ctx,
    range_header: Annotated[str | None, Header(alias="Range", max_length=100)] = None,
) -> Response:
    """The ZIP (`application/zip`, `Cache-Control: no-store`, a safe `Content-Disposition`),
    resumable with `Range` (A-01-T22). 409 `export_not_ready`, 410 `export_expired`. Audited
    `engagement_export.downloaded` with bytes and range."""
    await _stub(ctx)

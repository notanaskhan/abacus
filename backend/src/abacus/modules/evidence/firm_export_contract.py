"""Firm export with dual approval: the contract stub (Q-02-T38; compliance-kernel v1.1; DEC-72,
conflict C-11). Contract: `docs/contracts/compliance-kernel.md` §4.

For G-02's ADM-06 (b, c, f, g) and Q-02-T43, which implements it. Behind `compliance.firm_export`
(off: 404; on: 501 `not_implemented` until Q-02-T43). The shapes are fixed here so G-02's consumer
tests and fixture mode run against them:

- `GET /v1/firm/data-exports` (`firm_export.read`): the last 12, newest first (the export card
  and the history tray).
- `POST /v1/firm/data-exports` (`firm_export.request`, fresh MFA, `Idempotency-Key`): a security
  admin asks for an export and names the partner-level approver, who must be someone else (422
  `approver_invalid`). 202, `awaiting_approval`.
- `POST /v1/firm/data-exports/{export_id}/approve` and `/decline` (`firm_export.approve`, fresh
  MFA): the named approver decides; the requester can't (409 `approver_must_differ`), a decided
  export answers 409 `export_not_awaiting_approval`.
- `POST /v1/firm/data-exports/{export_id}/link` (`firm_export.download`, fresh MFA): a 15-minute
  link while the 7-day window holds (410 `export_expired` after it); requester or approver only.

Status codes are this contract's (`FirmExportStatus`); their words ("Waiting for approval ·
Margaret Okonkwo") are G-02's screen copy. Sizes are bytes; a size or a link exists only once
the archive is built.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import COMPLIANCE_FIRM_EXPORT
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.text import SingleLineText
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
# ADR-139: a request starts a workflow and notifies the approver, so it carries a key.
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]

FirmExportStatus = Literal[
    "awaiting_approval", "declined", "building", "ready", "downloaded", "expired", "failed"
]
# v1 exports everything the firm holds (ADM-06 b "Export all firm data?"): one A-01 package per
# engagement plus a firm index. Narrower scopes are additive later.
FirmExportScope = Literal["all"]
FirmExportOrigin = Literal["on_demand", "scheduled"]

router = AbacusRouter(prefix="/v1/firm/data-exports", tags=["firm export"])


class FirmExportRequestIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    approver_user_id: Annotated[UUID, classified("internal")]
    scope: Annotated[FirmExportScope, classified("internal")] = "all"


class FirmExportDeclineIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    reason: Annotated[
        SingleLineText | None, Field(default=None, max_length=500), classified("confidential")
    ]


class FirmExportPersonOut(BaseModel):
    """A person named on the export, for the card's line ("Waiting for approval · Margaret
    Okonkwo"); the id links to ADM-02."""

    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]


class FirmExportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    status: Annotated[FirmExportStatus, classified("internal")]
    scope: Annotated[FirmExportScope, classified("internal")]
    origin: Annotated[FirmExportOrigin, classified("internal")]
    requested_by: Annotated[FirmExportPersonOut, classified("internal")]
    requested_at: Annotated[datetime, classified("internal")]
    approver: Annotated[FirmExportPersonOut, classified("internal")]
    decided_at: Annotated[datetime | None, classified("internal")] = None
    ready_at: Annotated[datetime | None, classified("internal")] = None
    # The 7-day window in which links can be made (`firm_export_link_days`).
    available_until: Annotated[datetime | None, classified("internal")] = None
    size_bytes: Annotated[int | None, Field(ge=0), classified("internal")] = None
    manifest_sha256: Annotated[
        str | None, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")
    ] = None


class FirmExportPageOut(BaseModel):
    """The last 12 exports, newest first."""

    model_config = ConfigDict(frozen=True)

    items: Annotated[list[FirmExportOut], Field(max_length=12), classified("internal")]


class FirmExportLinkOut(BaseModel):
    """A presigned download link for 15 minutes; Restricted (it opens the firm's whole archive)
    and never logged."""

    model_config = ConfigDict(frozen=True)

    url: Annotated[str, classified("restricted")]
    expires_at: Annotated[datetime, classified("internal")]
    manifest_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]


async def _stub(ctx: AuthContext) -> NoReturn:
    if not await flag_enabled(ctx.tenant, COMPLIANCE_FIRM_EXPORT):
        raise NotFound("compliance.firm_export")
    raise NotImplementedYet


@router.get("", action="firm_export.read", response_model=FirmExportPageOut, errors=(501,))
async def list_firm_exports_route(ctx: Ctx) -> FirmExportPageOut:
    """ADM-06 a and c: the export card and the history tray."""
    await _stub(ctx)


@router.post(
    "",
    action="firm_export.request",
    response_model=FirmExportOut,
    status_code=202,
    errors=(501,),
)
async def request_firm_export_route(
    body: FirmExportRequestIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FirmExportOut:
    """ADM-06 b and g: `awaiting_approval`; 422 `approver_invalid` when the approver is the
    requester or holds no partner-level membership. Audited `firm_export.requested`."""
    await _stub(ctx)


@router.post(
    "/{export_id}/approve",
    action="firm_export.approve",
    response_model=FirmExportOut,
    errors=(409, 501),
)
async def approve_firm_export_route(export_id: UUID, ctx: Ctx) -> FirmExportOut:
    """ADM-06 f: the named approver starts the build (`building`). 409 `approver_must_differ` for
    the requester, `export_not_awaiting_approval` once decided. Audited `firm_export.approved`."""
    await _stub(ctx)


@router.post(
    "/{export_id}/decline",
    action="firm_export.approve",
    response_model=FirmExportOut,
    errors=(409, 501),
)
async def decline_firm_export_route(
    export_id: UUID, body: FirmExportDeclineIn, ctx: Ctx
) -> FirmExportOut:
    """The named approver declines (`declined`); the same 409s as approve. Audited
    `firm_export.declined`."""
    await _stub(ctx)


@router.post(
    "/{export_id}/link",
    action="firm_export.download",
    response_model=FirmExportLinkOut,
    errors=(409, 410, 501),
)
async def link_firm_export_route(export_id: UUID, ctx: Ctx) -> FirmExportLinkOut:
    """A 15-minute link for the requester or the approver while the archive is `ready` or
    `downloaded` (409 `export_not_ready` before); 410 `export_expired` after the 7 days. Audited
    `firm_export.downloaded`."""
    await _stub(ctx)

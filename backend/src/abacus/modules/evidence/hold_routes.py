"""Legal-hold routes (Q-02-T29; Q-02 §4.3; contract `docs/contracts/legal-holds.md`).

Behind `compliance.legal_holds` (off: 404). Placing and lifting need fresh MFA and answer 202:
the hold counts every version at once and S3 follows in the background. The list shows
metadata and counts, never the details text or the release reason.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.text import SingleLineText
from abacus.modules.evidence.holds import (
    HoldScope,
    HoldStatus,
    HoldView,
    ReasonCode,
    ScopeKind,
    lift_hold,
    list_holds,
    place_hold,
)
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

router = AbacusRouter(prefix="/v1/legal-holds", tags=["legal holds"])


class LegalHoldScopeIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[ScopeKind, classified("internal")]
    client_id: Annotated[UUID | None, classified("internal")] = None
    tax_year: Annotated[int | None, Field(default=None, ge=1990, le=2100), classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")] = None
    work_item_id: Annotated[UUID | None, classified("internal")] = None


class LegalHoldIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    scope: Annotated[LegalHoldScopeIn, classified("internal")]
    reason_code: Annotated[ReasonCode, classified("internal")]
    details: Annotated[
        str | None, Field(default=None, min_length=1, max_length=2000), classified("confidential")
    ]
    notify_user_ids: Annotated[
        list[UUID], Field(default_factory=list, max_length=50), classified("internal")
    ]


class LegalHoldReleaseIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    reason: Annotated[SingleLineText, Field(max_length=500), classified("confidential")]


class LegalHoldOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    scope_kind: Annotated[ScopeKind, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    tax_year: Annotated[int | None, classified("internal")] = None
    engagement_id: Annotated[UUID | None, classified("internal")] = None
    work_item_id: Annotated[UUID | None, classified("internal")] = None
    reason_code: Annotated[ReasonCode, classified("internal")]
    status: Annotated[HoldStatus, classified("internal")]
    placed_by: Annotated[UUID, classified("internal")]
    placed_at: Annotated[datetime, classified("internal")]
    released_by: Annotated[UUID | None, classified("internal")] = None
    released_at: Annotated[datetime | None, classified("internal")] = None
    objects_held: Annotated[int, classified("internal")]
    objects_applied: Annotated[int, classified("internal")]


class LegalHoldsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[LegalHoldOut], classified("internal")]


def _out(view: HoldView) -> LegalHoldOut:
    return LegalHoldOut(
        id=view.id,
        scope_kind=view.scope_kind,
        client_id=view.client_id,
        tax_year=view.tax_year,
        engagement_id=view.engagement_id,
        work_item_id=view.work_item_id,
        reason_code=view.reason_code,
        status=view.status,
        placed_by=view.placed_by,
        placed_at=view.placed_at,
        released_by=view.released_by,
        released_at=view.released_at,
        objects_held=view.objects_held,
        objects_applied=view.objects_applied,
    )


@router.get("", action="legal_hold.read", response_model=LegalHoldsOut)
async def list_legal_holds_route(
    ctx: Annotated[AuthContext, Depends(current_context)],
) -> LegalHoldsOut:
    return LegalHoldsOut(items=[_out(v) for v in await list_holds(ctx)])


@router.post(
    "",
    action="legal_hold.place",
    response_model=LegalHoldOut,
    status_code=202,
)
async def place_legal_hold_route(
    body: LegalHoldIn, ctx: Annotated[AuthContext, Depends(current_context)]
) -> LegalHoldOut:
    """Fresh MFA. 202 while applying; 404 for a scope outside the firm; 422
    `notify_not_member`."""
    scope = body.scope
    view = await place_hold(
        ctx,
        HoldScope(
            scope.kind, scope.client_id, scope.tax_year, scope.engagement_id, scope.work_item_id
        ),
        body.reason_code,
        body.details,
        body.notify_user_ids,
    )
    return _out(view)


@router.post(
    "/{hold_id}/release",
    action="legal_hold.lift",
    response_model=LegalHoldOut,
    status_code=202,
    errors=(409,),
)
async def release_legal_hold_route(
    hold_id: UUID,
    body: LegalHoldReleaseIn,
    ctx: Annotated[AuthContext, Depends(current_context)],
) -> LegalHoldOut:
    """Fresh MFA. 202 while releasing; 409 `hold_not_active` before it is active or once lifted."""
    return _out(await lift_hold(ctx, hold_id, body.reason))

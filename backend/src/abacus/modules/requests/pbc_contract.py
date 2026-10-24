"""C5 section `portal-pbc`, the requests writes (R-01-T01 stub; ADR P-36, ADR-139, DEC-24).
Contract: `docs/contracts/portal-pbc.md`; screens POR-03 and POR-04, BND-02 and AUD-03 firm-side.

The client's Undo of an Ignore and of Mark as Done, as compensating events (never a delete), and
the firm's void of a wrong rule fulfilment. The Ignore itself and Mark as Done are P-06's
(`contract.py`); R-01's additive note on the Ignore is P-06's `IgnoreIn.note`, stored as a shared
comment with origin `ignore_note` (R-01-T08).

Behind `portal.documents_v2` (the two undos) and `portal.drop_sort` (the void): off, each route
answers 404; on, 501 `not_implemented` until R-01-T08 (undos) and R-01-T09 (void) land. An undo
after the firm has acted on the request or the binder answers 409 `firm_already_acted`; a void of
anything but an unaccepted rule fulfilment answers 409 `not_voidable`. The void is human only: the
agent is denied `fulfilment.confirm` (INV-1).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict

from abacus.kernel._flags import PORTAL_DOCUMENTS_V2, PORTAL_DROP_SORT
from abacus.kernel._statuses import RequestStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]

# The one reason a person may void a rule fulfilment for (R-01 Story 2.2).
VoidReason = Literal["wrong_request"]
# What the portal answers carry instead of a firm status code (the portal read model's words):
# the request's client words, and the Mark as Done button's state.
ClientStatus = Literal["to_do", "done", "ignored", "returned"]
MarkDoneState = Literal["tonal", "ready", "marked"]


class IgnoreUndoneOut(BaseModel):
    """`request_item.ignore_undone`: `client_ignored_at` cleared; the client reads "To do" again.
    The ignore note stays in the thread (comments are never deleted)."""

    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]
    client_status: Annotated[ClientStatus, classified("internal")]  # "to_do" again
    undone_at: Annotated[datetime, classified("internal")]


class MarkDoneUndoneOut(BaseModel):
    """`binder.mark_done_undone`: the binder is `published` again and BND-02's "Marked done by
    Claire Feld" goes; the client reads Mark as Done tonal (requests open) or ready."""

    model_config = ConfigDict(frozen=True)

    binder_id: Annotated[UUID, classified("internal")]
    mark_done: Annotated[MarkDoneState, classified("internal")]
    undone_at: Annotated[datetime, classified("internal")]


class FulfilmentVoidIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: Annotated[VoidReason, classified("internal")]


class FulfilmentVoidedOut(BaseModel):
    """The link is stamped void, never deleted. The request returns to `requested` when nothing
    else fulfils it, and the version waits in the engagement drop zone for a person again."""

    model_config = ConfigDict(frozen=True)

    fulfilment_id: Annotated[UUID, classified("internal")]
    request_item_id: Annotated[UUID, classified("internal")]
    request_status: Annotated[RequestStatus, classified("internal")]  # C2
    voided_at: Annotated[datetime, classified("internal")]


async def _stub(ctx: AuthContext, flag: Flag) -> NoReturn:
    if not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)
    raise NotImplementedYet


pbc_portal_router = AbacusRouter(prefix="/v1/portal", tags=["portal"])
pbc_firm_router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["requests"])


@pbc_portal_router.post(
    "/request-items/{item_id}/ignore/undo",
    action="request_item.ignore",
    response_model=IgnoreUndoneOut,
    errors=(409, 501),
)
async def undo_ignore_route(
    item_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> IgnoreUndoneOut:
    """The client's Undo of an Ignore (POR-03 f, POR-04 b): a compensating event, allowed until
    the firm acts on the request (409 `firm_already_acted`, DEC-24)."""
    await _stub(ctx, PORTAL_DOCUMENTS_V2)


@pbc_portal_router.post(
    "/binders/{binder_id}/mark-done/undo",
    action="binder.mark_done",
    response_model=MarkDoneUndoneOut,
    errors=(409, 501),
)
async def undo_mark_done_route(
    binder_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> MarkDoneUndoneOut:
    """The client's Undo of Mark as Done (POR-03 e), until the firm returns a request or sends a
    new one (409 `firm_already_acted`)."""
    await _stub(ctx, PORTAL_DOCUMENTS_V2)


@pbc_firm_router.post(
    "/fulfilments/{fulfilment_id}/void",
    action="fulfilment.confirm",
    response_model=FulfilmentVoidedOut,
    errors=(409, 501),
)
async def void_fulfilment_route(
    engagement_id: UUID,
    fulfilment_id: UUID,
    body: FulfilmentVoidIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> FulfilmentVoidedOut:
    """Staff correct a wrong rule link (BND-02, AUD-03). Only an unaccepted `rule` fulfilment;
    a human or accepted link answers 409 `not_voidable`."""
    await _stub(ctx, PORTAL_DROP_SORT)

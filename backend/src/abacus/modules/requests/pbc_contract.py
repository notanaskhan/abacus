"""C5 section `portal-pbc`, the requests writes (R-01-T01 stub; ADR P-36, ADR-139, DEC-24).
Contract: `docs/contracts/portal-pbc.md`; screens POR-03 and POR-04, BND-02 and AUD-03 firm-side.

The client's Undo of an Ignore and of Mark as Done, as compensating events (never a delete). The
firm's void of a wrong rule fulfilment is served by evidence (`drops_contract.py`, TASK-1248): it
returns the dropped file to the inbox in the same unit of work. The Ignore itself and Mark as
Done are P-06's (`contract.py`); R-01's additive note on the Ignore is P-06's `IgnoreIn.note`,
stored as a shared comment with origin `ignore_note` (R-01-T08).

Behind `portal.documents_v2` (the two undos, live since R-01-T08): off, each route answers 404.
An undo after the firm has acted on the request or the binder answers 409 `firm_already_acted`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict

from abacus.kernel._flags import PORTAL_DOCUMENTS_V2
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.requests import binders, lifecycle

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]

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


async def _documents_on(ctx: AuthContext) -> None:
    """`portal.documents_v2` off: the undos answer 404."""
    if not await flag_enabled(ctx.tenant, PORTAL_DOCUMENTS_V2):
        raise NotFound(PORTAL_DOCUMENTS_V2.name)


pbc_portal_router = AbacusRouter(prefix="/v1/portal", tags=["portal"])


@pbc_portal_router.post(
    "/request-items/{item_id}/ignore/undo",
    action="request_item.ignore",
    response_model=IgnoreUndoneOut,
    errors=(409,),
)
async def undo_ignore_route(
    item_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> IgnoreUndoneOut:
    """The client's Undo of an Ignore (POR-03 f, POR-04 b): a compensating event, allowed until
    the firm acts on the request (409 `firm_already_acted`, DEC-24, DEC-334). A retry with the
    same key is authorised again, then answers what the first answered."""
    await _documents_on(ctx)
    await lifecycle.check_ignore(ctx, item_id)

    async def run() -> tuple[int, dict[str, object]]:
        at = await lifecycle.undo_ignore(ctx, item_id)
        out = IgnoreUndoneOut(request_item_id=item_id, client_status="to_do", undone_at=at)
        return 200, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="request_item.ignore_undo",
        key=idempotency_key,
        body={"request_item_id": str(item_id)},
        run=run,
    )
    return IgnoreUndoneOut.model_validate(stored.body)


@pbc_portal_router.post(
    "/binders/{binder_id}/mark-done/undo",
    action="binder.mark_done",
    response_model=MarkDoneUndoneOut,
    errors=(409,),
)
async def undo_mark_done_route(
    binder_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> MarkDoneUndoneOut:
    """The client's Undo of Mark as Done (POR-03 e), until the firm returns a request or sends a
    new one (409 `firm_already_acted`, DEC-334)."""
    await _documents_on(ctx)
    await binders.check_action(ctx, binder_id, "binder.mark_done")

    async def run() -> tuple[int, dict[str, object]]:
        view = await binders.undo_mark_done(ctx, binder_id)
        out = MarkDoneUndoneOut(
            binder_id=view.binder_id,
            mark_done="tonal" if view.mark_done == "tonal" else "ready",
            undone_at=view.undone_at,
        )
        return 200, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="binder.mark_done_undo",
        key=idempotency_key,
        body={"binder_id": str(binder_id)},
        run=run,
    )
    return MarkDoneUndoneOut.model_validate(stored.body)

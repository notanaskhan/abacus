"""C5 section `portal-pbc`, the portal drop (R-01-T01 stub; ADR P-36, ADR-139, DEC-58 a, c, g).
Contract: `docs/contracts/portal-pbc.md`; screens POR-03 (motion, b, c, d) and POR-14.

One file of a drop anywhere on POR-03, stored in the engagement drop zone (`inbox_files`, channel
`portal_drop`) for the code-rule sort; the client posts each file of one drop with the same
`X-Drop-Batch` and its own `Idempotency-Key`, and polls `GET /v1/portal/drops/{batch_id}` (the
portal read model). The body is the raw file, as on the per-request upload.

Behind `portal.drop_sort`: off, 404 (the screen then sends every file through the per-request
upload or "Brightwater Hale will sort this"); on, 501 `not_implemented` until R-01-T09 lands. A
binder outside the dropper's grant, a draft or a closed binder answers 404 (INV-4). Limits:
413 `file_too_large` over 50 MB, 415 `type_not_allowed` outside PDF, JPG, PNG, HEIC, XLSX, DOCX
and CSV (DEC-58 c); a duplicate is accepted and flagged for a person, never refused (DEC-58 g).
No code path here or behind it accepts, confirms or links on a person's behalf: a decisive match
becomes a `rule` fulfilment that a named person accepts (ADR-005).
"""

from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict

from abacus.kernel._flags import PORTAL_DROP_SORT
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
DropBatch = Annotated[UUID, Header(alias="X-Drop-Batch")]


class DropAcceptedOut(BaseModel):
    """202: the file is stored and waits for the sort; its outcome comes from the batch poll."""

    model_config = ConfigDict(frozen=True)

    batch_id: Annotated[UUID, classified("internal")]
    file_id: Annotated[UUID, classified("internal")]


async def _stub(ctx: AuthContext) -> NoReturn:
    if not await flag_enabled(ctx.tenant, PORTAL_DROP_SORT):
        raise NotFound(PORTAL_DROP_SORT.name)
    raise NotImplementedYet


drops_router = AbacusRouter(prefix="/v1/portal", tags=["portal"])


@drops_router.post(
    "/binders/{binder_id}/drops",
    action="evidence.upload",
    response_model=DropAcceptedOut,
    status_code=202,
    errors=(413, 415, 501),
)
async def drop_file_route(
    binder_id: UUID,
    request: Request,
    ctx: Ctx,
    filename: Annotated[str, Query(min_length=1, max_length=255)],
    batch_id: DropBatch,
    idempotency_key: IdempotencyKey,
) -> DropAcceptedOut:
    """One dropped file (POR-03 b → c, d). Sorted by code against the dropper's visible items."""
    await _stub(ctx)

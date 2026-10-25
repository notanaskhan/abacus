"""C5 section `portal-pbc`, the portal drop (R-01-T01 stub; ADR P-36, ADR-139, DEC-58 a, c, g).
Contract: `docs/contracts/portal-pbc.md`; screens POR-03 (motion, b, c, d) and POR-14.

One file of a drop anywhere on POR-03, stored in the engagement drop zone (`inbox_files`, channel
`portal_drop`) for the code-rule sort; the client posts each file of one drop with the same
`X-Drop-Batch` and its own `Idempotency-Key`, and polls `GET /v1/portal/drops/{batch_id}` (the
portal read model). The body is the raw file, as on the per-request upload.

Behind `portal.drop_sort`: off, 404 (the screen then sends every file through the per-request
upload or "Brightwater Hale will sort this"); on, served (R-01-T09). A binder outside the
dropper's grant, a draft or a closed binder answers 404 (INV-4). Limits are the one upload policy
every channel uses (DEC-296: 50 MB; the byte-sniffed allowlist, the extension agreeing), answered
in this contract's words: 413 `file_too_large`, 415 `type_not_allowed` (DEC-323). A duplicate is
accepted and flagged for a person, never refused (DEC-58 g).
No code path here or behind it accepts, confirms or links on a person's behalf: a decisive match
becomes a `rule` fulfilment that a named person accepts (ADR-005).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict

from abacus.kernel._flags import PORTAL_DROP_SORT
from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainTooLarge, DomainUnsupported, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.evidence.drops import check_drop, drop_file
from abacus.modules.evidence.uploads import (
    MAX_UPLOAD_BYTES,
    UploadTooLarge,
    UploadTypeNotAllowed,
)
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
DropBatch = Annotated[UUID, Header(alias="X-Drop-Batch")]


class DropAcceptedOut(BaseModel):
    """202: the file is stored and waits for the sort; its outcome comes from the batch poll."""

    model_config = ConfigDict(frozen=True)

    batch_id: Annotated[UUID, classified("internal")]
    file_id: Annotated[UUID, classified("internal")]


class DropTooLarge(DomainTooLarge):
    """413: over the one upload policy's 50 MB (DEC-296)."""

    code = "file_too_large"


class DropTypeNotAllowed(DomainUnsupported):
    """415: a type, or an extension, the one upload policy refuses (DEC-296)."""

    code = "type_not_allowed"


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
    """One dropped file (POR-03 b → c, d). Sorted by code against the dropper's visible items
    (R-01-T09). Over the limit or outside the allowlist: 413 `file_too_large` or 415
    `type_not_allowed`, the one upload policy's refusals in this contract's words (DEC-323)."""
    if not await flag_enabled(ctx.tenant, PORTAL_DROP_SORT):
        raise NotFound(PORTAL_DROP_SORT.name)
    await check_drop(ctx, binder_id)  # authorised before a byte of the file is read
    try:
        data = bytearray()
        async for chunk in request.stream():
            data += chunk
            if len(data) > MAX_UPLOAD_BYTES:
                raise UploadTooLarge
        accepted = await drop_file(
            ctx,
            binder_id,
            batch_id=batch_id,
            key=idempotency_key,
            file_name=filename,
            content=bytes(data),
        )
    except UploadTooLarge:
        raise DropTooLarge from None
    except UploadTypeNotAllowed:
        raise DropTypeNotAllowed from None
    return DropAcceptedOut(batch_id=accepted.batch_id, file_id=accepted.file_id)

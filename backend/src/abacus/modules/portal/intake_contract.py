"""C5 v1.2 intake half: portal intake, the stubs (N-01-T02; N-01 §4.3; ADR-162, ADR-210).
Contract: `docs/contracts/firm-intake.md` §portal intake.

POR-03 "Upload something else": a portal principal sends documents that answer no request. One
upload batch is one thread with one message, the client's note its body (DEC-702); files follow
one request each (`?filename=`, DEC-703), scanned before storage and refused closed when the
scanner is down. The principal lists and withdraws only its own uploads (INV-4), withdrawal only
while unfiled (ADR-162). Every route answers 404 with `portal.intake_upload` off and 501
`not_implemented` with it on until N-01-T14. The scope is checked under `scope_only` by the
implementation (the matrix's condition needs the scope's resource); a firm principal never
reaches these routes (404).

Client words (portal never renders "Accrued"): Sent · Received by {firm} · Withdrawn.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel import listing
from abacus.kernel._statuses import PortalIntakeUploadStatus
from abacus.kernel.classification import classified
from abacus.kernel.listing import ListPage
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.communications.api import portal_intake
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_member

Member = Annotated[AuthContext, Depends(current_member)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
ScopeKind = Literal["client", "client_entity", "engagement"]


class ScopeRef(BaseModel):
    """The portal scope the upload is for (one of the principal's grants)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[ScopeKind, classified("internal")]
    id: Annotated[UUID, classified("internal")]


class IntakeUploadIn(BaseModel):
    """`POST /v1/portal/intake-uploads`: the batch; files follow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scope_ref: Annotated[ScopeRef, classified("internal")]
    note: Annotated[str | None, Field(max_length=4000), classified("restricted")] = None


class IntakeUploadFileOut(BaseModel):
    """One file of an upload, in client words."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    file_name: Annotated[str, classified("confidential")]
    size_bytes: Annotated[int, classified("internal")]
    status: Annotated[PortalIntakeUploadStatus, classified("internal")]


class IntakeUploadOut(BaseModel):
    """One upload batch; `status` is `sent` until the firm has it."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    scope_kind: Annotated[ScopeKind, classified("internal")]
    scope_id: Annotated[UUID, classified("internal")]
    status: Annotated[PortalIntakeUploadStatus, classified("internal")]
    sent_at: Annotated[datetime, classified("internal")]
    files: Annotated[list[IntakeUploadFileOut], classified("internal")]
    can_withdraw: Annotated[bool, classified("internal")]


intake_router = AbacusRouter(prefix="/v1/portal/intake-uploads", tags=["portal"])


def _upload_out(u: portal_intake.IntakeBatch) -> IntakeUploadOut:
    return IntakeUploadOut(
        id=u.id,
        scope_kind=cast(ScopeKind, u.scope_kind),
        scope_id=u.scope_id,
        status=cast(PortalIntakeUploadStatus, u.status),
        sent_at=u.sent_at,
        files=[
            IntakeUploadFileOut(
                id=f.id,
                file_name=f.file_name,
                size_bytes=f.size_bytes,
                status=cast(PortalIntakeUploadStatus, f.status),
            )
            for f in u.files
        ],
        can_withdraw=u.can_withdraw,
    )


@intake_router.post(
    "",
    action="portal_intake.upload",
    response_model=IntakeUploadOut,
    status_code=201,
    errors=(409,),
)
async def create_intake_upload_route(
    body: IntakeUploadIn, ctx: Member, idempotency_key: IdempotencyKey
) -> IntakeUploadOut:
    """POR-03 "Upload something else": the batch (N-01-T14)."""

    async def run() -> tuple[int, dict[str, object]]:
        made = await portal_intake.create_upload(
            ctx, body.scope_ref.kind, body.scope_ref.id, body.note
        )
        return 201, _upload_out(made).model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="portal_intake.upload",
        key=idempotency_key,
        body=body.model_dump(mode="json"),
        run=run,
    )
    return IntakeUploadOut.model_validate(stored.body)


@intake_router.post(
    "/{upload_id}/files",
    action="portal_intake.upload",
    response_model=IntakeUploadFileOut,
    status_code=201,
    errors=(409, 413, 415, 503),
)
async def add_intake_upload_file_route(
    upload_id: UUID,
    request: Request,
    ctx: Member,
    idempotency_key: IdempotencyKey,
    filename: Annotated[str, Query(min_length=1, max_length=255)],
) -> IntakeUploadFileOut:
    """One file, scanned before storage under a detached key, fail closed (N-01-T14)."""
    content = await request.body()

    async def run() -> tuple[int, dict[str, object]]:
        made = await portal_intake.add_file(ctx, upload_id, filename, content)
        out = IntakeUploadFileOut(
            id=made.id,
            file_name=made.file_name,
            size_bytes=made.size_bytes,
            status=cast(PortalIntakeUploadStatus, made.status),
        )
        return 201, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="portal_intake.upload_file",
        key=idempotency_key,
        body={"upload_id": str(upload_id), "filename": filename, "size": len(content)},
        run=run,
    )
    return IntakeUploadFileOut.model_validate(stored.body)


@intake_router.get(
    "",
    action="portal_intake.read_own",
    response_model=ListPage[IntakeUploadOut],
)
async def list_intake_uploads_route(
    ctx: Member,
    scope_kind: ScopeKind,
    scope_id: UUID,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ListPage[IntakeUploadOut]:
    """The principal's own uploads for one scope, newest first (N-01-T14)."""
    page = await portal_intake.list_uploads(ctx, scope_kind, scope_id, cursor, limit)
    return listing.envelope(
        [_upload_out(u) for u in page.uploads],
        next_position=page.next_position,
        tenant_id=ctx.tenant_id,
        resource=portal_intake.LIST_RESOURCE,
        query=page.query,
        total=(page.total, False),
    )


@intake_router.post(
    "/{upload_id}/withdraw",
    action="portal_intake.withdraw",
    response_model=IntakeUploadOut,
    errors=(409,),
)
async def withdraw_intake_upload_route(
    upload_id: UUID, ctx: Member, idempotency_key: IdempotencyKey
) -> IntakeUploadOut:
    """Only while every file is New or Waiting; a filed one answers 409 `attachment_filed`
    (ADR-162; N-01-T14)."""
    return _upload_out(await portal_intake.withdraw(ctx, upload_id))

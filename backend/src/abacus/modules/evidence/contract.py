"""C5 v1: the client's withdrawal of an unaccepted upload (P-06-T19; ADR-162, P-31).
Contract: `docs/contracts/c5-requests-binders.md`; spec: SPEC-319 AC-15.

Behind `evidence.withdrawal` (ADR-162 §3): off, 404. On: void and hide at once
(`withdrawals.withdraw`). An ever-accepted version answers 409 `evidence_accepted`; a version that
is not a client's detached-key upload 409 `evidence_not_withdrawable`; another person's upload,
for a contributor, 403 `not_your_upload`. The `Idempotency-Key` is required: a retry is
authorised again, then answers what the first answered (ED-023's shape).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.evidence.withdrawals import check_withdraw, withdraw, withdrawal_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]


class WithdrawalOut(BaseModel):
    """Void and hidden at once; erased after `erase_after` unless a legal hold applies."""

    model_config = ConfigDict(frozen=True)

    evidence_version_id: Annotated[UUID, classified("internal")]
    request_item_id: Annotated[UUID | None, classified("internal")]
    withdrawn_at: Annotated[datetime, classified("internal")]
    erase_after: Annotated[datetime, classified("internal")]


async def _flag_on(ctx: AuthContext) -> None:
    if not await withdrawal_enabled(ctx):
        raise NotFound("evidence.withdrawal")


withdrawal_router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["evidence"])


@withdrawal_router.post(
    "/evidence-versions/{version_id}/withdraw",
    action="evidence.withdraw",
    response_model=WithdrawalOut,
    errors=(409,),
)
async def withdraw_evidence_version_route(
    engagement_id: UUID, version_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WithdrawalOut:
    """The client takes back an upload the firm never accepted (P-06-T19): void and hidden at
    once, erased after `erase_after` unless a legal hold applies."""
    await _flag_on(ctx)
    await check_withdraw(ctx, engagement_id, version_id)

    async def run() -> tuple[int, dict[str, object]]:
        view = await withdraw(ctx, engagement_id, version_id)
        return 200, WithdrawalOut.model_validate(view, from_attributes=True).model_dump(
            mode="json"
        )

    stored = await idempotent(
        ctx.tenant,
        route="evidence.withdraw",
        key=idempotency_key,
        body={"engagement_id": str(engagement_id), "evidence_version_id": str(version_id)},
        run=run,
    )
    return WithdrawalOut.model_validate(stored.body)

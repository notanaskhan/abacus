"""C5 v1: the client's withdrawal of an unaccepted upload (P-06-T01 stub; ADR-162, P-31).
Contract: `docs/contracts/c5-requests-binders.md`; spec: SPEC-319.

Behind `binders.engine` until P-06-T19 creates `evidence.withdrawal` and moves it there (ADR-162
§3): off, 404; on, 501 `not_implemented`. An ever-accepted version will answer 409
`evidence_accepted`; another contributor's upload 403 `not_your_upload`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict

from abacus.kernel._flags import BINDERS_ENGINE
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
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


async def _stub(ctx: AuthContext) -> NoReturn:
    if not await flag_enabled(ctx.tenant, BINDERS_ENGINE):
        raise NotFound("binders.engine")
    raise NotImplementedYet


withdrawal_router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["evidence"])


@withdrawal_router.post(
    "/evidence-versions/{version_id}/withdraw",
    action="evidence.withdraw",
    response_model=WithdrawalOut,
    errors=(409, 501),
)
async def withdraw_evidence_version_route(
    engagement_id: UUID, version_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> WithdrawalOut:
    """The client takes back an upload the firm never accepted (P-06-T19)."""
    await _stub(ctx)

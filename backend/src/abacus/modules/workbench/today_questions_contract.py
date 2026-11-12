"""Today questions, the route shape (I-02-T03 stub; SPEC-654 §3.7; I-02 §4.3). Contract:
`docs/contracts/today.md`.

`POST /v1/me/today/questions` appends a read-only `workbench.assistant` turn to the viewer's Today
session for the day (a `workbench_session` with context kind `today_brief`, created on the first
question, listed under Mine with a "Today · <date>" chip, Q4). `propose` and `approved_write` tools
are withheld whatever `workbench.plans` says (INV-1). The answer is read through the session's
items and its `session:<id>` topic. It answers, in order: the matrix (`briefing.ask`),
`today_brief.enabled` (404), `workbench.enabled` (404: the composer is hidden), then 501 until
I-02-T14.
"""

from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import TODAY_BRIEF_ENABLED, WORKBENCH_ENABLED
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")
Restricted = classified("restricted")


class TodayQuestionIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # 422 `text_too_long` above 1,000 characters; never logged (Restricted).
    text: Annotated[str, Field(min_length=1, max_length=1000), Restricted]
    brief_id: Annotated[UUID, Internal]


class TodayQuestionAcceptedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: Annotated[UUID, Internal]
    item_id: Annotated[UUID, Internal]


today_questions_router = AbacusRouter(prefix="/v1/me/today", tags=["today"])


def _not_yet() -> NoReturn:
    raise NotImplementedYet


@today_questions_router.post(
    "/questions",
    action="briefing.ask",
    response_model=TodayQuestionAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def today_question_route(
    body: TodayQuestionIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> TodayQuestionAcceptedOut:
    """409 `capability_unavailable {reason}` when the assistant is unavailable (DF-04)."""
    for flag in (TODAY_BRIEF_ENABLED, WORKBENCH_ENABLED):
        if not await flag_enabled(ctx.tenant, flag):
            raise NotFound(flag.name)
    _not_yet()

"""AUD-29 · the engagement activity log, contract stub (P-05-T02; TASK-6503; SPEC-650 AC-31 to
AC-38; P-05 §4.3; DEC-3103).

`POST /v1/engagements/{engagement_id}/audit-events/query` and `…/export`. Each checks the
principal (a client principal 404s), the engagement (404 alike for a walled or an unknown one,
DEC-43), the one matrix action, then the flag `audit_trail.engagement_activity` (off: 404), and
answers 501 until P-05-T11. The search text travels in the body and is never logged or put in the
URL (AC-34). Rows are the explorer's `AuditEventRow`: action code, category, mark, actor grammar
and identifier facts; the SPA words them (P-34 rule).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import AUDIT_TRAIL_ENGAGEMENT_ACTIVITY
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.audit_trail.audit_log_contract import AuditEventPageOut, Ctx
from abacus.modules.engagements import api as engagements
from abacus.modules.identity.api import AbacusRouter, AuthContext, authorise

READ_ENGAGEMENT = "audit_event.read_engagement"
EXPORT = "export.create"

Segment = Literal["all", "human", "via_agent", "policy"]

engagement_activity_router = AbacusRouter(prefix="/v1/engagements", tags=["activity"])


class EngagementActivityQueryIn(BaseModel):
    """AUD-29's filter: segment, categories, the business-time window, the search text and the
    keyset cursor. Counts (`all`, `human`, `via_agent`, `policy`) foot under every filter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    segment: Annotated[Segment, classified("internal")] = "all"
    categories: Annotated[list[Annotated[str, Field(max_length=60)]], classified("internal")] = (
        Field(default_factory=list[str], max_length=20)
    )
    since: Annotated[datetime | None, classified("internal")] = None
    until: Annotated[datetime | None, classified("internal")] = None
    # The search text: matched server-side against the actor's name, the resolved target label,
    # the detail facts and the catalogue's keywords. It can name a client, so it is confidential
    # and stays in the body (AC-34).
    q: Annotated[str | None, Field(max_length=120), classified("confidential")] = None
    cursor: Annotated[str | None, Field(max_length=512), classified("internal")] = None
    limit: Annotated[int, Field(ge=1, le=100), classified("internal")] = 50


class EngagementActivityExportIn(BaseModel):
    """The same filter, streamed as CSV (masked values, formula cells neutralised; AC-38)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    segment: Annotated[Segment, classified("internal")] = "all"
    categories: Annotated[list[Annotated[str, Field(max_length=60)]], classified("internal")] = (
        Field(default_factory=list[str], max_length=20)
    )
    since: Annotated[datetime | None, classified("internal")] = None
    until: Annotated[datetime | None, classified("internal")] = None
    q: Annotated[str | None, Field(max_length=120), classified("confidential")] = None


async def _gate(ctx: AuthContext, engagement_id: UUID, action: str) -> None:
    """Principal, engagement, action, then flag: no one learns the flag state of an engagement
    they may not read."""
    if ctx.client:
        raise NotFound("engagement")
    ref = await engagements.get_ref(ctx, engagement_id)  # 404 for a walled or unknown engagement
    await authorise(ctx, action, ref.resource())
    if not await flag_enabled(ctx.tenant, AUDIT_TRAIL_ENGAGEMENT_ACTIVITY):
        raise NotFound(AUDIT_TRAIL_ENGAGEMENT_ACTIVITY.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


@engagement_activity_router.post(
    "/{engagement_id}/audit-events/query",
    action=READ_ENGAGEMENT,
    response_model=AuditEventPageOut,
    errors=(501,),
)
async def engagement_activity_query_route(
    engagement_id: UUID, body: EngagementActivityQueryIn, ctx: Ctx
) -> AuditEventPageOut:
    """AUD-29's list, newest first by business time, keyset on `seq` (P-05-T11)."""
    await _gate(ctx, engagement_id, READ_ENGAGEMENT)
    _not_yet()


@engagement_activity_router.post(
    "/{engagement_id}/audit-events/export",
    action=EXPORT,
    response_model=bytes,
    errors=(501,),
)
async def engagement_activity_export_route(
    engagement_id: UUID, body: EngagementActivityExportIn, ctx: Ctx
) -> Response:
    """The filtered rows as CSV; `export.create` needs a fresh MFA (matrix `mfa_recent`) and
    `audit_event.exported` records the filter hash and row count (P-05-T11)."""
    await _gate(ctx, engagement_id, EXPORT)
    _not_yet()

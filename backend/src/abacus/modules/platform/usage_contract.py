"""C6 v2, agent-minute reads (P-10-T09 stub; P-10 §3.10, §4.3; ADR-148; SPEC-647). Contract:
`docs/contracts/agent-runs.md` §9.

Minutes by service line, engagement and capability, on the firm's usage month. Integers summed by
code; never USD (DEC-51). ADM-14 and ENG-06 read these. 501 until P-10-T42.
"""

from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotImplementedYet
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
Internal = classified("internal")
Confidential = classified("confidential")


class UsageLineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Internal]
    label: Annotated[str, Confidential]
    minutes: Annotated[int, Internal]


class FirmUsageOut(BaseModel):
    """ADM-14: 14,920 of 20,000 = 8,640 + 4,610 + 1,420 + 120 + 130."""

    model_config = ConfigDict(frozen=True)

    usage_month: Annotated[str, Internal]
    used_minutes: Annotated[int, Internal]
    included_minutes: Annotated[int, Internal]
    by_service_line: Annotated[list[UsageLineOut], Confidential]
    by_engagement: Annotated[list[UsageLineOut], Confidential]
    by_capability: Annotated[list[UsageLineOut], Confidential]


class EngagementEffortOut(BaseModel):
    """ENG-06's AI part: 412 = 46 + 24 + 342."""

    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, Internal]
    used_minutes: Annotated[int, Internal]
    budget_minutes: Annotated[int, Internal]
    lines: Annotated[list[UsageLineOut], Confidential]


firm_usage_router = AbacusRouter(prefix="/v1/firm/usage", tags=["agent minutes"])
engagement_effort_router = AbacusRouter(prefix="/v1/engagements", tags=["agent minutes"])


def _not_yet() -> NoReturn:
    raise NotImplementedYet


@firm_usage_router.get("", action="usage.read", response_model=FirmUsageOut, errors=(501,))
async def firm_usage_route(
    ctx: Ctx, month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None
) -> FirmUsageOut:
    _not_yet()


@engagement_effort_router.get(
    "/{engagement_id}/effort",
    action="engagement.read",
    response_model=EngagementEffortOut,
    errors=(501,),
)
async def engagement_effort_route(engagement_id: UUID, ctx: Ctx) -> EngagementEffortOut:
    _not_yet()

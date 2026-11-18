"""C6 v2, agent-minute reads (P-10-T09 stub; P-10 §3.10, §4.3; ADR-148; SPEC-647). Contract:
`docs/contracts/agent-runs.md` §9.

Minutes by service line, engagement and capability, on the firm's usage month. Integers summed by
code; never USD (DEC-51). ADM-14 and ENG-06 read these. Implemented by P-10-T42
(`platform/metering.py`; DEC-3401); `errors=(501,)` stays as every implemented stub's.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict

from abacus.kernel.classification import classified
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.platform.metering import (
    UsageLine,
    engagement_effort,
    firm_usage,
)
from abacus.modules.platform.usage_alerts import alerts_sent

Ctx = Annotated[AuthContext, Depends(current_context)]
Internal = classified("internal")
Confidential = classified("confidential")


class UsageLineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Internal]
    label: Annotated[str, Confidential]
    minutes: Annotated[int, Internal]


class AlertSentOut(BaseModel):
    """A firm alert sent this usage month (ADM-14 b: "alert sent Oct 9, 1:47 PM to …")."""

    model_config = ConfigDict(frozen=True)

    threshold_pct: Annotated[int, Internal]
    sent_at: Annotated[datetime, Internal]
    recipients: Annotated[list[str], Confidential]


class FirmUsageOut(BaseModel):
    """ADM-14: 14,920 of 20,000 = 8,640 + 4,610 + 1,420 + 120 + 130."""

    model_config = ConfigDict(frozen=True)

    usage_month: Annotated[str, Internal]
    used_minutes: Annotated[int, Internal]
    starts_on: Annotated[date | None, Internal] = None  # P-10-T42: the first day (Sep 15)
    ends_on: Annotated[date | None, Internal] = None
    included_minutes: Annotated[int, Internal]
    by_service_line: Annotated[list[UsageLineOut], Confidential]
    by_engagement: Annotated[list[UsageLineOut], Confidential]
    by_capability: Annotated[list[UsageLineOut], Confidential]
    # G-04-T18 (plan-usage contract §2, P-10 additive): the month's firm alerts, lowest first, and
    # the minutes over included (ADM-14 b, c). Integers from code; never an amount (P-27).
    alerts_sent: Annotated[list[AlertSentOut], Confidential] = []
    over_included: Annotated[int, Internal] = 0


class EngagementEffortOut(BaseModel):
    """ENG-06's AI part: 412 = 46 + 24 + 342."""

    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, Internal]
    used_minutes: Annotated[int, Internal]
    budget_minutes: Annotated[int, Internal]
    lines: Annotated[list[UsageLineOut], Confidential]
    runs: Annotated[int, Internal] = 0  # P-10-T42: completed runs; a 0-minute run still counts


firm_usage_router = AbacusRouter(prefix="/v1/firm/usage", tags=["agent minutes"])
engagement_effort_router = AbacusRouter(prefix="/v1/engagements", tags=["agent minutes"])


def _lines(lines: list[UsageLine]) -> list[UsageLineOut]:
    return [UsageLineOut(key=line.key, label=line.label, minutes=line.minutes) for line in lines]


@firm_usage_router.get("", action="usage.read", response_model=FirmUsageOut, errors=(501,))
async def firm_usage_route(
    ctx: Ctx, month: Annotated[str | None, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")] = None
) -> FirmUsageOut:
    usage = await firm_usage(ctx, month)
    sent = await alerts_sent(ctx.tenant, usage.usage_month)
    return FirmUsageOut(
        usage_month=usage.usage_month,
        used_minutes=usage.used_minutes,
        starts_on=usage.starts_on,
        ends_on=usage.ends_on,
        included_minutes=usage.included_minutes,
        by_service_line=_lines(usage.by_service_line),
        by_engagement=_lines(usage.by_engagement),
        by_capability=_lines(usage.by_capability),
        alerts_sent=[
            AlertSentOut(
                threshold_pct=a.threshold_pct, sent_at=a.crossed_at, recipients=list(a.recipients)
            )
            for a in sent
        ],
        over_included=max(usage.used_minutes - usage.included_minutes, 0),
    )


@engagement_effort_router.get(
    "/{engagement_id}/effort",
    action="engagement.read",
    response_model=EngagementEffortOut,
    errors=(501,),
)
async def engagement_effort_route(engagement_id: UUID, ctx: Ctx) -> EngagementEffortOut:
    effort = await engagement_effort(ctx, engagement_id)
    return EngagementEffortOut(
        engagement_id=effort.engagement_id,
        used_minutes=effort.used_minutes,
        budget_minutes=effort.budget_minutes,
        lines=_lines(effort.lines),
        runs=effort.runs,
    )

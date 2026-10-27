"""HOME-01's running pill (I-01-T08; `home-and-gates.md` §3): the agent runs running now that the
viewer may read, queued and dispatched runs left out, shadow runs never counted (SPEC-036 AC-5).
Narrowed to an office through the run's engagement (DEC-30: a filter, never a boundary)."""

from __future__ import annotations

from collections import Counter
from typing import cast
from uuid import UUID

from sqlalchemy import ColumnElement, select

from abacus.kernel.db import tenant_session
from abacus.modules.agents.models import AgentRun
from abacus.modules.engagements.api import gate_offices
from abacus.modules.identity.api import AuthContext, visible
from abacus.modules.platform.api import HomeCount, HomeOfficeCount, register_home_count

# A firm-level run has no engagement: `visible()` never counts it here.
_ENGAGEMENT = cast(ColumnElement[UUID], AgentRun.engagement_id.expression)


async def agent_runs_running(viewer: object, office_id: UUID | None) -> HomeCount:
    ctx = cast(AuthContext, viewer)
    async with tenant_session(ctx.tenant) as session:
        engagements = [
            e
            for e in (
                await session.execute(
                    select(AgentRun.engagement_id).where(
                        AgentRun.status == "running",
                        AgentRun.shadow.is_(False),
                        visible(ctx, "agent_run.read", _ENGAGEMENT),
                    )
                )
            ).scalars()
            if e is not None
        ]
    offices = await gate_offices(ctx.tenant, [(e, None) for e in set(engagements)])
    by_office = Counter(o for e in engagements if (o := offices.get((e, None))) is not None)
    if office_id is not None:
        engagements = [e for e in engagements if offices.get((e, None)) == office_id]
    return HomeCount(
        total=len(engagements),
        by_office=tuple(HomeOfficeCount(o, n) for o, n in sorted(by_office.items(), key=str)),
    )


def register_home_counts() -> None:
    register_home_count("agent_runs_running", agent_runs_running)

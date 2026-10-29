"""W7 for the pilot metrics (Q-04-T008; DEC-825): Q-02-T50's `override_rate.v1` over each
agent's live outputs in the week (`live_override`, the shadow report's function; DEC-96), only
when enough were decided. Registered with platform at import."""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from abacus.kernel.db import TenantContext
from abacus.modules.agents.shadow_score import SCREENER, live_override
from abacus.modules.platform.api import PilotWeek

AGENTS: Final = (SCREENER,)


async def w7_override_rate(tenant: TenantContext, week: PilotWeek) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    for agent in AGENTS:
        rate = await live_override(tenant, agent, week.start, week.end)
        if rate.rate is not None:
            values[f"w7.v1.{agent}"] = rate.rate
    return values

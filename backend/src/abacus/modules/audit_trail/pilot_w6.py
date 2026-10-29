"""W6 for the pilot metrics (Q-04-T008; DEC-825): the median days from a request's first
`request_item.sent` to its last `request_item.uploaded` in the week (the allowlisted duration
read), and that median less the enrolment's baseline. Registered with platform at import."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from statistics import median
from typing import Final

from abacus.kernel.db import TenantContext
from abacus.modules.audit_trail.metrics import Window, first_to_last_durations
from abacus.modules.platform.api import PILOT_PLACES, PilotWeek

_DAY: Final = Decimal(86_400)


async def w6_request_to_received(tenant: TenantContext, week: PilotWeek) -> dict[str, Decimal]:
    durations = await first_to_last_durations(
        tenant, "request_item.sent", "request_item.uploaded", Window(week.start, week.end)
    )
    if not durations:
        return {}
    days = (Decimal(str(median(d.seconds for d in durations))) / _DAY).quantize(
        PILOT_PLACES, ROUND_HALF_UP
    )
    values = {"w6_request_to_received_days.v1": days}
    if week.baseline_days is not None:
        values["w6_vs_baseline_days.v1"] = days - Decimal(week.baseline_days)
    return values

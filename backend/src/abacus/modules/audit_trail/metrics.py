"""Pilot metric reads over the audit trail (Q-04-T006; Q-04 §4; DEC-715).

Two reads for the pilot metrics, both inside one firm's own session (forced row-level security):

- `event_counts(tenant, actions, window)`: how many events of each action fell in the window.
- `first_to_last_durations(tenant, start_action, end_action, window)`: for each target that had
  both, the time from its first `start_action` to its last `end_action` inside the window, in
  seconds. Targets without both are left out.

Only actions on `METRIC_ACTIONS` may be read (requests, portal sessions and evidence): anything
else is refused (`MetricActionRefused`), so the reads cannot become a back door into the audit log.
Results are identifiers, counts and durations only: no actor, no `before` or `after` facts. The
index `audit_events_action_time (tenant_id, action, occurred_at)` (migration 0275) serves both.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

METRIC_ACTIONS: Final = frozenset(
    {
        "request_item.created",
        "request_item.sent",
        "request_item.uploaded",
        "request_item.returned_to_client",
        "request_item.waived",
        "evidence.uploaded",
        "review_decision.recorded",
        "portal_sign_in.code_requested",
        "session.started",
        "session.ended",
    }
)


class MetricActionRefused(ValueError):
    """An action the pilot metrics may not read (names the action only)."""


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class TargetDuration:
    target_type: str
    target_id: str
    seconds: float


def _allowed(actions: Sequence[str]) -> list[str]:
    for action in actions:
        if action not in METRIC_ACTIONS:
            raise MetricActionRefused(action)
    return sorted(set(actions))


_COUNTS: Final = text(
    "SELECT action, count(*) AS n FROM audit_events "
    "WHERE action = ANY(CAST(:actions AS text[])) AND occurred_at >= :start "
    "AND occurred_at < :end GROUP BY action"
)
_DURATIONS: Final = text(
    "SELECT s.target_type, s.target_id, "
    "EXTRACT(EPOCH FROM max(e.occurred_at) - min(s.occurred_at)) AS seconds "
    "FROM audit_events s JOIN audit_events e "
    "ON e.tenant_id = s.tenant_id AND e.target_type = s.target_type "
    "AND e.target_id = s.target_id "
    "WHERE s.action = :start_action AND e.action = :end_action "
    "AND s.occurred_at >= :start AND e.occurred_at < :end AND e.occurred_at >= s.occurred_at "
    "GROUP BY s.target_type, s.target_id ORDER BY s.target_type, s.target_id"
)


async def event_counts(
    tenant: TenantContext, actions: Sequence[str], window: Window
) -> dict[str, int]:
    names = _allowed(actions)
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            _COUNTS,
            {"actions": "{" + ",".join(names) + "}", "start": window.start, "end": window.end},
        )
        found = {str(r.action): int(r.n) for r in rows}
    return {name: found.get(name, 0) for name in names}


async def first_to_last_durations(
    tenant: TenantContext, start_action: str, end_action: str, window: Window
) -> list[TargetDuration]:
    _allowed([start_action, end_action])
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            _DURATIONS,
            {
                "start_action": start_action,
                "end_action": end_action,
                "start": window.start,
                "end": window.end,
            },
        )
        return [
            TargetDuration(str(r.target_type), str(r.target_id), float(r.seconds)) for r in rows
        ]

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
from typing import Any, Final

from sqlalchemy import Select, and_, func, select

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow.explorer import AUDIT_EVENTS

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


t = AUDIT_EVENTS.c  # the kernel's composed read surface, as the explorer reads it


def _counts(
    names: Sequence[str], window: Window
) -> Select[*tuple[Any, ...]]:  # Any: action and count
    return (
        select(t.action, func.count().label("n"))
        .where(t.action.in_(names), t.occurred_at >= window.start, t.occurred_at < window.end)
        .group_by(t.action)
    )


def _durations(
    start_action: str, end_action: str, window: Window
) -> Select[*tuple[Any, ...]]:  # Any: wide
    s, e = AUDIT_EVENTS.alias("s"), AUDIT_EVENTS.alias("e")
    seconds = func.extract("epoch", func.max(e.c.occurred_at) - func.min(s.c.occurred_at))
    return (
        select(s.c.target_type, s.c.target_id, seconds.label("seconds"))
        .select_from(
            s.join(
                e,
                and_(
                    e.c.tenant_id == s.c.tenant_id,
                    e.c.target_type == s.c.target_type,
                    e.c.target_id == s.c.target_id,
                ),
            )
        )
        .where(
            s.c.action == start_action,
            e.c.action == end_action,
            s.c.occurred_at >= window.start,
            e.c.occurred_at < window.end,
            e.c.occurred_at >= s.c.occurred_at,
        )
        .group_by(s.c.target_type, s.c.target_id)
        .order_by(s.c.target_type, s.c.target_id)
    )


async def event_counts(
    tenant: TenantContext, actions: Sequence[str], window: Window
) -> dict[str, int]:
    names = _allowed(actions)
    async with tenant_session(tenant) as session:
        rows = await session.execute(_counts(names, window))
        found = {str(r.action): int(r.n) for r in rows}
    return {name: found.get(name, 0) for name in names}


async def first_to_last_durations(
    tenant: TenantContext, start_action: str, end_action: str, window: Window
) -> list[TargetDuration]:
    _allowed([start_action, end_action])
    async with tenant_session(tenant) as session:
        rows = await session.execute(_durations(start_action, end_action, window))
        return [
            TargetDuration(str(r.target_type), str(r.target_id), float(r.seconds)) for r in rows
        ]

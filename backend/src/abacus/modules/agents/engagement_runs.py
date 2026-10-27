"""Active C6 v1 engagement runs, for AUD-01's "Processing" pill and AUD-02's audit bar (A-01-T27;
DV-11; DEC-717).

An engagement run is a run of an agent registered here as an engagement-run agent
(`register_engagement_run_agent`; P-09's orchestrator registers its own). The SPEC-027 engagement
agent's policy ticks and the specialists (screener, matcher, reviewer, drafter) are not, so they
never light the pill. A run is active while `running` and not shadow (SPEC-036: shadow runs are
never shown). Workpaper progress is the run's own output (`workpapers_complete`,
`workpapers_total`), 0 when it states none; `blocked_on_role` is a role code it names.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

_AGENTS: set[str] = set()


def register_engagement_run_agent(agent_id: str) -> None:
    _AGENTS.add(agent_id)


def engagement_run_agents() -> frozenset[str]:
    return frozenset(_AGENTS)


@dataclass(frozen=True)
class ActiveRun:
    run_id: UUID
    engagement_id: UUID
    run_number: int
    started_at: datetime
    initiator_user_id: UUID
    workpapers_complete: int
    workpapers_total: int
    blocked_on_role: Literal["partner", "manager"] | None


_ACTIVE = text(
    "SELECT r.id, r.engagement_id, r.started_at, r.initiator_user_id, r.output, "
    "(SELECT count(*) FROM agent_runs p WHERE p.engagement_id = r.engagement_id "
    " AND p.agent_id = ANY(CAST(:agents AS text[])) AND p.started_at <= r.started_at) AS n "
    "FROM agent_runs r WHERE r.engagement_id = ANY(CAST(:engagements AS uuid[])) "
    "AND r.agent_id = ANY(CAST(:agents AS text[])) AND r.status = 'running' AND NOT r.shadow "
    "ORDER BY r.started_at DESC"
)


BlockedOn = Literal["partner", "manager"]  # the C6 run summary's codes
_BLOCKED_ON: Final[dict[str, BlockedOn]] = {"partner": "partner", "manager": "manager"}


def _blocked_on(code: object) -> BlockedOn | None:
    return _BLOCKED_ON.get(code) if isinstance(code, str) else None


def _int(output: dict[str, object] | None, key: str) -> int:
    value = (output or {}).get(key)
    return value if isinstance(value, int) and value >= 0 else 0


async def active_engagement_runs(
    tenant: TenantContext, engagement_ids: Sequence[UUID]
) -> dict[UUID, ActiveRun]:
    """The newest active engagement run per engagement (none without a registered agent)."""
    agents = sorted(_AGENTS)
    if not agents or not engagement_ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            _ACTIVE,
            {
                "agents": agents,
                "engagements": list(engagement_ids),
            },
        )
        found: dict[UUID, ActiveRun] = {}
        for r in rows:
            if r.engagement_id in found:
                continue
            output = cast(dict[str, object] | None, r.output)
            role = (output or {}).get("blocked_on_role")
            found[r.engagement_id] = ActiveRun(
                r.id,
                r.engagement_id,
                int(r.n),
                r.started_at,
                r.initiator_user_id,
                _int(output, "workpapers_complete"),
                _int(output, "workpapers_total"),
                _blocked_on(role),
            )
        return found

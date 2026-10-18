"""Change an agent's stage for a real firm, or report on its shadow runs (SPEC-036; TASK-076 D1).

Run:
  python -m abacus_tools.agent_stage report <firm-id> <agent-id>
  python -m abacus_tools.agent_stage set <firm-id> <agent-id> <shadow|live|off> "<note>"

The founder's operations command. It writes through the owner role (the application role can only
read `agent_stages`), as the platform (`platform:founder`), and audits each change in the same
transaction. `live` is refused until the agent has had at least 50 shadow runs over 14 days for
the firm (SPEC-036 Q1). The report compares shadow output with what the firm's people decided:
for the screener, its proposal against the review decision (D3).
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

import asyncpg

from abacus.kernel.config import settings

ACTOR: Final = "platform:founder"
MIN_RUNS: Final = 50
MIN_DAYS: Final = 14
STAGES: Final = ("shadow", "live", "off")
SCREENER: Final = "evidence.screener"
# A screener proposal agrees with a person when it proposed what they did (Q1, D3).
AGREES: Final = {"ready_for_review": ("accept",), "needs_revision": ("reject", "send_back")}


@dataclass(frozen=True)
class ShadowReport:
    runs: int
    first: datetime | None
    outcomes: dict[str, int]
    cost_usd: Decimal
    compared: int  # screener proposals with a person's decision
    agreed: int

    @property
    def days(self) -> int:
        return (datetime.now(UTC) - self.first).days if self.first else 0

    @property
    def ready(self) -> bool:
        return self.runs >= MIN_RUNS and self.days >= MIN_DAYS


def _dsn() -> str:
    url = settings().migrations_database_url
    if url is None:
        raise StageRefused("ABACUS_MIGRATIONS_DATABASE_URL (the owner role) is not set")
    return url.get_secret_value().replace("postgresql+asyncpg://", "postgresql://")


async def _connect(firm: UUID) -> asyncpg.Connection:
    connection = await asyncpg.connect(_dsn())
    await connection.execute(
        "SELECT set_config('app.tenant_id', $1, false), "
        "set_config('app.actor_kind', 'system', false), set_config('app.actor_id', $2, false)",
        str(firm),
        ACTOR,
    )
    return connection


async def report(firm: UUID, agent_id: str) -> ShadowReport:
    connection = await _connect(firm)
    try:
        runs = await connection.fetch(
            "SELECT status, count(*) AS n, min(started_at) AS first FROM agent_runs "
            "WHERE agent_id = $1 AND shadow GROUP BY status",
            agent_id,
        )
        cost = await connection.fetchval(
            "SELECT COALESCE(sum(u.cost_usd), 0) FROM usage_records u "
            "JOIN agent_runs r ON r.id = u.agent_run_id WHERE r.agent_id = $1 AND r.shadow",
            agent_id,
        )
        pairs = (
            await connection.fetch(
                "SELECT s.action, d.decision FROM screening_results s "
                "JOIN agent_runs r ON r.id = s.agent_run_id AND r.shadow "
                "JOIN LATERAL (SELECT decision FROM review_decisions x "
                "WHERE x.evidence_version_id = s.evidence_version_id AND x.actor_kind = 'human' "
                "ORDER BY x.created_at DESC LIMIT 1) d ON true WHERE r.agent_id = $1",
                agent_id,
            )
            if agent_id == SCREENER
            else []
        )
    finally:
        await connection.close()
    rows = cast(list[dict[str, object]], [dict(r) for r in runs])
    firsts = [cast(datetime, r["first"]) for r in rows]
    pairs_ = [(str(p["action"]), str(p["decision"])) for p in pairs]
    return ShadowReport(
        runs=sum(cast(int, r["n"]) for r in rows),
        first=min(firsts) if firsts else None,
        outcomes={str(r["status"]): cast(int, r["n"]) for r in rows},
        cost_usd=Decimal(str(cost)),
        compared=len(pairs_),
        agreed=sum(1 for action, decision in pairs_ if decision in AGREES.get(action, ())),
    )


class StageRefused(Exception):
    pass


async def set_stage(firm: UUID, agent_id: str, stage: str, note: str) -> None:
    """Append the stage row and its audit event in one transaction, as the platform."""
    if stage not in STAGES:
        raise StageRefused(f"stage is one of {', '.join(STAGES)}")
    if not note.strip():
        raise StageRefused("a note is required")
    if stage == "live":
        found = await report(firm, agent_id)
        if not found.ready:
            raise StageRefused(
                f"live needs {MIN_RUNS} shadow runs over {MIN_DAYS} days; "
                f"this firm has {found.runs} over {found.days}"
            )
    connection = await _connect(firm)
    try:
        async with connection.transaction():
            stage_id = await connection.fetchval(
                "INSERT INTO agent_stages (tenant_id, agent_id, stage, changed_by, note) "
                "VALUES ($1, $2, $3, $4, $5) RETURNING id",
                firm,
                agent_id,
                stage,
                ACTOR,
                note.strip(),
            )
            await connection.execute(
                "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, "
                "target_type, target_id, after_ref) VALUES ($1, 'system', $2, "
                "'agent_stage.changed', 'agent_stage', $3, $4::jsonb)",
                firm,
                ACTOR,
                str(stage_id),
                json.dumps({"stage": STAGES.index(stage)}),
            )
    finally:
        await connection.close()


def _print(found: ShadowReport) -> None:
    print(f"shadow runs: {found.runs} over {found.days} days; outcomes {found.outcomes}")
    print(f"cost: ${found.cost_usd}")
    if found.compared:
        share = found.agreed / found.compared
        print(f"agreed with people's decisions: {found.agreed}/{found.compared} ({share:.0%})")
    print(
        "ready to promote" if found.ready else f"not ready: needs {MIN_RUNS} runs, {MIN_DAYS} days"
    )


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "report":
        _print(asyncio.run(report(UUID(argv[1]), argv[2])))
        return 0
    if len(argv) == 5 and argv[0] == "set":
        try:
            asyncio.run(set_stage(UUID(argv[1]), argv[2], argv[3], argv[4]))
        except StageRefused as refused:
            print(f"refused: {refused}")
            return 1
        print(f"{argv[2]} is now {argv[3]} for firm {argv[1]}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

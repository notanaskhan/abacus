"""A run's model calls as the gateway recorded them (TASK-461; P-09 run trace).

Read-only, for a caller that has authorised on the run: when each attempt happened, its outcome,
route and token counts. The model id is never returned (the trace shows the runtime label).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session


@dataclass(frozen=True)
class Attempt:
    at: datetime
    outcome: str
    route: str
    tier: str
    prompt: str  # prompt id and version, e.g. "evidence.screen@3"
    input_tokens: int
    output_tokens: int


async def attempts_for(tenant: TenantContext, run_id: UUID) -> list[Attempt]:
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(
                "SELECT created_at, outcome, route, tier, prompt_id, prompt_version, "
                "input_tokens, output_tokens FROM usage_records "
                "WHERE agent_run_id = :run ORDER BY created_at, id"
            ),
            {"run": run_id},
        )
        return [
            Attempt(r[0], r[1], r[2], r[3], f"{r[4]}@{r[5]}", int(r[6]), int(r[7]))
            for r in rows.all()
        ]

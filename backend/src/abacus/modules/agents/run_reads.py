"""Read-only views of a run's steps for the owning module's screens (C-01-T20;
CLS-02 run card and history). Identifiers, codes and times only; the caller authorised the work
item (and so its engagement) before asking. agents' tables stay agents' (ADR-008): owners read
them through `agents.api`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session


@dataclass(frozen=True)
class RunStepRow:
    step_id: UUID
    seq: int
    key: str | None
    level: int
    kind: str
    state: str
    error_code: str | None
    started_at: datetime | None
    ended_at: datetime | None
    retry_of_step_id: UUID | None


_STEPS = text(
    "SELECT id, seq, plan_step_key, level, kind, state, error_code, started_at, ended_at, "
    "retry_of_step_id FROM agent_run_steps WHERE run_id = :r ORDER BY seq"
)


async def run_step_rows(tenant: TenantContext, run_id: UUID) -> list[RunStepRow]:
    """A run's steps in order, retries as their own rows (LIST_EXEMPT: as above)."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_STEPS, {"r": run_id})).all()
    return [RunStepRow(*r) for r in rows]  # pyright: ignore[reportArgumentType] -- column order

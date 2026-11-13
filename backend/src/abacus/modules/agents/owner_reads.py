"""What an owner reads about the agent's open work on its records (T-05-T52; TASK-7903; DEC-4905).

Counts only, for a gate or a guard that has already authorised on the engagement (or runs as the
system for a gate): proposals of a kind still awaiting a person's decision, and run questions
still open on a work item's runs. Nothing here decides or writes.
"""

from __future__ import annotations

from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

_PENDING: Final = text(
    "SELECT count(*) FROM proposals WHERE engagement_id = :e AND kind = :k AND state = 'pending'"
)
_OPEN_QUESTIONS: Final = text(
    "SELECT count(*) FROM agent_questions q JOIN agent_runs r ON r.id = q.run_id "
    "WHERE r.work_item_ref = :ref AND q.state = 'open' "
    "AND r.state NOT IN ('succeeded', 'failed', 'cancelled', 'completed', 'rejected')"
)


async def pending_proposal_count(tenant: TenantContext, engagement_id: UUID, kind: str) -> int:
    """Proposals of `kind` on the engagement awaiting a person's decision."""
    async with tenant_session(tenant) as session:
        return cast(int, await session.scalar(_PENDING, {"e": engagement_id, "k": kind}) or 0)


async def open_question_count(tenant: TenantContext, work_item_ref: str) -> int:
    """Run questions still open on a work item's live runs (`tax_return:<id>`)."""
    async with tenant_session(tenant) as session:
        return cast(int, await session.scalar(_OPEN_QUESTIONS, {"ref": work_item_ref}) or 0)


__all__ = ["open_question_count", "pending_proposal_count"]

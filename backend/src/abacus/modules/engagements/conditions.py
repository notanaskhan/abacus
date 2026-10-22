"""What engagements tells identity for the matrix conditions (F-03-T24; chapter 03 §4.4): a
person's functions on a work item (`function_in`), whether gates are met (`gates_met`), and an
engagement's service line (`in_scope`). Registered from `engagements.api`; identity never imports
this module."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.models import Engagement
from abacus.modules.engagements.slots import gate_fact

_FUNCTIONS = text(
    "SELECT function FROM work_item_assignments "
    "WHERE work_item_id = :work_item_id AND user_id = :user_id AND removed_at IS NULL"
)


async def functions_on(tenant: TenantContext, work_item_id: UUID, user_id: UUID) -> frozenset[str]:
    """The functions the person holds on the work item now (removed assignments don't count)."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            _FUNCTIONS, {"work_item_id": work_item_id, "user_id": user_id}
        )
        return frozenset(str(r.function) for r in rows)


async def gates_of(
    tenant: TenantContext, engagement_id: UUID, gates: tuple[str, ...]
) -> dict[str, bool]:
    """Each gate met or not, from the fail-closed gate slot (an unregistered gate is unmet)."""
    return {gate: (await gate_fact(tenant, engagement_id, gate)).met for gate in gates}


async def service_line_of(tenant: TenantContext, engagement_id: UUID) -> str | None:
    async with tenant_session(tenant) as session:
        return (
            await session.execute(
                select(Engagement.service_line).where(Engagement.id == engagement_id)
            )
        ).scalar_one_or_none()

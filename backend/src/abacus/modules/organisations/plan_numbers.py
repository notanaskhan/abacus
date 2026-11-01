"""A-05-T10: a plan entity's Form 5500 plan number (`client_entities.plan_number`, 0082).

The EBP-01 service reads it and, after its own checks (DEC-1955), writes it in its unit of work;
the caller has authorised the edit on the work item's engagement. The column's CHECK holds three
digits; the service refuses 000 and a recordkeeper's plan ID before it gets here.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Target, UnitOfWork
from abacus.modules.identity.api import AuthContext
from abacus.modules.organisations.models import ClientEntity


async def entity_plan_number(tenant: TenantContext, entity_id: UUID) -> str | None:
    async with tenant_session(tenant) as session:
        return await session.scalar(
            select(ClientEntity.plan_number).where(ClientEntity.id == entity_id)
        )


async def set_entity_plan_number(
    tx: UnitOfWork, ctx: AuthContext, entity_id: UUID, plan_number: str
) -> None:
    del ctx  # the caller authorised; the unit of work carries the actor
    done = await tx.session.execute(
        update(ClientEntity)
        .where(ClientEntity.id == entity_id)
        .values(plan_number=plan_number)
        .returning(ClientEntity.id)
    )
    if done.scalar_one_or_none() is None:
        raise NotFound("client_entity")
    tx.record("client_entity.plan_number_set", target=Target("client_entity", entity_id))


async def entity_name(tenant: TenantContext, entity_id: UUID) -> str | None:
    """The entity's display name (EBP-01's plan name), for a caller that authorised on it."""
    async with tenant_session(tenant) as session:
        return await session.scalar(select(ClientEntity.name).where(ClientEntity.id == entity_id))

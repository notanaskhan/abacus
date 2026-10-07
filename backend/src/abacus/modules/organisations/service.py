"""Organisations rules. Clients are created with their first engagement for now (TASK-008 Q4)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Target, UnitOfWork
from abacus.modules.organisations.repository import (
    insert_client,
    insert_client_entity,
    names_in_firm,
    names_of,
)


@dataclass(frozen=True)
class NewClient:
    client_id: UUID
    client_entity_id: UUID


@dataclass(frozen=True)
class ClientNames:
    client_name: str
    client_entity_name: str


async def create_client(
    tx: UnitOfWork, tenant_id: UUID, client_name: str, client_entity_name: str
) -> NewClient:
    """Inside the caller's unit of work; the caller has authorised the action that needs it."""
    new = NewClient(uuid4(), uuid4())
    await insert_client(tx.session, tenant_id, new.client_id, client_name)
    await insert_client_entity(
        tx.session, tenant_id, new.client_id, new.client_entity_id, client_entity_name
    )
    tx.record("client.created", target=Target("client", new.client_id))
    tx.record("client_entity.created", target=Target("client_entity", new.client_entity_id))
    return new


async def client_names(session: AsyncSession, entity_ids: list[UUID]) -> dict[UUID, ClientNames]:
    names = await names_of(session, entity_ids)
    return {entity: ClientNames(*pair) for entity, pair in names.items()}


@dataclass(frozen=True)
class FirmName:
    client_id: UUID
    id: UUID  # the client's or the entity's
    name: str


async def firm_names(tenant: TenantContext) -> list[FirmName]:
    """Every client and entity name of the firm (SPEC-006 scope checker)."""
    async with tenant_session(tenant) as session:
        return [FirmName(c, i, n) for c, i, n in await names_in_firm(session)]

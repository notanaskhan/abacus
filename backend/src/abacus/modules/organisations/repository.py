"""Organisations data access: clients and client entities only (ADR-008)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.organisations.models import Client, ClientEntity


async def insert_client(
    session: AsyncSession, tenant_id: UUID, client_id: UUID, name: str
) -> None:
    await session.execute(insert(Client).values(id=client_id, tenant_id=tenant_id, name=name))


async def insert_client_entity(
    session: AsyncSession, tenant_id: UUID, client_id: UUID, entity_id: UUID, name: str
) -> None:
    await session.execute(
        insert(ClientEntity).values(
            id=entity_id, tenant_id=tenant_id, client_id=client_id, name=name
        )
    )


async def names_of(session: AsyncSession, entity_ids: list[UUID]) -> dict[UUID, tuple[str, str]]:
    """Client and entity names by entity ID. The caller has authorised access to their
    engagements."""
    if not entity_ids:
        return {}
    rows = (
        await session.execute(
            select(ClientEntity.id, Client.name, ClientEntity.name)
            .join(
                Client,
                (Client.id == ClientEntity.client_id)
                & (Client.tenant_id == ClientEntity.tenant_id),
            )
            .where(ClientEntity.id.in_(entity_ids))
        )
    ).all()
    return {row[0]: (row[1], row[2]) for row in rows}


async def names_in_firm(session: AsyncSession) -> list[tuple[UUID, UUID, str]]:
    """Every client and entity name in the tenant: (client id, entity or client id, name). For
    the outbound scope checker (SPEC-006), which needs names outside an engagement too."""
    clients = (await session.execute(select(Client.id, Client.name))).all()
    entities = (
        await session.execute(select(ClientEntity.client_id, ClientEntity.id, ClientEntity.name))
    ).all()
    return [(c, c, n) for c, n in clients] + [(c, e, n) for c, e, n in entities]

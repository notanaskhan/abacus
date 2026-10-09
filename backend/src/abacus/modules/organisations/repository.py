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


async def clients_matching(
    session: AsyncSession, normalised: str, *, exact: bool = False, limit: int = 20
) -> list[tuple[Client, list[ClientEntity]]]:
    """The firm's clients whose normalised name starts with (or, `exact`, equals) the text, with
    their entities; for a caller that authorised `client.read` (SPEC-025; LIST_EXEMPT: clients
    are firm-level, and the caller removes walled ones)."""
    where = (
        Client.normalised_name == normalised
        if exact
        else Client.normalised_name.like(normalised.replace("%", "").replace("_", "") + "%")
    )
    clients = list(
        (
            await session.execute(
                select(Client).where(where).order_by(Client.name, Client.id).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    if not clients:
        return []
    entities = (
        (
            await session.execute(
                select(ClientEntity)
                .where(ClientEntity.client_id.in_([c.id for c in clients]))
                .order_by(ClientEntity.name, ClientEntity.id)
            )
        )
        .scalars()
        .all()
    )
    by_client: dict[UUID, list[ClientEntity]] = {}
    for entity in entities:
        by_client.setdefault(entity.client_id, []).append(entity)
    return [(c, by_client.get(c.id, [])) for c in clients]


async def get_client(session: AsyncSession, client_id: UUID) -> Client | None:
    return (
        await session.execute(select(Client).where(Client.id == client_id))
    ).scalar_one_or_none()


async def get_entity(session: AsyncSession, entity_id: UUID) -> ClientEntity | None:
    return (
        await session.execute(select(ClientEntity).where(ClientEntity.id == entity_id))
    ).scalar_one_or_none()

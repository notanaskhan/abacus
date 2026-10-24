"""Organisations data access: clients and client entities only (ADR-008)."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import ColumnElement, Select, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute

from abacus.modules.organisations.models import Client, ClientEntity, Contact, Office


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


async def names_of(
    session: AsyncSession, entity_ids: list[UUID]
) -> dict[UUID, tuple[str, str, UUID]]:
    """Client and entity names by entity ID. The caller has authorised access to their
    engagements."""
    if not entity_ids:
        return {}
    rows = (
        await session.execute(
            select(ClientEntity.id, Client.name, ClientEntity.name, Client.id)
            .join(
                Client,
                (Client.id == ClientEntity.client_id)
                & (Client.tenant_id == ClientEntity.tenant_id),
            )
            .where(ClientEntity.id.in_(entity_ids))
        )
    ).all()
    return {row[0]: (row[1], row[2], row[3]) for row in rows}


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


async def update_client(
    session: AsyncSession, client_id: UUID, values: Mapping[str, object]
) -> bool:
    """Set client record columns (F-03-T25); whether the client exists in this firm."""
    done = await session.execute(
        update(Client).where(Client.id == client_id).values(dict(values)).returning(Client.id)
    )
    return done.first() is not None


async def update_entity(
    session: AsyncSession, entity_id: UUID, values: Mapping[str, object]
) -> bool:
    done = await session.execute(
        update(ClientEntity)
        .where(ClientEntity.id == entity_id)
        .values(dict(values))
        .returning(ClientEntity.id)
    )
    return done.first() is not None


async def insert_contact(session: AsyncSession, values: Mapping[str, object]) -> None:
    await session.execute(insert(Contact).values(dict(values)))


async def contacts_of(session: AsyncSession, client_id: UUID) -> list[Contact]:
    """One client's contacts, for a caller that authorised the client (F-03-T25)."""
    rows = await session.execute(
        select(Contact)
        .where(Contact.client_id == client_id)
        .order_by(Contact.display_name, Contact.id)
    )
    return list(rows.scalars().all())


async def get_contact(session: AsyncSession, contact_id: UUID) -> Contact | None:
    return (
        await session.execute(select(Contact).where(Contact.id == contact_id))
    ).scalar_one_or_none()


async def contact_ids_of_user(session: AsyncSession, user_id: UUID) -> list[UUID]:
    """The firm's contacts linked to a portal user (P-08-T17: the MFA floor's designations)."""
    rows = await session.execute(select(Contact.id).where(Contact.user_id == user_id))
    return [r.id for r in rows]


async def contacts_by_id(
    session: AsyncSession, contact_ids: list[UUID]
) -> dict[UUID, tuple[UUID, str, UUID | None]]:
    """Contacts by ID: their client, display name and portal user (P-06-T07: a binder's
    recipients; P-06-T10: a request's delegate), for a caller that authorised the record."""
    if not contact_ids:
        return {}
    rows = await session.execute(
        select(Contact.id, Contact.client_id, Contact.display_name, Contact.user_id).where(
            Contact.id.in_(contact_ids)
        )
    )
    return {r.id: (r.client_id, r.display_name, r.user_id) for r in rows}


async def offices_in_firm(session: AsyncSession) -> list[tuple[UUID, str]]:
    """The firm's offices by name (LIST_EXEMPT: firm structure, a filter only, DEC-30)."""
    rows = await session.execute(select(Office.id, Office.name).order_by(Office.name))
    return [(r.id, r.name) for r in rows]


# P-06-T11 (BND-01): names another module's list shows and searches, as correlated subqueries
# on its own rows. They read under the same session's RLS; the outer list applies `visible()`.
Column = ColumnElement[UUID] | QueryableAttribute[UUID] | QueryableAttribute[UUID | None]


def client_name_column(client_id: Column) -> ColumnElement[str]:
    """The client's name for each outer row."""
    return (
        select(Client.name)
        .where(Client.id == client_id)
        .correlate_except(Client)
        .scalar_subquery()
    )


def office_name_column(office_id: Column) -> ColumnElement[str]:
    """The office's name for each outer row (None without an office)."""
    return (
        select(Office.name)
        .where(Office.id == office_id)
        .correlate_except(Office)
        .scalar_subquery()
    )


def attest_client_ids() -> Select[UUID]:
    """The firm's attest clients (derived `is_attest_client`, DEC-128) as a subquery for identity's
    `visible()` under `g2_blocks_view` (P-07-T24, ADR-164 item 3). Row-level security scopes it to
    the session's tenant; it is only ever embedded in a query that `visible()` already filters."""
    return select(Client.id).where(Client.is_attest_client.is_(True))

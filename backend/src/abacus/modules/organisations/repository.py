"""Organisations data access: clients and client entities only (ADR-008)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import ColumnElement, Select, bindparam, insert, select, text, update
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
) -> dict[UUID, tuple[UUID, str, UUID | None, str | None]]:
    """Contacts by ID: their client, display name, portal user and organisation (P-06-T07: a
    binder's recipients; P-06-T10: a request's delegate; P-08-T18: an invitation's card), for a
    caller that authorised the record."""
    if not contact_ids:
        return {}
    rows = await session.execute(
        select(
            Contact.id,
            Contact.client_id,
            Contact.display_name,
            Contact.user_id,
            Contact.organisation_name,
        ).where(Contact.id.in_(contact_ids))
    )
    return {r.id: (r.client_id, r.display_name, r.user_id, r.organisation_name) for r in rows}


async def set_contact_active(
    session: AsyncSession, contact_id: UUID, user_id: UUID
) -> UUID | None:
    """The contact's portal user and state after an accepted invitation (P-08-T18); its client,
    or None when it is unknown or linked to someone else."""
    row = (
        await session.execute(
            update(Contact)
            .where(
                Contact.id == contact_id,
                (Contact.user_id.is_(None)) | (Contact.user_id == user_id),
            )
            .values(user_id=user_id, portal_state="active")
            .returning(Contact.client_id)
        )
    ).first()
    return None if row is None else row.client_id


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


# --- CLI-04 contacts (P-07-T25; 0146) -----------------------------------------------------------


@dataclass(frozen=True)
class ContactRoleRow:
    contact_id: UUID
    role: str
    scope_kind: str
    scope_id: UUID
    title_text: str | None


async def entities_of(session: AsyncSession, client_id: UUID) -> dict[UUID, str]:
    rows = await session.execute(
        select(ClientEntity.id, ClientEntity.name).where(ClientEntity.client_id == client_id)
    )
    return {r.id: r.name for r in rows}


async def contact_roles_of(
    session: AsyncSession, contact_ids: Sequence[UUID]
) -> list[ContactRoleRow]:
    if not contact_ids:
        return []
    rows = await session.execute(
        text(
            "SELECT contact_id, role, scope_kind, scope_id, title_text FROM contact_roles "
            "WHERE contact_id IN :ids ORDER BY created_at, role, scope_id"
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": list(contact_ids)},
    )
    return [ContactRoleRow(r[0], r[1], r[2], r[3], r[4]) for r in rows.all()]


async def replace_contact_roles(
    session: AsyncSession,
    tenant_id: UUID,
    contact_id: UUID,
    roles: Sequence[tuple[str, str, UUID, str | None]],
) -> None:
    """The contact's roles become `roles` (role, scope kind, scope id, title)."""
    await session.execute(
        text("DELETE FROM contact_roles WHERE contact_id = :contact"), {"contact": contact_id}
    )
    for role, kind, scope_id, title in roles:
        await session.execute(
            text(
                "INSERT INTO contact_roles (tenant_id, contact_id, scope_kind, scope_id, role, "
                "title_text) VALUES (:tenant, :contact, :kind, :scope, :role, :title)"
            ),
            {
                "tenant": tenant_id,
                "contact": contact_id,
                "kind": kind,
                "scope": scope_id,
                "role": role,
                "title": title,
            },
        )


async def update_contact_versioned(
    session: AsyncSession, contact_id: UUID, seen_version: int, values: Mapping[str, object]
) -> int | None:
    """The contact's fields set and its version moved on, only at `seen_version`: the new
    version, or None when the contact has moved on (or is unknown)."""
    row = (
        await session.execute(
            update(Contact)
            .where(Contact.id == contact_id, Contact.version == seen_version)
            .values(**dict(values), version=Contact.version + 1)
            .returning(Contact.version)
        )
    ).first()
    return None if row is None else int(row.version)


async def set_portal_state(session: AsyncSession, contact_id: UUID, state: str) -> None:
    await session.execute(
        update(Contact).where(Contact.id == contact_id).values(portal_state=state)
    )

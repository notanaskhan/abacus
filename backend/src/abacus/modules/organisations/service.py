"""Organisations rules. A client is created with its first engagement, then picked again for later
ones (SPEC-025 AC-1; TASK-043)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Target, UnitOfWork
from abacus.modules.organisations.repository import (
    clients_matching,
    get_client,
    get_entity,
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


# --- Clients you already have (SPEC-025 AC-1; TASK-043) ----------------------------------------

_SUFFIXES: Final = frozenset(
    [
        "inc",
        "incorporated",
        "llc",
        "ltd",
        "limited",
        "corp",
        "corporation",
        "co",
        "company",
        "plc",
        "lp",
        "llp",
        "pc",
        "pllc",
    ]
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalise(name: str) -> str:
    """As the database's generated `normalised_name` (migration 0035; a unit test keeps them in
    step): lower case, punctuation as spaces, legal suffixes dropped, spaces collapsed."""
    words = _NON_ALNUM.sub(" ", name.lower()).split()
    return " ".join(w for w in words if w not in _SUFFIXES)


class EntityExists(DomainConflict):
    """The client already has an entity with this name: pick it instead."""

    code = "entity_exists"


@dataclass(frozen=True)
class EntityChoice:
    id: UUID
    name: str


@dataclass(frozen=True)
class ClientChoice:
    id: UUID
    name: str
    entities: tuple[EntityChoice, ...]


async def find_clients(
    tenant: TenantContext, text_: str, *, exact: bool = False
) -> list[ClientChoice]:
    """Clients matching a name (normalised), for a caller that authorised `client.read`."""
    wanted = normalise(text_)
    if not wanted:
        return []
    async with tenant_session(tenant) as session:
        found = await clients_matching(session, wanted, exact=exact)
    return [
        ClientChoice(c.id, c.name, tuple(EntityChoice(e.id, e.name) for e in entities))
        for c, entities in found
    ]


async def client_with_entity(
    tx: UnitOfWork, tenant_id: UUID, client_id: UUID, entity_id: UUID | None, entity_name: str
) -> NewClient:
    """An existing client, with one of its entities or a new one (inside the caller's unit of
    work; the caller has authorised and checked walls). `NotFound` if either isn't the firm's."""
    client = await get_client(tx.session, client_id)
    if client is None:
        raise NotFound("client")
    if entity_id is not None:
        entity = await get_entity(tx.session, entity_id)
        if entity is None or entity.client_id != client_id:
            raise NotFound("client_entity")
        return NewClient(client_id, entity_id)
    if any(
        normalise(e.name) == normalise(entity_name)
        for _, entities in await clients_matching(tx.session, client.normalised_name, exact=True)
        for e in entities
        if e.client_id == client_id
    ):
        raise EntityExists(entity_name)
    new_entity = uuid4()
    await insert_client_entity(tx.session, tenant_id, client_id, new_entity, entity_name)
    tx.record("client_entity.created", target=Target("client_entity", new_entity))
    return NewClient(client_id, new_entity)

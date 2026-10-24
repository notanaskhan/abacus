"""Organisations rules. A client is created with its first engagement, then picked again for later
ones (SPEC-025 AC-1; TASK-043)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date
from typing import Final, Literal
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Target, UnitOfWork
from abacus.modules.organisations.models import Contact
from abacus.modules.organisations.repository import (
    clients_matching,
    contact_ids_of_user,
    contacts_by_id,
    contacts_of,
    get_client,
    get_contact,
    get_entity,
    insert_client,
    insert_client_entity,
    insert_contact,
    names_in_firm,
    names_of,
    offices_in_firm,
    update_client,
    update_entity,
)


@dataclass(frozen=True)
class NewClient:
    client_id: UUID
    client_entity_id: UUID


@dataclass(frozen=True)
class ClientNames:
    client_name: str
    client_entity_name: str
    client_id: UUID  # SPEC-303 (TASK-304): the clients index groups by it


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


# --- F-03-T25: the client record, entity attributes and contacts (DEC-62, DEC-63) -------------

ClientKind = Literal["household", "business", "plan_sponsor", "nonprofit", "trust_family"]
ClientStatus = Literal["prospect", "active", "inactive", "former"]
RiskTier = Literal["low", "moderate", "high"]
PortalStatus = Literal["not_invited", "invited", "active"]
EntityType = Literal[
    "individual",
    "household_mfj",
    "c_corp",
    "s_corp",
    "llc",
    "partnership",
    "trust",
    "estate",
    "ebp_plan",
    "exempt_org",
]
ContactKind = Literal[
    "client_person", "third_party", "k1_recipient", "tcwg", "component_auditor", "prospect"
]
PortalState = Literal["not_invited", "invited", "active", "locked"]
_FOREIGN_KEY_VIOLATION: Final = "23503"
_UNIQUE_VIOLATION: Final = "23505"
_CHECK_VIOLATION: Final = "23514"


class ContactExists(DomainConflict):
    """A client has one contact per email address."""

    code = "contact_exists"


class ClientRecordInvalid(DomainInvalid):
    """A value the client record's constraints refuse (an office or partner of another firm, a
    malformed fiscal year end)."""

    code = "client_record_invalid"


@dataclass(frozen=True)
class ClientRecordChange:
    """The client record fields to set; None leaves a field as it is."""

    kind: ClientKind | None = None
    status: ClientStatus | None = None
    primary_office_id: UUID | None = None
    relationship_partner_id: UUID | None = None
    risk_tier: RiskTier | None = None
    portal_status: PortalStatus | None = None
    practice_mgmt_ref: str | None = None


@dataclass(frozen=True)
class EntityAttributes:
    """An entity's attributes to set; None leaves one as it is. No taxpayer ID (P-12)."""

    entity_type: EntityType | None = None
    fye_month_day: str | None = None
    state_of_formation: str | None = None
    plan_number: str | None = None
    date_of_death: date | None = None
    grantor_status: bool | None = None


@dataclass(frozen=True)
class NewContact:
    display_name: str
    contact_kind: ContactKind
    email: str | None = None
    phone: str | None = None
    title: str | None = None
    organisation_name: str | None = None


@dataclass(frozen=True)
class ContactView:
    id: UUID
    client_id: UUID
    display_name: str
    contact_kind: str
    email: str | None
    phone: str | None
    title: str | None
    organisation_name: str | None
    user_id: UUID | None
    portal_state: str


@dataclass(frozen=True)
class ClientRecord:
    id: UUID
    name: str
    kind: str | None
    status: str
    primary_office_id: UUID | None
    relationship_partner_id: UUID | None
    risk_tier: str | None
    is_attest_client: bool
    portal_status: str
    practice_mgmt_ref: str | None
    contacts: tuple[ContactView, ...]


def _sqlstate(exc: IntegrityError) -> str | None:
    return getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)


def _set(change: ClientRecordChange | EntityAttributes) -> dict[str, object]:
    return {k: v for k, v in asdict(change).items() if v is not None}


async def set_client_record(tx: UnitOfWork, client_id: UUID, change: ClientRecordChange) -> None:
    """Inside the caller's unit of work; the caller has authorised it. `NotFound` if the client
    isn't the firm's."""
    values = _set(change)
    if not values:
        return
    try:
        async with tx.session.begin_nested():
            found = await update_client(tx.session, client_id, values)
    except IntegrityError as exc:
        if _sqlstate(exc) in (_FOREIGN_KEY_VIOLATION, _CHECK_VIOLATION):
            raise ClientRecordInvalid from None
        raise
    if not found:
        raise NotFound("client")
    tx.record("client.record_changed", target=Target("client", client_id))


async def set_entity_attributes(
    tx: UnitOfWork, entity_id: UUID, attributes: EntityAttributes
) -> None:
    values = _set(attributes)
    if not values:
        return
    try:
        async with tx.session.begin_nested():
            found = await update_entity(tx.session, entity_id, values)
    except IntegrityError as exc:
        if _sqlstate(exc) == _CHECK_VIOLATION:
            raise ClientRecordInvalid from None
        raise
    if not found:
        raise NotFound("client_entity")
    tx.record("client_entity.attributes_changed", target=Target("client_entity", entity_id))


async def add_contact(
    tx: UnitOfWork, tenant_id: UUID, client_id: UUID, contact: NewContact
) -> UUID:
    """A new contact of the client (inside the caller's unit of work, authorised there)."""
    contact_id = uuid4()
    try:
        async with tx.session.begin_nested():
            await insert_contact(
                tx.session,
                {"id": contact_id, "tenant_id": tenant_id, "client_id": client_id}
                | asdict(contact),
            )
    except IntegrityError as exc:
        state = _sqlstate(exc)
        if state == _UNIQUE_VIOLATION:
            raise ContactExists from None
        if state == _FOREIGN_KEY_VIOLATION:
            raise NotFound("client") from None
        if state == _CHECK_VIOLATION:
            raise ClientRecordInvalid from None
        raise
    # The audit explorer places client targets (a contact is the client's), never contact ids.
    tx.record("contact.created", target=Target("client", client_id))
    return contact_id


def _contact_view(c: Contact) -> ContactView:
    return ContactView(
        c.id,
        c.client_id,
        c.display_name,
        c.contact_kind,
        c.email,
        c.phone,
        c.title,
        c.organisation_name,
        c.user_id,
        c.portal_state,
    )


async def client_record(session: AsyncSession, client_id: UUID) -> ClientRecord | None:
    """The client record with its contacts, for a caller that authorised reading the client."""
    client = await get_client(session, client_id)
    if client is None:
        return None
    contacts = await contacts_of(session, client_id)
    return ClientRecord(
        client.id,
        client.name,
        client.kind,
        client.status,
        client.primary_office_id,
        client.relationship_partner_id,
        client.risk_tier,
        client.is_attest_client,
        client.portal_status,
        client.practice_mgmt_ref,
        tuple(_contact_view(c) for c in contacts),
    )


async def contact_client(session: AsyncSession, contact_id: UUID) -> UUID | None:
    """The client a contact belongs to, or None if it isn't the firm's."""
    contact = await get_contact(session, contact_id)
    return None if contact is None else contact.client_id


@dataclass(frozen=True)
class ContactFacts:
    """A contact's client and name (P-06-T07: binder recipients)."""

    client_id: UUID
    display_name: str
    user_id: UUID | None = None  # the portal user, once the contact has signed in (P-06-T10)


async def contact_facts(
    session: AsyncSession, contact_ids: list[UUID]
) -> dict[UUID, ContactFacts]:
    """The firm's contacts among `contact_ids`; others (another firm's, unknown) are left out.
    For a caller that authorised the record the contacts are named on."""
    found = await contacts_by_id(session, contact_ids)
    return {cid: ContactFacts(client, name, user) for cid, (client, name, user) in found.items()}


async def contacts_of_user(session: AsyncSession, user_id: UUID) -> list[UUID]:
    """The firm's contacts the portal user is linked to (P-08-T17: the MFA floor), read in the
    caller's tenant session."""
    return await contact_ids_of_user(session, user_id)


async def attest_client_of(tenant: TenantContext, client_id: UUID) -> bool | None:
    """Whether the client is an attest client now (DEC-128), or None if it isn't the firm's."""
    async with tenant_session(tenant) as session:
        client = await get_client(session, client_id)
    return None if client is None else client.is_attest_client


async def client_exists(tenant: TenantContext, client_id: UUID) -> bool:
    """Whether the client is the firm's (for the `client` scope resolver, F-03-T26)."""
    async with tenant_session(tenant) as session:
        return await get_client(session, client_id) is not None


async def client_of_entity(tenant: TenantContext, entity_id: UUID) -> UUID | None:
    """The client entity's client, or None outside the firm (the `client_entity` scope resolver,
    DEC-211)."""
    async with tenant_session(tenant) as session:
        entity = await get_entity(session, entity_id)
    return entity.client_id if entity is not None else None


async def firm_offices(tenant: TenantContext) -> list[tuple[UUID, str]]:
    """P-01-T04: the firm's offices for identity's `/v1/me` (registered as its office list)."""
    async with tenant_session(tenant) as session:
        return await offices_in_firm(session)

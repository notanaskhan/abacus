"""Public interface of the organisations module; other modules import only this (ADR-008)."""

from abacus.modules.identity.api import AbacusRouter, register_office_list
from abacus.modules.organisations.contract import client_entities_router, clients_router

# P-06-T11: correlated name columns for another module's list (BND-01's client and office).
from abacus.modules.organisations.repository import client_name_column, office_name_column
from abacus.modules.organisations.service import (
    ClientChoice,
    ClientNames,
    ClientRecord,
    ClientRecordChange,
    ClientRecordInvalid,
    ContactExists,
    ContactFacts,
    ContactKind,
    ContactView,
    EntityAttributes,
    EntityChoice,
    FirmName,
    NewClient,
    NewContact,
    add_contact,
    attest_client_of,
    client_exists,
    client_names,
    client_record,
    client_with_entity,
    contact_client,
    contact_facts,
    create_client,
    find_clients,
    firm_names,
    firm_offices,
    normalise,
    set_client_record,
    set_entity_attributes,
)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    clients_router,  # the clients family contract, v1 stub (P-07-T04)
    client_entities_router,
)

# P-01-T04: identity's `/v1/me` lists the firm's offices through this.
register_office_list(firm_offices)

__all__ = [
    "ROUTERS",
    "ClientChoice",
    "ClientNames",
    "ClientRecord",
    "ClientRecordChange",
    "ClientRecordInvalid",
    "ContactExists",
    "ContactFacts",
    "ContactKind",
    "ContactView",
    "EntityAttributes",
    "EntityChoice",
    "FirmName",
    "NewClient",
    "NewContact",
    "add_contact",
    "attest_client_of",
    "client_exists",
    "client_name_column",
    "client_names",
    "client_record",
    "client_with_entity",
    "contact_client",
    "contact_facts",
    "create_client",
    "find_clients",
    "firm_names",
    "normalise",
    "office_name_column",
    "set_client_record",
    "set_entity_attributes",
]

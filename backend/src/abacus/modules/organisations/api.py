"""Public interface of the organisations module; other modules import only this (ADR-008)."""

from abacus.modules.identity.api import register_office_list
from abacus.modules.organisations.service import (
    ClientChoice,
    ClientNames,
    ClientRecord,
    ClientRecordChange,
    ClientRecordInvalid,
    ContactExists,
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
    create_client,
    find_clients,
    firm_names,
    firm_offices,
    normalise,
    set_client_record,
    set_entity_attributes,
)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[()] = ()

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
    "client_names",
    "client_record",
    "client_with_entity",
    "contact_client",
    "create_client",
    "find_clients",
    "firm_names",
    "normalise",
    "set_client_record",
    "set_entity_attributes",
]

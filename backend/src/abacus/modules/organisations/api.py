"""Public interface of the organisations module; other modules import only this (ADR-008)."""

from abacus.modules.identity.api import AbacusRouter, register_office_list, register_settings_area
from abacus.modules.organisations.contacts_contract import (
    client_contacts_router,
    contact_invitations_router,
    contacts_router,
)
from abacus.modules.organisations.contract import client_entities_router, clients_router
from abacus.modules.organisations.live import (
    NewRelationship,
    add_relationship,
    contacts_section,
    entities_section,
    key_dates_section,
)

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
    ContactLinked,
    ContactView,
    EntityAttributes,
    EntityChoice,
    FirmName,
    NewClient,
    NewContact,
    activate_contact,
    add_contact,
    attest_client_ids,
    attest_client_of,
    client_exists,
    client_names,
    client_of_entity,
    client_record,
    client_with_entity,
    contact_client,
    contact_facts,
    contacts_of_user,
    create_client,
    find_clients,
    firm_names,
    firm_offices,
    normalise,
    set_client_record,
    set_entity_attributes,
)
from abacus.modules.organisations.settings_contract import offices_glance, org_settings_router
from abacus.modules.organisations.slots import (
    OverviewItem,
    OverviewSection,
    SectionRows,
    register_client_engagements,
    register_open_requests,
    register_overview_section,
)
from abacus.modules.organisations.tin import (
    MaskedTin,
    TinConflict,
    TinInvalid,
    TinKindNotAllowed,
    clear_tin,
    mask_tin,
    seal_tin,
)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    clients_router,  # the clients family contract, v1 stub (P-07-T04)
    client_entities_router,
    client_contacts_router,  # contacts and portal access, v1 stub (P-07-T17)
    contacts_router,
    contact_invitations_router,
    org_settings_router,  # firm-settings family v1: offices and teams (G-01-T02 stub)
)

# P-01-T04: identity's `/v1/me` lists the firm's offices through this.
register_office_list(firm_offices)
# G-01-T04: the Offices & teams row of the settings overview's At a glance.
register_settings_area("offices_teams", 20, offices_glance)
# P-07-T09: CLI-02's overview sections organisations owns (metadata; `client.read`).
for _section in (
    OverviewSection("entities", "details", "client.read", 10, entities_section),
    OverviewSection("key_dates", "key_dates", "client.read", 30, key_dates_section),
    OverviewSection("contacts", "table", "client.read", 40, contacts_section),
):
    register_overview_section(_section)

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
    "ContactLinked",
    "ContactView",
    "EntityAttributes",
    "EntityChoice",
    "FirmName",
    "MaskedTin",
    "NewClient",
    "NewContact",
    "NewRelationship",
    "OverviewItem",
    "OverviewSection",
    "SectionRows",
    "TinConflict",
    "TinInvalid",
    "TinKindNotAllowed",
    "activate_contact",
    "add_contact",
    "add_relationship",
    "attest_client_ids",
    "attest_client_of",
    "clear_tin",
    "client_exists",
    "client_name_column",
    "client_names",
    "client_of_entity",
    "client_record",
    "client_with_entity",
    "contact_client",
    "contact_facts",
    "contacts_of_user",
    "create_client",
    "find_clients",
    "firm_names",
    "mask_tin",
    "normalise",
    "office_name_column",
    "register_client_engagements",
    "register_open_requests",
    "register_overview_section",
    "seal_tin",
    "set_client_record",
    "set_entity_attributes",
]

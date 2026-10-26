"""Public interface of the integrations module; other modules import only this (ADR-008).

C20 v1 (A-02-T06): the POR-16 contract stub and the framework's ports. A-02-T12: the
fail-closed adapter registry, the catalogue read with its honest listing, the catalogue load's
document and plan (the operator's command is `abacus_tools.integration_catalog`), and sealed
integration secrets. The write-capability registry file and its compiler land with A-02-T15.
"""

from abacus.modules.identity.api import AbacusRouter
from abacus.modules.integrations.adapters import (
    AdapterRefused,
    register_adapter,
    registered_adapter,
    registered_keys,
    unregister_adapter,
)
from abacus.modules.integrations.catalog import (
    CatalogEntry,
    CatalogRow,
    catalog_rows,
    client_catalog,
    is_available,
    listed,
    listing_of,
)
from abacus.modules.integrations.catalog_load import CatalogDocument, LoadPlan, plan_load
from abacus.modules.integrations.contract import firm_router, portal_router
from abacus.modules.integrations.ports import (
    IntegrationAdapter,
    IntegrationCategory,
    ReadConnectorEntry,
    WriteCapabilityEntry,
    WriteCapabilityRegistry,
)
from abacus.modules.integrations.secrets import erase_secret, open_secret, store_secret

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    portal_router,  # C20 v1 stub (A-02-T06): POR-16
    firm_router,  # C20 v1 stub (A-02-T06): reconnect requests and on-demand pulls
)

__all__ = [
    "ROUTERS",
    "AdapterRefused",
    "CatalogDocument",
    "CatalogEntry",
    "CatalogRow",
    "IntegrationAdapter",
    "IntegrationCategory",
    "LoadPlan",
    "ReadConnectorEntry",
    "WriteCapabilityEntry",
    "WriteCapabilityRegistry",
    "catalog_rows",
    "client_catalog",
    "erase_secret",
    "is_available",
    "listed",
    "listing_of",
    "open_secret",
    "plan_load",
    "register_adapter",
    "registered_adapter",
    "registered_keys",
    "store_secret",
    "unregister_adapter",
]

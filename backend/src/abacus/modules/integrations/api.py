"""Public interface of the integrations module; other modules import only this (ADR-008).

C20 v1 (A-02-T06): the POR-16 contract stub and the framework's ports. A-02-T12: the
fail-closed adapter registry, the catalogue read with its honest listing, the catalogue load's
document and plan (the operator's command is `abacus_tools.integration_catalog`), and sealed
integration secrets. A-02-T15: the compiled write-capability registry, the egress allowlist
export, the `Writer` port and the write gate (`authorise_write`, `execute_write`), which refuses
every write in v1. A-02-T16: the POR-16 routes, composed in `client_connect`.
"""

from abacus.modules.connections.api import qbo_app
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.integrations.adapters import (
    AdapterRefused,
    register_adapter,
    registered_adapter,
    registered_keys,
    unregister_adapter,
)
from abacus.modules.integrations.capabilities import (
    UndeclaredEgress,
    assert_egress_declared,
    egress_allowlist,
    egress_hosts_by_connector,
    egress_read_posts,
    policy_refusal,
    registry,
    undeclared_egress,
    write_capability,
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

# The routers the API mounts, in order (P-39; F-03-T07).
from abacus.modules.integrations.engine_settings_contract import (
    engine_settings_router,
)
from abacus.modules.integrations.ports import (
    IntegrationAdapter,
    IntegrationCategory,
    ReadConnectorEntry,
    WriteCapabilityEntry,
    WriteCapabilityRegistry,
)
from abacus.modules.integrations.qbo_adapter import register_if_configured

# A-02-T16: the live POR-16 routes are declared on C20's `portal_router` in `routes`, so it is
# imported from there (loading the module registers them before the API mounts the router).
from abacus.modules.integrations.routes import firm_router, portal_router
from abacus.modules.integrations.secrets import (
    connected_integration,
    docusign_install_secret,
    erase_secret,
    open_secret,
    store_secret,
)
from abacus.modules.integrations.writers import WritePreview, Writer, WriteReceipt, WriteRequest
from abacus.modules.integrations.writes import (
    WriteCapabilityRefused,
    authorise_write,
    execute_write,
)

ROUTERS: tuple[AbacusRouter, ...] = (
    engine_settings_router,  # ADM-08 tax-engine settings (T-01-T02 stub)
    portal_router,  # C20 v1: POR-16, live since A-02-T16
    firm_router,  # C20 v1: reconnect requests (live since A-02-T23); pulls a stub until T30
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
    "UndeclaredEgress",
    "WriteCapabilityEntry",
    "WriteCapabilityRefused",
    "WriteCapabilityRegistry",
    "WritePreview",
    "WriteReceipt",
    "WriteRequest",
    "Writer",
    "assert_egress_declared",
    "authorise_write",
    "catalog_rows",
    "client_catalog",
    "connected_integration",
    "docusign_install_secret",
    "egress_allowlist",
    "egress_hosts_by_connector",
    "egress_read_posts",
    "erase_secret",
    "execute_write",
    "is_available",
    "listed",
    "listing_of",
    "open_secret",
    "plan_load",
    "policy_refusal",
    "register_adapter",
    "registered_adapter",
    "registered_keys",
    "registry",
    "store_secret",
    "undeclared_egress",
    "unregister_adapter",
    "write_capability",
]

# A-02-T26 (DEC-709): the QuickBooks Online adapter, only where the app registration exists.
register_if_configured(qbo_app() is not None)

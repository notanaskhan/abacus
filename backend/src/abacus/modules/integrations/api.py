"""Public interface of the integrations module; other modules import only this (ADR-008).

C20 v1 (A-02-T06): the POR-16 contract stub and the framework's ports. A-02-T12: the
fail-closed adapter registry, the catalogue read with its honest listing, the catalogue load's
document and plan (the operator's command is `abacus_tools.integration_catalog`), and sealed
integration secrets. A-02-T15: the compiled write-capability registry, the egress allowlist
export, the `Writer` port and the write gate (`authorise_write`, `execute_write`), which refuses
every write in v1. A-02-T16: the POR-16 routes, composed in `client_connect`. W-01-T07 to T09
(C20 v2): the Connect catalogue, its v2 import, Connect and disconnect, and the fakes.
"""

from collections.abc import Mapping

from abacus.kernel.uow.relay import Handler
from abacus.kernel.work_class import WorkClass
from abacus.modules.connections.api import qbo_app
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.integrations.adapters import (
    AdapterRefused,
    register_adapter,
    registered_adapter,
    registered_keys,
    unregister_adapter,
)
from abacus.modules.integrations.availability import notify_available
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
from abacus.modules.integrations.catalog_import import (
    CatalogDocumentV2,
    ImportPlan,
    document_sha256,
    plan_import,
)
from abacus.modules.integrations.catalog_load import CatalogDocument, LoadPlan, plan_load
from abacus.modules.integrations.connect_contract import router as connect_router
from abacus.modules.integrations.connect_service import membership_ended
from abacus.modules.integrations.engine_profile import EngineFieldProfile, engine_field_profile

# The routers the API mounts, in order (P-39; F-03-T07).
from abacus.modules.integrations.engine_settings import (
    ExportSettings,
    FormatCheck,
    engine_return_id,
    export_settings,
    last_engine_sync,
    register_engine_file_check,
    register_last_engine_sync,
)
from abacus.modules.integrations.engine_settings_contract import (
    engine_settings_router,
)
from abacus.modules.integrations.esign_install import (
    EsignInstallExists,
    connect_esign_install,
    disconnect_esign_install,
    esign_install_state,
    rotate_esign_secret,
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
    ESIGN_CATALOG,
    connected_integration,
    erase_secret,
    esign_install_secret,
    esign_webhook_secret,
    open_secret,
    store_secret,
)
from abacus.modules.integrations.synthetic import (
    SyntheticInstallRefused,
    seed_synthetic_event,
    seed_synthetic_install,
)
from abacus.modules.integrations.w1_contract import w1_portal_router, w1_router
from abacus.modules.integrations.writers import WritePreview, Writer, WriteReceipt, WriteRequest

# C-02-T18 (ADR-344): the W1 writer's port and types, for adjustments/posting.py only (POST-001).
from abacus.modules.integrations.writers.quickbooks_online import (
    FakeQboTransport,
    JournalEntry,
    JournalLine,
    Posted,
    QboTransport,
    QuickBooksOnlineWriter,
    WriteError,
)
from abacus.modules.integrations.writes import (
    W1_CAPABILITY,
    W1Evidence,
    W1Ledger,
    W1Operation,
    W1Refusal,
    W1Refused,
    W1Scope,
    WriteCapabilityRefused,
    authorise_write,
    execute_write,
    register_w1_kill_switch,
    w1_ledger,
    w1_refusal,
)

ROUTERS: tuple[AbacusRouter, ...] = (
    engine_settings_router,  # ADM-08 tax-engine settings (T-01-T02 stub)
    portal_router,  # C20 v1: POR-16, live since A-02-T16
    firm_router,  # C20 v1: reconnect requests (live since A-02-T23); pulls a stub until T30
    connect_router,  # C20 v2: W-01-T03 Connect stub (WB-10, WB-11)
    w1_router,  # C20 v2.1: C-02-T06 W1 console, switches and settings stub (CLS-11, ADM-08b)
    w1_portal_router,  # C20 v2.1: C-02-T06 POR-16 write grant stub
)

__all__ = [
    "ESIGN_CATALOG",
    "ROUTERS",
    "W1_CAPABILITY",  # C-02-T18 (ADR-344): the W1 path and its switches
    "AdapterRefused",
    "CatalogDocument",
    "CatalogDocumentV2",
    "CatalogEntry",
    "CatalogRow",
    "EngineFieldProfile",
    "EsignInstallExists",
    "ExportSettings",
    "FakeQboTransport",
    "FormatCheck",
    "ImportPlan",
    "IntegrationAdapter",
    "IntegrationCategory",
    "IntegrationHealthWorkflow",  # imported below, for the S45-S48 replay recorder
    "JournalEntry",
    "JournalLine",
    "LoadPlan",
    "Posted",
    "QboTransport",
    "QuickBooksOnlineWriter",
    "ReadConnectorEntry",
    "SyntheticInstallRefused",
    "UndeclaredEgress",
    "W1Evidence",
    "W1Ledger",
    "W1Operation",
    "W1Refusal",
    "W1Refused",
    "W1Scope",
    "WriteCapabilityEntry",
    "WriteCapabilityRefused",
    "WriteCapabilityRegistry",
    "WriteError",
    "WritePreview",
    "WriteReceipt",
    "WriteRequest",
    "Writer",
    "assert_egress_declared",
    "authorise_write",
    "catalog_rows",
    "client_catalog",
    "connect_esign_install",
    "connected_integration",
    "disconnect_esign_install",
    "document_sha256",
    "egress_allowlist",
    "egress_hosts_by_connector",
    "egress_read_posts",
    "engine_field_profile",
    "engine_return_id",
    "erase_secret",
    "esign_install_secret",
    "esign_install_state",
    "esign_webhook_secret",
    "execute_write",
    "export_settings",
    "is_available",
    "last_engine_sync",
    "listed",
    "listing_of",
    "notify_available",
    "open_secret",
    "plan_import",
    "plan_load",
    "policy_refusal",
    "register_adapter",
    "register_engine_file_check",
    "register_last_engine_sync",
    "register_w1_kill_switch",
    "registered_adapter",
    "registered_keys",
    "registry",
    "rotate_esign_secret",
    "seed_synthetic_event",
    "seed_synthetic_install",
    "store_secret",
    "undeclared_egress",
    "unregister_adapter",
    "w1_ledger",
    "w1_refusal",
    "write_capability",
]

# A-02-T26 (DEC-709): the QuickBooks Online adapter, only where the app registration exists.
register_if_configured(qbo_app() is not None)

# W-01-T08 (AC-13): a deactivated person's personal installs are disconnected and their secrets
# deleted. The worker reads these three (no workflow or activity of the module's own yet).
SUBSCRIPTIONS: Mapping[str, Handler] = {"membership.deactivated": membership_ended}
from abacus.kernel.dispatch import register_work_classes  # noqa: E402

# W-01-T13 (DEC-5333): the health monitor's Schedule, its workflow and its activity.
from abacus.modules.integrations.health_workflow import (  # noqa: E402
    ACTIVITIES as _HEALTH_ACTIVITIES,
)
from abacus.modules.integrations.health_workflow import (  # noqa: E402
    SCHEDULES as SCHEDULES,
)
from abacus.modules.integrations.health_workflow import (  # noqa: E402
    WORKFLOWS as _HEALTH_WORKFLOWS,
)
from abacus.modules.integrations.health_workflow import (  # noqa: E402
    IntegrationHealthWorkflow,  # the S45-S48 replay recorder
)

WORKFLOWS: dict[type, WorkClass] = dict(_HEALTH_WORKFLOWS)  # type: ignore[arg-type] -- the work class literal
ACTIVITIES: tuple[object, ...] = (*_HEALTH_ACTIVITIES,)
register_work_classes(WORKFLOWS)  # ADR-071: the sweep's batch class

# W-01-T14 (DEC-5320, DEC-5334): run admission and the dependents slot the agents module fills.
from abacus.modules.integrations.dependents import admit as admit  # noqa: E402
from abacus.modules.integrations.dependents import (  # noqa: E402
    register_dependents_provider as register_dependents_provider,
)

# G-04-T10 (DEC-5417): the firm's install health for SHL-05's status.
from abacus.modules.integrations.firm_health import register as _register_firm_health  # noqa: E402

_register_firm_health()

# C-02-T02 (DEC-5501): the posting, W1 and delivery error codes, declared before their services.
from abacus.modules.integrations import write_errors as write_errors  # noqa: E402

# C-02-T12 (DEC-5621): the engagement posting switch, for adjustments' close approvals.
from abacus.modules.integrations.posting_settings import (  # noqa: E402
    posting_enabled_for as posting_enabled_for,
)

"""Public interface of the integrations module; other modules import only this (ADR-008).

C20 v1 (A-02-T06): the POR-16 contract stub and the framework's ports. The framework itself
(catalogue, firm integrations, sealed secrets, the fail-closed adapter registry) lands with
A-02-T12; the write-capability registry file and its compiler with A-02-T15.
"""

from abacus.modules.identity.api import AbacusRouter
from abacus.modules.integrations.contract import firm_router, portal_router
from abacus.modules.integrations.ports import (
    IntegrationAdapter,
    IntegrationCategory,
    ReadConnectorEntry,
    WriteCapabilityEntry,
    WriteCapabilityRegistry,
)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    portal_router,  # C20 v1 stub (A-02-T06): POR-16
    firm_router,  # C20 v1 stub (A-02-T06): reconnect requests and on-demand pulls
)

__all__ = [
    "ROUTERS",
    "IntegrationAdapter",
    "IntegrationCategory",
    "ReadConnectorEntry",
    "WriteCapabilityEntry",
    "WriteCapabilityRegistry",
]

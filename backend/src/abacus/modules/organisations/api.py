"""Public interface of the organisations module; other modules import only this (ADR-008)."""

from abacus.modules.organisations.service import (
    ClientChoice,
    ClientNames,
    EntityChoice,
    FirmName,
    NewClient,
    client_names,
    client_with_entity,
    create_client,
    find_clients,
    firm_names,
    normalise,
)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[()] = ()

__all__ = [
    "ROUTERS",
    "ClientChoice",
    "ClientNames",
    "EntityChoice",
    "FirmName",
    "NewClient",
    "client_names",
    "client_with_entity",
    "create_client",
    "find_clients",
    "firm_names",
    "normalise",
]

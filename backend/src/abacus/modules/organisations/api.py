"""Public interface of the organisations module; other modules import only this (ADR-008)."""

from abacus.modules.organisations.service import (
    ClientNames,
    NewClient,
    client_names,
    create_client,
)

__all__ = ["ClientNames", "NewClient", "client_names", "create_client"]

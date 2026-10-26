"""The fail-closed adapter registry (A-02-T12; C20 v1; ADR-136, ADR-040; SPEC-333 AC-49).

An adapter is listed only once it is registered here, in this process, for this environment.
Registration refuses anything that is not a read-only `IntegrationAdapter`: a key outside the
key grammar, a category the catalogue does not know, an egress host or read scope outside the
write-capability registry's grammar, no read scope, a second adapter under the same key or for
the same connection provider, and any public method whose name is write-shaped (connectors only
read; CONN-001 asks the same of `connections.Connector`). Lookups of anything unregistered answer
None: there is no default adapter and no fallback.
"""

from __future__ import annotations

import re
from typing import Final, get_args

from pydantic import ValidationError

from abacus.modules.integrations.ports import (
    IntegrationAdapter,
    IntegrationCategory,
    ReadConnectorEntry,
)

KEY: Final = re.compile(r"^[a-z][a-z0-9_]{1,49}$")
# A public attribute with one of these words as a name part is a write (ADR-040).
_WRITE_WORDS: Final = frozenset(
    {"write", "post", "put", "patch", "delete", "create", "update", "insert", "upsert"}
    | {"send", "push", "upload", "submit", "remove", "void", "pay", "transfer", "sync_to"}
)
_ADAPTERS: dict[str, IntegrationAdapter] = {}


class AdapterRefused(ValueError):
    """An adapter that may not be registered; the message names the rule, never a secret."""


def _write_shaped(adapter: object) -> list[str]:
    found: list[str] = []
    for name in dir(adapter):
        if name.startswith("_"):
            continue
        parts = set(name.lower().split("_"))
        if parts & _WRITE_WORDS or name.lower() in _WRITE_WORDS:
            found.append(name)
    return found


def register_adapter(adapter: object) -> None:
    """Register a read-only adapter; refuses (`AdapterRefused`) anything else."""
    if not isinstance(adapter, IntegrationAdapter):
        raise AdapterRefused("not an IntegrationAdapter")
    key = adapter.key
    if not KEY.fullmatch(key):
        raise AdapterRefused("key outside the grammar")
    if adapter.category not in get_args(IntegrationCategory):
        raise AdapterRefused("unknown category")
    try:
        ReadConnectorEntry(
            adapter_key=key,
            category=adapter.category,
            egress_hosts=list(adapter.egress_hosts()),
            read_scopes=list(adapter.read_scopes()),
        )
    except ValidationError as exc:
        raise AdapterRefused("egress hosts or read scopes outside the grammar") from exc
    writes = _write_shaped(adapter)
    if writes:
        raise AdapterRefused(f"write-shaped method: {', '.join(sorted(writes))}")
    if key in _ADAPTERS:
        raise AdapterRefused("an adapter is registered once")
    provider = adapter.connector_provider
    if provider is not None:
        if not KEY.fullmatch(provider):
            raise AdapterRefused("connector provider outside the grammar")
        if any(a.connector_provider == provider for a in _ADAPTERS.values()):
            raise AdapterRefused("a connection provider has one adapter")
    _ADAPTERS[key] = adapter


def unregister_adapter(key: str) -> None:
    """Take an adapter out (a kill switch, a test). Unknown keys are ignored."""
    _ADAPTERS.pop(key, None)


def registered_adapter(key: str | None) -> IntegrationAdapter | None:
    """The adapter under `key`, or None: never a default (fail-closed)."""
    if key is None:
        return None
    return _ADAPTERS.get(key)


def registered_keys() -> frozenset[str]:
    return frozenset(_ADAPTERS)

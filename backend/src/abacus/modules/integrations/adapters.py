"""The fail-closed adapter registry (A-02-T12; C20 v1; ADR-136, ADR-040; SPEC-333 AC-49).

An adapter is listed only once it is registered here, in this process, for this environment.
Registration refuses anything that is not a read-only `IntegrationAdapter`: a key outside the
key grammar, a category the catalogue does not know, an egress host or read scope outside the
write-capability registry's grammar, no read scope, a second adapter under the same key or for
the same connection provider. Lookups of anything unregistered answer None: there is no default
adapter and no fallback.

**Allowlist, not a blocklist** (connectors only read, ADR-040; security review M1, DEC-438): an
adapter's public attributes may be only the port's members (`key`, `category`,
`connector_provider`, `read_scopes`, `egress_hosts`), `read_methods`, and the read methods it
declares there. A declared read method is callable and named `read_…`, `get_…`, `list_…` or
`fetch_…`. Anything else public (another method such as `apply_payment` or `commit`, or a public
attribute such as an HTTP `client` whose `.post` a caller could reach) is refused at
registration; an adapter keeps its machinery private (`_client`).
"""

from __future__ import annotations

import re
from typing import Final, cast, get_args

from pydantic import ValidationError

from abacus.modules.integrations.ports import (
    IntegrationAdapter,
    IntegrationCategory,
    ReadConnectorEntry,
)

KEY: Final = re.compile(r"^[a-z][a-z0-9_]{1,49}$")
# The port's members, and the attribute that names an adapter's own read methods.
PORT_MEMBERS: Final = frozenset(
    {"key", "category", "connector_provider", "read_scopes", "egress_hosts"}
)
DECLARES: Final = "read_methods"
READ_METHOD: Final = re.compile(r"^(read|get|list|fetch)_[a-z0-9_]{1,60}$")
_ADAPTERS: dict[str, IntegrationAdapter] = {}


class AdapterRefused(ValueError):
    """An adapter that may not be registered; the message names the rule, never a secret."""


def _declared(adapter: object) -> frozenset[str]:
    """The read methods the adapter declares, each callable and read-named; refuses others."""
    raw: object = getattr(adapter, DECLARES, ())
    if not isinstance(raw, tuple | list | frozenset):
        raise AdapterRefused("read_methods is a tuple of method names")
    names = tuple(cast(tuple[object, ...], raw))
    for name in names:
        if not isinstance(name, str) or not READ_METHOD.fullmatch(name):
            raise AdapterRefused("a declared read method is named read_, get_, list_ or fetch_")
        if name in PORT_MEMBERS or not callable(getattr(adapter, name, None)):
            raise AdapterRefused("a declared read method is a method of the adapter")
    return frozenset(cast(tuple[str, ...], names))


def _undeclared(adapter: object) -> list[str]:
    """Every public attribute outside the allowlist (the port, `read_methods`, declared reads)."""
    allowed = PORT_MEMBERS | {DECLARES} | _declared(adapter)
    return sorted(
        name for name in dir(adapter) if not name.startswith("_") and name not in allowed
    )


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
    extra = _undeclared(adapter)
    if extra:
        raise AdapterRefused(f"public attributes outside the read allowlist: {', '.join(extra)}")
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

"""The fail-closed Connect port registry (W-01-T08, T09; SPEC-659 AC-10 to AC-16, AC-24).

A port is how one integration is connected (its OAuth consent URL and code exchange, PKCE S256),
health-checked and revoked. It is never a read adapter: reads stay on `IntegrationAdapter`
behind its own allowlist (ADR-040). A port is listed here only once registered in this process;
`port_for` answers a registered one, or, for a synthetic firm where fakes are allowed (never
production, W-01-T09), the scripted fake for the key; otherwise None (no default, no fallback).

**Allowlist:** a port's public attributes are the port's members only (`key`, `mode`,
`egress_hosts`, `authorise_url`, `exchange_code`, `check_health`, `revoke`); anything else public
is refused at registration, as for read adapters.
"""

from __future__ import annotations

import re
from typing import Final

from abacus.modules.integrations.fakes import fake_port, fakes_allowed
from abacus.modules.integrations.ports import ConnectMode, ConnectPort

KEY: Final = re.compile(r"^[a-z][a-z0-9_]{1,49}$")
HOST: Final = re.compile(r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
MEMBERS: Final = frozenset(
    {"key", "mode", "egress_hosts", "authorise_url", "exchange_code", "check_health", "revoke"}
)
_PORTS: dict[str, ConnectPort] = {}


class PortRefused(ValueError):
    """A port that may not be registered; the message names the rule, never a secret."""


def _extra(port: object) -> list[str]:
    return sorted(n for n in dir(port) if not n.startswith("_") and n not in MEMBERS)


def check_port(port: object) -> ConnectPort:
    """The port's rules, as registration applies them (the conformance suite runs every port,
    fakes included, through this)."""
    if not isinstance(port, ConnectPort):
        raise PortRefused("not a ConnectPort")
    if not KEY.fullmatch(port.key):
        raise PortRefused("key outside the grammar")
    hosts = port.egress_hosts()
    if not hosts or any(not HOST.fullmatch(h) for h in hosts):
        raise PortRefused("egress hosts outside the grammar")
    extra = _extra(port)
    if extra:
        raise PortRefused(f"public attributes outside the port: {', '.join(extra)}")
    return port


def register_port(port: object) -> None:
    checked = check_port(port)
    if checked.key in _PORTS:
        raise PortRefused("a port is registered once")
    _PORTS[checked.key] = checked


def unregister_port(key: str) -> None:
    _PORTS.pop(key, None)


def port_for(key: str, mode: ConnectMode, *, synthetic: bool) -> ConnectPort | None:
    """The port a firm connects `key` through, or None (fail-closed)."""
    found = _PORTS.get(key)
    if found is not None:
        return found if found.mode == mode else None
    if synthetic and fakes_allowed():
        return fake_port(key, mode)
    return None

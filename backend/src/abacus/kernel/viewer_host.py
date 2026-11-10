"""The viewer's host: the host the person's browser asked for, behind the edge or not (TASK-6990;
DEC-3990; ADR-163 §5 and its amendment).

Behind CloudFront the request's `Host` is the origin's own name (the internal load balancer):
both distributions use `Managed-AllViewerExceptHostHeader`, and their viewer-request functions
pass the viewer's `Host` as `X-Forwarded-Host`, replacing any value the viewer sent. So:

- from a peer in `proxy_trusted_hosts` (the load balancer; the same peers uvicorn believes
  `X-Forwarded-For` from), `X-Forwarded-Host` is the viewer host when present, and `Host` when
  absent (the load balancer's own probes);
- from any other peer `X-Forwarded-Host` is ignored and `Host` is the viewer host.

Several forwarded values, a comma chain, an empty one, or a missing or repeated `Host` are no host
at all (`None`): never a guess. The value is lower case, without its port or a trailing dot; a
single empty `Host` stays `""` (served only where every host is, and neutral everywhere).

`api.middleware.TrustedHosts` resolves it once from the real peer (it runs outside uvicorn's
proxy middleware, which rewrites the peer), refuses an untrusted one, and keeps it on the scope;
every host-dependent route reads it through `ViewerHost`. It is a branding hint and a session pin,
never a tenant: tenant resolution comes from membership or grant (ADR-002, INV-4).
"""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable
from typing import Annotated, Final

from fastapi import Depends, Request

SCOPE_KEY: Final = "abacus.viewer_host"

_HOST: Final = b"host"
_FORWARDED_HOST: Final = b"x-forwarded-host"


def host_name(value: str) -> str:
    """The host without its port, lower case and without a trailing dot ("" for none)."""
    host = value.strip().lower()
    if host.startswith("["):  # [::1]:8000
        end = host.find("]")
        return host[1:end] if end > 0 else ""
    if host.count(":") == 1:
        host = host.split(":", 1)[0]
    return host.rstrip(".")


class ProxyPeers:
    """uvicorn's rule for `proxy_trusted_hosts`: `*` trusts every peer; otherwise IP addresses and
    CIDR networks, and any other entry is compared as a literal (a unix socket name)."""

    def __init__(self, entries: Iterable[str]) -> None:
        self._any = False
        self._literals: set[str] = set()
        self._networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        for raw in entries:
            entry = raw.strip()
            if entry == "*":
                self._any = True
                continue
            try:
                self._networks.append(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                self._literals.add(entry)

    def trusts(self, peer: str | None) -> bool:
        if self._any:
            return True
        if not peer:
            return False
        if peer in self._literals:
            return True
        try:
            address = ipaddress.ip_address(peer)
        except ValueError:
            return False
        return any(
            address in network for network in self._networks if address.version == network.version
        )


def resolve_viewer_host(
    headers: Iterable[tuple[bytes, bytes]], peer: str | None, proxies: ProxyPeers
) -> str | None:
    """The viewer host of a request with these raw `headers` from TCP peer `peer`."""
    hosts: list[bytes] = []
    forwarded: list[bytes] = []
    for name, value in headers:
        if name == _HOST:
            hosts.append(value)
        elif name == _FORWARDED_HOST:
            forwarded.append(value)
    if forwarded and proxies.trusts(peer):
        if len(forwarded) != 1 or b"," in forwarded[0]:
            return None
        return host_name(forwarded[0].decode("latin-1")) or None
    if len(hosts) != 1:
        return None
    return host_name(hosts[0].decode("latin-1"))


def viewer_host(request: Request) -> str | None:
    """The viewer host `TrustedHosts` resolved for this request. An app without that middleware
    (a bare router in a test) falls back to the request's own `Host`, never a forwarded one."""
    if SCOPE_KEY in request.scope:
        found: object = request.scope[SCOPE_KEY]
        return found if isinstance(found, str) else None
    return host_name(request.headers.get("host", "")) or None


ViewerHost = Annotated[str | None, Depends(viewer_host)]

__all__ = [
    "SCOPE_KEY",
    "ProxyPeers",
    "ViewerHost",
    "host_name",
    "resolve_viewer_host",
    "viewer_host",
]

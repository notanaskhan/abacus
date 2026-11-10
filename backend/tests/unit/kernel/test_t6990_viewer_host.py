"""TASK-6990 (DEC-3990; ADR-163 amendment): the viewer's host, the one host-dependent value the
API reads. Behind CloudFront the request's `Host` is the origin's own name and the viewer's host
arrives only as `X-Forwarded-Host`; that header is believed only from a peer in
`proxy_trusted_hosts` (the load balancer), the same peers uvicorn believes `X-Forwarded-For` from.
From anyone else it is ignored and the request's own `Host` is the viewer host. Either way the
value is lower case, without its port or a trailing dot. A branding hint and a pin, never a
tenant (INV-4)."""

from __future__ import annotations

import pytest

from abacus.kernel.viewer_host import ProxyPeers, host_name, resolve_viewer_host

ALB = "10.0.0.5"
STRANGER = "198.51.100.7"
PROXIES = ProxyPeers([ALB])


def headers(**values: str | list[str]) -> list[tuple[bytes, bytes]]:
    out: list[tuple[bytes, bytes]] = []
    for name, value in values.items():
        for one in value if isinstance(value, list) else [value]:
            out.append((name.replace("_", "-").encode(), one.encode("latin-1")))
    return out


def test_a_spoofed_forwarded_host_from_an_untrusted_peer_is_ignored() -> None:
    sent = headers(host="acme.portal.example.test", x_forwarded_host="other.portal.example.test")
    assert resolve_viewer_host(sent, STRANGER, PROXIES) == "acme.portal.example.test"


def test_without_a_proxy_list_no_peer_is_trusted() -> None:
    sent = headers(host="acme.portal.example.test", x_forwarded_host="other.portal.example.test")
    assert resolve_viewer_host(sent, ALB, ProxyPeers([])) == "acme.portal.example.test"


def test_a_trusted_peers_forwarded_host_is_the_viewer_host() -> None:
    sent = headers(
        host="internal-alb.example.internal", x_forwarded_host="acme.portal.example.test"
    )
    assert resolve_viewer_host(sent, ALB, PROXIES) == "acme.portal.example.test"


def test_a_trusted_peer_without_a_forwarded_host_falls_back_to_host() -> None:
    assert resolve_viewer_host(headers(host="10.0.1.7:8000"), ALB, PROXIES) == "10.0.1.7"


@pytest.mark.parametrize(
    ("forwarded", "expected"),
    [
        ("ACME.Portal.Example.Test", "acme.portal.example.test"),
        ("acme.portal.example.test:443", "acme.portal.example.test"),
        ("acme.portal.example.test.", "acme.portal.example.test"),
        ("  acme.portal.example.test  ", "acme.portal.example.test"),
        ("[2001:db8::1]:443", "2001:db8::1"),
    ],
)
def test_the_viewer_host_is_normalised(forwarded: str, expected: str) -> None:
    sent = headers(host="internal-alb.example.internal", x_forwarded_host=forwarded)
    assert resolve_viewer_host(sent, ALB, PROXIES) == expected


@pytest.mark.parametrize(
    "forwarded",
    [
        ["acme.portal.example.test", "other.portal.example.test"],  # two headers
        "acme.portal.example.test, other.portal.example.test",  # a chain
        "",
    ],
)
def test_an_ambiguous_forwarded_host_from_a_trusted_peer_is_no_host(
    forwarded: str | list[str],
) -> None:
    """Fail closed: never pick one of several values, and never fall back to `Host` (the origin's
    own name) when the edge said something it should not have."""
    sent = headers(host="internal-alb.example.internal", x_forwarded_host=forwarded)
    assert resolve_viewer_host(sent, ALB, PROXIES) is None


def test_a_missing_or_repeated_host_is_no_host() -> None:
    assert resolve_viewer_host([], STRANGER, PROXIES) is None
    sent = headers(host=["a.example.test", "b.example.test"])
    assert resolve_viewer_host(sent, STRANGER, PROXIES) is None


@pytest.mark.parametrize(
    ("entries", "peer", "trusted"),
    [
        (["10.0.0.5"], "10.0.0.5", True),
        (["10.0.0.5"], "10.0.0.6", False),
        (["10.0.0.0/24"], "10.0.0.200", True),
        (["10.0.0.0/24"], "10.0.1.1", False),
        (["2001:db8::/32"], "2001:db8::7", True),
        (["*"], STRANGER, True),
        (["unix:/run/abacus.sock"], "unix:/run/abacus.sock", True),
        (["10.0.0.5"], None, False),
        (["10.0.0.0/24"], "not-an-address", False),
        ([], "10.0.0.5", False),
    ],
)
def test_proxy_peers_follow_uvicorns_trust_rule(
    entries: list[str], peer: str | None, trusted: bool
) -> None:
    assert ProxyPeers(entries).trusts(peer) is trusted


def test_host_name_keeps_only_the_name() -> None:
    assert host_name("Acme.Example.Test:8443") == "acme.example.test"
    assert host_name("[::1]:8000") == "::1"
    assert host_name("[::1") == ""


def test_an_empty_host_stays_an_empty_host() -> None:
    """As before this change: `*` serves it (neutral branding); an explicit list refuses it."""
    assert resolve_viewer_host(headers(host=""), STRANGER, PROXIES) == ""

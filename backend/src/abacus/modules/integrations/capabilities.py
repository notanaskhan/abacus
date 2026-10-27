"""The compiled write-capability registry, read (A-02-T15; ADR-150, P-17, DEC-46; ADR-040;
SPEC-333 AC-50; C20 v1).

`_capabilities.py` is generated from the protected `docs/architecture/write-capabilities.yaml`
(`abacus_tools.codegen.write_capabilities`; a hand edit fails `make check-generated`). It is
validated again here, on first use, against the schema: a generated file edited to enable a
write does not load, and the API's start-up reads it first (`assert_egress_declared`), so the
process does not start (fail closed). Importing this module does not read it, so the compiler
can always regenerate it.

- `egress_allowlist()`: every host a declared read connector may reach (Q-01's DNS Firewall
  allowlist; the CLI's `--egress` prints the same set).
- `undeclared_egress()`: for each registered adapter, the hosts it says it reaches that the
  registry does not declare for it; and each connection provider (`connections.CONNECTORS`)
  that reaches a host but is no declared read connector (review M3). The API and the worker
  refuse to start while any exists, and configure `kernel.egress` (the connectors' only HTTP
  client) with the declared hosts.
- `policy_refusal(entry, attest_client=…)`: the registry-level policy. A W1-shaped capability
  (posting into a client's ledger) is refused for an attest client whatever the file says
  (I-POLICY-NOT-ATTEST, ch. 10 §10.10); anything not enabled is refused, and v1 enables nothing.
"""

from __future__ import annotations

from functools import cache
from typing import Final, Literal

from abacus.modules.connections.api import CONNECTORS, is_networkless
from abacus.modules.integrations import _capabilities as compiled
from abacus.modules.integrations.adapters import registered_adapter, registered_keys
from abacus.modules.integrations.ports import WriteCapabilityEntry, WriteCapabilityRegistry

RefusalReason = Literal[
    "unknown_capability",
    "attest_client",
    "not_enabled",
    "not_permitted",
    "unknown_client",
    "error",
]
# Audited as an index (references carry no text): keep the order, append only.
REASONS: Final[tuple[RefusalReason, ...]] = (
    "unknown_capability",
    "attest_client",
    "not_enabled",
    "not_permitted",
    "unknown_client",
    "error",  # review L4: working out the reason failed; refused all the same
)
ATTEST_REFUSED_SHAPES: Final = frozenset({"W1"})


@cache
def registry() -> WriteCapabilityRegistry:
    """The compiled registry, validated once against the schema."""
    return WriteCapabilityRegistry.model_validate(
        {
            "version": compiled.VERSION,
            "read_connectors": list(compiled.READ_CONNECTORS),
            "writes": list(compiled.WRITES),
        }
    )


def egress_allowlist() -> frozenset[str]:
    """Q-01's export: the hosts any declared read connector may reach."""
    return registry().egress_hosts()


def egress_read_posts() -> frozenset[tuple[str, str]]:
    """The provider POSTs declared as reads (token exchange, refresh, revoke)."""
    return registry().read_posts()


def declared_hosts(adapter_key: str) -> frozenset[str]:
    return frozenset(
        h
        for r in registry().read_connectors
        if r.adapter_key == adapter_key
        for h in r.egress_hosts
    )


def undeclared_egress() -> dict[str, tuple[str, ...]]:
    """Registered adapters reaching a host the registry does not declare for them."""
    out: dict[str, tuple[str, ...]] = {}
    for key in sorted(registered_keys()):
        adapter = registered_adapter(key)
        if adapter is None:
            continue
        extra = tuple(sorted(set(adapter.egress_hosts()) - declared_hosts(key)))
        if extra:
            out[key] = extra
    declared = {r.adapter_key for r in registry().read_connectors}
    for provider in sorted(p for p in set(CONNECTORS) - declared if not is_networkless(p)):
        out[f"connector:{provider}"] = ("(no read_connectors entry)",)
    return out


class UndeclaredEgress(RuntimeError):
    """An adapter would reach a host the registry does not declare (names keys and hosts only)."""


def assert_egress_declared() -> None:
    """Called at start-up: refuse to serve while an adapter's host is undeclared."""
    registry()  # a generated file that does not validate stops start-up here
    found = undeclared_egress()
    if found:
        listed = "; ".join(f"{k}: {', '.join(v)}" for k, v in found.items())
        raise UndeclaredEgress(f"egress hosts not in write-capabilities.yaml: {listed}")


def write_capability(key: str) -> WriteCapabilityEntry | None:
    return next((w for w in registry().writes if w.key == key), None)


def policy_refusal(entry: WriteCapabilityEntry, *, attest_client: bool) -> RefusalReason | None:
    """Why the registry refuses this capability for this client, or None (never in v1)."""
    if attest_client and entry.shape in ATTEST_REFUSED_SHAPES:
        return "attest_client"
    if not entry.enabled:
        return "not_enabled"
    return None

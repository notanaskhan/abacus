"""The integrations framework's ports (A-02-T06; C20 v1; ADR-136, ADR-040). Contract:
`docs/contracts/c20-integrations.md` §3.

- `IntegrationAdapter`: what an adapter declares so the catalogue can list it honestly (a row
  whose adapter is not registered is never "available", AC-49) and the egress allowlist can be
  built. It has no write method: connectors only read (ADR-040, CONN-001). A-02-T12 adds the
  fail-closed adapter registry over this port.
- `WriteCapabilityRegistry`: the schema of the protected
  `docs/architecture/write-capabilities.yaml` (A-02-T15 writes the file, its compiler and drift
  test). v1 lists the read connectors with their
  egress hosts and reserves the write section: an entry can be declared but never enabled
  (`enabled` is `false` by type), so an empty registry and a registry of reservations both
  validate and nothing can be switched on by editing the file.
"""

from __future__ import annotations

from typing import Annotated, Literal, Protocol, Self, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus.kernel.classification import classified

IntegrationCategory = Literal[
    "ledger", "bank_feed", "card_feed", "sales", "payroll", "hr", "ticketing", "grc"
]
# The catalogue's categories: the read connectors' and the e-signature provider's (ADR-342,
# migration 0407). Never a read adapter's category, so never a portal card.
CatalogCategory = IntegrationCategory | Literal["esignature"]
# A catalogue key or adapter key: `quickbooks_online`, `front_range_bank`, `bamboohr`.
Key = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,49}$")]
Host = Annotated[
    str,
    Field(
        pattern=r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
        min_length=4,
        max_length=253,
    ),
]
ScopeCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{1,59}$")]


@runtime_checkable
class IntegrationAdapter(Protocol):
    """A registered adapter: read-only by construction (no write method on the port)."""

    @property
    def key(self) -> str: ...

    @property
    def category(self) -> IntegrationCategory: ...

    @property
    def connector_provider(self) -> str | None:
        """The `connections.provider` code it serves, for client-authorised connections."""
        ...

    def read_scopes(self) -> tuple[str, ...]: ...

    def egress_hosts(self) -> tuple[str, ...]: ...


class ReadPost(BaseModel):
    """A provider POST that is a read of the platform's own grant (A-02-T26): the OAuth token
    exchange or refresh, and the revoke. Never a path of the client's books (ADR-040, ED-156)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    host: Annotated[Host, classified("internal")]
    path: Annotated[str, Field(pattern=r"^/[a-z0-9/_.-]{1,120}$"), classified("internal")]


class ReadConnectorEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    adapter_key: Annotated[Key, classified("internal")]
    category: Annotated[IntegrationCategory, classified("internal")]
    egress_hosts: Annotated[list[Host], Field(min_length=1), classified("internal")]
    read_scopes: Annotated[list[ScopeCode], Field(min_length=1), classified("internal")]
    read_posts: Annotated[list[ReadPost], classified("internal")] = []

    @model_validator(mode="after")
    def _posts_on_declared_hosts(self) -> ReadConnectorEntry:
        stray = {p.host for p in self.read_posts} - set(self.egress_hosts)
        if stray:
            raise ValueError(f"read_posts outside egress_hosts: {sorted(stray)}")
        return self


class WriteCapabilityEntry(BaseModel):
    """A reserved write (W1 posting under ADR-161, W2 the CCH file bridge, W7 DocuSeal …).
    Reserved only: `enabled` is false by type until a later version of this schema."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: Annotated[Key, classified("internal")]
    adapter_key: Annotated[Key, classified("internal")]
    shape: Annotated[str, Field(pattern=r"^W[1-9]$"), classified("internal")]
    owner_epic: Annotated[str, Field(pattern=r"^[A-Z]-[0-9]{2}$"), classified("internal")]
    # The decision that would enable it (a plan P-nn or a repo ADR). The schema allows none so a
    # bare reservation validates; the protected file's compiler requires one (A-02-T15).
    decision: Annotated[
        str | None, Field(pattern=r"^(P-[0-9]{2}|ADR-[0-9]{3})$"), classified("internal")
    ] = None
    enabled: Annotated[Literal[False], classified("internal")] = False


class WriteCapabilityRegistry(BaseModel):
    """`docs/architecture/write-capabilities.yaml`, version 1."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Annotated[Literal[1], classified("public")]
    read_connectors: Annotated[list[ReadConnectorEntry], classified("internal")] = []
    writes: Annotated[list[WriteCapabilityEntry], classified("internal")] = []

    @model_validator(mode="after")
    def _unique(self) -> Self:
        adapters = [r.adapter_key for r in self.read_connectors]
        if len(set(adapters)) != len(adapters):
            raise ValueError("a read connector is declared once")
        writes = [w.key for w in self.writes]
        if len(set(writes)) != len(writes):
            raise ValueError("a write capability is declared once")
        return self

    def egress_hosts(self) -> frozenset[str]:
        """Every host a declared read connector may reach (Q-01's egress allowlist)."""
        return frozenset(h for r in self.read_connectors for h in r.egress_hosts)

    def read_posts(self) -> frozenset[tuple[str, str]]:
        """Every provider POST declared as a read, as (host, path) (`kernel.egress`)."""
        return frozenset((p.host, p.path) for r in self.read_connectors for p in r.read_posts)

"""The integrations framework's ports (A-02-T06; C20 v1; ADR-136, ADR-040). Contract:
`docs/contracts/c20-integrations.md` §3.

- `IntegrationAdapter`: what an adapter declares so the catalogue can list it honestly (a row
  whose adapter is not registered is never "available", AC-49) and the egress allowlist can be
  built. It has no write method: connectors only read (ADR-040, CONN-001). A-02-T12 adds the
  fail-closed adapter registry over this port.
- `WriteCapabilityRegistry`: the schema of the protected
  `docs/architecture/write-capabilities.yaml` (A-02-T15 writes the file, its compiler and drift
  test). It lists the read connectors with their egress hosts and the writes. Version 2 (ADR-150
  accepted 2026-10-30, DEC-1280) lets an entry be enabled only when its shape is one whose own
  approved path is built (`OPENABLE_SHAPES`: W7, the e-signature send, behind N-02-T20's
  consumed approval grant); a write into a client's system (W1 posting, W2 the tax-engine file)
  cannot be enabled by editing the file. The compiler also requires the enabling decision to be
  an accepted ADR.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Final, Literal, Protocol, Self, runtime_checkable

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


# The shapes a version 2 registry may enable: writes to the platform's own provider account
# whose approved path is built (W7: the human's send consumes its grant before EnvelopeWorkflow
# starts, N-02-T20). Never a write into a client's system (W1, W2): that needs the gate's dry
# run and evidence path, which no version has yet.
OPENABLE_SHAPES: Final = frozenset({"W7"})


# ADR-344 (P-16): W1 writes journal entries and the closing date, nothing else; it never edits or
# deletes an existing transaction, writes an attachment or changes the chart of accounts.
W1Operation = Literal["create_journal_entry", "set_closing_date"]
W1Preflight = Literal[
    "balanced", "open_period", "mapped_accounts", "active_accounts", "closing_date_unlocked"
]
W1_PREFLIGHT: Final = (
    "balanced",
    "open_period",
    "mapped_accounts",
    "active_accounts",
    "closing_date_unlocked",
)


class WriteCapabilityEntry(BaseModel):
    """A declared write (W1 posting under ADR-161, W2 the CCH file bridge, W7 DocuSeal …).
    Enabled only for a shape in `OPENABLE_SHAPES` whose decision is an ADR (the compiler checks
    that ADR is accepted)."""

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
    enabled: Annotated[bool, classified("internal")] = False
    # C-02-T02 (ADR-344, DEC-5501): the W1 policy, declared on the entry and checked here so the
    # protected file cannot widen it. Only W1 carries these; every field is required for W1.
    operations: Annotated[list[W1Operation] | None, classified("internal")] = None
    attest_clients: Annotated[Literal["refused"] | None, classified("internal")] = None
    policy_principal: Annotated[Literal["never"] | None, classified("internal")] = None
    preflight: Annotated[list[W1Preflight] | None, classified("internal")] = None
    verify_after: Annotated[Literal["read_back"] | None, classified("internal")] = None
    reversal: Annotated[Literal["new_write"] | None, classified("internal")] = None
    kill_switch: Annotated[
        str | None, Field(pattern=r"^write\.[a-z_]+\.[a-z_]+$"), classified("internal")
    ] = None

    @model_validator(mode="after")
    def _w1_policy(self) -> Self:
        policy = (
            self.operations,
            self.attest_clients,
            self.policy_principal,
            self.preflight,
            self.verify_after,
            self.reversal,
            self.kill_switch,
        )
        if self.shape == "W1":
            if any(p is None for p in policy) or not self.operations:
                raise ValueError("a W1 write declares its whole policy (ADR-344)")
            if len(set(self.operations or [])) != len(self.operations or []):
                raise ValueError("a W1 operation is declared once")
            if set(self.preflight or []) != set(W1_PREFLIGHT):
                raise ValueError("a W1 write runs every preflight check (ADR-344)")
        elif any(p is not None for p in policy):
            raise ValueError("only a W1 write carries the posting policy")
        return self

    @model_validator(mode="after")
    def _openable(self) -> Self:
        if self.enabled and self.shape not in OPENABLE_SHAPES:
            raise ValueError(f"a {self.shape} write cannot be enabled")
        if self.enabled and not (self.decision or "").startswith("ADR-"):
            raise ValueError("an enabled write names the accepted ADR that enables it")
        return self


class WriteCapabilityRegistry(BaseModel):
    """`docs/architecture/write-capabilities.yaml`, version 2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Annotated[Literal[2], classified("public")]
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


# --- W-01-T09: the Connect port (OAuth, health, revoke) ------------------------------------------
# Kept apart from the read port above: connecting is not a read, so an `IntegrationAdapter`
# never grows these methods and the read allowlist (ADR-040) stays as it is.

ConnectMode = Literal["token", "personal", "firm_app", "file_bridge"]
# OQ-7: a transient failure counts toward Needs attention (three in a row); the others mean the
# grant is gone and the install reads Needs reauth at once.
HealthOutcome = Literal["ok", "transient", "unauthorised", "invalid_grant", "token_expired"]
HEALTH_OUTCOMES: Final[tuple[HealthOutcome, ...]] = (
    "ok",
    "transient",
    "unauthorised",
    "invalid_grant",
    "token_expired",
)


class ConnectRefused(Exception):
    """The provider declined the grant (the person cancelled, or a scope was refused)."""


@dataclass(frozen=True)
class TokenGrant:
    """What an exchange returns: the secret to seal (Restricted, never logged), when it renews,
    and the scopes granted."""

    secret: bytes
    renews_at: datetime | None
    scopes: tuple[str, ...]


@runtime_checkable
class ConnectPort(Protocol):
    """How one integration is connected, checked and revoked (W-01-T08, T09)."""

    @property
    def key(self) -> str: ...

    @property
    def mode(self) -> ConnectMode: ...

    def egress_hosts(self) -> tuple[str, ...]: ...

    def authorise_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        """The provider's consent page; PKCE S256 with `code_challenge`."""
        ...

    async def exchange_code(
        self, *, code: str, code_verifier: str, redirect_uri: str
    ) -> TokenGrant: ...

    async def check_health(self, secret: bytes | None) -> HealthOutcome: ...

    async def revoke(self, secret: bytes) -> bool:
        """Best effort: True when the provider confirmed (AC-24)."""
        ...

"""The connector contract (ADR-037, ADR-040). PROTECTED. TASK-010 design §2.

Every connector implements this one interface and passes the conformance suite
(`tests/unit/connections/conformance.py`). Connectors only read: the contract has no write
operations and CONN-001 forbids adding any. `pull` returns the provider's bytes exactly as
sent; the pipeline stores them unaltered before anything interprets them (ADR-038).

A-02-T16 security review: the read-only grant's handshake has PKCE (RFC 7636, S256:
`authorise_url` takes the challenge, `exchange_code` the verifier) and an end: `revoke` asks the
provider to revoke the grant the connection holds, after a disconnect or a replaced grant. It
changes nothing in the client's books; it withdraws the platform's own access.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar, Literal

# C-01-T16 (C9 v2.1; migration 0882's `sync_runs.dataset`): the chart of accounts, a month's trial
# balance and the general-ledger detail join the year's trial balance. Additive only.
Dataset = Literal["trial_balance", "accounts", "gl_detail", "trial_balance_month"]
# A provider's credentials as the connector serialises them: opaque to everything else, sealed
# with the tenant's key at rest (ADR-035; SPEC-020 TASK-036 D2).
Credentials = bytes


_CODE = re.compile(r"[a-z][a-z_]{0,49}")


class ConnectorError(Exception):
    """A pull failed; `code` is a short machine-readable reason, recorded on the sync run. Never
    provider text: anything that isn't a safe code becomes `provider_error`."""

    retryable: ClassVar[bool] = False

    def __init__(self, code: str) -> None:
        safe = code if _CODE.fullmatch(code) else "provider_error"
        super().__init__(safe)
        self.code = safe


class Unavailable(ConnectorError):
    """Temporary: the provider timed out or is down. Retrying may succeed."""

    retryable: ClassVar[bool] = True


class RateLimited(Unavailable):
    """C-01-T16 (ADR-043): the provider throttled the call (HTTP 429) or the connector's own
    per-company limiter or circuit breaker held it back. Retryable; `retry_after` is the
    provider's Retry-After in seconds (bounded), or None."""

    def __init__(self, code: str = "rate_limited", retry_after: float | None = None) -> None:
        super().__init__(code)
        self.retry_after = retry_after


class NotSupported(ConnectorError):
    """The connector doesn't offer this operation (see `capabilities()`)."""


@dataclass(frozen=True)
class Period:
    start: date
    end: date


@dataclass(frozen=True)
class Capabilities:
    datasets: frozenset[Dataset]
    oauth: bool
    incremental: bool
    attachments: bool


@dataclass(frozen=True)
class RawPayload:
    """The provider's response, unaltered. `request` says what was read (for the access log);
    `next_cursor` continues a paginated or incremental pull (None: complete)."""

    content: bytes
    media_type: str
    source: str
    pulled_at: datetime
    request: str
    next_cursor: str | None = None


class Connector(ABC):
    provider: ClassVar[str]

    @abstractmethod
    def capabilities(self) -> Capabilities: ...

    @abstractmethod
    async def authorise_url(
        self, state: str, redirect_uri: str, *, code_challenge: str | None = None
    ) -> str: ...

    @abstractmethod
    async def exchange_code(
        self, code: str, redirect_uri: str, *, code_verifier: str | None = None
    ) -> Credentials | None: ...

    @abstractmethod
    async def revoke(self) -> None:
        """Revoke the grant at the provider (the connector holds its credentials). `NotSupported`
        when the provider has no revocation; `Unavailable` to be retried."""
        ...

    @abstractmethod
    async def refresh(self) -> None: ...

    @abstractmethod
    async def pull(self, dataset: Dataset, period: Period, cursor: str | None) -> RawPayload: ...

    @abstractmethod
    async def changes_since(self, since: datetime) -> Sequence[str]: ...

    @abstractmethod
    async def fetch_attachment(self, ref: str) -> RawPayload: ...

    @abstractmethod
    async def health(self) -> bool: ...

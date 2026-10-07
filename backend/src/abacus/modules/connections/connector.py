"""The connector contract (ADR-037, ADR-040). PROTECTED. TASK-010 design §2.

Every connector implements this one interface and passes the conformance suite
(`tests/unit/connections/conformance.py`). Connectors only read: the contract has no write
operations and CONN-001 forbids adding any. `pull` returns the provider's bytes exactly as sent; the
pipeline stores them unaltered before anything interprets them (ADR-038).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar, Literal

Dataset = Literal["trial_balance"]


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
    async def authorise_url(self, state: str, redirect_uri: str) -> str: ...

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> None: ...

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

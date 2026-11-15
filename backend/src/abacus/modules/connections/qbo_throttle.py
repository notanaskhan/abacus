"""Per-company throttling and the provider's circuit breaker for QuickBooks Online (C-01-T16;
ADR-043).

Intuit allows a company (realm) 500 requests a minute and 10 at once. The limiter keeps each
realm's calls inside both before they leave, so a busy firm never trips Intuit's 429 for another
firm's company (fair by realm). The breaker counts consecutive throttles and outages across the
provider; after five it opens for a minute and every call is held back with `circuit_open`,
then one call is let through to try again. Both are process-local: Temporal's activity retries
carry the back-off between processes (the LedgerSyncWorkflow, C-01-T17).
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Final

from abacus.modules.connections.connector import RateLimited

PER_MINUTE: Final = 500
CONCURRENT: Final = 10
WINDOW_SECONDS: Final = 60.0
BREAKER_FAILURES: Final = 5
BREAKER_OPEN_SECONDS: Final = 60.0
MAX_RETRY_AFTER: Final = 120.0
# A call that would wait longer than this for a slot is refused now and retried by the caller.
MAX_WAIT_SECONDS: Final = 5.0


@dataclass
class _Realm:
    calls: deque[float] = field(default_factory=lambda: deque[float]())
    gate: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(CONCURRENT))


@dataclass
class _Breaker:
    failures: int = 0
    opened_at: float | None = None


_realms: dict[str, _Realm] = {}
_breaker = _Breaker()


def reset() -> None:
    """Forget every realm's window and close the breaker (tests)."""
    _realms.clear()
    _breaker.failures, _breaker.opened_at = 0, None


def _clock() -> float:
    return time.monotonic()


class Slot:
    """One call's slot for a realm: `async with Slot(realm):` around the request."""

    def __init__(self, realm: str) -> None:
        self._realm = _realms.setdefault(realm, _Realm())

    async def __aenter__(self) -> Slot:
        if _breaker.opened_at is not None:
            if _clock() - _breaker.opened_at < BREAKER_OPEN_SECONDS:
                raise RateLimited("circuit_open", BREAKER_OPEN_SECONDS)
            _breaker.opened_at = None  # half open: this call tries again
        window = self._realm.calls
        while True:
            now = _clock()
            while window and now - window[0] >= WINDOW_SECONDS:
                window.popleft()
            if len(window) < PER_MINUTE:
                break
            wait = WINDOW_SECONDS - (now - window[0])
            if wait > MAX_WAIT_SECONDS:
                raise RateLimited("rate_limited", wait)
            await asyncio.sleep(wait)
        await self._realm.gate.acquire()
        window.append(_clock())
        return self

    async def __aexit__(self, *_: object) -> None:
        self._realm.gate.release()


def succeeded() -> None:
    _breaker.failures = 0


def failed() -> None:
    """A 429 or an outage: five in a row open the breaker for a minute."""
    _breaker.failures += 1
    if _breaker.failures >= BREAKER_FAILURES:
        _breaker.opened_at = _clock()
        _breaker.failures = 0


def retry_after(headers: dict[str, str]) -> float | None:
    """Intuit's Retry-After in whole seconds, bounded; anything else is None (header text is
    untrusted)."""
    for key, value in headers.items():
        if key.lower() == "retry-after" and value.isdigit():
            return min(float(value), MAX_RETRY_AFTER)
    return None

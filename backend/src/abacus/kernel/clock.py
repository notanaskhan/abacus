"""The business clock (ADR-143; F-04-T02; DEC-27).

Business time comes from here, never from a direct `datetime.now()`:

- `now(tenant)` / `today(tenant)`: business time. In order: a `frozen(at)` block (the scenario
  loader replays each event inside one); the tenant's demo clock, when a provider is registered
  (identity, for synthetic firms only: F-04-T07); the process demo clock `ABACUS_DEMO_CLOCK`
  (local and staging only), running from its anchor; otherwise the real time.
- `system_now()`: real time, always. Security windows use it and a demo clock can't move them
  (MFA recency, OAuth state, Object Lock, budgets, token expiry: F-04.4).
- `check_startup()`: the API, worker and migration job refuse to start in production with a demo
  clock set (`ClockMisconfigured`, F-04.2).

Workflow code keeps `workflow.now()` (ADR-090); activities pass the tenant in.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, date, datetime
from typing import Final
from zoneinfo import ZoneInfo

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext

# The demo instant (ADR-143): Mon 14 Sep 2026, 9:24 AM Central.
DEMO_INSTANT: Final = datetime(2026, 9, 14, 9, 24, tzinfo=ZoneInfo("America/Chicago"))
FIRM_ZONE: Final = ZoneInfo("America/Chicago")

TenantClock = Callable[[TenantContext], Awaitable[datetime | None]]

_frozen: ContextVar[datetime | None] = ContextVar("abacus_clock_frozen", default=None)
_tenant_clock: list[TenantClock] = []
_started: Final = datetime.now(UTC)


class ClockMisconfigured(RuntimeError):
    """A demo clock is set where it must never be (production)."""


def system_now() -> datetime:
    """Real time, always: for security windows a demo clock must not move."""
    return datetime.now(UTC)


def _process_clock() -> datetime | None:
    raw = settings().demo_clock
    if not raw:
        return None
    anchor = DEMO_INSTANT if raw == "demo" else datetime.fromisoformat(raw)
    if anchor.tzinfo is None:
        raise ClockMisconfigured("ABACUS_DEMO_CLOCK needs a time zone")
    return anchor + (system_now() - _started)


def register_tenant_clock(provider: TenantClock) -> None:
    """Identity registers the tenant demo clock (synthetic firms only); one provider."""
    if _tenant_clock:
        raise ValueError("a tenant clock is already registered")
    _tenant_clock.append(provider)


async def now(tenant: TenantContext | None = None) -> datetime:
    """Business time for the tenant (see the module docstring for the order)."""
    frozen_at = _frozen.get()
    if frozen_at is not None:
        return frozen_at
    if tenant is not None and _tenant_clock and settings().environment != "production":
        tenant_time = await _tenant_clock[0](tenant)
        if tenant_time is not None:
            return tenant_time
    return _process_clock() or system_now()


async def today(tenant: TenantContext | None = None, zone: ZoneInfo = FIRM_ZONE) -> date:
    """The business date in the firm's zone (Central until offices carry their own)."""
    return (await now(tenant)).astimezone(zone).date()


@contextmanager
def frozen(at: datetime) -> Generator[datetime]:
    """Business time stands at `at` inside the block (scenario replay, golden tests)."""
    if at.tzinfo is None:
        raise ValueError("a frozen instant needs a time zone")
    token = _frozen.set(at)
    try:
        yield at
    finally:
        _frozen.reset(token)


def check_startup() -> None:
    """F-04.2: refuse to start in production with a demo clock set."""
    current = settings()
    if current.environment == "production" and current.demo_clock:
        raise ClockMisconfigured("ABACUS_DEMO_CLOCK is set in production")
    _process_clock()  # a malformed value fails at startup, not on the first request

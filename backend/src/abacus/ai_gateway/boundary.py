"""The model data boundary (SPEC-026 AC-2; TASK-049; ADR-031). PROTECTED.

A real model sees only synthetic data until zero-retention and no-training terms are recorded and
staging exists. Settings refuse real routes outside the evaluation environment (AC-1); this is the
per-call layer: before any network call on a route other than `fake`, the call's firm must be
marked synthetic. Identity owns that fact and registers the check; unregistered means refused.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Final

from abacus.kernel.config import Route
from abacus.kernel.db import TenantContext
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import Target, uow

SyntheticCheck = Callable[[TenantContext], Awaitable[bool]]
_CACHE_SECONDS: Final = 60.0
_check: SyntheticCheck | None = None
_cache: dict[object, tuple[bool, float]] = {}
_log = get_logger(__name__)
_refused = meter(__name__).create_counter(
    "abacus.ai.boundary_refused", description="Real-model calls refused at the data boundary"
)


class DataBoundaryRefused(Exception):
    """A real model was asked to see a firm that isn't synthetic. Never retried or rerouted."""


def register_synthetic_tenants(check: SyntheticCheck) -> None:
    global _check
    if _check is not None and _check is not check:
        raise RuntimeError("the synthetic-tenant check is already registered")
    _check = check


async def _synthetic(tenant: TenantContext) -> bool:
    if _check is None:
        return False
    now = time.monotonic()
    found = _cache.get(tenant.tenant_id)
    if found is not None and found[1] > now:
        return found[0]
    answer = await _check(tenant)
    _cache[tenant.tenant_id] = (answer, now + _CACHE_SECONDS)
    return answer


async def enforce_boundary(tenant: TenantContext, route: Route, prompt: str) -> None:
    """Return if `route` may see this firm's data; else audit, count and raise."""
    if route == "fake" or await _synthetic(tenant):
        return
    _refused.add(1, {"route": route, "prompt": prompt})
    _log.warning("ai.boundary_refused", tenant_id=tenant.tenant_id, route=route, prompt=prompt)
    async with uow(tenant) as tx:
        tx.record("ai.boundary_refused", target=Target("firm", tenant.tenant_id))
    raise DataBoundaryRefused(f"route {route!r} may see synthetic firms only (SPEC-026)")


def clear_cache() -> None:
    """Tests only."""
    _cache.clear()

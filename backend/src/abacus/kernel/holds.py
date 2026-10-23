"""The hold-check slot (Q-02-T29; Q-02 AC-37; ADR-033, ADR-162). Fail closed.

Anything that erases or lets go of evidence (P-06's withdrawal purge, Q-05's destruction, a
retention purge) asks here first which of the versions it means to erase are held:

    held = await held_versions(tenant, version_ids)      # raises HoldCheckMissing without a check
    erasable = [v for v in version_ids if v not in held]

The evidence module registers `holds_covering` at import (its `api.py`). With nothing registered
the caller gets `HoldCheckMissing` and must erase nothing: an unknown hold state is a hold.
The kernel imports no module (ADR-101), hence a slot.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from uuid import UUID

from abacus.kernel.db import TenantContext

HoldCheck = Callable[[TenantContext, Sequence[UUID]], Awaitable[frozenset[UUID]]]
_CHECK: list[HoldCheck] = []


class HoldCheckMissing(RuntimeError):
    """No hold check is registered: erase nothing (fail closed)."""


def _same(a: HoldCheck, b: HoldCheck) -> bool:
    return (a.__module__, a.__qualname__) == (b.__module__, b.__qualname__)


def register_hold_check(check: HoldCheck) -> None:
    """Register the one hold check (evidence's `holds_covering`)."""
    if _CHECK and not _same(_CHECK[0], check):
        raise ValueError("a hold check is already registered")
    _CHECK[:] = [check]


def reset_hold_check() -> None:
    """Tests only: back to no check, the fail-closed state."""
    _CHECK.clear()


def hold_check() -> HoldCheck | None:
    return _CHECK[0] if _CHECK else None


async def held_versions(tenant: TenantContext, version_ids: Sequence[UUID]) -> frozenset[UUID]:
    """The versions among `version_ids` that a legal hold covers. `HoldCheckMissing` when no check
    is registered, so a caller that ignores the answer still can't erase."""
    check = hold_check()
    if check is None:
        raise HoldCheckMissing("no hold check is registered")
    if not version_ids:
        return frozenset()
    return await check(tenant, version_ids)


async def erasable_versions(tenant: TenantContext, version_ids: Sequence[UUID]) -> list[UUID]:
    """`version_ids` less the held ones, in order; `HoldCheckMissing` like `held_versions`."""
    held = await held_versions(tenant, version_ids)
    return [v for v in version_ids if v not in held]

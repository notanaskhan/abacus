"""What can be reviewed (P-04; SPEC-313). Each owner registers a provider that lists its
reviewables on an engagement with their current content hash; the matrix and the G5 gate read
every registered provider. Fail closed: an unregistered type has nothing to review, and a
provider that raises makes the gate unmet."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext

# The levels every reviewable needs before completion (L1 preparer, L2 reviewer). K-02's
# methodology policies will set more per area and risk.
REQUIRED_LEVELS: Final = (1, 2)


@dataclass(frozen=True)
class Reviewable:
    target_type: str
    target_id: UUID
    code: str
    title: str
    content_hash: str
    has_content: bool


ReviewableProvider = Callable[[TenantContext, UUID], Awaitable[list[Reviewable]]]
_PROVIDERS: dict[str, ReviewableProvider] = {}


def register_reviewable(target_type: str, provider: ReviewableProvider) -> None:
    known = _PROVIDERS.get(target_type)
    if known is not None and (known.__module__, known.__qualname__) != (
        provider.__module__,
        provider.__qualname__,
    ):
        raise ValueError(f"reviewable {target_type!r} is already registered")
    _PROVIDERS[target_type] = provider


def reviewable_types() -> tuple[str, ...]:
    return tuple(sorted(_PROVIDERS))


async def reviewables_of(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    """Every registered type's reviewables, by type then code (callers authorised first)."""
    out: list[Reviewable] = []
    for target_type in reviewable_types():
        found = await _PROVIDERS[target_type](tenant, engagement_id)
        out.extend(sorted(found, key=lambda r: r.code))
    return out

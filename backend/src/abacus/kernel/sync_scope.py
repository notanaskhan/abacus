"""The ledger sync's scope slot (C-01-T17; C-01 §4.5 `entities_due`; DEC-5076).

The closes module registers which entities have an unlocked close and the months to keep fresh;
the connections module's `LedgerSyncWorkflow` reads it. Neither imports the other: nothing depends
on connections but integrations and the portal (BOUND-002), and connections never imports closes.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext


@dataclass(frozen=True)
class SyncScope:
    """An entity with an unlocked close: its engagement and the close months to keep fresh."""

    client_entity_id: UUID
    engagement_id: UUID
    periods: tuple[str, ...]


ScopeProvider = Callable[[TenantContext], Awaitable[Sequence[SyncScope]]]
_SCOPE: Final[list[ScopeProvider]] = []


def register_sync_scope(provider: ScopeProvider) -> None:
    """The closes module's entities-due provider (one)."""
    if _SCOPE and _SCOPE[0] is not provider:
        raise ValueError("a ledger sync scope is already registered")
    if not _SCOPE:
        _SCOPE.append(provider)


async def scope_of(tenant: TenantContext) -> dict[UUID, SyncScope]:
    if not _SCOPE:
        return {}
    return {s.client_entity_id: s for s in await _SCOPE[0](tenant) if s.periods}

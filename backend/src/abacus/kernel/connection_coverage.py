"""Connection entity coverage, as a slot (A-09-T11, T13; DEC-5070).

The connections module registers how to tell whether a live connection covers an entity and how
to add the entities a covering ledger connection reads (a NetSuite OneWorld connection covers a
group's subsidiaries). The consolidation routes in assurance call it here, so nothing depends on
connections but integrations and the portal (BOUND-002). Unregistered, nothing is covered.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, NotFound

Covers = Callable[[TenantContext, UUID, UUID], Awaitable[bool]]
Extend = Callable[[TenantContext, UUID, Sequence[UUID]], Awaitable[int]]
_COVERS: Final[list[Covers]] = []
_EXTEND: Final[list[Extend]] = []


class EntityAlreadyCovered(DomainConflict):
    code = "entity_already_covered"


def register_connection_coverage(covers: Covers, extend: Extend) -> None:
    _COVERS[:] = [covers]
    _EXTEND[:] = [extend]


async def covers(tenant: TenantContext, connection_id: UUID, client_entity_id: UUID) -> bool:
    if not _COVERS:
        return False
    return await _COVERS[0](tenant, connection_id, client_entity_id)


async def cover_entities(
    tenant: TenantContext, connection_id: UUID, client_entity_ids: Sequence[UUID]
) -> int:
    if not _EXTEND:
        raise NotFound("connection")
    return await _EXTEND[0](tenant, connection_id, client_entity_ids)

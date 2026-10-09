"""Which datasets the engagement's live connection can deliver (SPEC-022 AC-3; TASK-038 D2).

Connections depends on requests, so it registers the lookup here (ADR-106). Unregistered, nothing
is available: no item looks retrievable and nothing is retrieved automatically (fail closed).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from abacus.kernel.db import TenantContext

AvailableDatasets = Callable[[TenantContext, UUID], Awaitable[frozenset[str]]]
_lookup: AvailableDatasets | None = None


def register_available_datasets(lookup: AvailableDatasets) -> None:
    global _lookup
    if _lookup is not None and _lookup is not lookup:
        raise RuntimeError("the dataset availability lookup is already registered")
    _lookup = lookup


async def available_datasets(tenant: TenantContext, client_entity_id: UUID) -> frozenset[str]:
    return frozenset() if _lookup is None else await _lookup(tenant, client_entity_id)

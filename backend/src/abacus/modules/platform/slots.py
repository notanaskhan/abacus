"""The search projection slot (C15; F-03-T08; chapter 03 §2.4 and §8).

Each module with searchable objects registers a builder for its object type. An unregistered
type is never indexed (fail closed).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from abacus.kernel.db import TenantContext


@dataclass(frozen=True)
class SearchDocument:
    object_type: str
    object_id: UUID
    engagement_id: UUID | None
    title: str
    body: str


SearchBuilder = Callable[[TenantContext, UUID], Awaitable[SearchDocument | None]]
_PROJECTIONS: dict[str, SearchBuilder] = {}


def register_search_projection(object_type: str, builder: SearchBuilder) -> None:
    if object_type in _PROJECTIONS:
        raise ValueError(f"search projection {object_type!r} is already registered")
    _PROJECTIONS[object_type] = builder


async def search_document(
    tenant: TenantContext, object_type: str, object_id: UUID
) -> SearchDocument | None:
    """The object's search document; None (not indexed) when its type is unregistered."""
    builder = _PROJECTIONS.get(object_type)
    return None if builder is None else await builder(tenant, object_id)

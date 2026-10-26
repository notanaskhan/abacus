"""The search projection slot (C15; F-03-T08; chapter 03 §2.4 and §8) and Home's count slot
(C13 home half; I-01-T02).

Each module with searchable objects registers a builder for its object type. An unregistered
type is never indexed (fail closed).
"""

from __future__ import annotations

import re
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


# --- C13 home half (I-01-T02; I-01 §4.3): Home's tiles and pills ---------------------------------


@dataclass(frozen=True)
class HomeStatusCount:
    """One status bucket of a tile ("17 Planning"), with the filter its link applies."""

    code: str
    n: int
    filter: str


@dataclass(frozen=True)
class HomeOfficeCount:
    office_id: UUID
    n: int


@dataclass(frozen=True)
class HomeCount:
    """What an owner counts for one tile or pill, already under `visible()` for the viewer and
    narrowed to the office filter when one is given. Counts only: no names, no amounts."""

    total: int
    by_status: tuple[HomeStatusCount, ...] = ()
    by_office: tuple[HomeOfficeCount, ...] = ()
    target_filter: str | None = None


# `provider(viewer, office_id)`: the viewer is the identity module's `AuthContext`, passed through
# untyped here because `platform` sits below identity (DEC-13 graph).
HomeCountProvider = Callable[[object, UUID | None], Awaitable[HomeCount]]
_HOME_COUNTS: dict[str, HomeCountProvider] = {}
_HOME_KEY = re.compile(r"[a-z][a-z_]{0,39}")


def register_home_count(key: str, provider: HomeCountProvider) -> None:
    """An owner's tile or pill (`audits`, `binders`, `agent_runs_running`, ...). Registered once;
    the same function registered again (a reloaded module) is a no-op."""
    if not _HOME_KEY.fullmatch(key):
        raise ValueError(f"home count {key!r} must be snake_case")
    known = _HOME_COUNTS.get(key)
    if known is not None and (known.__module__, known.__qualname__) != (
        provider.__module__,
        provider.__qualname__,
    ):
        raise ValueError(f"home count {key!r} is already registered")
    _HOME_COUNTS[key] = provider


def home_count_keys() -> tuple[str, ...]:
    return tuple(sorted(_HOME_COUNTS))


async def home_count(viewer: object, key: str, office_id: UUID | None) -> HomeCount | None:
    """Fail closed: an unregistered key has no tile (None), and an owner that raises shows none
    rather than a wrong number."""
    provider = _HOME_COUNTS.get(key)
    if provider is None:
        return None
    try:
        return await provider(viewer, office_id)
    except Exception:
        return None

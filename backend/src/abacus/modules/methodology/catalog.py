"""The knowledge catalog's read model (K-01-T03; K-01 §3.1, §4.3; KNW-01; DEC-571).

KNW-01 shows every kind of firm knowledge without knowing each kind. Two slots, both fail closed:

- `register_catalog_provider(category, provider)`: an owning module's cards, review-queue rows
  and change-log entries for one category. The provider applies its own read rules (drafts only to
  the people who manage or approve them). An unregistered category has no cards and no facet
  count (`count: null` on the wire is its absence, never `0`); a provider that raises is treated
  as unregistered for that request, and logged.
- `register_usage_counter(object_type, counter)`: how many engagements use each object, counted
  by the owner over `visible()`, so a walled engagement is never counted (INV-3). No counter, or
  one that raises, leaves `usage_count` null.

The composition here is code: search is lexical (case-folded substring) with match ranges in the
title for the highlight; the status facet counts cards by their current status (the Draft and
Review-queue counting rule, AC1.4: a draft sitting under a published card is a review-queue row,
never a Draft card); categories come in the addendum's order. `methodology` imports none of the
providers' modules: they register here from their own `api.py`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Final
from uuid import UUID

from abacus.kernel._flags import KNOWLEDGE_CATALOG
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import (
    Facet,
    ListPage,
    Position,
    clamp_limit,
    decode_cursor,
    envelope,
    query_hash,
)
from abacus.kernel.logging import get_logger
from abacus.modules.identity.api import AuthContext, Resource, allowed_actions, authorise, names_of

_log = get_logger(__name__)

# KNW-01's categories in the addendum's §4 order (the CategoryList, after All).
CATEGORIES: Final = (
    "engagement_templates",
    "methodology",
    "frameworks",
    "firm_standards",
    "skills",
    "notes",
    "pbc_templates",
    "research",
    "content_packs",
    "agent_instructions",
)
STATUSES: Final = ("published", "draft", "superseded")
_ITEMS = "knowledge_items"
_CHANGES = "knowledge_change_log"
# Who sees drafts and the review queue: the people who manage or approve content (K-01 §4.3,
# OQ-2). Read without the fresh second factor: seeing is not acting.
_EDITORS: Final = ("methodology.manage", "methodology.approve")


@dataclass(frozen=True)
class Viewer:
    """What a provider needs to know about the reader."""

    ctx: AuthContext
    sees_drafts: bool  # holds methodology.manage or methodology.approve
    approves: bool  # holds methodology.approve


@dataclass(frozen=True)
class CatalogItem:
    id: UUID
    category: str
    title: str
    subtitle: str | None
    status: str  # knowledge_item: draft, published, superseded
    version_label: str | None
    effective_from: date | None
    owner_user_id: UUID | None
    updated_at: datetime
    route: str
    # The object a usage counter counts for this card (type, id); None: no usage.
    usage: tuple[str, UUID] | None = None
    # Other words the card is found by (area and program names); never shown, never ranged.
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewItem:
    category: str
    object_id: UUID
    title: str
    version_label: str
    status: str  # methodology_version
    submitted_by: UUID | None
    submitted_at: datetime | None
    flags_open: int
    route: str


def _no_facts() -> dict[str, str | int | bool | None]:
    return {}


@dataclass(frozen=True)
class ChangeEntry:
    id: UUID
    at: datetime
    seq: int
    category: str
    object_id: UUID
    title: str
    kind: str
    actor_kind: str
    actor_user_id: UUID | None
    on_behalf_of_user_id: UUID | None
    facts: Mapping[str, str | int | bool | None] = field(default_factory=_no_facts)


@dataclass(frozen=True)
class CatalogProvider:
    items: Callable[[Viewer], Awaitable[Sequence[CatalogItem]]]
    review_queue: Callable[[Viewer], Awaitable[Sequence[ReviewItem]]]
    change_log: Callable[[Viewer], Awaitable[Sequence[ChangeEntry]]]


UsageCounter = Callable[[AuthContext, Sequence[UUID]], Awaitable[Mapping[UUID, int]]]

_PROVIDERS: dict[str, CatalogProvider] = {}
_COUNTERS: dict[str, UsageCounter] = {}


def _same(a: object, b: object) -> bool:
    return (getattr(a, "__module__", None), getattr(a, "__qualname__", None)) == (
        getattr(b, "__module__", None),
        getattr(b, "__qualname__", None),
    )


def register_catalog_provider(category: str, provider: CatalogProvider) -> None:
    """A category's provider, once (an owner's `api.py` at import). Re-registering the same
    provider is a no-op; another provider for a taken category is refused."""
    if category not in CATEGORIES:
        raise ValueError(f"{category!r} is not a knowledge category")
    known = _PROVIDERS.get(category)
    if known is not None and not all(
        _same(getattr(known, part), getattr(provider, part))
        for part in ("items", "review_queue", "change_log")
    ):
        raise ValueError(f"knowledge category {category!r} already has a provider")
    _PROVIDERS[category] = provider


def register_usage_counter(object_type: str, counter: UsageCounter) -> None:
    """How many engagements the caller may see use each object of `object_type`."""
    known = _COUNTERS.get(object_type)
    if known is not None and not _same(known, counter):
        raise ValueError(f"{object_type!r} already has a usage counter")
    _COUNTERS[object_type] = counter


def catalog_categories() -> tuple[str, ...]:
    """The categories with a registered provider, in the addendum's order."""
    return tuple(c for c in CATEGORIES if c in _PROVIDERS)


# --- Shared guard ---------------------------------------------------------------------------


async def _viewer(ctx: AuthContext) -> Viewer:
    """A client principal never reaches knowledge (INV-4): 404. Then `knowledge.read` at the
    firm (the agent, the system and anyone else refused), then the flag."""
    if ctx.client:
        raise NotFound("knowledge")
    await authorise(ctx, "knowledge.read", Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, KNOWLEDGE_CATALOG):
        raise NotFound(KNOWLEDGE_CATALOG.name)
    held = await allowed_actions(ctx, Resource.firm(ctx.tenant_id), _EDITORS)
    return Viewer(ctx, sees_drafts=bool(held), approves="methodology.approve" in held)


async def _gathered[T](
    viewer: Viewer,
    category: str | None,
    read: Callable[[CatalogProvider], Callable[[Viewer], Awaitable[Sequence[T]]]],
) -> dict[str, list[T]]:
    """Each registered category's rows; a provider that raises shows nothing (fail closed)."""
    found: dict[str, list[T]] = {}
    for name in catalog_categories():
        if category is not None and name != category:
            continue
        try:
            found[name] = list(await read(_PROVIDERS[name])(viewer))
        except Exception as exc:  # one provider's failure never shows a wrong catalog
            _log.warning("knowledge.provider_failed", category=name, error=type(exc).__name__)
    return found


# --- Search ---------------------------------------------------------------------------------


def match_ranges(title: str, q: str) -> list[tuple[int, int]]:
    """Every case-folded occurrence of `q` in `title`, as [start, end) offsets, not overlapping."""
    needle = q.casefold()
    if not needle:
        return []
    hay = title.casefold()
    if len(hay) != len(title):  # case folding changed the length: no safe offsets
        return []
    found: list[tuple[int, int]] = []
    at = hay.find(needle)
    while at != -1:
        found.append((at, at + len(needle)))
        at = hay.find(needle, at + len(needle))
    return found


def _matches(item: CatalogItem, q: str) -> bool:
    needle = q.casefold()
    return any(
        needle in text.casefold() for text in (item.title, item.subtitle or "", *item.keywords)
    )


# --- The three reads ------------------------------------------------------------------------


@dataclass(frozen=True)
class CatalogCard:
    item: CatalogItem
    owner_name: str | None
    usage_count: int | None
    match: tuple[tuple[int, int], ...]


async def _usage(ctx: AuthContext, items: Sequence[CatalogItem]) -> dict[tuple[str, UUID], int]:
    wanted: dict[str, list[UUID]] = {}
    for item in items:
        if item.usage is not None:
            wanted.setdefault(item.usage[0], []).append(item.usage[1])
    counted: dict[tuple[str, UUID], int] = {}
    for object_type, ids in wanted.items():
        counter = _COUNTERS.get(object_type)
        if counter is None:
            continue
        try:
            counts = await counter(ctx, sorted(set(ids), key=str))
        except Exception as exc:  # no number rather than a wrong one
            _log.warning(
                "knowledge.counter_failed", object_type=object_type, error=type(exc).__name__
            )
            continue
        for object_id in ids:
            counted[(object_type, object_id)] = int(counts.get(object_id, 0))
    return counted


def _sort_key(item: CatalogItem) -> str:
    return (
        f"{CATEGORIES.index(item.category):02d}|{item.title.casefold()}|{item.version_label or ''}"
    )


async def catalog_items(
    ctx: AuthContext,
    *,
    category: str | None,
    status: str | None,
    q: str | None,
    cursor: str | None,
    limit: int | None,
) -> ListPage[CatalogCard]:
    """`GET /v1/knowledge/items`: cards in category order, then by title. `counts` per status
    over the category and search filters (the Picker), `facets.category` per registered category
    over the status and search filters (the CategoryList; an unregistered one is absent)."""
    viewer = await _viewer(ctx)
    size = clamp_limit(limit)
    search = (q or "").strip()
    query = query_hash(category=category, status=status, q=search)
    after = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=_ITEMS, query=query)
        if cursor
        else None
    )
    gathered = await _gathered(viewer, None, lambda p: p.items)
    every = [
        i
        for rows in gathered.values()
        for i in rows
        if i.category in gathered  # a provider answers for its own category only
        and i.status in STATUSES
        and (viewer.sees_drafts or i.status != "draft")
    ]
    if search:
        every = [i for i in every if _matches(i, search)]
    by_category = [i for i in every if category is None or i.category == category]
    counts = {s: sum(1 for i in by_category if i.status == s) for s in STATUSES}
    by_status = [i for i in every if status is None or i.status == status]
    facets = {
        "category": [
            Facet(value=c, label=c, n=sum(1 for i in by_status if i.category == c))
            for c in CATEGORIES
            if c in gathered
        ]
    }
    chosen = sorted(
        (i for i in by_status if category is None or i.category == category),
        key=lambda i: (_sort_key(i), str(i.id)),
    )
    total = len(chosen)
    if after is not None:
        chosen = [i for i in chosen if (_sort_key(i), str(i.id)) > (str(after.key), after.id)]
    page = chosen[:size]
    position = (
        Position(key=_sort_key(page[-1]), id=str(page[-1].id)) if len(chosen) > size else None
    )
    usage = await _usage(ctx, page)
    owners = [i.owner_user_id for i in page if i.owner_user_id is not None]
    names = await names_of(sorted(set(owners), key=str)) if owners else {}
    cards = [
        CatalogCard(
            i,
            names.get(i.owner_user_id) if i.owner_user_id is not None else None,
            usage.get(i.usage) if i.usage is not None else None,
            tuple(match_ranges(i.title, search)),
        )
        for i in page
    ]
    return envelope(
        cards,
        next_position=position,
        tenant_id=ctx.tenant_id,
        resource=_ITEMS,
        query=query,
        total=(total, False),
        counts=counts,
        facets=facets,
    )


@dataclass(frozen=True)
class QueueRow:
    item: ReviewItem
    submitted_by_name: str | None


async def review_queue(ctx: AuthContext) -> ListPage[QueueRow]:
    """`GET /v1/knowledge/review-queue`: what waits on the viewer's approval, and their own
    drafts. Nothing for a reader who neither manages nor approves content."""
    viewer = await _viewer(ctx)
    if not viewer.sees_drafts:
        rows: list[ReviewItem] = []
    else:
        gathered = await _gathered(viewer, None, lambda p: p.review_queue)
        rows = sorted(
            (r for name, found in gathered.items() for r in found if r.category == name),
            key=lambda r: (r.submitted_at.isoformat() if r.submitted_at else "", str(r.object_id)),
        )
    people = [r.submitted_by for r in rows if r.submitted_by is not None]
    names = await names_of(sorted(set(people), key=str)) if people else {}
    queue = [
        QueueRow(r, names.get(r.submitted_by) if r.submitted_by is not None else None)
        for r in rows
    ]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.status] = counts.get(r.status, 0) + 1
    return ListPage[QueueRow](items=queue, total=len(queue), counts=counts)


@dataclass(frozen=True)
class ChangeRow:
    entry: ChangeEntry
    actor_name: str | None


def _change_key(e: ChangeEntry) -> str:
    return f"{e.at.isoformat()}|{e.seq:020d}"


async def change_log(
    ctx: AuthContext, *, cursor: str | None, limit: int | None
) -> ListPage[ChangeRow]:
    """`GET /v1/knowledge/change-log`: lifecycle events across providers, oldest first (newest
    last), each naming the person who acted (INV-5: an agent's act names who it acted for)."""
    viewer = await _viewer(ctx)
    size = clamp_limit(limit)
    query = query_hash()
    after = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=_CHANGES, query=query)
        if cursor
        else None
    )
    gathered = await _gathered(viewer, None, lambda p: p.change_log)
    entries = sorted(
        (e for name, found in gathered.items() for e in found if e.category == name),
        key=lambda e: (_change_key(e), str(e.id)),
    )
    total = len(entries)
    if after is not None:
        entries = [e for e in entries if (_change_key(e), str(e.id)) > (str(after.key), after.id)]
    page = entries[:size]
    position = (
        Position(key=_change_key(page[-1]), id=str(page[-1].id)) if len(entries) > size else None
    )
    people = {p for e in page for p in (e.actor_user_id, e.on_behalf_of_user_id) if p is not None}
    names = await names_of(sorted(people, key=str)) if people else {}
    rows = [
        ChangeRow(e, names.get(e.actor_user_id) if e.actor_user_id is not None else None)
        for e in page
    ]
    return envelope(
        rows,
        next_position=position,
        tenant_id=ctx.tenant_id,
        resource=_CHANGES,
        query=query,
        total=(total, False),
    )


__all__ = [
    "CATEGORIES",
    "CatalogCard",
    "CatalogItem",
    "CatalogProvider",
    "ChangeEntry",
    "ChangeRow",
    "QueueRow",
    "ReviewItem",
    "UsageCounter",
    "Viewer",
    "catalog_categories",
    "catalog_items",
    "change_log",
    "match_ranges",
    "register_catalog_provider",
    "register_usage_counter",
    "review_queue",
]

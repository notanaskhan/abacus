"""C15 v1: the search registration contract (P-02-T01; P-02 §8.1; ADR-241 decision 9).

Each owning module registers one `SearchProjection` per object type in its own `api.py`. The
projection names the canonical group its rows land in, the read action and scope kind of the
screen a row opens (so a result never 404s when opened), its data class, the events that
reindex it and a builder that reads the owner's current state. Registration fails closed: an
unknown group, an action that is not a read in the permission matrix, or a scope kind
`visible()` does not know raises at import, so boot fails in tests (the F-03 slot rule).

A built document is metadata only (ADR-241 decision 4): a title, a short context line, record
identifiers, related party names with their labels, a status code, a due date and the
identifiers its target needs. It never carries a TIN, an amount, document text or a comment
body; `check_document` refuses a document whose strings are too long or whose target parameters
are not identifiers.

C15 v0 (`register_search_projection(object_type, builder)` in `platform.slots`, F-03-T08) keeps
working through `register_search_projection` below for one sprint after v1 freezes (Fri Apr 28,
2028): a v0 call goes to the slot unchanged.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from types import MappingProxyType
from typing import Final, Literal, get_args
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import RULES
from abacus.modules.platform import slots

# The canonical result groups in display order (P-02 OQ-3; DEC-4503). "Actions", "Recent" and
# "Create" are composed by the palette, never indexed; "agents" lists installed agent definitions
# in `>` mode only.
SearchGroup = Literal[
    "clients",
    "returns",
    "audits",
    "closes",
    "binders",
    "files",
    "inbox",
    "sessions",
    "todos",
    "saved_prompts",
    "agents",
]
GROUP_ORDER: Final[tuple[SearchGroup, ...]] = get_args(SearchGroup)

# `visible()`'s scope kinds (ADR-145, P-06) plus `firm` (any firm role the action allows) and
# `own` (the document's owner only). `portal_scope` is never served: search is firm-only (INV-4).
ScopeKind = Literal["engagement", "work_item", "client", "client_entity", "firm", "own"]
SCOPE_KINDS: Final[frozenset[str]] = frozenset(get_args(ScopeKind))

# `tri` documents need the offshore-disclosure consent for an offshore member (§7216).
DataClass = Literal["internal", "confidential", "tri"]
DATA_CLASSES: Final[frozenset[str]] = frozenset(get_args(DataClass))

TITLE_MAX: Final = 300
CONTEXT_MAX: Final = 300
RELATED_MAX: Final = 20
IDENTIFIERS_MAX: Final = 20
_OBJECT_TYPE = re.compile(r"[a-z][a-z0-9_]{1,39}")
_SCREEN_ID = re.compile(r"[A-Z]{2,4}-\d{2}")
_EVENT_TYPE = re.compile(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+")
# A target parameter is an identifier (a uuid, a slug, a form family, a tax year), never text.
_PARAM_KEY = re.compile(r"[a-z][a-zA-Z0-9]{0,39}")
_PARAM_VALUE = re.compile(r"[A-Za-z0-9_.:-]{1,80}")


@dataclass(frozen=True)
class RelatedParty:
    """A related party a document can be found by ("Jonah Feld", "limited partner 25%")."""

    name: str
    label: str


@dataclass(frozen=True)
class SearchIndexDocument:
    """One object's metadata-only search document, as its owner's builder returns it.

    `scope` ids are the columns `visible()` filters on: an `engagement` or `work_item` document
    names its engagement, a `client` or `client_entity` document its client, an `own` document its
    owner. `client_id` is required unless the projection's scope kind is `firm` or `own`, because
    walls are evaluated on it.
    """

    object_id: UUID
    title: str
    source_updated_at: datetime
    target_params: Mapping[str, str]
    context: str | None = None
    engagement_id: UUID | None = None
    work_item_id: UUID | None = None
    client_id: UUID | None = None
    owner_user_id: UUID | None = None
    identifiers: tuple[str, ...] = ()
    related: tuple[RelatedParty, ...] = ()
    status_code: str | None = None
    status_context: str | None = None
    due_on: date | None = None
    tag: str | None = None
    use_count: int | None = None


Builder = Callable[[TenantContext, UUID], Awaitable[SearchIndexDocument | None]]
# An event's payload (identifiers only, ADR-139) to the ids of the objects it reindexes.
Trigger = Callable[[Mapping[str, object]], Iterable[UUID]]


@dataclass(frozen=True)
class SearchProjection:
    """How one object type is found (C15 v1)."""

    object_type: str
    group: SearchGroup
    read_action: str
    scope_kind: ScopeKind
    build: Builder
    target: str  # the screen a row opens, a manifest screen id ("TAX-02")
    data_class: DataClass = "confidential"
    triggers: Mapping[str, Trigger] = field(default_factory=lambda: MappingProxyType({}))
    rank: int = 100  # order within the group when relevance ties; lower first


class SearchRegistrationInvalid(ValueError):
    """A projection that would serve rows the viewer could not open: refused at import."""


_PROJECTIONS: dict[str, SearchProjection] = {}


def _check(projection: SearchProjection) -> None:
    kind = projection.object_type
    if not _OBJECT_TYPE.fullmatch(kind):
        raise SearchRegistrationInvalid(f"search object type {kind!r} must be snake_case")
    if projection.group not in GROUP_ORDER:
        raise SearchRegistrationInvalid(f"{kind}: unknown search group {projection.group!r}")
    if projection.scope_kind not in SCOPE_KINDS:
        raise SearchRegistrationInvalid(f"{kind}: unknown scope kind {projection.scope_kind!r}")
    if projection.data_class not in DATA_CLASSES:
        raise SearchRegistrationInvalid(f"{kind}: unknown data class {projection.data_class!r}")
    rule = RULES.get(projection.read_action)
    if rule is None:
        raise SearchRegistrationInvalid(
            f"{kind}: {projection.read_action!r} is not in the permission matrix"
        )
    if not rule.reads:
        raise SearchRegistrationInvalid(f"{kind}: {projection.read_action!r} is not a read action")
    if not _SCREEN_ID.fullmatch(projection.target):
        raise SearchRegistrationInvalid(f"{kind}: target {projection.target!r} is not a screen id")
    for event_type in projection.triggers:
        if not _EVENT_TYPE.fullmatch(event_type):
            raise SearchRegistrationInvalid(f"{kind}: trigger {event_type!r} is not an event type")


def register(projection: SearchProjection) -> None:
    """Register a C15 v1 projection. The same projection registered again (a reloaded module) is a
    no-op; a different one for a known type raises."""
    _check(projection)
    known = _PROJECTIONS.get(projection.object_type)
    if known is not None:
        if (known.build.__module__, known.build.__qualname__) == (
            projection.build.__module__,
            projection.build.__qualname__,
        ):
            return
        raise SearchRegistrationInvalid(
            f"search projection {projection.object_type!r} is already registered"
        )
    _PROJECTIONS[projection.object_type] = projection


def register_search_projection(
    projection: SearchProjection | str, builder: slots.SearchBuilder | None = None
) -> None:
    """C15's one registration call. A `SearchProjection` is v1; `(object_type, builder)` is
    the F-03 v0 slot, kept through this adapter for one sprint after v1 freezes."""
    if isinstance(projection, SearchProjection):
        if builder is not None:
            raise TypeError("a v1 SearchProjection carries its own builder")
        register(projection)
        return
    if builder is None:
        raise TypeError("a v0 registration needs its builder")
    slots.register_search_projection(projection, builder)


def projection(object_type: str) -> SearchProjection | None:
    """The registered projection, or None: an unregistered type is never indexed (fail closed)."""
    return _PROJECTIONS.get(object_type)


def projections() -> tuple[SearchProjection, ...]:
    """Every registered projection, in canonical group order, then rank, then type."""
    order = {g: i for i, g in enumerate(GROUP_ORDER)}
    return tuple(
        sorted(_PROJECTIONS.values(), key=lambda p: (order[p.group], p.rank, p.object_type))
    )


def check_document(projection: SearchProjection, document: SearchIndexDocument) -> None:
    """A built document within the contract (ADR-241 decision 4), or `SearchRegistrationInvalid`.
    The indexer (P-02-T06) runs it before every upsert; the scrubbing of hostile strings is its own
    step (P-02-T07), not this check."""
    kind = projection.object_type
    if not document.title or len(document.title) > TITLE_MAX:
        raise SearchRegistrationInvalid(f"{kind}: title must be 1-{TITLE_MAX} characters")
    if document.context is not None and len(document.context) > CONTEXT_MAX:
        raise SearchRegistrationInvalid(f"{kind}: context is over {CONTEXT_MAX} characters")
    if len(document.related) > RELATED_MAX or len(document.identifiers) > IDENTIFIERS_MAX:
        raise SearchRegistrationInvalid(f"{kind}: too many related parties or identifiers")
    if projection.scope_kind not in ("firm", "own") and document.client_id is None:
        raise SearchRegistrationInvalid(
            f"{kind}: a {projection.scope_kind} document names a client"
        )
    if projection.scope_kind in ("engagement", "work_item") and document.engagement_id is None:
        raise SearchRegistrationInvalid(
            f"{kind}: an engagement-scoped document names its engagement"
        )
    if projection.scope_kind == "own" and document.owner_user_id is None:
        raise SearchRegistrationInvalid(f"{kind}: an own-scoped document names its owner")
    for key, value in document.target_params.items():
        if not _PARAM_KEY.fullmatch(key) or not _PARAM_VALUE.fullmatch(value):
            raise SearchRegistrationInvalid(f"{kind}: target parameters are identifiers only")

"""The portal home's sources (P-08-T13; C5 v1.1 `home_sources/<module>.py` convention).

Each source reads one module's part of a scope's home: to-dos, work cards, the binder card, the
team or Earlier rows, in client codes only. A source sees only the targets `home.py` already
authorised for `portal_home.read` (`scope_only` per target, INV-4), so no aggregate crosses into
another scope. Later epics add a module file and register it; none edits `home.py`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from abacus.modules.engagements.api import PortalWorkItem
from abacus.modules.identity.api import AuthContext
from abacus.modules.portal.codes import (
    EarlierKind,
    Facts,
    NoteCode,
    PillCode,
    PillVariant,
    PortalScreen,
    StageCode,
    StageState,
    TeamRoleCode,
    TodoKind,
    TodoState,
)


@dataclass(frozen=True)
class HomeScope:
    """One grant's scope, with the engagements and work items it covers for this person."""

    kind: str
    id: UUID
    client_id: UUID
    engagements: tuple[UUID, ...]
    work_items: tuple[PortalWorkItem, ...]
    today: date


@dataclass(frozen=True)
class Target:
    screen: PortalScreen
    params: dict[str, str] = field(default_factory=dict[str, str])


@dataclass(frozen=True)
class Todo:
    kind: TodoKind
    count: int
    state: TodoState
    due_date: date | None = None
    detail: str | None = None
    facts: Facts = field(default_factory=dict[str, str | int | bool])
    target: Target | None = None


@dataclass(frozen=True)
class Pill:
    code: PillCode
    variant: PillVariant


@dataclass(frozen=True)
class Stage:
    code: StageCode
    state: StageState
    facts: Facts = field(default_factory=dict[str, str | int | bool])


@dataclass(frozen=True)
class WorkCard:
    work_item_id: UUID
    kind: str
    title: str
    pill: Pill
    stages: list[Stage]
    sub: str | None = None
    note_code: NoteCode | None = None
    note_subject: str | None = None
    note_date: date | None = None


@dataclass(frozen=True)
class Binder:
    binder_id: UUID
    done: int
    total: int
    sorted_count: int


@dataclass(frozen=True)
class TeamMember:
    user_id: UUID
    display_name: str
    role_code: TeamRoleCode


@dataclass(frozen=True)
class Earlier:
    kind: EarlierKind
    date: date | None = None
    facts: Facts = field(default_factory=dict[str, str | int | bool])
    target: Target | None = None


@dataclass
class HomePart:
    todos: list[Todo] = field(default_factory=list[Todo])
    work_cards: list[WorkCard] = field(default_factory=list[WorkCard])
    binders: list[Binder] = field(default_factory=list[Binder])
    team: list[TeamMember] = field(default_factory=list[TeamMember])
    earlier: list[Earlier] = field(default_factory=list[Earlier])


HomeSource = Callable[[AuthContext, HomeScope], Awaitable[HomePart]]
_SOURCES: dict[str, HomeSource] = {}


def register_home_source(name: str, source: HomeSource) -> None:
    """One source per module; registering the same name again (a reloaded module) replaces it."""
    _SOURCES[name] = source


def home_sources() -> list[tuple[str, HomeSource]]:
    return sorted(_SOURCES.items())

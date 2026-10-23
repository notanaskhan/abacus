"""What other modules tell the clients family (P-07-T08, T09; ADR-008).

A client's facts live with their owners: its engagements and service lines with engagements, its
open requests with requests. Each owner registers a query over its own tables, and organisations
joins them to its own; it never reads another module's tables. An unregistered fact fails closed:
no service lines, "—" for open requests, no overview section.

- `register_client_engagements`: rows `(client_id, engagement_id, name, status, service_line)`,
  one per non-archived engagement.
- `register_open_requests`: rows `(engagement_id, n)`, open request items per engagement.
- `register_overview_section`: one CLI-02 overview section, shown only to a caller who holds its
  own read action (ADR-024), for the client kinds it names.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import Select

from abacus.modules.identity.api import AuthContext

Profile = Literal["business", "household", "plan_sponsor", "empty"]
SectionKind = Literal["stats", "details", "table", "key_dates", "activity"]
FactQuery = Callable[[], Select[*tuple[Any, ...]]]  # Any: the fact's row shape, named above

_FACTS: dict[str, FactQuery] = {}


def _same(a: object, b: object) -> bool:
    return (getattr(a, "__module__", None), getattr(a, "__qualname__", None)) == (
        getattr(b, "__module__", None),
        getattr(b, "__qualname__", None),
    )


def _register_fact(name: str, query: FactQuery) -> None:
    known = _FACTS.get(name)
    if known is not None and not _same(known, query):
        raise ValueError(f"client fact {name!r} is already registered")
    _FACTS[name] = query


def register_client_engagements(query: FactQuery) -> None:
    _register_fact("engagements", query)


def register_open_requests(query: FactQuery) -> None:
    _register_fact("open_requests", query)


def fact_query(name: str) -> Select[*tuple[Any, ...]] | None:  # Any: the fact's row shape
    """The registered query for a fact, or None (the caller fails closed)."""
    query = _FACTS.get(name)
    return None if query is None else query()


@dataclass(frozen=True)
class OverviewItem:
    """One stat, KV row, table row, key date or activity line. A figure is a decimal string
    computed in code (ADR-050)."""

    key: str
    text: str | None = None
    figure: str | None = None
    on: date | None = None
    at: datetime | None = None
    pill_object: str | None = None
    pill_code: str | None = None
    ref_type: str | None = None
    ref_id: UUID | None = None


@dataclass(frozen=True)
class SectionRows:
    items: list[OverviewItem]
    total: int | None = None


SectionProvider = Callable[[AuthContext, UUID], Awaitable[SectionRows]]


@dataclass(frozen=True)
class OverviewSection:
    code: str
    kind: SectionKind
    read_action: str
    order: int
    provide: SectionProvider
    profiles: frozenset[Profile] = field(
        default_factory=lambda: frozenset({"business", "household", "plan_sponsor"})
    )


_SECTIONS: dict[str, OverviewSection] = {}


def register_overview_section(section: OverviewSection) -> None:
    known = _SECTIONS.get(section.code)
    if known is not None and not _same(known.provide, section.provide):
        raise ValueError(f"overview section {section.code!r} is already registered")
    _SECTIONS[section.code] = section


def overview_sections(profile: Profile) -> list[OverviewSection]:
    return sorted(
        (s for s in _SECTIONS.values() if profile in s.profiles), key=lambda s: (s.order, s.code)
    )

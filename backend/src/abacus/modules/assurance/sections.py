"""The audits cockpit's registration slots (A-01-T02; A-01 §8.1; ADR-106 pattern).

Later epics extend the cockpit without editing A-01: A-02 registers Trial Balance, A-04 the
planning workpapers, A-09 the Group band, X-01 and X-03 their index segments. Three slots:

- `register_audit_section(key, band, order, route, state_provider)`: a rail row (AUD-02, AUD-03).
  The provider answers the row's state for one work item, or `None` to leave the row out. A
  section without a provider cannot be registered, and an unregistered key is never projected, so
  the rail fails closed: it hides a row rather than show a made-up state (A-01 DV-1).
- `register_index_tag(name, provider, classification)`: a tag on AUD-01 rows ("Letter sent Sep 8",
  "EQR · TW"). A `metadata` provider's tags reach metadata-only roles (firm admin,
  `client_service`); a `content` provider's do not (ADR-024, DEC-20).
- `register_audit_segment(family, entitlement)`: an AUD-01 segment. A segment with an entitlement
  renders only for firms that hold it (P-28; DEC-55).

Registering the same thing twice (a reloaded module) replaces itself; a different registration of
a taken key is refused.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from abacus.kernel._statuses import AuditSectionStatus
from abacus.kernel.db import TenantContext

# The rail's bands in their fixed order (AUD-02 spec and revision item 3: Group between Planning
# and Fieldwork, only for group engagements).
Band = Literal["overview", "planning", "group", "fieldwork", "completion", "reporting"]
BANDS: Final[tuple[Band, ...]] = (
    "overview",
    "planning",
    "group",
    "fieldwork",
    "completion",
    "reporting",
)
# AUD-01's segments (A-01 §5.1 `segment=`), in the Segmented's order.
Segment = Literal["fs", "ebp", "review", "soc", "ia"]
SEGMENTS: Final[tuple[Segment, ...]] = ("fs", "ebp", "review", "soc", "ia")
TagClassification = Literal["metadata", "content"]
# How a rail row draws its state: the sub-line of a running engagement run, the idle pill of the
# audit-program grammar, or a plain link row of the Overview band (AUD-02 a and g).
Grammar = Literal["sub_line", "idle_pill", "link"]


@dataclass(frozen=True)
class SectionState:
    """One rail row's state for one work item, by code. `sub_line` is code-built text (a count,
    a time), never model text; `blocked_on_user_id` names the person a decision waits on."""

    state: AuditSectionStatus | None
    grammar: Grammar
    sub_line: str | None = None
    blocked_on_user_id: UUID | None = None


SectionStateProvider = Callable[[TenantContext, UUID], Awaitable[SectionState | None]]


LinkStatus = Literal["live", "planned"]
# Where a section's required action is checked: on the work item's engagement, or on the firm
# (a firm-level read such as `methodology.read`).
ActionScope = Literal["engagement", "firm"]


@dataclass(frozen=True)
class AuditSection:
    key: str
    band: Band
    order: int
    route: str  # a manifest screen ID (AUD-06), resolved by the frontend's `to.<ID>()`
    state_provider: SectionStateProvider
    # A-01-T09 (DEC-312, additive): the rail's words and whether the target screen is built.
    title: str = ""
    link: LinkStatus = "planned"
    # Security review (DEC-312): a provider reads with the tenant's context, so it cannot check
    # the reader's own rights; the cockpit checks this action for the reader before asking it.
    required_action: str | None = None
    action_scope: ActionScope = "engagement"

    @property
    def label(self) -> str:
        """The row's title: the registered one, else the key in words ("Trial balance")."""
        return self.title or self.key.replace("_", " ").capitalize()


@dataclass(frozen=True)
class IndexTag:
    """A tag on an AUD-01 row: a code and its code-built text ("Letter sent Sep 8")."""

    code: str
    text: str


IndexTagProvider = Callable[
    [TenantContext, Sequence[UUID]], Awaitable[Mapping[UUID, Sequence[IndexTag]]]
]


@dataclass(frozen=True)
class IndexTagSource:
    name: str
    provider: IndexTagProvider
    classification: TagClassification


@dataclass(frozen=True)
class AuditSegment:
    family: Segment
    entitlement: str | None


_SECTIONS: dict[str, AuditSection] = {}
_TAGS: dict[str, IndexTagSource] = {}
_SEGMENTS: dict[Segment, AuditSegment] = {}


def _same(a: Callable[..., object], b: Callable[..., object]) -> bool:
    """The same provider, also after its module is reloaded (a new function object)."""
    return (a.__module__, a.__qualname__) == (b.__module__, b.__qualname__)


def register_audit_section(
    key: str,
    band: Band,
    order: int,
    route: str,
    state_provider: SectionStateProvider | None,
    *,
    title: str = "",
    link: LinkStatus = "planned",
    required_action: str | None = None,
    action_scope: ActionScope = "engagement",
) -> None:
    if state_provider is None:
        raise ValueError(f"audit section {key!r} needs a state provider")
    if band not in BANDS:
        raise ValueError(f"band {band!r} is unknown")
    section = AuditSection(
        key, band, order, route, state_provider, title, link, required_action, action_scope
    )
    known = _SECTIONS.get(key)
    if known is not None and (
        (known.band, known.order, known.route, known.title, known.link)
        != (band, order, route, title, link)
        or (known.required_action, known.action_scope) != (required_action, action_scope)
        or not _same(known.state_provider, state_provider)
    ):
        raise ValueError(f"audit section {key!r} is already registered")
    _SECTIONS[key] = section


def registered_sections() -> tuple[AuditSection, ...]:
    """Every registered section in rail order: by band, then by `order`, then by key."""
    return tuple(sorted(_SECTIONS.values(), key=lambda s: (BANDS.index(s.band), s.order, s.key)))


def register_index_tag(
    name: str, provider: IndexTagProvider, classification: TagClassification
) -> None:
    known = _TAGS.get(name)
    if known is not None and (
        known.classification != classification or not _same(known.provider, provider)
    ):
        raise ValueError(f"index tag {name!r} is already registered")
    _TAGS[name] = IndexTagSource(name, provider, classification)


def registered_index_tags(*, metadata_only: bool) -> tuple[IndexTagSource, ...]:
    """The tag sources a viewer may see: only `metadata` ones for a metadata-only role."""
    return tuple(
        t for _, t in sorted(_TAGS.items()) if not metadata_only or t.classification == "metadata"
    )


def register_audit_segment(family: Segment, entitlement: str | None) -> None:
    if family not in SEGMENTS:
        raise ValueError(f"segment {family!r} is unknown")
    known = _SEGMENTS.get(family)
    if known is not None and known.entitlement != entitlement:
        raise ValueError(f"segment {family!r} is already registered")
    _SEGMENTS[family] = AuditSegment(family, entitlement)


def registered_segments(entitlements: frozenset[str]) -> tuple[AuditSegment, ...]:
    """The segments a firm sees, in the Segmented's order: those without an entitlement and
    those whose entitlement the firm holds."""
    return tuple(
        _SEGMENTS[f]
        for f in SEGMENTS
        if f in _SEGMENTS
        and (_SEGMENTS[f].entitlement is None or _SEGMENTS[f].entitlement in entitlements)
    )


# --- The guarded C6 v1 run-summary read (A-01-T08, T09; DV-11) -------------------------------


@dataclass(frozen=True)
class RunSummary:
    """An active C6 v1 engagement run on one work item: the "Processing" pill, its popover and
    the audit bar's "Started 9:24 AM". v1 policy ticks are not engagement runs and never yield
    one."""

    run_id: UUID
    run_number: int
    started_at: datetime
    started_by_user_id: UUID
    started_by_name: str
    workpapers_complete: int
    workpapers_total: int
    blocked_on_role: Literal["partner", "manager"] | None = None


RunSummaryProvider = Callable[
    [TenantContext, Sequence[UUID]], Awaitable[Mapping[UUID, RunSummary]]
]
_run_summary: list[RunSummaryProvider] = []


def register_run_summary(provider: RunSummaryProvider) -> None:
    """P-10's engagement runs register here (C6 v1). Until then no row shows "Processing"."""
    if _run_summary and not _same(_run_summary[0], provider):
        raise ValueError("the run summary provider is already registered")
    _run_summary[:] = [provider]


async def run_summaries(
    tenant: TenantContext, work_item_ids: Sequence[UUID]
) -> Mapping[UUID, RunSummary]:
    """The active engagement runs of these work items, guarded: no provider, or a provider that
    fails, yields none (the pill is never shown from a guess)."""
    if not _run_summary or not work_item_ids:
        return {}
    try:
        return await _run_summary[0](tenant, work_item_ids)
    except Exception:  # a failing C6 read hides the pill, never the index or the cockpit
        return {}

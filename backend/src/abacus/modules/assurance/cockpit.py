"""AUD-02's host projection, live (A-01-T09; SPEC-330 AC-22 to AC-24; DEC-312;
docs/contracts/audits-cockpit.md §3).

The route authorises `engagement.read_metadata` on the work item's engagement (404 outside the
tenant, behind a wall or for another kind of work item, INV-3): the audit bar and the overview
card are metadata. Everything else needs the engagement's content too (`engagement.read`,
probed through `allowed_actions`, ADR-024): the bands, the dock tabs and the actions. A
metadata-only reader (firm admin, `client_service`) gets the bar and the card alone.

**Bands** hold only registered sections (DV-1): each provider is asked for this work item, and
its row is left out when it answers `None` or fails, so the rail hides a row rather than show a
made-up state. Overview is always first; Planning, Fieldwork, Completion and Reporting follow
(an empty one collapsed), Group only on a group audit, and a review, compilation or preparation
has no Planning band (DV-5). **Run**: "Started 9:24 AM" only from a registered C6 v1
engagement-run provider (DV-11). **Archived** work items read `read_only_reason: archived` with
no actions.
"""

from __future__ import annotations

from collections.abc import Awaitable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.logging import get_logger
from abacus.modules.assurance.sections import (
    BANDS,
    AuditSection,
    Band,
    SectionState,
    registered_sections,
    run_summaries,
)
from abacus.modules.engagements.api import assurance_index, assurance_item, get_ref
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
)

READ: Final = "engagement.read_metadata"
CONTENT: Final = "engagement.read"
# The actions the cockpit offers (contract §3), for a content reader on a live work item.
ACTIONS: Final = ("assurance.record_phase", "engagement.update", "export.create", "agent.pause")
_NO_PLANNING: Final = frozenset({"review", "compilation", "preparation"})
_log = get_logger(__name__)


@dataclass(frozen=True)
class SectionRow:
    key: str
    title: str
    work_item_ref: UUID
    section_state: str | None
    grammar: str
    sub_line: str | None
    route: str
    link: str
    blocked_on_user_id: UUID | None = None
    blocked_on_name: str | None = None
    allowed_actions: list[str] = field(default_factory=list[str])


@dataclass(frozen=True)
class BandView:
    key: Band
    collapsed: bool
    rows: list[SectionRow]


@dataclass(frozen=True)
class AuditBar:
    title: str
    methodology_label: str | None
    run_started_at: datetime | None
    auto_mode: bool | None = None


@dataclass(frozen=True)
class Overview:
    client_id: UUID
    client_name: str
    name: str
    period_label: str | None
    phase: str


@dataclass(frozen=True)
class Cockpit:
    work_item_id: UUID
    engagement_id: UUID
    audit_bar: AuditBar
    overview: Overview
    bands: list[BandView]
    dock_tabs: list[str]
    phase_mode: str
    read_only_reason: str | None
    version: int
    allowed_actions: list[str]


async def _state(key: str, provider_call: Awaitable[SectionState | None]) -> SectionState | None:
    """A provider's answer; one that fails leaves its row out (fail closed), logged by key."""
    try:
        found = await provider_call
    except Exception:  # a failing provider hides its row, never the cockpit
        _log.warning("audits.section_provider_failed", section=key)
        return None
    return found if isinstance(found, SectionState) else None


def _scoped(sections: Sequence[AuditSection], action: str, scope: str) -> bool:
    return any(s.required_action == action and s.action_scope == scope for s in sections)


def refuse_non_firm(ctx: AuthContext, action: str) -> None:
    """INV-4 and the security review (DEC-312): a client principal holds
    `engagement.read_metadata` cells (SPEC-020), so the read models refuse client principals,
    agents and the system themselves, not only their routes."""
    if ctx.client or ctx.tenant.actor_kind != "human":
        raise Forbidden(action, "role")


async def audit_cockpit(ctx: AuthContext, work_item_id: UUID) -> Cockpit:
    refuse_non_firm(ctx, READ)
    item = await assurance_item(ctx.tenant, work_item_id)
    ref = await get_ref(ctx, item.engagement_id)
    resource = ref.resource()
    await authorise(ctx, READ, resource)
    can = await allowed_actions(ctx, resource, (CONTENT, *ACTIONS))
    content = CONTENT in can
    a = assurance_index()
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(select(a).where(a.c.work_item_id == work_item_id))).first()
    if row is None:
        raise NotFound("audit")
    archived = (
        ref.archived
        or row.status == "archived"
        or row.work_item_status == "archived"
        or row.archived_at is not None
        or row.archive_locked_at is not None
    )
    methodology: str | None = None
    bands: list[BandView] = []
    if content:
        rows: dict[Band, list[SectionRow]] = {}
        sections = registered_sections()
        needed = {s.required_action for s in sections if s.required_action}
        on_engagement = await allowed_actions(
            ctx, resource, sorted(a for a in needed if _scoped(sections, a, "engagement"))
        )
        on_firm = await allowed_actions(
            ctx,
            Resource.firm(ctx.tenant_id),
            sorted(a for a in needed if _scoped(sections, a, "firm")),
        )
        for section in sections:
            if section.required_action is not None and section.required_action not in (
                on_firm if section.action_scope == "firm" else on_engagement
            ):
                continue  # the reader may not see what the provider would read
            state = await _state(section.key, section.state_provider(ctx.tenant, work_item_id))
            if state is None:
                continue
            if section.key == "methodology":
                methodology = state.sub_line
            rows.setdefault(section.band, []).append(
                SectionRow(
                    key=section.key,
                    title=section.label,
                    work_item_ref=work_item_id,
                    section_state=None if state.state is None else str(state.state),
                    grammar=state.grammar,
                    sub_line=state.sub_line,
                    route=section.route,
                    link=section.link,
                    blocked_on_user_id=state.blocked_on_user_id,
                )
            )
        for band in BANDS:
            if band == "group" and not row.is_group_audit and not rows.get(band):
                continue
            if band == "planning" and row.type in _NO_PLANNING and not rows.get(band):
                continue
            found = rows.get(band, [])
            bands.append(BandView(band, band in ("completion", "reporting") and not found, found))
    run = (await run_summaries(ctx.tenant, [work_item_id])).get(work_item_id) if content else None
    phase = "released" if row.phase in ("archiving", "archived") else row.phase
    return Cockpit(
        work_item_id=work_item_id,
        engagement_id=item.engagement_id,
        audit_bar=AuditBar(
            title=row.title,
            methodology_label=methodology,
            run_started_at=run.started_at if run is not None else None,
        ),
        overview=Overview(row.client_id, row.client_name, row.name, row.period_label, phase),
        bands=bands,
        dock_tabs=["agent", "viewer"] if content else [],
        phase_mode=row.phase_source,
        read_only_reason="archived" if archived else None,
        version=item.version,
        allowed_actions=[] if archived or not content else sorted(set(ACTIONS) & can),
    )

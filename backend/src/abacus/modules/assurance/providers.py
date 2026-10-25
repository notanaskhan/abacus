"""A-01's own cockpit rows and index tags, registered through the slots like any later epic's
(A-01-T09; SPEC-330 AC-22, AC-23; DEC-312; docs/screens/AUD-02.md "overview.rows").

Overview band (link rows, no state): Client ("Northwind Robotics, Inc."), Methodology (the pinned
methodology version, hidden while none is pinned), Standards set (hidden until K-01/K-02 name the
work item's standards set), Source Documents ("11 of 24 received", the same counts as AUD-01's
PBC and the canvas), Team ("MO · TW · HL · MD · AC", in role order), Activity.

Index tags (all `metadata`, so a firm admin sees them, ADR-024): "Letter sent Sep 8" while the
recorded letter is out and unsigned (G3 unmet), "EQR · TW" from In review on (the reviewer's
concurrence, G6, is what Ready to release waits on), and "No report" on a released preparation
engagement (AR-C 70 issues none). Every text is built by code from stored facts.

A provider answers for work items its caller has already read; each reads under the tenant's
own session (RLS).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, Final
from uuid import UUID

from sqlalchemy import Row, select

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.assurance.sections import (
    IndexTag,
    LinkStatus,
    SectionState,
    SectionStateProvider,
    register_audit_section,
    register_index_tag,
)
from abacus.modules.engagements.api import assurance_index, letters_sent, version_detail
from abacus.modules.identity.api import EQR_ROLES, engagement_team_query, names_of
from abacus.modules.requests.api import pbc_counts_of

# Team row order (AUD-02 "MO · TW · HL · MD · AC"): partner, quality reviewer, manager, senior,
# staff.
TEAM_ORDER: Final = ("engagement_partner", "reviewer", "manager", "senior", "staff")
_FROM_IN_REVIEW: Final = frozenset(
    {"in_review", "completion", "ready_to_release", "released", "archiving", "archived"}
)
_RELEASED: Final = frozenset({"released", "archiving", "archived"})


def initials(name: str) -> str:
    return "".join(part[0] for part in name.split() if part[:1].isalpha())[:3].upper()


def month_day(on: date) -> str:
    """ "Sep 8"."""
    return f"{on:%b} {on.day}"


async def _facts(
    tenant: TenantContext, work_item_ids: Sequence[UUID]
) -> dict[UUID, Row[Any]]:  # Any: the assurance index's columns
    a = assurance_index()
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(select(a).where(a.c.work_item_id.in_(list(work_item_ids))))
        ).all()
    return {r.work_item_id: r for r in rows}


async def _one(
    tenant: TenantContext, work_item_id: UUID
) -> Row[Any] | None:  # Any: the assurance index's columns
    return (await _facts(tenant, [work_item_id])).get(work_item_id)


async def _team(tenant: TenantContext, engagement_ids: Sequence[UUID]) -> dict[UUID, list[str]]:
    """Each engagement's team as initials in TEAM_ORDER (a person once, at their first role)."""
    team = engagement_team_query().subquery("team")
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                select(team.c.engagement_id, team.c.user_id, team.c.role).where(
                    team.c.engagement_id.in_(list(engagement_ids))
                )
            )
        ).all()
    names = await names_of(sorted({r.user_id for r in rows})) if rows else {}
    rank = {role: n for n, role in enumerate(TEAM_ORDER)}
    out: dict[UUID, list[str]] = {}
    seen: dict[UUID, set[UUID]] = {}
    for r in sorted(rows, key=lambda r: (rank.get(r.role, len(rank)), names.get(r.user_id, ""))):
        if r.user_id in seen.setdefault(r.engagement_id, set()) or r.user_id not in names:
            continue
        seen[r.engagement_id].add(r.user_id)
        out.setdefault(r.engagement_id, []).append(initials(names[r.user_id]))
    return out


async def _reviewers(
    tenant: TenantContext, engagement_ids: Sequence[UUID]
) -> dict[UUID, list[str]]:
    team = engagement_team_query().subquery("reviewers")
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                select(team.c.engagement_id, team.c.user_id).where(
                    team.c.engagement_id.in_(list(engagement_ids)), team.c.role.in_(EQR_ROLES)
                )
            )
        ).all()
    names = await names_of(sorted({r.user_id for r in rows})) if rows else {}
    out: dict[UUID, list[str]] = {}
    for r in rows:
        if r.user_id in names:
            out.setdefault(r.engagement_id, []).append(initials(names[r.user_id]))
    return {e: sorted(v) for e, v in out.items()}


# --- Overview rows ------------------------------------------------------------------------------


async def client_row(tenant: TenantContext, work_item_id: UUID) -> SectionState | None:
    found = await _one(tenant, work_item_id)
    if found is None:
        return None
    return SectionState(None, "link", sub_line=found.client_name)


async def methodology_row(tenant: TenantContext, work_item_id: UUID) -> SectionState | None:
    found = await _one(tenant, work_item_id)
    pinned = found.methodology_version_id if found is not None else None
    if pinned is None:
        return None
    try:
        view = await version_detail(tenant, pinned)
    except NotFound:
        return None
    return SectionState(
        None, "link", sub_line=f"{view.summary.template_name} · v{view.summary.version}"
    )


async def standards_set_row(tenant: TenantContext, work_item_id: UUID) -> SectionState | None:
    """Hidden until K-01/K-02 give a standards set a name ("GAAS nonissuer · AU-C 703"); an id
    alone is never shown."""
    del tenant, work_item_id
    return None


async def source_documents_row(tenant: TenantContext, work_item_id: UUID) -> SectionState | None:
    counts = (await pbc_counts_of(tenant, [work_item_id])).get(work_item_id)
    line = None if counts is None else f"{counts[0]} of {counts[1]} received"
    return SectionState(None, "link", sub_line=line)


async def team_row(tenant: TenantContext, work_item_id: UUID) -> SectionState | None:
    found = await _one(tenant, work_item_id)
    if found is None:
        return None
    engagement = found.engagement_id
    people = (await _team(tenant, [engagement])).get(engagement, [])
    return SectionState(None, "link", sub_line=" · ".join(people) or None)


async def activity_row(tenant: TenantContext, work_item_id: UUID) -> SectionState | None:
    del tenant, work_item_id
    return SectionState(None, "link")


# --- Index tags ---------------------------------------------------------------------------------


async def letter_sent_tags(
    tenant: TenantContext, work_item_ids: Sequence[UUID]
) -> Mapping[UUID, Sequence[IndexTag]]:
    facts = await _facts(tenant, work_item_ids)
    by_engagement = {r.engagement_id: wid for wid, r in facts.items()}
    sent = await letters_sent(tenant, list(by_engagement))
    return {
        by_engagement[e]: [IndexTag("letter_sent", f"Letter sent {month_day(on)}")]
        for e, on in sent.items()
    }


async def eqr_tags(
    tenant: TenantContext, work_item_ids: Sequence[UUID]
) -> Mapping[UUID, Sequence[IndexTag]]:
    facts = {
        wid: r
        for wid, r in (await _facts(tenant, work_item_ids)).items()
        if r.phase in _FROM_IN_REVIEW
    }
    by_engagement = {r.engagement_id: wid for wid, r in facts.items()}
    reviewers = await _reviewers(tenant, list(by_engagement)) if by_engagement else {}
    return {
        by_engagement[e]: [IndexTag("eqr", f"EQR · {' · '.join(people)}")]
        for e, people in reviewers.items()
        if people
    }


async def no_report_tags(
    tenant: TenantContext, work_item_ids: Sequence[UUID]
) -> Mapping[UUID, Sequence[IndexTag]]:
    return {
        wid: [IndexTag("no_report", "No report")]
        for wid, r in (await _facts(tenant, work_item_ids)).items()
        if r.type == "preparation" and r.phase in _RELEASED
    }


def register() -> None:
    """A-01's rows and tags (api.py calls this once; a reload replaces itself)."""
    overview: tuple[tuple[str, str, str, LinkStatus, SectionStateProvider], ...] = (
        ("client", "Client", "CLI-02", "live", client_row),
        ("methodology", "Methodology", "KNW-03", "planned", methodology_row),
        ("standards_set", "Standards set", "KNW-04", "planned", standards_set_row),
        ("source_documents", "Source Documents", "AUD-03", "planned", source_documents_row),
        ("team", "Team", "ENG-05", "planned", team_row),
        ("activity", "Activity", "AUD-29", "planned", activity_row),
    )
    for order, (key, title, route, link, provider) in enumerate(overview):
        # The pinned methodology's name is firm content: shown only to a reader of it.
        needs = "methodology.read" if key == "methodology" else None
        register_audit_section(
            key,
            "overview",
            order,
            route,
            provider,
            title=title,
            link=link,
            required_action=needs,
            action_scope="firm" if needs else "engagement",
        )
    register_index_tag("letter_sent", letter_sent_tags, "metadata")
    register_index_tag("eqr", eqr_tags, "metadata")
    register_index_tag("no_report", no_report_tags, "metadata")

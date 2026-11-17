"""The group audit's host registrations (A-09-T30; A-09 §3.1, §5; AUD-01, AUD-02 h, AUD-06 g,
ENG-03 g; DEC-5408; amber).

Under the `group_audit` capability (the entitlement and both flags) and only for a work item
ENG-03 g made a group audit, AUD-02's Group band shows three rows in order (revision h):
Structure (AUD-32 and its eliminations, "5 entities · finalized"), Scoping (AUD-34, "Group
materiality 240,000 · decided 3:40 PM"), Component auditors (AUD-35, "Pruett & Lang LLP ·
questionnaire received Sep 10");
AUD-01 tags a group row ("Group · 4 components") and its component auditors ("Component auditor
· Pruett & Lang LLP"). With the capability off, or on any other work item, every provider
answers nothing, so every live screen renders exactly as before. AUD-06 g's entity strip is the
consolidation's entities with their current TB state (code's, no figures).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal
from uuid import UUID

from sqlalchemy import Row, select, text

from abacus.kernel._statuses import AuditSectionStatus
from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.assurance.sections import (
    IndexTag,
    SectionState,
    register_audit_section,
    register_index_tag,
)

# AUD-02 revision h: three rows (Structure covers AUD-32 and AUD-33's eliminations).
GROUP_SECTIONS: Final = (
    ("group_structure", "Structure", "AUD-32"),
    ("group_scoping", "Scoping", "AUD-34"),
    ("component_auditors", "Component auditors", "AUD-35"),
)


async def _group_item(tenant: TenantContext, work_item_id: UUID) -> Row[Any] | None:  # Any: index
    from abacus.modules.engagements.api import assurance_index
    from abacus.modules.platform.api import group_audit_on

    if not await group_audit_on(tenant):
        return None
    a = assurance_index()
    async with tenant_session(tenant) as session:
        row = (await session.execute(select(a).where(a.c.work_item_id == work_item_id))).first()
    return row if row is not None and row.is_group_audit else None


async def _consolidation(tenant: TenantContext, work_item_id: UUID) -> object | None:
    from abacus.modules.ledger import api as ledger

    for consolidation_id in await ledger.consolidations_of(tenant, work_item_id):
        facts = await ledger.consolidation_facts(tenant, consolidation_id)
        if facts.status != "discarded":
            return facts
    return None


def _time(at: datetime | None) -> str:
    return "" if at is None else f"{at:%-I:%M %p}"


async def structure_row(tenant: TenantContext, work_item_id: UUID) -> SectionState | None:
    if await _group_item(tenant, work_item_id) is None:
        return None
    facts = await _consolidation(tenant, work_item_id)
    if facts is None:
        return SectionState(AuditSectionStatus.NOT_STARTED, "idle_pill")
    status = getattr(facts, "status", "draft")
    locked = getattr(facts, "lock_state", "open") == "locked"
    if locked:
        return SectionState(AuditSectionStatus.LOCKED, "sub_line", "Locked")
    entities = len(getattr(facts, "entities", ()))
    if status == "finalized":
        return SectionState(
            AuditSectionStatus.SIGNED_OFF, "sub_line", f"{entities} entities · finalized"
        )
    return SectionState(AuditSectionStatus.IN_PROGRESS, "sub_line", f"{entities} entities")


_DECIDED: Final = text(
    "SELECT overall, created_at FROM materiality_versions WHERE work_item_id = :w "
    "AND scope = 'group' AND status IN ('decided', 'revised') ORDER BY version_no DESC LIMIT 1"
)


async def scoping_row(tenant: TenantContext, work_item_id: UUID) -> SectionState | None:
    if await _group_item(tenant, work_item_id) is None:
        return None
    async with tenant_session(tenant) as session:
        decided = (await session.execute(_DECIDED, {"w": work_item_id})).first()
    if decided is None:
        return SectionState(AuditSectionStatus.BLOCKED_ON_DECISION, "sub_line", "Materiality")
    return SectionState(
        AuditSectionStatus.SIGNED_OFF,
        "sub_line",
        f"Group materiality {decided.overall:,.0f} · decided {_time(decided.created_at)}",
    )


_AUDITORS: Final = text(
    "SELECT a.organisation_name, a.questionnaire_received_on, i.status "
    "FROM component_auditors a LEFT JOIN "
    "component_instructions i ON i.component_auditor_id = a.id WHERE a.work_item_id = :w "
    "ORDER BY a.created_at"
)


async def component_auditors_row(tenant: TenantContext, work_item_id: UUID) -> SectionState | None:
    if await _group_item(tenant, work_item_id) is None:
        return None
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_AUDITORS, {"w": work_item_id})).all()
    if not rows:
        return SectionState(AuditSectionStatus.NOT_STARTED, "idle_pill")
    acknowledged = sum(1 for r in rows if r.status == "acknowledged")
    return SectionState(
        AuditSectionStatus.SIGNED_OFF
        if acknowledged == len(rows)
        else AuditSectionStatus.IN_PROGRESS,
        "sub_line",
        f"{acknowledged} of {len(rows)} acknowledged",
    )


_PROVIDERS: Final = {
    "group_structure": structure_row,
    "group_scoping": scoping_row,
    "component_auditors": component_auditors_row,
}


# --- AUD-01 tags ---------------------------------------------------------------------------------


async def group_tags(
    tenant: TenantContext, work_item_ids: Sequence[UUID]
) -> Mapping[UUID, Sequence[IndexTag]]:
    """'Group · 4 components' on a group audit's row (capability on only)."""
    from abacus.modules.engagements.api import assurance_index
    from abacus.modules.platform.api import group_audit_on

    if not work_item_ids or not await group_audit_on(tenant):
        return {}
    a = assurance_index()
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                select(a.c.work_item_id).where(
                    a.c.work_item_id.in_(list(work_item_ids)), a.c.is_group_audit.is_(True)
                )
            )
        ).all()
        counts = {
            r.work_item_id: int(r.n)
            for r in await session.execute(
                text(
                    "SELECT work_item_id, count(*) AS n FROM components "
                    "WHERE work_item_id = ANY(:w) GROUP BY work_item_id"
                ),
                {"w": [r.work_item_id for r in rows]},
            )
        }
    return {
        r.work_item_id: [
            IndexTag(
                "group",
                f"Group · {counts.get(r.work_item_id, 0)} components"
                if counts.get(r.work_item_id)
                else "Group",
            )
        ]
        for r in rows
    }


async def component_auditor_tags(
    tenant: TenantContext, work_item_ids: Sequence[UUID]
) -> Mapping[UUID, Sequence[IndexTag]]:
    """'Component auditor · Pruett & Lang LLP' for each component auditor on the row."""
    from abacus.modules.platform.api import group_audit_on

    if not work_item_ids or not await group_audit_on(tenant):
        return {}
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT work_item_id, organisation_name FROM component_auditors "
                    "WHERE work_item_id = ANY(:w) ORDER BY created_at"
                ),
                {"w": list(work_item_ids)},
            )
        ).all()
    out: dict[UUID, list[IndexTag]] = {}
    for r in rows:
        out.setdefault(r.work_item_id, []).append(
            IndexTag("component_auditor", f"Component auditor · {r.organisation_name}")
        )
    return out


# --- AUD-06 g: the entity strip ------------------------------------------------------------------


@dataclass(frozen=True)
class StripEntity:
    consolidation_entity_id: UUID
    client_entity_id: UUID
    name: str
    level: int
    tb_state: Literal["attached", "missing", "not_needed", "needs_reauth"]


async def entity_strip(tenant: TenantContext, work_item_id: UUID) -> list[StripEntity]:
    """The group's entities in structure order with their current-period TB state (code's)."""
    from abacus.modules.organisations.api import client_names

    if await _group_item(tenant, work_item_id) is None:
        return []
    facts = await _consolidation(tenant, work_item_id)
    if facts is None:
        return []
    entities = list(getattr(facts, "entities", ()))
    slots = list(getattr(facts, "slots", ()))
    async with tenant_session(tenant) as session:
        names = await client_names(session, [e.client_entity_id for e in entities])
    out: list[StripEntity] = []
    for e in sorted(entities, key=lambda e: (e.level, e.position)):
        current = [
            s
            for s in slots
            if s.key.consolidation_entity_id == e.id and s.key.period_kind == "current"
        ]
        state = current[0].state if current else "missing"
        out.append(
            StripEntity(
                e.id,
                e.client_entity_id,
                names[e.client_entity_id].client_entity_name
                if e.client_entity_id in names
                else "",
                e.level,
                state,
            )
        )
    return out


def register() -> None:
    """At import (assurance/api.py): the Group band rows and the AUD-01 tags."""
    for order, (key, title, route) in enumerate(GROUP_SECTIONS):
        register_audit_section(
            key,
            "group",
            order,
            route,
            _PROVIDERS[key],
            title=title,
            link="live",
            required_action="group_scoping.read",
        )
    register_index_tag("group", group_tags, "metadata")
    register_index_tag("component_auditor", component_auditor_tags, "metadata")

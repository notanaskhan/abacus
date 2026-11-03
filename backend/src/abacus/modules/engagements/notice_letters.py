"""QN-1: how G3 is met for a `notice_response` engagement (N-04-T08; N-04 §11 R3; DEC-2205).

A notice lives under one `notice_response` engagement per client entity, created at the first
notice. A separate signed letter per notice would stall intake, so G3 for such an engagement is
met by its own signed letter **or** by the client's current tax engagement letter whose clause
set includes `notice_support` (ENG-04's clause library is database content; the clause is on when
the signed version says so, or by the template's default). This module answers which tax
engagements' signed letters cover the notice engagement; the G3 provider (signatures) checks
that each one's letter itself meets G3. Never a model's judgment, never the agent's.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.letters import clause_defs, clause_views
from abacus.modules.methodology.api import report_template_parts

NOTICE_TYPE: Final = "notice_response"
COVERING_TYPES: Final = frozenset({"tax_compliance"})
CLAUSE: Final = "notice_support"

_NOTICE = text(
    "SELECT type, client_id, client_entity_id FROM engagements WHERE id = :id AND tenant_id = :t"
)
# The client entity's other tax engagements, newest period first, with their signed versions.
_COVERING = text(
    "SELECT e.id, v.template_version_id, v.clause_states FROM engagements e "
    "JOIN engagement_letter_versions v ON v.tenant_id = e.tenant_id AND v.engagement_id = e.id "
    "WHERE e.tenant_id = :t AND e.id <> :id AND e.client_entity_id = :entity "
    "AND e.type = ANY(:types) AND v.status = 'signed' "
    "ORDER BY e.fiscal_period_end DESC, v.version_no DESC"
)


async def covering_letter_engagements(tenant: TenantContext, engagement_id: UUID) -> list[UUID]:
    """The tax engagements whose signed letter includes `notice_support`, for a
    `notice_response` engagement; empty for any other type (their G3 is their own letter)."""
    async with tenant_session(tenant) as session:
        found = (
            (await session.execute(_NOTICE, {"id": engagement_id, "t": tenant.tenant_id}))
            .mappings()
            .one_or_none()
        )
        if found is None or found["type"] != NOTICE_TYPE:
            return []
        rows = (
            (
                await session.execute(
                    _COVERING,
                    {
                        "t": tenant.tenant_id,
                        "id": engagement_id,
                        "entity": found["client_entity_id"],
                        "types": sorted(COVERING_TYPES),
                    },
                )
            )
            .mappings()
            .all()
        )
        out: list[UUID] = []
        for row in rows:
            if row["id"] in out:
                continue
            parts = await report_template_parts(session, cast(UUID, row["template_version_id"]))
            if parts is None:
                continue
            states = cast(Mapping[str, str], row["clause_states"])
            views = clause_views(clause_defs(parts), states)
            if any(v.key == CLAUSE and v.state != "off" for v in views):
                out.append(cast(UUID, row["id"]))
        return out


async def notice_engagement(tenant: TenantContext, client_entity_id: UUID) -> UUID | None:
    """N-04-T07 (QN-1): the client entity's `notice_response` engagement, the newest if several."""
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text(
                "SELECT id FROM engagements WHERE tenant_id = :t AND client_entity_id = :entity "
                "AND type = 'notice_response' ORDER BY fiscal_period_end DESC LIMIT 1"
            ),
            {"t": tenant.tenant_id, "entity": client_entity_id},
        )
    return cast(UUID | None, found)

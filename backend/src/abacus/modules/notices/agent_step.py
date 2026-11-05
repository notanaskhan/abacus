"""The notice analysis's agent step (N-04-T19; N-04 §6; DEC-2313): code's facts to the responder.

Registered at import. A refused step leaves the code analysis standing ("Analysis by code only").
The responder's stage decides what shows: `shadow` records and shows nothing, and only `live`
returns a recommendation (`analysis._agent_step` enforces it).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.ai_gateway.context import DataSubject
from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.agents.api import AnalyzeFacts, analyze_notice
from abacus.modules.notices.analysis import AgentStep

OPTIONS: Final = ("agree", "partial", "disagree")
_JOINT: Final = frozenset({"mfj", "married_filing_jointly", "married_joint", "joint"})
JsonRow = dict[str, Any]  # Any: the analysis's JSON


async def _subjects(
    tenant: TenantContext, notice_id: UUID
) -> tuple[UUID, tuple[DataSubject, ...]]:
    """The notice's taxpayer. A joint return's spouse joins with T-01's return parties: until
    then a
    joint notice's second consent is the gateway's refusal, never skipped (`entity_id` None
    fails)."""
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT n.engagement_id, n.client_entity_id, n.tax_year, s.filing_status "
                    "FROM notices n LEFT JOIN LATERAL (SELECT filing_status FROM "
                    "notice_return_snapshots r WHERE r.work_item_id = n.work_item_id "
                    "ORDER BY r.created_at DESC, r.id DESC LIMIT 1) s ON true "
                    "WHERE n.work_item_id = :w"
                ),
                {"w": notice_id},
            )
        ).one()
    subjects = [DataSubject(row.client_entity_id, row.tax_year)]
    if (row.filing_status or "").lower() in _JOINT:
        subjects.append(DataSubject(None, row.tax_year))
    return row.engagement_id, tuple(subjects)


def _handles(rows: Sequence[JsonRow]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (str(r["citation"]), str(r.get("label", ""))) for r in rows if r.get("citation")
    )  # fmt: skip


async def step(
    tenant: TenantContext,
    notice_id: UUID,
    facts: dict[str, Any],  # Any: JSON
) -> AgentStep:
    engagement_id, subjects = await _subjects(tenant, notice_id)
    rows = cast("list[JsonRow]", facts.get("rows", []))
    result = await analyze_notice(
        tenant,
        engagement_id=engagement_id,
        initiator=cast(UUID, facts["initiator"]),
        facts=AnalyzeFacts(
            tuple(rows),
            tuple(cast("list[JsonRow]", facts.get("checks", []))),
            tuple(cast("list[JsonRow]", facts.get("information_returns", []))),
            OPTIONS,
            _handles(rows),
        ),
        subjects=subjects,
    )
    return AgentStep(result.stage, result.run_id, result.recommended)

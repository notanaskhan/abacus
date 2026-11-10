"""C13 source for a notice response ready to go (I-01-T23; N-04 US-8.2): HOME-02's sends.

The position's decision card and the response's sign-offs reach Home through review's own sources;
what's left is the send: approved, with no envelope yet. A row is a link to NOT-02; a person sends
from there.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.identity.api import AuthContext
from abacus.modules.review.api import (
    GateFacts,
    GateSource,
    GateView,
    OpenGate,
    register_gate_presenter,
    register_gate_source,
)

SUBJECT: Final = "notice_response_send"
_EVENTS: Final = frozenset({"notice_response.ready_to_send", "notice.response_sent"})


async def sends_due(tenant: TenantContext, engagement_id: UUID | None) -> list[OpenGate]:
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT r.id, n.engagement_id, n.assignee_user_id, n.respond_by, "
                    "n.work_item_id FROM notice_responses r "
                    "JOIN notices n ON n.work_item_id = r.work_item_id "
                    "WHERE n.status = 'approved' AND r.envelope_id IS NULL "
                    "AND (CAST(:e AS uuid) IS NULL OR n.engagement_id = :e)"
                ),
                {"e": engagement_id},
            )
        ).all()
    return [
        OpenGate(
            r.id,
            r.engagement_id,
            assignee_user_id=r.assignee_user_id,
            due_on=r.respond_by,
            work_item_id=r.work_item_id,
        )
        for r in rows
    ]


async def present_sends(ctx: AuthContext, rows: Sequence[GateView]) -> Mapping[UUID, GateFacts]:
    async with tenant_session(ctx.tenant) as session:
        found = {
            r.id: r
            for r in (
                await session.execute(
                    text(
                        "SELECT r.id, r.work_item_id, n.notice_code, n.tax_year "
                        "FROM notice_responses r "
                        "JOIN notices n ON n.work_item_id = r.work_item_id "
                        "WHERE r.id = ANY(:ids)"
                    ),
                    {"ids": [row.subject_id for row in rows]},
                )
            ).all()
        }
    out: dict[UUID, GateFacts] = {}
    for row in rows:
        hit = found.get(row.subject_id)
        if hit is None:
            continue
        year = "" if hit.tax_year is None else f" · TY{hit.tax_year}"
        out[row.id] = GateFacts(
            title=f"Send the {hit.notice_code} response{year}",
            subject_route=f"NOT-02?noticeId={hit.work_item_id}",
        )
    return out


def register_notice_gates() -> None:
    register_gate_source(GateSource(SUBJECT, "send", "notice.read", _EVENTS, sends_due))
    register_gate_presenter(SUBJECT, present_sends)

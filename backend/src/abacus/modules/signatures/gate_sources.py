"""C13 sources for envelopes (I-01-T23; N-02 hand-off to I-01): what HOME-01 and HOME-02 list.

`envelope_send` waits on whoever may send a draft; `envelope_countersign` waits on the named firm
countersigner once every client has signed. The same conditions as the gate kinds in
`countersign.py`, as rows. A row is a link to SIG-01; a person sends or countersigns there. An
envelope with no engagement stays off the queue (the projection reads by engagement).
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
from abacus.modules.signatures.countersign import COUNTERSIGN_GATE, SEND_GATE

_EVENTS: Final = frozenset(
    {
        "envelope.drafted",
        "envelope.send_approved",
        "envelope.signer_signed",
        "envelope.completed",
        "envelope.superseded",
        "envelope.declined",
        "envelope.expired",
    }
)
_ROUTE: Final = "SIG-01"
_READ: Final = "envelope.read"


async def sends_due(tenant: TenantContext, engagement_id: UUID | None) -> list[OpenGate]:
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, engagement_id, client_id FROM envelopes WHERE status = 'draft' "
                    "AND superseded_at IS NULL AND engagement_id IS NOT NULL "
                    "AND (CAST(:e AS uuid) IS NULL OR engagement_id = :e)"
                ),
                {"e": engagement_id},
            )
        ).all()
    return [OpenGate(r.id, r.engagement_id, client_id=r.client_id) for r in rows]


async def countersigns_due(tenant: TenantContext, engagement_id: UUID | None) -> list[OpenGate]:
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT e.id, e.engagement_id, e.client_id, s.user_id FROM envelopes e "
                    "JOIN envelope_signers s ON s.envelope_id = e.id "
                    "AND s.party_kind = 'user' AND s.role = 'countersigner' "
                    "AND s.status <> 'signed' "
                    "WHERE e.status IN ('sent', 'viewed', 'partially_signed') "
                    "AND e.superseded_at IS NULL AND e.engagement_id IS NOT NULL "
                    "AND (CAST(:e AS uuid) IS NULL OR e.engagement_id = :e) "
                    "AND NOT EXISTS (SELECT 1 FROM envelope_signers c WHERE c.envelope_id = e.id "
                    "AND c.party_kind = 'contact' AND c.status <> 'signed')"
                ),
                {"e": engagement_id},
            )
        ).all()
    return [
        OpenGate(r.id, r.engagement_id, assignee_user_id=r.user_id, client_id=r.client_id)
        for r in rows
    ]


def _title(subkind: str, number: int, title: str) -> str:
    verb = "Send" if subkind == SEND_GATE else "Countersign"
    return f"{verb} E{number} · {title}"


async def present_envelopes(
    ctx: AuthContext, rows: Sequence[GateView]
) -> Mapping[UUID, GateFacts]:
    """Rows are already walled by the projection (P-04); the title is the envelope's own."""
    async with tenant_session(ctx.tenant) as session:
        found = {
            r.id: r
            for r in (
                await session.execute(
                    text("SELECT id, number, title FROM envelopes WHERE id = ANY(:ids)"),
                    {"ids": [row.subject_id for row in rows]},
                )
            ).all()
        }
    return {
        row.id: GateFacts(
            title=_title(
                row.subject_type, found[row.subject_id].number, found[row.subject_id].title
            ),
            subject_route=_ROUTE,
        )
        for row in rows
        if row.subject_id in found
    }


def register_envelope_gates() -> None:
    register_gate_source(GateSource(SEND_GATE, "send", _READ, _EVENTS, sends_due))
    register_gate_source(
        GateSource(
            COUNTERSIGN_GATE,
            "sign_off_request",
            _READ,
            _EVENTS,
            countersigns_due,
            assigned_only=True,
        )
    )
    register_gate_presenter(SEND_GATE, present_envelopes)
    register_gate_presenter(COUNTERSIGN_GATE, present_envelopes)

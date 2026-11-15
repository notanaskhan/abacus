"""C13 source for an instrument interpretation waiting on its L3 approval (T-07-T03 part,
TASK-8069; T-07 §4.8; SPEC-656 AC-4.1): HOME-02's `instrument_interpretation_approval` row.

A person's L1 write adopts the interpretation; until the manager's L3 sign-off approves it (or a
reopen sends it back), one gate waits on the engagement's managers. The row links to TXT-01's
sign-off overlay; identifiers and the form only, never a determination's value.
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

SUBJECT: Final = "instrument_interpretation_approval"
_EVENTS: Final = frozenset(
    {
        "instrument_interpretation.adopted",
        "instrument_interpretation.approved",
        "instrument_interpretation.reopened",
    }
)
_DUE: Final = text(
    "SELECT id, engagement_id, work_item_id FROM instrument_interpretations "
    "WHERE status = 'adopted' AND superseded_at IS NULL "
    "AND (CAST(:e AS uuid) IS NULL OR engagement_id = :e)"
)
_FACTS: Final = text(
    "SELECT i.id, i.work_item_id, r.form, r.tax_year FROM instrument_interpretations i "
    "JOIN tax_returns r ON r.work_item_id = i.work_item_id WHERE i.id = ANY(:ids)"
)


async def approvals_due(tenant: TenantContext, engagement_id: UUID | None) -> list[OpenGate]:
    """Current interpretations at Adopted: the manager's L3 is next (DEC-84)."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_DUE, {"e": engagement_id})).all()
    return [
        OpenGate(r.id, r.engagement_id, role="manager", work_item_id=r.work_item_id) for r in rows
    ]


async def present(ctx: AuthContext, rows: Sequence[GateView]) -> Mapping[UUID, GateFacts]:
    async with tenant_session(ctx.tenant) as session:
        found = {
            r.id: r
            for r in (
                await session.execute(_FACTS, {"ids": [row.subject_id for row in rows]})
            ).all()
        }
    out: dict[UUID, GateFacts] = {}
    for row in rows:
        hit = found.get(row.subject_id)
        if hit is None:
            continue
        year = "" if hit.tax_year is None else f" · TY{hit.tax_year}"
        out[row.id] = GateFacts(
            title=f"Approve the instrument interpretation ({hit.form}{year})",
            subject_route=f"TXT-01?returnId={hit.work_item_id}&ov=signoff",
        )
    return out


def register_instrument_gates() -> None:
    register_gate_source(
        GateSource(SUBJECT, "sign_off_request", "instrument.read", _EVENTS, approvals_due)
    )
    register_gate_presenter(SUBJECT, present)

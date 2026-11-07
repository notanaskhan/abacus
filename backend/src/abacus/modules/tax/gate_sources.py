"""C13 source for a return ready to export to the tax engine (I-01-T23; T-01 §3.9): HOME-02.

The signer's final approval reaches Home through review's own sources; what's left is the export: a
return at `final_approved` whose approval no engine export has followed yet. A row is a link to
TAX-02; a person exports from there (`tax_return.export`, human only, consuming the approval's
grant). Identifiers and the form only: values are TRI and never read here.
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

SUBJECT: Final = "tax_return_export"
_EVENTS: Final = frozenset({"tax_return.approved", "engine_sync.exported"})


async def exports_due(tenant: TenantContext, engagement_id: UUID | None) -> list[OpenGate]:
    """Returns at final approval with no engine export since that approval."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT t.work_item_id, t.engagement_id FROM tax_returns t "
                    "WHERE t.status = 'final_approved' "
                    "AND (CAST(:e AS uuid) IS NULL OR t.engagement_id = :e) "
                    "AND NOT EXISTS (SELECT 1 FROM engine_exports x "
                    "WHERE x.return_id = t.work_item_id AND x.generated_at >= ("
                    "SELECT max(s.at) FROM tax_return_status_events s "
                    "WHERE s.work_item_id = t.work_item_id AND s.event = 'final_approved'))"
                ),
                {"e": engagement_id},
            )
        ).all()
    return [OpenGate(r.work_item_id, r.engagement_id, work_item_id=r.work_item_id) for r in rows]


async def present_exports(ctx: AuthContext, rows: Sequence[GateView]) -> Mapping[UUID, GateFacts]:
    async with tenant_session(ctx.tenant) as session:
        found = {
            r.work_item_id: r
            for r in (
                await session.execute(
                    text(
                        "SELECT work_item_id, form, tax_year FROM tax_returns "
                        "WHERE work_item_id = ANY(:ids)"
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
            title=f"Export the {hit.form}{year} to the tax engine",
            subject_route=f"TAX-02?returnId={hit.work_item_id}",
        )
    return out


def register_tax_gates() -> None:
    register_gate_source(GateSource(SUBJECT, "send", "tax_return.read", _EVENTS, exports_due))
    register_gate_presenter(SUBJECT, present_exports)

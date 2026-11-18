"""C-02-T14: held entries as C13 human gates (SPEC-700; C-02 §4.6; DEC-5622). PROTECTED (red).

A proposed entry whose threshold result is Review required waits on a manager or partner of its
engagement (HOME-02 band Approvals & sends, DF-25 kind `final_approval`). The gate opens from the
owner's state, never from an event payload; it closes when the entry leaves Review required
(an approval, a rejection or a withdrawal recomputes it). A request names its approver: the
newest `proposed_entry.approval_requested` recipient becomes the assignee through the event's
notification (C16 `entry_approval_requested`), and the gate stays visible to every person who
may approve on the engagement. Recipients are re-authorised by the projector at fan-out and at
read: a walled or removed recipient sees nothing.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._statuses import ProposedEntryStatus
from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.review.api import GateSource, OpenGate, register_gate_source

SUBJECT: Final = "proposed_entry"
EVENTS: Final = frozenset({"proposed_entry.approval_requested", "proposed_entry.approval_decided"})


async def held_entries(tenant: TenantContext, engagement_id: UUID | None) -> list[OpenGate]:
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, engagement_id, work_item_id FROM proposed_entries "
                    "WHERE status = :s AND (CAST(:e AS uuid) IS NULL OR engagement_id = :e)"
                ),
                {"s": ProposedEntryStatus.REVIEW_REQUIRED.value, "e": engagement_id},
            )
        ).mappings()
        return [
            OpenGate(
                UUID(str(r["id"])),
                UUID(str(r["engagement_id"])),
                role="manager",
                work_item_id=UUID(str(r["work_item_id"])),
            )
            for r in rows
        ]


SOURCE: Final = GateSource(SUBJECT, "final_approval", "proposed_entry.read", EVENTS, held_entries)


def register_approval_gates() -> None:
    register_gate_source(SOURCE)

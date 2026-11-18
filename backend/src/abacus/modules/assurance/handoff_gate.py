"""T-06-T20 (DEC-5631): C12's `audit_release` and `review_release` hand-off gates, owned by
assurance. An audit or review is a hand-off source only once its report is released (G8,
`assurance.release.released`); before that, or for an unknown work item, refuses (fail closed)."""

from __future__ import annotations

from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.assurance.release import released
from abacus.modules.ledger.api import tb_handoff


async def report_released(tenant: TenantContext, work_item_id: UUID) -> bool:
    return await released(tenant, work_item_id) is not None


def register() -> None:
    tb_handoff.register_handoff_gate("audit_release", report_released)
    tb_handoff.register_handoff_gate("review_release", report_released)

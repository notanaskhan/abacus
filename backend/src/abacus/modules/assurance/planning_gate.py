"""A-04-T18: G4's facts (A-04 §3.4 AC4.4; F-03-T13's gate slots; DEC-2056).

G4 (planning complete) is met when materiality stands (decided, or reassessed with no change),
the engagement partner approved the risk register and no row changed since (every row EP
approved), and nothing waits for the partner (no proposed significance or rebuttal). Each unmet
part is a blocker in words the gate panel maps: `materiality_not_decided`,
`register_not_approved`, `register_changed_after_approval`, `proposal_pending`. With
`assurance.risk_register` off the firm is not planning in Accrued, so G4 is hidden rather than
blocking: it reads met with no blockers. A-04-T43's `assurance/gates.py` registers the provider.
"""

from __future__ import annotations

from uuid import UUID

from abacus.kernel._flags import ASSURANCE_RISK_REGISTER
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import flag_enabled
from abacus.modules.assurance import materiality, risks
from abacus.modules.engagements.api import GateFact, assurance_item_id


async def g4_facts(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    if not await flag_enabled(tenant, ASSURANCE_RISK_REGISTER):
        return GateFact(met=True)
    work_item = await assurance_item_id(tenant, engagement_id)
    if work_item is None:
        return GateFact(met=False, blockers=("not_an_audit",))
    blockers: list[str] = []
    if materiality.in_force(await materiality.versions_of(tenant, work_item)) is None:
        blockers.append("materiality_not_decided")
    rows = await risks.rows_of(tenant, work_item)
    statuses = {r.status for r in rows}
    if "revised" in statuses:
        blockers.append("register_changed_after_approval")
    elif not rows or statuses != {"ep_approved"}:
        blockers.append("register_not_approved")
    if any(r.significance == "proposed" or r.fraud == "rebuttal_proposed" for r in rows):
        blockers.append("proposal_pending")
    return GateFact(met=not blockers, blockers=tuple(blockers))

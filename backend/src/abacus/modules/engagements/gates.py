"""Gates G1 to G3, computed by engagements (C1; F-03-T06/T19; chapter 03 §3.1.3).

G1 acceptance (the partner accepted), G2 independence (the partner concluded it), G3 the
engagement letter (signed, or not required by the firm or this year). They are registered in the
fail-closed gate slot; later gates come from their owners (signatures, assurance). An engagement's
projection lists the gates its type requires among G1 to G3, each met or with its blockers.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.gate_policy import required_gates
from abacus.modules.engagements.repository import get_letter, latest_acceptance
from abacus.modules.engagements.slots import GateFact, gate_fact, register_gate_provider
from abacus.modules.identity.api import letter_policy

C1_GATES = ("G1", "G2", "G3")


async def _acceptance(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    async with tenant_session(tenant) as session:
        acceptance = await latest_acceptance(session, engagement_id)
    if acceptance is None:
        return GateFact(met=False, blockers=("acceptance",))
    if acceptance.decision != "accepted":
        return GateFact(met=False, blockers=("acceptance_declined",))
    return GateFact(met=True)


async def _independence(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    async with tenant_session(tenant) as session:
        acceptance = await latest_acceptance(session, engagement_id)
    if acceptance is None or acceptance.independence_concluded_at is None:
        return GateFact(met=False, blockers=("independence_conclusion",))
    return GateFact(met=True)


async def _letter(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    if not await letter_policy(tenant):
        return GateFact(met=True)
    async with tenant_session(tenant) as session:
        letter = await get_letter(session, engagement_id)
    if letter is None or letter.status not in ("signed", "not_required_this_year"):
        return GateFact(met=False, blockers=("engagement_letter",))
    return GateFact(met=True)


def register_gates() -> None:
    register_gate_provider("G1", _acceptance)
    register_gate_provider("G2", _independence)
    register_gate_provider("G3", _letter)


@dataclass(frozen=True)
class GateView:
    gate: str
    met: bool
    blockers: tuple[str, ...]


async def engagement_gates(
    tenant: TenantContext, engagement_id: UUID, engagement_type: str
) -> list[GateView]:
    """C1: the G1 to G3 gates this type requires, each met or with its blockers. The caller has
    authorised reading the engagement."""
    wanted = [g for g in required_gates(engagement_type) if g in C1_GATES]
    views: list[GateView] = []
    for gate in wanted:
        fact = await gate_fact(tenant, engagement_id, gate)
        views.append(GateView(gate, fact.met, fact.blockers))
    return views

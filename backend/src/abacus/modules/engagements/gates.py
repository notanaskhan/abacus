"""Gates G1 to G3, computed by engagements (C1; F-03-T06/T19; chapter 03 §3.1.3).

G1 acceptance (the partner accepted), G2 independence (the partner concluded it), G3 the
engagement letter (signed, or `not_required_this_year` for the engagement), strict whatever the
firm's letter policy (DEC-39 (b), ED-010). They are registered in the
fail-closed gate slot; later gates come from their owners (signatures, assurance). An engagement's
projection lists the gates its type requires among G1 to G3, each met or with its blockers.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.acceptance_tables import g1_decision
from abacus.modules.engagements.gate_policy import required_gates
from abacus.modules.engagements.independence_tables import (
    POSITIVE,
    latest_conclusion,
    legacy_concluded,
    open_breach_ids,
)
from abacus.modules.engagements.repository import get_letter, latest_acceptance
from abacus.modules.engagements.slots import GateFact, gate_fact, register_gate_provider

C1_GATES = ("G1", "G2", "G3")


async def _acceptance(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    """G1: the acceptance record's decision, or SPEC-025's row without a record (DEC-372)."""
    async with tenant_session(tenant) as session:
        decided = await g1_decision(session, engagement_id)
    if decided is None:
        return GateFact(met=False, blockers=("acceptance",))
    if not decided.accepted:
        return GateFact(met=False, blockers=("acceptance_declined",))
    return GateFact(met=True)


async def _independence(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    """G2: the engagement partner's newest conclusion is positive and no breach is open
    (P-07-T41, DEC-428); SPEC-025's conclusion where no conclusion row exists."""
    async with tenant_session(tenant) as session:
        if await open_breach_ids(session, engagement_id):
            return GateFact(met=False, blockers=("independence_breach",))
        concluded = await latest_conclusion(session, engagement_id)
        if concluded is not None:
            met = concluded.option in POSITIVE
        else:
            legacy = await latest_acceptance(session, engagement_id)
            met = legacy_concluded(legacy) is not None  # pre-0175 rows only (DEC-429)
    if not met:
        return GateFact(met=False, blockers=("independence_conclusion",))
    return GateFact(met=True)


async def _letter(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    """G3: a signed letter, or `not_required_this_year` (the exceptions path, 0182). The firm's
    letter policy never meets it (DEC-39 (b), ED-010)."""
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

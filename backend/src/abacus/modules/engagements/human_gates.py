"""What waits on a person in acceptance, independence and EQR (P-07-T47; P-07 §4.8; C13; DEC-539).

These are the owner's answers to C13's `open_for(tenant, engagement_id | None)`: computed from
engagements' own records now, never from an event's payload. Review registers them as gate
sources (`review/engagement_gates.py`; review already depends on engagements, never the reverse).
Each is a person's own act: the projection only says that it waits; deciding, confirming,
concluding and approving stay the owners' human-only routes (INV-1).

- `acceptance_decision_due`: an acceptance record `awaiting_partner`, for the engagement partner.
- `independence_conclusion_due`: an engagement whose members all confirmed (none requested or
  declined) and which has no conclusion yet, for the engagement partner.
- `independence_confirmation_due`: a member's confirmation still `requested`, for that member.
- `eqr_eligibility_due`: an engagement's EQR whose competence the history cannot show and whom
  the quality owner has not approved eligible, for each quality owner.

Need to know (security review M3, DEC-544): every gate is assigned to a named person, never left
to a role. A decision with several engagement partners is one gate per partner (each its own
subject, all closing together); with none, nobody is told (nobody may decide). An EQR gate goes to
each quality owner except the candidate themself and anyone on the engagement (who may not
approve it); the candidate never sees their own eligibility gate.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import aliased

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements import acceptance_tables as acceptance
from abacus.modules.engagements import independence_tables as independence
from abacus.modules.engagements.models import Engagement, IndependenceConfirmation
from abacus.modules.engagements.team import (
    eligibility_checks,
    eqr_approved,
    eqr_target,
    needs_eqr_approval,
)
from abacus.modules.identity.api import (
    EQR_ROLE,
    engagement_partners,
    member_details,
    quality_partners,
)

_NAMESPACE: Final = uuid.UUID("2a4d0f6e-8b1c-4f3a-9e7d-5c6b8a1f2e47")
ACCEPTANCE_DECISION_DUE: Final = "acceptance_decision_due"
INDEPENDENCE_CONCLUSION_DUE: Final = "independence_conclusion_due"
INDEPENDENCE_CONFIRMATION_DUE: Final = "independence_confirmation_due"
EQR_ELIGIBILITY_DUE: Final = "eqr_eligibility_due"


@dataclass(frozen=True)
class DueGate:
    """A subject waiting on a person, as engagements says now (review maps it to C13's
    `OpenGate`)."""

    subject_id: UUID
    engagement_id: UUID
    client_id: UUID | None
    assignee_user_id: UUID | None
    role: str | None


async def _per_partner(
    tenant: TenantContext, kind: str, subject: UUID, engagement_id: UUID, client_id: UUID | None
) -> list[DueGate]:
    """One gate per engagement partner, each its own subject; none without a partner."""
    return [
        DueGate(
            uuid.uuid5(_NAMESPACE, f"{kind}:{subject}:{partner}"),
            engagement_id,
            client_id,
            partner,
            "engagement_partner",
        )
        for partner in await engagement_partners(tenant.tenant_id, engagement_id)
    ]


def confirmation_subject(engagement_id: UUID, user_id: UUID) -> UUID:
    """A confirmation has no id of its own (its key is the engagement and the member)."""
    return uuid.uuid5(_NAMESPACE, f"independence_confirmation:{engagement_id}:{user_id}")


async def acceptance_decisions_due(
    tenant: TenantContext, engagement_id: UUID | None
) -> list[DueGate]:
    stmt = select(
        acceptance.records.c.id, acceptance.records.c.engagement_id, acceptance.records.c.client_id
    ).where(acceptance.records.c.status == "awaiting_partner")
    if engagement_id is not None:
        stmt = stmt.where(acceptance.records.c.engagement_id == engagement_id)
    async with tenant_session(tenant) as session:
        rows = (await session.execute(stmt)).all()
    out: list[DueGate] = []
    for r in rows:
        out.extend(
            await _per_partner(tenant, ACCEPTANCE_DECISION_DUE, r.id, r.engagement_id, r.client_id)
        )
    return out


async def _clients(tenant: TenantContext, engagement_ids: Sequence[UUID]) -> dict[UUID, UUID]:
    if not engagement_ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(Engagement.id, Engagement.client_id).where(Engagement.id.in_(engagement_ids))
        )
        return {r.id: r.client_id for r in rows}


async def independence_conclusions_due(
    tenant: TenantContext, engagement_id: UUID | None
) -> list[DueGate]:
    outer = IndependenceConfirmation
    other = aliased(IndependenceConfirmation)
    # Every member's confirmation is a v2 three-statement one (`statements`, P-07-T41) and none
    # is still requested or declined; a pre-v2 confirmation (SPEC-025) opens no conclusion gate.
    still_open = select(other.user_id).where(
        other.engagement_id == outer.engagement_id,
        or_(other.status.in_(("requested", "declined")), other.statements.is_(None)),
    )
    concluded = select(independence.conclusions.c.id).where(
        independence.conclusions.c.engagement_id == outer.engagement_id
    )
    stmt = select(outer.engagement_id).where(~exists(still_open), ~exists(concluded)).distinct()
    if engagement_id is not None:
        stmt = stmt.where(IndependenceConfirmation.engagement_id == engagement_id)
    async with tenant_session(tenant) as session:
        engagement_ids = list((await session.execute(stmt)).scalars().all())
    clients = await _clients(tenant, engagement_ids)
    out: list[DueGate] = []
    for e in engagement_ids:
        out.extend(await _per_partner(tenant, INDEPENDENCE_CONCLUSION_DUE, e, e, clients.get(e)))
    return out


async def independence_confirmations_due(
    tenant: TenantContext, engagement_id: UUID | None
) -> list[DueGate]:
    stmt = select(IndependenceConfirmation.engagement_id, IndependenceConfirmation.user_id).where(
        IndependenceConfirmation.status == "requested"
    )
    if engagement_id is not None:
        stmt = stmt.where(IndependenceConfirmation.engagement_id == engagement_id)
    async with tenant_session(tenant) as session:
        rows = (await session.execute(stmt)).all()
    clients = await _clients(tenant, sorted({r.engagement_id for r in rows}))
    return [
        DueGate(
            confirmation_subject(r.engagement_id, r.user_id),
            r.engagement_id,
            clients.get(r.engagement_id),
            r.user_id,
            None,
        )
        for r in rows
    ]


async def eqr_eligibility_due(tenant: TenantContext, engagement_id: UUID | None) -> list[DueGate]:
    """Per engagement (the reconcile after an event is one engagement; the operator's rebuild
    walks them all: DEC-548)."""
    owners = await quality_partners(tenant.tenant_id)
    if not owners:
        return []
    if engagement_id is not None:
        engagement_ids = [engagement_id]
    else:
        async with tenant_session(tenant) as session:
            engagement_ids = list((await session.execute(select(Engagement.id))).scalars().all())
    clients = await _clients(tenant, engagement_ids)
    out: list[DueGate] = []
    for engagement in engagement_ids:
        details = await member_details(tenant, engagement)
        eqrs = [d.user_id for d in details if d.role == EQR_ROLE]
        if not eqrs:
            continue
        on_engagement = {d.user_id for d in details}
        target = await eqr_target(tenant, engagement)
        for eqr in eqrs:
            checks = await eligibility_checks(tenant, target, eqr, confirmation=None)
            if not needs_eqr_approval(checks) or await eqr_approved(tenant, engagement, eqr):
                continue
            # Never the candidate, never anyone on the engagement (they may not approve it).
            for owner in owners:
                if owner == eqr or owner in on_engagement:
                    continue
                out.append(
                    DueGate(
                        uuid.uuid5(_NAMESPACE, f"eqr_eligibility:{engagement}:{eqr}:{owner}"),
                        engagement,
                        clients.get(engagement),
                        owner,
                        "quality_partner",
                    )
                )
    return out


__all__ = [
    "ACCEPTANCE_DECISION_DUE",
    "EQR_ELIGIBILITY_DUE",
    "INDEPENDENCE_CONCLUSION_DUE",
    "INDEPENDENCE_CONFIRMATION_DUE",
    "DueGate",
    "acceptance_decisions_due",
    "confirmation_subject",
    "eqr_eligibility_due",
    "independence_conclusions_due",
    "independence_confirmations_due",
]

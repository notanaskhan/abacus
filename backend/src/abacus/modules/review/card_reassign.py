"""The decision card's reassign hook (I-01-T07; DEC-575): a card awaiting its reserved role moves
to another holder of that role on the engagement, never to the mover, never to someone walled off
from the client. Who may move it: the reserved person, the engagement partner or a manager on the
engagement. `decision_cards_reassign_guard` (0223) holds the same rules at the database, and
needs the reassignment row written first in the same transaction (review's unit of work does).
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import update

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import UnitOfWork
from abacus.modules.identity.api import AuthContext, Forbidden, hidden_clients, team_of
from abacus.modules.review.gate_actions import (
    REASSIGN,
    Candidate,
    GateNotOpen,
    ReassignHook,
    register_reassign_hook,
)
from abacus.modules.review.gates import GateView
from abacus.modules.review.models import DecisionCard

SUBJECT: Final = "decision_card"
_MOVERS: Final = frozenset({"engagement_partner", "manager"})


async def _card(ctx: AuthContext, gate: GateView) -> DecisionCard:
    async with tenant_session(ctx.tenant) as session:
        card = await session.get(DecisionCard, gate.subject_id)
    if card is None:
        raise NotFound(SUBJECT)
    if card.status != "awaiting_role":
        raise GateNotOpen(facts={"gate_id": str(gate.id)})
    return card


async def candidates(ctx: AuthContext, gate: GateView) -> list[Candidate]:
    card = await _card(ctx, gate)
    team = await team_of(ctx.tenant_id, card.engagement_id)
    roles = {role for user, role in team if user == ctx.user_id}
    if card.reserved_user_id != ctx.user_id and not roles & _MOVERS:
        raise Forbidden(REASSIGN, "role")
    holders = sorted(
        {u for u, role in team if role == card.reserved_role and u != card.reserved_user_id},
        key=str,
    )
    if gate.client_id is not None:
        holders = [u for u in holders if not await hidden_clients(ctx.tenant, u, [gate.client_id])]
    return [Candidate(u, card.reserved_role) for u in holders]


async def move(tx: UnitOfWork, ctx: AuthContext, gate: GateView, to_user_id: UUID) -> None:
    moved = (
        await tx.session.execute(
            update(DecisionCard)
            .where(DecisionCard.id == gate.subject_id, DecisionCard.status == "awaiting_role")
            .values(reserved_user_id=to_user_id)
            .returning(DecisionCard.id)
        )
    ).scalar_one_or_none()
    if moved is None:  # decided or superseded since it was read
        raise GateNotOpen(facts={"gate_id": str(gate.id)})


def register_card_reassign() -> None:
    register_reassign_hook(SUBJECT, ReassignHook(candidates, move))


__all__ = ["register_card_reassign"]

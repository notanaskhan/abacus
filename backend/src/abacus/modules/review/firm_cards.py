"""Firm-scope decision cards (Q-05-T16 part 2; SPEC-711 AC-10; OQ-5; DEC-5826). PROTECTED (red).

One grammar for a decision that belongs to no engagement: the annual SQMS evaluation. A firm card
(`scope_kind = firm`) names its decider (`reserved_role = qm_ultimate`, `reserved_user_id` the QM
owner), carries the kind's code-fixed options, and is decided only by that person, live, with a
fresh MFA, under `quality_evaluation.decide` on the firm (the agent and the system never). The
kind's owner (practice, Q-05-T18) registers the kind and raises the card.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Final, cast
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise
from abacus.modules.review.sealing import seal_text

SUBJECT: Final = "decision_card"
DECIDE: Final = "quality_evaluation.decide"
MFA_WINDOW: Final = timedelta(minutes=10)


class CardState(DomainConflict):
    code = "decision_card_state"
    message = "This card is no longer awaiting its decision."


class MfaRequired(DomainConflict):
    code = "mfa_required"
    message = "Confirm it's you to decide."


async def raise_firm_card(
    ctx: AuthContext,
    *,
    kind: str,
    question_key: str,
    reserved_user_id: UUID,
    options: list[dict[str, object]],
    context: list[dict[str, object]] | None = None,
) -> UUID:
    """A firm card for `reserved_user_id` (qm_ultimate). The raiser holds `quality.manage`."""
    await authorise(ctx, "quality.manage", Resource.firm(ctx.tenant_id))
    if not options:
        raise DomainConflict(facts={"reason": "no_options"})
    async with uow(ctx.tenant) as tx:
        card_id = cast(
            UUID,
            await tx.session.scalar(
                text(
                    "INSERT INTO decision_cards (tenant_id, engagement_id, work_item_id, kind, "
                    "version_no, question_key, reserved_role, reserved_user_id, options, context, "
                    "factors, blocking_refs, raised_by_kind, raised_by_id, scope_kind) VALUES (:t, "
                    "NULL, NULL, :k, 1, :q, 'qm_ultimate', :u, CAST(:o AS jsonb), CAST(:c AS "
                    "jsonb), '[]'::jsonb, '[]'::jsonb, 'human', :by, 'firm') RETURNING id"
                ),
                {
                    "t": ctx.tenant_id, "k": kind, "q": question_key, "u": reserved_user_id,
                    "o": json.dumps(options), "c": json.dumps(context or []),
                    "by": ctx.tenant.actor_id,
                },
            ),
        )  # fmt: skip
        tx.record("decision_card.raised", target=Target(SUBJECT, card_id), after=Ref(version=1))
    return card_id


async def decide_firm_card(
    ctx: AuthContext, card_id: UUID, *, option_key: str, rationale: str, seen_version: int
) -> UUID:
    """Only the named person, live, with a fresh MFA; one decision per card."""
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(DECIDE, "role")
    if ctx.mfa_at is None or await clock.now(ctx.tenant) - ctx.mfa_at > MFA_WINDOW:
        raise MfaRequired
    await authorise(ctx, DECIDE, Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        card = (
            await tx.session.execute(
                text(
                    "SELECT id, status, version_no, reserved_user_id, options FROM decision_cards "
                    "WHERE id = :c AND scope_kind = 'firm' FOR UPDATE"
                ),
                {"c": card_id},
            )
        ).first()
        if card is None:
            raise NotFound(SUBJECT)
        if card.reserved_user_id != ctx.user_id:
            raise Forbidden(DECIDE, "reserved_user")
        if card.status != "awaiting_role" or int(card.version_no) != seen_version:
            raise CardState
        if option_key not in {str(o.get("key")) for o in card.options}:
            raise DomainConflict(facts={"reason": "unknown_option"})
        decision_id = uuid4()  # the sealed rationale is bound to its row (P-04-T23)
        await tx.session.execute(
            text(
                "INSERT INTO decisions (id, tenant_id, card_id, option_key, rationale_sealed, "
                "seen_card_version, decided_by, mfa_at) VALUES (:id, :t, :c, :o, :r, :v, :u, :m)"
            ),
            {
                "id": decision_id, "t": ctx.tenant_id, "c": card_id, "o": option_key,
                "r": await seal_text(ctx.tenant, rationale, "decision", decision_id, "rationale"),
                "v": seen_version, "u": ctx.user_id, "m": ctx.mfa_at,
            },
        )  # fmt: skip
        await tx.session.execute(
            text("UPDATE decision_cards SET status = 'decided' WHERE id = :c"), {"c": card_id}
        )
        tx.record("decision.recorded", target=Target(SUBJECT, card_id), after=Ref(decision=decision_id))
    return decision_id


__all__ = ["DECIDE", "CardState", "MfaRequired", "decide_firm_card", "raise_firm_card"]

"""Undo a proposal decision (P-04-T29; DEC-24, ADR-161 clause 6; DEC-713).

`POST /v1/proposals/{id}/undo` `{decision_id}`: only the person who decided, within 10 seconds on
`kernel.clock`, and only while it is the proposal's latest decision; else 409
`undo_window_closed`. In one unit of work it writes the `undone` decision (naming the one it
undoes), takes the proposal back to `pending` (migration 0273's guard checks both), voids any
approval grant the decision holds so a held client-visible effect is never delivered, and records
`proposal.undone`. What the decision wrote is put back:

- **A rejection** wrote nothing else.
- **An approval that wrote field values** (row appliers): each field gets its previous value back
  (`record_value`, cause `restore`). A field changed by anyone since, or with no earlier value, or
  an approval applied by an owner's change-set applier, cannot be put back generically: 409
  `effect_started`.
- **A held effect that has started** (its grant was consumed): 409 `effect_started`.
- **Typed proposals** (`upload_review:<id>`, `screening_result:<id>`): the approval or send-back
  was a review decision, undone through `evidence.api.undo_review_decision` (P-01-T13), which
  returns the request to "Uploaded - needs review". A match (`inbox_match:<id>`) filed a version
  and cannot be undone here (409 `effect_started`).

A closed tab keeps the decision: nothing undoes it but this call.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.agents.models import Proposal
from abacus.modules.agents.proposal_store import (
    insert_proposal_decision,
    lock_proposal,
    rows_of,
    set_proposal,
)
from abacus.modules.engagements.api import lock_ref
from abacus.modules.evidence.api import review_decision_engagement, undo_review_decision
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, void_grant
from abacus.modules.review.api import previous_value, record_value

UNDO: Final = "proposal.undo"
SUBJECT: Final = "proposal"
_DECIDED: Final = frozenset({"approved", "approved_with_edits", "rejected"})
UNDO_WINDOW: Final = timedelta(seconds=10)  # DEC-24, as evidence's and requests'
FIELD_CHANGE_SET: Final = "field_change_set"  # `proposals.FIELD_CHANGE_SET`: row appliers


class UndoWindowClosed(DomainConflict):
    """Undo is possible for 10 seconds after a decision, by the person who made it, once."""

    code = "undo_window_closed"


class EffectStarted(DomainConflict):
    """What the decision did can no longer be put back (a held effect started, a field changed
    since, or an owner's change set applied)."""

    code = "effect_started"


async def _restore_fields(tx: UnitOfWork, proposal: Proposal, decided_at: datetime) -> None:
    """Put each row's field back to its previous value, or refuse (`effect_started`)."""
    for row in await rows_of(tx.session, proposal.id):
        ref = row.field_ref
        target_type, target_id = str(ref["target_type"]), UUID(str(ref["target_id"]))
        field_key = str(ref["field_key"])
        previous = await previous_value(tx, target_type, target_id, field_key)
        if previous is None or previous.latest_at < decided_at:
            raise EffectStarted(facts={"row": row.n})
        await record_value(
            tx,
            engagement_id=proposal.engagement_id,
            target_type=target_type,
            target_id=target_id,
            field_key=field_key,
            value=previous.value,
            value_source="human",
            cause="restore",
            value_kind=previous.value_kind,
        )


async def undo_proposal(ctx: AuthContext, proposal_id: UUID, decision_id: UUID) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden(UNDO, "role")
    async with uow(ctx.tenant) as tx:
        found = await lock_proposal(tx.session, proposal_id)
        if found is None or found.engagement_id is None:
            raise NotFound(SUBJECT)
        ref = await lock_ref(tx, found.engagement_id)
        await authorise(ctx, UNDO, ref.resource())
        latest = (
            await tx.session.execute(
                text(
                    "SELECT id, decision, decided_by, created_at, approval_grant_id "
                    "FROM proposal_decisions WHERE proposal_id = :p "
                    "ORDER BY created_at DESC, id DESC LIMIT 1"
                ),
                {"p": proposal_id},
            )
        ).first()
        if (
            latest is None
            or latest.id != decision_id
            or latest.decision not in _DECIDED
            or found.state != latest.decision
            or latest.decided_by != ctx.user_id
            or await clock.now(ctx.tenant) >= latest.created_at + UNDO_WINDOW
        ):
            raise UndoWindowClosed
        if latest.approval_grant_id is not None and not await void_grant(
            tx, latest.approval_grant_id
        ):
            raise EffectStarted(facts={"reason": "grant_consumed"})
        if latest.decision != "rejected":
            if found.kind != FIELD_CHANGE_SET:  # an owner's change-set applier wrote it
                raise EffectStarted(facts={"reason": "change_set"})
            await _restore_fields(tx, found, latest.created_at)
        undo_id = uuid4()
        await insert_proposal_decision(
            tx.session,
            {
                "id": undo_id,
                "tenant_id": ctx.tenant_id,
                "proposal_id": found.id,
                "decision": "undone",
                "undoes_decision_id": latest.id,
                "seen_version": found.version,
                "decided_by": ctx.user_id,
            },
        )
        version = await set_proposal(tx.session, found.id, state="pending")
        tx.record(
            "proposal.undone",
            target=Target(SUBJECT, found.id),
            after=Ref(decision=undo_id, undoes=latest.id, version=version),
            scope=Scope(engagement_id=found.engagement_id),
        )


async def undo_typed(ctx: AuthContext, kind: str, subject: UUID, decision_id: UUID) -> None:
    """A typed proposal's verdict is the owner's review decision; undo it there."""
    if kind == "inbox_match":
        raise EffectStarted(facts={"reason": "filed"})
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden(UNDO, "role")
    async with uow(ctx.tenant) as tx:
        engagement_id = await review_decision_engagement(tx, decision_id)
        if engagement_id is None:
            raise NotFound(SUBJECT)
        await undo_review_decision(tx, ctx, engagement_id, decision_id)
        tx.record(
            "proposal.undone",
            target=Target(kind, subject),
            after=Ref(undoes=decision_id),
            scope=Scope(engagement_id=engagement_id),
        )

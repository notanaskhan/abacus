"""The engagement lifecycle as data (F-03-T13; chapter 03 §3.1.3; DEC-39; INV-1, INV-5).

Every legal move between the eight states is one row: who may make it (a person, through the
matrix action named, or the system on a fact) and the audit action it writes. Anything else
answers 409 `illegal_transition` with the two states as facts. Accept, decline and hold are human
only: an agent or a system principal is refused before anything is written. Each move writes one
audit event naming the person (INV-5) and one `engagement.status_changed` outbox event, in the
caller's unit of work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, ClassVar, Final, Literal
from uuid import UUID

from sqlalchemy import select, update

from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.models import Engagement
from abacus.modules.engagements.service import lock_ref
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, team_standing

Status = Literal[
    "prospect",
    "accepted",
    "declined",
    "contracted",
    "active",
    "on_hold",
    "delivered",
    "archived",
]


@dataclass(frozen=True)
class Move:
    """One legal transition: `human` moves need a person allowed `action`; `system` moves are
    made by the platform on a fact (a signed letter, a published binder, every delivery)."""

    by: Literal["human", "system"]
    audit: str
    action: str | None = None


LIFECYCLE: Final[dict[tuple[Status, Status], Move]] = {
    ("prospect", "accepted"): Move("human", "engagement.accepted", "acceptance.record"),
    ("prospect", "declined"): Move("human", "engagement.declined", "acceptance.record"),
    ("accepted", "contracted"): Move("system", "engagement.contracted"),
    ("contracted", "active"): Move("system", "engagement.activated"),
    ("active", "on_hold"): Move("human", "engagement.held", "engagement.hold"),
    ("on_hold", "active"): Move("human", "engagement.resumed", "engagement.hold"),
    ("active", "delivered"): Move("system", "engagement.delivered"),
    ("delivered", "archived"): Move("system", "engagement.archived"),
}

_BY_PAIR: Final[dict[tuple[str, str], Move]] = {pair: move for pair, move in LIFECYCLE.items()}
# The action a person needs to move an engagement *to* a state (one per target state): checked
# before the current state is read, so a walled or unauthorised caller learns nothing about it.
_HUMAN_ACTION_TO: Final[dict[str, str]] = {
    to: move.action for (_, to), move in LIFECYCLE.items() if move.by == "human" and move.action
}

# Why an engagement is held (§3.1.3 "reason required"): codes, never free text. Append only: the
# audit row of a hold stores the code's position here (`after.reason_code`), since an audit
# reference carries identifiers and integers only (TASK-1198 security review, DEC-328).
HOLD_REASON_CODES: Final = (
    "client_unresponsive",
    "fees_outstanding",
    "scope_change",
    "independence_review",
    "other",
)
HOLD_REASONS: Final = frozenset(HOLD_REASON_CODES)
# A hold for this reason is lifted by the engagement partner only (DEC-328).
PARTNER_RESUMES: Final = frozenset({"independence_review"})


class IllegalTransition(DomainConflict):
    """The engagement cannot move from its state to the one asked for (DEC-39)."""

    code = "illegal_transition"


class HoldReasonRequired(DomainInvalid):
    """Putting an engagement on hold names a reason from the hold reason codes."""

    code = "hold_reason_required"


class EngagementStatusChanged(DomainEvent):
    event_type: ClassVar[str] = "engagement.status_changed"

    engagement_id: Annotated[UUID, classified("internal")]
    from_status: Annotated[str, classified("internal")]
    to_status: Annotated[str, classified("internal")]
    reason: Annotated[str | None, classified("internal")] = None


def move_for(current: str, to: str) -> Move:
    """The row for `current → to`, or `IllegalTransition` with both states as facts."""
    move = _BY_PAIR.get((current, to))
    if move is None:
        raise IllegalTransition(facts={"from_status": current, "to_status": to})
    return move


async def transition(
    tx: UnitOfWork,
    engagement_id: UUID,
    to: Status,
    *,
    by: AuthContext | Literal["system"],
    reason: str | None = None,
) -> None:
    """Move the engagement to `to` inside `tx`, or raise without writing anything."""
    action = _HUMAN_ACTION_TO.get(to)
    if isinstance(by, AuthContext) and action is not None:
        # INV-1 and walls first: only a signed-in person, through the matrix (which denies agents
        # and the system), and before the state is read (a walled caller gets 404 for any state).
        # A person asking for a system-only state is refused below (409 `illegal_transition`).
        if by.tenant.actor_kind != "human":
            raise Forbidden(action, "role")
        await authorise(by, action, (await lock_ref(tx, engagement_id)).resource())
    row = (
        await tx.session.execute(
            select(Engagement.status, Engagement.client_id, Engagement.hold_reason)
            .where(Engagement.id == engagement_id)
            .with_for_update()
        )
    ).one_or_none()
    if row is None:
        raise NotFound("engagement")
    current = str(row.status)
    move = move_for(current, to)
    if move.by == "human":
        if not isinstance(by, AuthContext):
            raise Forbidden(move.action or "engagement.transition", "role")
    elif by != "system":
        raise IllegalTransition(facts={"from_status": current, "to_status": to})
    if to == "on_hold" and reason not in HOLD_REASONS:
        raise HoldReasonRequired
    if (
        current == "on_hold"
        and row.hold_reason in PARTNER_RESUMES
        and isinstance(by, AuthContext)
        and await team_standing(by.tenant, engagement_id, by.user_id) != "partner"
    ):
        raise Forbidden("engagement.hold", "role")  # DEC-328: the EP lifts an independence hold
    held = reason if to == "on_hold" else None
    await tx.session.execute(
        update(Engagement)
        .where(Engagement.id == engagement_id)
        .values(status=to, hold_reason=held)
    )
    after = Ref(reason_code=HOLD_REASON_CODES.index(held)) if held is not None else None
    tx.record(move.audit, target=Target("engagement", engagement_id), after=after)
    tx.emit(
        EngagementStatusChanged(
            engagement_id=engagement_id,
            from_status=current,
            to_status=to,
            reason=reason if to == "on_hold" else None,
        )
    )


async def hold(ctx: AuthContext, engagement_id: UUID, reason: str) -> None:
    """Put an active engagement on hold (a person, with a reason code)."""
    async with uow(ctx.tenant) as tx:
        await transition(tx, engagement_id, "on_hold", by=ctx, reason=reason)


async def resume(ctx: AuthContext, engagement_id: UUID) -> None:
    """Take an engagement off hold."""
    async with uow(ctx.tenant) as tx:
        await transition(tx, engagement_id, "active", by=ctx)

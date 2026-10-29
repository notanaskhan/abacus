"""C13's gate actions and presentation facts (I-01-T07; I-01 §4.3; `home-and-gates.md` §2, §5).

- **Presentation facts** (`register_gate_presenter`): an owner resolves its rows' title, context,
  bulk eligibility, subject route, overlay, glyph and `proposed_by` in one batch call
  (`resolve_many`), authorising each row itself; a row it leaves out gets none (fail closed), and
  a presenter that raises leaves its rows bare rather than wrong. `version` is review's own: one
  more than the gate's reassignments, so a reassign names what it saw (409 `stale_version`).
- **Snooze** (`human_gate.snooze`): a person's own, of an open gate that waits on them, until a
  moment after now (422 `snooze_in_past`) and no later than the gate's due date in the firm's time
  zone (422 `snooze_past_due`), at most 30 days (the table's CHECK); an overdue gate is never
  snoozed (409 `gate_overdue`). Unsnooze writes a row whose `until` is now. Both insert-only rows
  the database binds to the session's person (0223).
- **Reassign** (`human_gate.reassign`): only through the owner's hook (`register_reassign_hook`;
  409 `not_reassignable` without one). The hook names the eligible people (`candidates`) and
  moves the owner's record (`move`) in review's unit of work, after the reassignment row is
  written (the decision card's guard needs it first, DEC-575). A person not among the
  candidates is 422 `candidate_not_eligible`.
- Every act is audited (`human_gate.snoozed`, `.unsnoozed`, `.reassigned`); a reassignment also
  emits `human_gate.reassigned`, whose notification (`gate_reassigned`) tells the new person.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import func, insert, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel import clock
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import engagement_resource_of
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise
from abacus.modules.review.events import HumanGateReassigned
from abacus.modules.review.gates import GateView, gate_view, open_for_caller
from abacus.modules.review.models import HumanGate, HumanGateReassignment, HumanGateSnooze

SNOOZE: Final = "human_gate.snooze"
REASSIGN: Final = "human_gate.reassign"
MAX_SNOOZE: Final = timedelta(days=30)
_log = get_logger(__name__)


class GateNotOpen(DomainConflict):
    """The gate is done or voided: nothing to snooze or move."""

    code = "gate_not_open"


class GateOverdue(DomainConflict):
    """An overdue gate is never snoozed."""

    code = "gate_overdue"


class NotReassignable(DomainConflict):
    """The gate's owner registered no way to move it to someone else."""

    code = "not_reassignable"


class GateStaleVersion(DomainConflict):
    """The gate moved since you saw it: reload."""

    code = "stale_version"


class SnoozePastDue(DomainInvalid):
    """A snooze ends no later than the gate's due date (and within 30 days)."""

    code = "snooze_past_due"


class SnoozeInPast(DomainInvalid):
    """A snooze ends after now."""

    code = "snooze_in_past"


class CandidateNotEligible(DomainInvalid):
    """The person can't take this gate (not a holder of its role, or walled off)."""

    code = "candidate_not_eligible"


# --- presentation facts --------------------------------------------------------------------------


@dataclass(frozen=True)
class ProposedBy:
    """INV-5: the run that proposed it and the person it ran for; never the agent as decider."""

    run_id: UUID
    initiator_user_id: UUID | None
    at: datetime


@dataclass(frozen=True)
class GateFacts:
    title: str | None = None
    context: str | None = None
    bulk_eligible: bool = False
    subject_route: str | None = None  # a route the SPA resolves, never a URL with data in it
    overlay: str | None = None  # the overlay code the row opens (`decision_card`, `sign_off`…)
    glyph: str | None = None  # a glyph code
    proposed_by: ProposedBy | None = None


Presenter = Callable[[AuthContext, Sequence[GateView]], Awaitable[Mapping[UUID, GateFacts]]]


@dataclass(frozen=True)
class Candidate:
    user_id: UUID
    role: str


@dataclass(frozen=True)
class ReassignHook:
    """`candidates(ctx, gate)`: who may take it now (walls applied). `move(tx, ctx, gate, to)`:
    the owner's record moves inside review's unit of work, after the reassignment row."""

    candidates: Callable[[AuthContext, GateView], Awaitable[Sequence[Candidate]]]
    move: Callable[[UnitOfWork, AuthContext, GateView, UUID], Awaitable[None]]


_PRESENTERS: dict[str, Presenter] = {}
_HOOKS: dict[str, ReassignHook] = {}


def register_gate_presenter(subject_type: str, presenter: Presenter) -> None:
    """An owner's batch resolver for its gates' rows (once, at the owner's import)."""
    _PRESENTERS[subject_type] = presenter


def register_reassign_hook(subject_type: str, hook: ReassignHook) -> None:
    """How an owner's gate moves to another person (I-01-T07); without one it never does."""
    _HOOKS[subject_type] = hook


def reassignable(subject_type: str) -> bool:
    return subject_type in _HOOKS


async def resolve_many(ctx: AuthContext, rows: Sequence[GateView]) -> dict[UUID, GateFacts]:
    """Each owner's facts for its rows, in one call per owner; fail closed per owner."""
    by_type: dict[str, list[GateView]] = {}
    for row in rows:
        by_type.setdefault(row.subject_type, []).append(row)
    facts: dict[UUID, GateFacts] = {}
    for subject_type, mine in sorted(by_type.items()):
        presenter = _PRESENTERS.get(subject_type)
        if presenter is None:
            continue
        try:
            found = await presenter(ctx, mine)
        except Exception as exc:  # a presenter that fails shows nothing rather than a wrong row
            _log.warning(
                "human_gates.presenter_failed", subject=subject_type, error=type(exc).__name__
            )
            continue
        ids = {r.id for r in mine}
        facts.update({k: v for k, v in found.items() if k in ids})  # only its own rows
    return facts


# --- reading one gate for an act -----------------------------------------------------------------


async def _gate_for_caller(ctx: AuthContext, gate_id: UUID) -> GateView:
    """The gate as the caller may see it (walls and read actions applied, waiting on them or on
    their role): 404 otherwise. Done and voided gates the caller could see are 409."""
    async with tenant_session(ctx.tenant) as session:
        visible = (
            await session.execute(
                select(HumanGate).where(HumanGate.id == gate_id, *open_for_caller(ctx, state=None))
            )
        ).scalar_one_or_none()
        if visible is None:
            raise NotFound("human_gate")
        version = await _version(session, gate_id)
    gate = gate_view(visible, version)
    if gate.state != "open":
        raise GateNotOpen(facts={"gate_id": str(gate_id)})
    return gate


async def _version(session: AsyncSession, gate_id: UUID) -> int:
    found = await session.execute(
        select(func.count()).where(HumanGateReassignment.gate_id == gate_id)
    )
    return 1 + int(found.scalar_one())


def _live_human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def resource_of(ctx: AuthContext, engagement_id: UUID | None) -> Resource:
    """A gate's resource: its engagement (team roles count there), else the firm."""
    if engagement_id is None:
        return Resource.firm(ctx.tenant_id)
    return await engagement_resource_of(ctx.tenant, engagement_id)


async def _authorised(ctx: AuthContext, action: str, gate_id: UUID) -> GateView:
    """A live person, the gate as they may see it, then `action` on its engagement."""
    _live_human(ctx, action)
    gate = await _gate_for_caller(ctx, gate_id)
    await authorise(ctx, action, await resource_of(ctx, gate.engagement_id))
    return gate


async def _hooked(ctx: AuthContext, gate_id: UUID) -> tuple[GateView, ReassignHook]:
    """The gate and its owner's hook (409 `not_reassignable` without one, before anything else
    about the caller is asked), then `human_gate.reassign` on its engagement."""
    _live_human(ctx, REASSIGN)
    gate = await _gate_for_caller(ctx, gate_id)
    hook = _HOOKS.get(gate.subject_type)
    if hook is None:
        raise NotReassignable(facts={"gate_id": str(gate_id)})
    await authorise(ctx, REASSIGN, await resource_of(ctx, gate.engagement_id))
    return gate, hook


# --- snooze ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Snoozed:
    gate_id: UUID
    until: datetime


async def snooze_gate(ctx: AuthContext, gate_id: UUID, until: datetime) -> Snoozed:
    gate = await _authorised(ctx, SNOOZE, gate_id)
    now = await clock.now(ctx.tenant)
    today = await clock.today(ctx.tenant)
    if until <= now:
        raise SnoozeInPast(facts={"gate_id": str(gate_id)})
    if gate.due_on is not None and gate.due_on < today:
        raise GateOverdue(facts={"gate_id": str(gate_id)})
    local = until.astimezone(clock.FIRM_ZONE)  # the due date is a day in the firm's zone
    if until - now > MAX_SNOOZE or (gate.due_on is not None and local.date() > gate.due_on):
        raise SnoozePastDue(facts={"gate_id": str(gate_id)})
    await _write_snooze(ctx, gate, until, "human_gate.snoozed")
    return Snoozed(gate_id, until)


async def unsnooze_gate(ctx: AuthContext, gate_id: UUID) -> Snoozed:
    """An unsnooze is a snooze that ends now (the latest row wins)."""
    gate = await _authorised(ctx, SNOOZE, gate_id)
    now = await clock.now(ctx.tenant)
    await _write_snooze(ctx, gate, now, "human_gate.unsnoozed")
    return Snoozed(gate_id, now)


async def _write_snooze(ctx: AuthContext, gate: GateView, until: datetime, action: str) -> None:
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            insert(HumanGateSnooze).values(
                tenant_id=ctx.tenant_id,
                gate_id=gate.id,
                user_id=ctx.user_id,
                until=until,
                actor_kind="human",
                actor_id=ctx.tenant.actor_id,
            )
        )
        tx.record(
            action,
            target=Target("human_gate", gate.id),
            after=Ref(user=ctx.user_id, until=int(until.timestamp())),
        )


# --- reassign ----------------------------------------------------------------------------------


async def reassign_candidates(ctx: AuthContext, gate_id: UUID) -> list[Candidate]:
    gate, hook = await _hooked(ctx, gate_id)
    return [c for c in await hook.candidates(ctx, gate) if c.user_id != ctx.user_id]


@dataclass(frozen=True)
class Reassigned:
    gate_id: UUID
    to_user_id: UUID
    version: int


async def reassign_gate(
    ctx: AuthContext, gate_id: UUID, to_user_id: UUID, seen_version: int
) -> Reassigned:
    gate, hook = await _hooked(ctx, gate_id)
    if gate.version != seen_version:
        raise GateStaleVersion(facts={"gate_id": str(gate_id)})
    eligible = {c.user_id for c in await hook.candidates(ctx, gate)}
    if to_user_id not in eligible or to_user_id == ctx.user_id:
        raise CandidateNotEligible(facts={"gate_id": str(gate_id)})
    try:
        async with uow(ctx.tenant) as tx:
            await tx.session.execute(
                insert(HumanGateReassignment).values(
                    tenant_id=ctx.tenant_id,
                    gate_id=gate.id,
                    subject_ref={"type": gate.subject_type, "id": str(gate.subject_id)},
                    from_user_id=gate.assignee_user_id,
                    to_user_id=to_user_id,
                    actor_kind="human",
                    actor_id=ctx.tenant.actor_id,
                )
            )
            await hook.move(tx, ctx, gate, to_user_id)
            tx.record(
                "human_gate.reassigned",
                target=Target("human_gate", gate.id),
                before=Ref(user=gate.assignee_user_id) if gate.assignee_user_id else None,
                after=Ref(user=to_user_id),
            )
            tx.emit(
                HumanGateReassigned(
                    gate_id=gate.id,
                    engagement_id=gate.engagement_id,
                    to_user_id=to_user_id,
                    by_user=ctx.user_id,
                )
            )
    except DBAPIError as exc:
        # The owner's guard refused the move (a race with the card's decision or a new wall).
        _log.info("human_gates.reassign_refused", error=type(exc).__name__)
        raise CandidateNotEligible(facts={"gate_id": str(gate_id)}) from None
    return Reassigned(gate.id, to_user_id, gate.version + 1)

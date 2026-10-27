"""Record-mode phases and the EBP profile (A-01-T05; SPEC-330 AC-9 to AC-14; DEC-262).

An assurance work item's phase follows its gates (blueprint §3.3.2). While Accrued computes no
gate for a phase (its provider is unregistered), a named person records the move instead:
record mode. Each move writes one insert-only `assurance_phase_events` row, whose SECURITY
DEFINER insert trigger checks the actor and the move and moves the projection on
`assurance_work_items` (the app role cannot update `phase` itself), audits and emits
`assurance.phase_changed`, in one unit of work. SPEC-314's release and archive lock move the phase
through `advance_by_gate` the same way.

- **Forward one step only.** The phases in order are planning, fieldwork, in review, completion,
  ready to release, released and archived; completion is not offered until DF-05 designs its tile
  (A-01 DV-12), so in review is followed by ready to release. A target at or before the current
  phase is `phase_backward`; one past the next is `phase_skip`.
- **A computed gate ends record mode for its phase.** Fieldwork follows G4, completion G5, ready
  to release G6 and G7, released G8 and archived G9 (§3.3.2: each gate is what the next phase
  waits on). When any of a phase's gates has a registered provider, recording it is
  `phase_follows_gate`; the phase is derived instead when `gate.met` reports its gates met
  (mode `derived`, actor `system`). In review has no gate and is always recorded.
- **Human only (INV-1).** The matrix denies agent and system; the service refuses anything but a
  live person's own context; the table's CHECK refuses a `recorded` row whose actor isn't human.

Code moves states a person chose; it never decides one (ADR-005). No model is called.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, ClassVar, Final
from uuid import UUID, uuid4

from sqlalchemy import insert, select

from abacus.kernel.classification import classified
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.kernel.uow import (
    DomainEvent,
    MissingAuditEvent,
    Ref,
    Scope,
    Target,
    UnitOfWork,
    uow,
)
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.assurance.completion_repository import archive_of, release_of
from abacus.modules.assurance.external_models import external_archive_of, external_release_of
from abacus.modules.assurance.phase_models import AssurancePhaseEvent
from abacus.modules.engagements.api import (
    AssuranceItem,
    assurance_item,
    assurance_item_id,
    gate_fact,
    gate_registered,
    lock_assurance_item,
    lock_ref,
    set_assurance_profile,
)
from abacus.modules.identity.api import AuthContext, Forbidden, authorise

# The phases in their order (C2 `audit_engagement`, stored codes; `archiving` is the index's
# archive clock, never a recorded phase).
ORDER: Final[tuple[str, ...]] = (
    "planning",
    "fieldwork",
    "in_review",
    "completion",
    "ready_to_release",
    "released",
    "archived",
)
# DV-12: Completion has no AUD-01 tile until DF-05's artboard, so it is not offered yet.
NOT_OFFERED: Final[frozenset[str]] = frozenset({"completion"})
# The gates a phase waits on (blueprint §3.3.2).
PHASE_GATES: Final[Mapping[str, tuple[str, ...]]] = {
    "fieldwork": ("G4",),
    "completion": ("G5",),
    "ready_to_release": ("G6", "G7"),
    "released": ("G8",),
    "archived": ("G9",),
}
REASON_MAX: Final = 300
_SYSTEM_ACTOR: Final = "assurance.phase_derive"


class PhaseBackward(DomainConflict):
    """The target phase is the current one or before it: phases only move forward."""

    code = "phase_backward"


class PhaseSkip(DomainConflict):
    """The target phase is past the next one: a phase cannot be skipped."""

    code = "phase_skip"


class PhaseFollowsGate(DomainConflict):
    """The target phase's gate is computed by a registered provider: it derives from `gate.met`
    and cannot be recorded."""

    code = "phase_follows_gate"


class PhaseInvalid(DomainInvalid):
    """The reason is over 300 characters, or the target is not a phase."""

    code = "phase_invalid"


class ProfileStale(DomainConflict):
    """PATCH profile with a `seen_version` older than the row's."""

    code = "stale_version"


class AssurancePhaseChanged(DomainEvent):
    """An assurance work item's phase moved: identifiers and codes only."""

    event_type: ClassVar[str] = "assurance.phase_changed"

    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    from_phase: Annotated[str, classified("internal")]
    to_phase: Annotated[str, classified("internal")]
    mode: Annotated[str, classified("internal")]


@dataclass(frozen=True)
class PhaseMove:
    work_item_id: UUID
    event_id: UUID
    from_phase: str
    to_phase: str
    mode: str
    recorded_at: datetime
    version: int


@dataclass(frozen=True)
class Profile:
    work_item_id: UUID
    ebp_plan_kind: str | None
    limited_scope_103a3c: bool
    standards_set_id: UUID | None
    version: int


def _offered() -> tuple[str, ...]:
    return tuple(p for p in ORDER if p not in NOT_OFFERED)


def _rank(phase: str) -> int:
    return ORDER.index(phase) if phase in ORDER else -1


def next_phase(current: str) -> str | None:
    """The phase after `current` in the offered order, or None at the end."""
    offered = _offered()
    after = [p for p in offered if _rank(p) > _rank(current)]
    return after[0] if after else None


def follows_gate(phase: str) -> bool:
    """A phase leaves record mode once any of its gates has a provider."""
    return any(gate_registered(g) for g in PHASE_GATES.get(phase, ()))


def check_move(current: str, to: str) -> None:
    """AC-9, AC-10: forward one step, and only while the phase is in record mode."""
    if to not in ORDER:
        raise PhaseInvalid(facts={"to": "unknown"})
    if _rank(to) <= _rank(current):
        raise PhaseBackward(facts={"from_phase": current, "to_phase": to})
    if to != next_phase(current):
        raise PhaseSkip(facts={"from_phase": current, "to_phase": to})
    if follows_gate(to):
        gates = ":".join(PHASE_GATES[to])
        raise PhaseFollowsGate(facts={"to_phase": to, "gates": gates})


def _human(ctx: AuthContext, action: str) -> None:
    """INV-1: a person's own act, never an agent, the platform or a support session."""
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


def _reason_context(event_id: UUID) -> str:
    """What a sealed reason is bound to: its own event, so it opens only as that event's."""
    return hashlib.sha256(f"assurance_phase_event.reason:{event_id}".encode()).hexdigest()


async def reason_of(tenant: TenantContext, event_id: UUID) -> str | None:
    """A phase event's reason, opened for a caller that may read the engagement."""
    async with tenant_session(tenant) as session:
        sealed = await session.scalar(
            select(AssurancePhaseEvent.reason_sealed).where(AssurancePhaseEvent.id == event_id)
        )
    if sealed is None:
        return None
    return (await open_sealed(tenant.tenant_id, sealed, _reason_context(event_id))).decode()


async def _write_move(
    tx: UnitOfWork,
    tenant: TenantContext,
    item: AssuranceItem,
    to: str,
    *,
    mode: str,
    actor_user_id: UUID | None,
    mfa_at: datetime | None,
    gate_ref: str | None,
    reason: str | None,
) -> PhaseMove:
    """One event row; its insert trigger checks the actor and the move and moves the projection
    (DEC-262), so the phase never changes without its history."""
    event_id = uuid4()
    sealed = (
        None
        if not reason
        else await seal(tenant.tenant_id, reason.encode(), _reason_context(event_id))
    )
    row = (
        await tx.session.execute(
            insert(AssurancePhaseEvent)
            .values(
                id=event_id,
                tenant_id=tenant.tenant_id,
                engagement_id=item.engagement_id,
                work_item_id=item.work_item_id,
                from_phase=item.phase,
                to_phase=to,
                mode=mode,
                reason_sealed=sealed,
                gate_ref=gate_ref,
                actor_kind=tenant.actor_kind,
                actor_user_id=actor_user_id,
                mfa_at=mfa_at,
            )
            .returning(AssurancePhaseEvent.recorded_at)
        )
    ).one()
    moved = await lock_assurance_item(tx, item.work_item_id)
    tx.record(
        "assurance.phase_recorded" if mode == "recorded" else "assurance.phase_derived",
        target=Target("engagement", item.engagement_id),
        before=Ref(work_item=item.work_item_id, version=item.version),
        after=Ref(work_item=item.work_item_id, event=event_id, version=moved.version),
        scope=Scope(engagement_id=item.engagement_id),
    )
    tx.emit(
        AssurancePhaseChanged(
            engagement_id=item.engagement_id,
            work_item_id=item.work_item_id,
            from_phase=item.phase,
            to_phase=to,
            mode=mode,
        )
    )
    return PhaseMove(
        item.work_item_id, event_id, item.phase, to, mode, row.recorded_at, moved.version
    )


async def record_phase(
    ctx: AuthContext, work_item_id: UUID, to: str, reason: str | None = None
) -> PhaseMove:
    """AC-9 to AC-12: a named person records the next phase while its gate is uncomputed."""
    if reason is not None and len(reason) > REASON_MAX:
        raise PhaseInvalid(facts={"reason": "too_long"})
    found = await assurance_item(ctx.tenant, work_item_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, found.engagement_id)
        await authorise(ctx, "assurance.record_phase", ref.resource())
        _human(ctx, "assurance.record_phase")
        item = await lock_assurance_item(tx, work_item_id)
        check_move(item.phase, to)
        return await _write_move(
            tx,
            ctx.tenant,
            item,
            to,
            mode="recorded",
            actor_user_id=ctx.user_id,
            mfa_at=ctx.mfa_at,
            gate_ref=None,
            reason=reason,
        )


def phase_for_gate(gate: str) -> str | None:
    """The phase a gate opens, if any."""
    return next((p for p, gates in PHASE_GATES.items() if gate in gates), None)


async def _gates_met(tenant: TenantContext, engagement_id: UUID, phase: str) -> bool:
    """Every gate of `phase` is computed (registered) and met; a phase without a gate never is."""
    gates = PHASE_GATES.get(phase, ())
    if not gates or not all(gate_registered(g) for g in gates):
        return False
    for g in gates:
        if not (await gate_fact(tenant, engagement_id, g)).met:
            return False
    return True


async def derive_phase(tenant: TenantContext, engagement_id: UUID, gate: str) -> PhaseMove | None:
    """AC-13: a registered gate became met. The phase walks forward **one step at a time** while
    the next phase's gates are all computed and met, one event per step (a met G9 never moves
    Planning to Archived); a phase with no gate (In review) or an uncomputed one stops the walk.
    A replay moves nothing. The last move is returned."""
    if phase_for_gate(gate) is None or not gate_registered(gate):
        return None
    work_item = await assurance_item_id(tenant, engagement_id)
    if work_item is None:
        return None
    moved: PhaseMove | None = None
    # Another delivery of the same event may move it first: then nothing is written.
    with suppress(MissingAuditEvent):
        async with uow(tenant) as tx:
            item = await lock_assurance_item(tx, work_item)
            while (step := next_phase(item.phase)) is not None and await _gates_met(
                tenant, engagement_id, step
            ):
                moved = await _write_move(
                    tx,
                    tenant,
                    item,
                    step,
                    mode="derived",
                    actor_user_id=None,
                    mfa_at=None,
                    gate_ref=PHASE_GATES[step][-1],
                    reason=None,
                )
                item = await lock_assurance_item(tx, work_item)
    return moved


class PhaseGateUnmet(DomainConflict):
    """The gate a gate move names is not met (computed, never the caller's say), or does not
    open the target phase."""

    code = "phase_gate_unmet"


async def _gate_met_in(
    tx: UnitOfWork, tenant: TenantContext, engagement_id: UUID, gate: str
) -> bool:
    """Whether `gate` is met now, computed: G8 (released) and G9 (archive locked) from SPEC-314's
    own rows, or A-01-T23's external release and archive records, read in the caller's unit,
    where the act that meets them was just written; any other gate from its registered provider.
    An unregistered gate is never met."""
    if not gate_registered(gate):
        return False
    if gate == "G8":
        return (
            await release_of(tx.session, engagement_id) is not None
            or await external_release_of(tx.session, engagement_id) is not None
        )
    if gate == "G9":
        return (
            await archive_of(tx.session, engagement_id) is not None
            or await external_archive_of(tx.session, engagement_id) is not None
        )
    return (await gate_fact(tenant, engagement_id, gate)).met


async def advance_by_gate(
    tx: UnitOfWork,
    tenant: TenantContext,
    engagement_id: UUID,
    to: str,
    gate: str,
    actor_user_id: UUID | None,
) -> PhaseMove | None:
    """SPEC-314's release (G8) and archive lock (G9), in the caller's unit: the person whose act
    met the gate moves the phase forward to `to` with one derived event (mode `derived`, the
    gate named), so the history has no gap. Nothing moves when the phase is already there.

    Security review (DEC-312): module-internal (not in `assurance.api`); only a person's own
    context (`actor_user_id` must be the session's actor; a system run derives through
    `derive_phase`), only a gate that opens `to`, and only once that gate is met, computed here."""
    if (
        tenant.actor_kind != "human"
        or actor_user_id is None
        or str(actor_user_id) != tenant.actor_id
    ):
        raise Forbidden("assurance.phase_advance", "role")
    if gate not in PHASE_GATES.get(to, ()):
        raise PhaseGateUnmet(facts={"to_phase": to, "gate": gate})
    work_item = await assurance_item_id(tenant, engagement_id)
    if work_item is None:
        return None
    item = await lock_assurance_item(tx, work_item)
    if _rank(item.phase) >= _rank(to):
        return None
    if not await _gate_met_in(tx, tenant, engagement_id, gate):
        raise PhaseGateUnmet(facts={"to_phase": to, "gate": gate})
    return await _write_move(
        tx,
        tenant,
        item,
        to,
        mode="derived",
        actor_user_id=actor_user_id,
        mfa_at=None,
        gate_ref=gate,
        reason=None,
    )


async def on_gate_met(event: OutboxEvent) -> None:
    """C1's `gate.met` for an assurance engagement: derive the phase it opens (AC-13). Today only
    G1 to G3 emit `gate.met`, and they open no phase, so this is dormant until A-04 (G4) and the
    later gates emit (DEC-262)."""
    gate = str(event.payload.get("gate", ""))
    raw = event.payload.get("engagement_id")
    if not isinstance(raw, str) or phase_for_gate(gate) is None:
        return
    tenant = TenantContext(event.tenant_id, "system", _SYSTEM_ACTOR)
    await derive_phase(tenant, UUID(raw), gate)


SUBSCRIPTIONS = {"gate.met": on_gate_met}


# --- EBP profile (AC-14) ------------------------------------------------------------------------


async def update_profile(
    ctx: AuthContext,
    work_item_id: UUID,
    seen_version: int,
    changes: Mapping[str, str | bool | UUID | None],
) -> Profile:
    """The EBP label facts; a stale `seen_version` is 409 `stale_version`. Only the fields given
    change; the audit event names them."""
    found = await assurance_item(ctx.tenant, work_item_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, found.engagement_id)
        await authorise(ctx, "engagement.update", ref.resource())
        _human(ctx, "engagement.update")
        item = await lock_assurance_item(tx, work_item_id)
        if item.version != seen_version:
            raise ProfileStale(facts={"version": item.version})
        version = item.version
        if changes:
            version = await set_assurance_profile(tx, work_item_id, changes)
            tx.record(
                "assurance.profile_updated",
                target=Target("engagement", item.engagement_id),
                before=Ref(work_item=item.work_item_id, version=item.version),
                after=Ref(work_item=item.work_item_id, version=version, fields=len(changes)),
                scope=Scope(engagement_id=item.engagement_id),
            )
        merged = {
            "ebp_plan_kind": item.ebp_plan_kind,
            "limited_scope_103a3c": item.limited_scope_103a3c,
            "standards_set_id": item.standards_set_id,
            **changes,
        }
        return Profile(
            work_item_id,
            _str_or_none(merged["ebp_plan_kind"]),
            merged["limited_scope_103a3c"] is True,
            _uuid_or_none(merged["standards_set_id"]),
            version,
        )


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _uuid_or_none(value: object) -> UUID | None:
    return value if isinstance(value, UUID) else None

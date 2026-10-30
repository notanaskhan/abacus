"""Checkpoints (P-04-T32; ADR-160 clause 9; SHL-16; DEC-85, DEC-145).

A checkpoint is a saved state of one target (a return, a workpaper, a trial balance): who or what
made it (`author_kind` agent, person or import), why (`cause`), its content hash, and the field
changes from the checkpoint before it (`checkpoint_diffs`, computed by code, ADR-050). Nothing is
ever deleted: a restore is a new checkpoint, a decision is a new row.

- **Current** is derived, never stored: the newest checkpoint that is approved or saved (a restore
  is saved). A proposed or rejected checkpoint is never Current.
- **State** of a field at a checkpoint is the fold of every in-effect checkpoint's diffs up to it
  (approved or saved), plus the checkpoint's own diffs when it is only proposed or rejected. The
  compare views are code over those states: `previous` is the checkpoint's own diffs; `current`
  is every field whose value differs between Current and the checkpoint.
- **Approve and reject** are a person's (INV-1: `require_live_human`, the matrix's agent and system
  denies and reviewer functions, the human-only CHECK on `checkpoint_decisions`, and the human-only
  audit list from 0290). A checkpoint that came from an SHL-10 proposal is decided through that
  proposal (the owner's hook), so one decision is what SHL-16 and SHL-10 both show; the proposal
  service records the checkpoint decision in its own unit of work (`follow_proposal_decision`).
- **Approve** announces `checkpoint.approved` (identifiers only); T-01 and N-02 read the summed
  amount deltas (`checkpoint_deltas`, from `delta_facts`) to void a signed 8879 above the Pub 1345
  tolerances (DEC-85).
- **Propose** is service-only (`checkpoint.propose`): the agent through its task scope, the system
  for an engine import ("Import pending approval", T-01).
- CHECKPOINT-001: only this module writes `checkpoints`, `checkpoint_diffs` and
  `checkpoint_decisions` (`banned_patterns`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.engagements.api import engagement_resource_of
from abacus.modules.identity.api import (
    Actor,
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    names_of,
)
from abacus.modules.review.events import (
    CheckpointApproved,
    CheckpointRecorded,
    CheckpointRejected,
)
from abacus.modules.review.models import Checkpoint, CheckpointDecision, CheckpointDiff
from abacus.modules.review.repository import (
    checkpoint_decisions_of,
    checkpoint_diffs_of,
    checkpoints_of,
    get_checkpoint,
    insert_checkpoint,
    insert_checkpoint_decision,
    insert_checkpoint_diffs,
    lock_checkpoint,
    lock_proposed_for,
    lock_target,
    next_checkpoint_seq,
    set_checkpoint,
)
from abacus.modules.review.sealing import open_text, seal_text
from abacus.modules.review.slots import (
    ReviewableFacts,
    checkpoint_proposal_hooks,
    reviewable_facts,
)

SUBJECT: Final = "checkpoint"
READ: Final = "checkpoint.read"
CREATE: Final = "checkpoint.create"
APPROVE: Final = "checkpoint.approve"
REJECT: Final = "checkpoint.reject"
RESTORE: Final = "checkpoint.restore"
RENAME: Final = "checkpoint.rename"
PROPOSE: Final = "checkpoint.propose"
ROW_ACTIONS: Final = (APPROVE, REJECT, RESTORE, RENAME)
IN_EFFECT: Final = frozenset({"approved", "saved"})
NOTE_KIND: Final = "checkpoint.reject_reason"
IMPORT_AUTHOR: Final = "Imported Return"
AGENT_AUTHOR: Final = "Accrued Agent"

AuthorKind = Literal["agent", "person", "import"]
Cause = Literal["agent_run", "engine_import", "human_edit", "restore", "amendment", "manual_save"]
Filter = Literal["agent", "named", "all"]
Compare = Literal["current", "previous"]
Value = Mapping[str, object] | None


class CheckpointChanged(DomainConflict):
    """The checkpoint is no longer proposed, or its hash is not the one the person saw: nothing
    is written."""

    code = "checkpoint_changed"


class CheckpointInvalid(DomainInvalid):
    """A restore of a checkpoint that is not in effect, or of Current itself; an empty proposal."""

    code = "checkpoint_invalid"


# --- views -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionView:
    id: UUID
    decision: str
    reason: str | None
    decided_by_user_id: UUID
    decided_by_name: str
    decided_at: datetime
    proposal_decision_id: UUID | None


@dataclass(frozen=True)
class CheckpointView:
    id: UUID
    target_type: str
    target_id: UUID
    seq: int
    name: str | None
    starred: bool
    author_kind: str
    author_user_id: UUID | None
    author_name: str
    cause: str
    status: str
    current: bool
    summary: str | None
    created_at: datetime
    content_hash: str
    proposal_id: UUID | None
    restored_from_id: UUID | None
    agent_run_id: UUID | None
    decision: DecisionView | None
    allowed_actions: list[str]


@dataclass(frozen=True)
class CheckpointList:
    target_type: str
    target_id: UUID
    filter: Filter
    items: list[CheckpointView]
    current_checkpoint_id: UUID | None
    allowed_actions: list[str]


@dataclass(frozen=True)
class DiffRow:
    field_key: str
    label: str
    old: str | None
    new: str | None
    cause: str
    citation_ids: list[UUID]


@dataclass(frozen=True)
class TotalRow:
    label: str
    value: str
    ties: bool


@dataclass(frozen=True)
class Detail:
    checkpoint: CheckpointView
    compare: Compare
    compared_to_id: UUID | None
    diff: list[DiffRow]
    totals: list[TotalRow]


@dataclass(frozen=True)
class ProposedChange:
    """One field's change in a proposed checkpoint (the agent's or the import's), code-computed
    by the caller from the target's values. `delta_facts` are amount deltas by fact key."""

    field_key: str
    old: Value
    new: Value
    cause: str
    citation_ids: tuple[UUID, ...] = ()
    delta_facts: Mapping[str, str] | None = None


# --- helpers -----------------------------------------------------------------------------------


def _live_human(ctx: Actor) -> bool:
    """INV-1 (`require_live_human`): a person's own act, never an agent, the platform, a client
    principal or a break-glass support session."""
    return (
        isinstance(cast(object, ctx), AuthContext)
        and not cast(AuthContext, ctx).client
        and ctx.tenant.actor_kind == "human"
        and not cast(AuthContext, ctx).is_support
    )


def _human(ctx: Actor, action: str) -> AuthContext:
    if not _live_human(ctx):
        raise Forbidden(action, "role")
    return cast(AuthContext, ctx)


def hash_out(digest: str) -> str:
    return f"sha256:{digest}"


def _hash_in(seen: str) -> str:
    return seen.removeprefix("sha256:")


def _text(value: Value) -> str | None:
    """A typed value `{t, v}` as the diff shows it; null is an empty cell ("—")."""
    if value is None:
        return None
    v = value.get("v")
    return None if v is None else str(v)


def _decimal(text: str | None) -> Decimal | None:
    if text is None:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _label(field_key: str) -> str:
    """The owner's field key read as words until field owners publish labels (P-04-T35)."""
    return field_key.rsplit(".", 1)[-1].replace("_", " ")


def _current(rows: Sequence[Checkpoint]) -> Checkpoint | None:
    """Current: the newest checkpoint in effect (approved or saved); never stored."""
    return next((r for r in reversed(rows) if r.status in IN_EFFECT), None)


def _state_at(
    rows: Sequence[Checkpoint], diffs: Mapping[UUID, Sequence[CheckpointDiff]], seq: int
) -> dict[str, Value]:
    """Every field's value at checkpoint `seq`: the in-effect checkpoints' diffs up to it, then
    the checkpoint's own diffs when it is only proposed or rejected (code, ADR-050)."""
    state: dict[str, Value] = {}
    for row in rows:
        if row.seq > seq:
            break
        if row.status in IN_EFFECT or row.seq == seq:
            for d in diffs.get(row.id, ()):
                state[d.field_key] = d.new
    return state


def _deltas(diffs: Sequence[CheckpointDiff]) -> dict[str, str]:
    """The summed amount deltas by fact key (DEC-85), as decimal strings."""
    sums: dict[str, Decimal] = {}
    for d in diffs:
        for key, value in (d.delta_facts or {}).items():
            amount = _decimal(str(value))
            if amount is not None:
                sums[key] = sums.get(key, Decimal(0)) + amount
    return {k: str(v) for k, v in sorted(sums.items())}


async def _target(
    ctx: Actor, target_type: str, target_id: UUID
) -> tuple[ReviewableFacts, Resource]:
    """The target's owner facts and its engagement as the resource, with its work item for the
    reviewer-function condition (404 for walls and other firms, like every engagement read)."""
    facts = await reviewable_facts(ctx.tenant, target_type, target_id)
    resource = await engagement_resource_of(ctx.tenant, facts.engagement_id)
    return facts, replace(resource, work_item_id=facts.work_item_id)


async def _readable(
    ctx: Actor, checkpoint_id: UUID
) -> tuple[Checkpoint, ReviewableFacts, Resource]:
    async with tenant_session(ctx.tenant) as session:
        row = await get_checkpoint(session, checkpoint_id)
    if row is None:
        raise NotFound(SUBJECT)
    facts, resource = await _target(ctx, row.target_type, row.target_id)
    await authorise(ctx, READ, resource)
    return row, facts, resource


Loaded = tuple[
    list[Checkpoint], dict[UUID, list[CheckpointDiff]], dict[UUID, list[CheckpointDecision]]
]


async def _load_in(session: AsyncSession, target_type: str, target_id: UUID) -> Loaded:
    rows = list(await checkpoints_of(session, target_type, target_id))
    ids = [r.id for r in rows]
    diffs: dict[UUID, list[CheckpointDiff]] = {}
    for d in await checkpoint_diffs_of(session, ids):
        diffs.setdefault(d.checkpoint_id, []).append(d)
    decisions: dict[UUID, list[CheckpointDecision]] = {}
    for c in await checkpoint_decisions_of(session, ids):
        decisions.setdefault(c.checkpoint_id, []).append(c)
    return rows, diffs, decisions


async def _load(tenant: TenantContext, target_type: str, target_id: UUID) -> Loaded:
    async with tenant_session(tenant) as session:
        return await _load_in(session, target_type, target_id)


def _summary(diffs: Sequence[CheckpointDiff]) -> str | None:
    """The card's summary line: the first change, "<field> (<old> → <new>)", and how many more,
    code-built from the diff and nothing else."""
    if not diffs:
        return None
    first = diffs[0]
    old, new = _text(first.old) or "—", _text(first.new) or "—"
    more = f" and {len(diffs) - 1} more" if len(diffs) > 1 else ""
    return f"{_label(first.field_key)} ({old} → {new}){more}"


async def _view(
    ctx: Actor,
    row: Checkpoint,
    *,
    current_id: UUID | None,
    diffs: Sequence[CheckpointDiff],
    decisions: Sequence[CheckpointDecision],
    names: Mapping[UUID, str],
    held: Sequence[str],
) -> CheckpointView:
    author_user: UUID | None = None
    if row.author_kind == "person":
        try:
            author_user = UUID(row.author_ref)
        except ValueError:
            author_user = None
    author_name = (
        AGENT_AUTHOR
        if row.author_kind == "agent"
        else IMPORT_AUTHOR
        if row.author_kind == "import"
        else names.get(author_user, "")
        if author_user is not None
        else ""
    )
    newest = decisions[-1] if decisions else None
    decision: DecisionView | None = None
    if newest is not None:
        reason = (
            await open_text(ctx.tenant, newest.note_sealed, NOTE_KIND, newest.checkpoint_id)
            if newest.note_sealed is not None
            else None
        )
        decision = DecisionView(
            id=newest.id,
            decision=newest.decision,
            reason=reason,
            decided_by_user_id=newest.decided_by,
            decided_by_name=names.get(newest.decided_by, ""),
            decided_at=newest.created_at,
            proposal_decision_id=newest.proposal_decision_id,
        )
    is_current = row.id == current_id
    actions = [RENAME] if RENAME in held else []
    if row.status == "proposed":
        actions += [a for a in (APPROVE, REJECT) if a in held]
    elif row.status in IN_EFFECT and not is_current and RESTORE in held:
        actions.append(RESTORE)
    return CheckpointView(
        id=row.id,
        target_type=row.target_type,
        target_id=row.target_id,
        seq=row.seq,
        name=row.name,
        starred=row.starred,
        author_kind=row.author_kind,
        author_user_id=author_user,
        author_name=author_name,
        cause=row.cause,
        status=row.status,
        current=is_current,
        summary=_summary(diffs),
        created_at=row.created_at,
        content_hash=hash_out(row.content_hash),
        proposal_id=row.proposal_id,
        restored_from_id=row.restored_from_id,
        agent_run_id=row.run_id,
        decision=decision,
        allowed_actions=sorted(actions),
    )


async def _held(ctx: Actor, resource: Resource) -> list[str]:
    """What the caller could do on this target's checkpoints now (every layer); a non-person
    holds only reads."""
    if not _live_human(ctx):
        return []
    return list(await allowed_actions(cast(AuthContext, ctx), resource, [CREATE, *ROW_ACTIONS]))


async def _names(
    rows: Sequence[Checkpoint], decisions: Mapping[UUID, Sequence[CheckpointDecision]]
) -> dict[UUID, str]:
    ids: set[UUID] = {c.decided_by for ds in decisions.values() for c in ds}
    for r in rows:
        if r.author_kind == "person":
            try:
                ids.add(UUID(r.author_ref))
            except ValueError:
                continue
    return dict(await names_of(sorted(ids)))


# --- reads -------------------------------------------------------------------------------------


async def list_checkpoints(
    ctx: Actor, target_type: str, target_id: UUID, filter: Filter
) -> CheckpointList:
    """SHL-16: the target's checkpoints newest first, filtered Agent only, Named only or All;
    Current marked; `checkpoint.read` on the target's engagement."""
    facts, resource = await _target(ctx, target_type, target_id)
    await authorise(ctx, READ, resource)
    rows, diffs, decisions = await _load(ctx.tenant, facts.target_type, facts.target_id)
    current = _current(rows)
    held = await _held(ctx, resource)
    names = await _names(rows, decisions)
    shown = [
        r
        for r in reversed(rows)
        if filter == "all"
        or (filter == "agent" and r.author_kind == "agent")
        or (filter == "named" and r.name is not None)
    ]
    items = [
        await _view(
            ctx,
            r,
            current_id=current.id if current else None,
            diffs=diffs.get(r.id, []),
            decisions=decisions.get(r.id, []),
            names=names,
            held=held,
        )
        for r in shown
    ]
    return CheckpointList(
        target_type=facts.target_type,
        target_id=facts.target_id,
        filter=filter,
        items=items,
        current_checkpoint_id=current.id if current else None,
        allowed_actions=[CREATE] if CREATE in held else [],
    )


async def detail(ctx: Actor, checkpoint_id: UUID, compare: Compare) -> Detail:
    """SHL-16 a, c: the card and its code-computed diff, against the checkpoint before it
    (`previous`, its own changes) or against Current (every field whose value differs)."""
    row, facts, resource = await _readable(ctx, checkpoint_id)
    rows, diffs, decisions = await _load(ctx.tenant, facts.target_type, facts.target_id)
    current = _current(rows)
    held = await _held(ctx, resource)
    names = await _names(rows, decisions)
    view = await _view(
        ctx,
        row,
        current_id=current.id if current else None,
        diffs=diffs.get(row.id, []),
        decisions=decisions.get(row.id, []),
        names=names,
        held=held,
    )
    if compare == "previous":
        own = diffs.get(row.id, [])
        before = next((r.id for r in reversed(rows) if r.seq < row.seq), None)
        return Detail(
            checkpoint=view,
            compare="previous",
            compared_to_id=before,
            diff=[
                DiffRow(
                    field_key=d.field_key,
                    label=_label(d.field_key),
                    old=_text(d.old),
                    new=_text(d.new),
                    cause=d.cause,
                    citation_ids=list(d.citation_ids),
                )
                for d in own
            ],
            totals=[
                TotalRow(label=_label(k), value=v, ties=Decimal(v) == 0)
                for k, v in _deltas(own).items()
            ],
        )
    if current is None or current.id == row.id:
        return Detail(view, "current", current.id if current else None, [], [])
    then = _state_at(rows, diffs, row.seq)
    now = _state_at(rows, diffs, current.seq)
    return Detail(
        checkpoint=view,
        compare="current",
        compared_to_id=current.id,
        diff=[
            DiffRow(
                field_key=k,
                label=_label(k),
                old=_text(now.get(k)),
                new=_text(then.get(k)),
                cause="compare",
                citation_ids=[],
            )
            for k in _differing(then, now)
        ],
        totals=[],
    )


def _differing(then: Mapping[str, Value], now: Mapping[str, Value]) -> list[str]:
    """The fields whose value differs between two states, by key."""
    return sorted(k for k in then.keys() | now.keys() if _text(then.get(k)) != _text(now.get(k)))


async def checkpoint_deltas(tenant: TenantContext, checkpoint_id: UUID) -> dict[str, str]:
    """The summed amount deltas of one checkpoint by fact key, decimal strings (DEC-85), for a
    consumer of `checkpoint.approved` under its own tenant context. Restricted: return figures."""
    async with tenant_session(tenant) as session:
        if await get_checkpoint(session, checkpoint_id) is None:
            raise NotFound(SUBJECT)
        return _deltas(list(await checkpoint_diffs_of(session, [checkpoint_id])))


@dataclass(frozen=True)
class ApprovedValues:
    """A target's field values as of its latest approved checkpoint of a cause (T-01-T43: the
    return as filed is the latest approved engine import). Values are typed `{t, v}`."""

    checkpoint_id: UUID
    seq: int
    values: Mapping[str, Value]


async def approved_values(
    tenant: TenantContext, target_type: str, target_id: UUID, cause: Cause
) -> ApprovedValues | None:
    """Every field's value at the newest approved checkpoint with `cause`, or None when there is
    none; the caller has authorised its own read of the target (DEC-1651). Restricted when the
    target is a tax return (figures are TRI)."""
    rows, diffs, _ = await _load(tenant, target_type, target_id)
    chosen = next((r for r in reversed(rows) if r.status == "approved" and r.cause == cause), None)
    if chosen is None:
        return None
    return ApprovedValues(chosen.id, chosen.seq, _state_at(rows, diffs, chosen.seq))


# --- writes ------------------------------------------------------------------------------------


async def _insert(
    tx: UnitOfWork,
    ctx: Actor,
    facts: ReviewableFacts,
    *,
    author_kind: AuthorKind,
    author_ref: str,
    cause: Cause,
    status: str,
    content_hash: str,
    name: str | None = None,
    proposal_id: UUID | None = None,
    restored_from_id: UUID | None = None,
    run_id: UUID | None = None,
    engine_sync_event_id: UUID | None = None,
    changes: Sequence[ProposedChange] = (),
) -> tuple[UUID, int]:
    await lock_target(tx.session, facts.target_type, facts.target_id)
    seq = await next_checkpoint_seq(tx.session, facts.target_type, facts.target_id)
    checkpoint_id = await insert_checkpoint(
        tx.session,
        tenant_id=ctx.tenant_id,
        engagement_id=facts.engagement_id,
        target_type=facts.target_type,
        target_id=facts.target_id,
        seq=seq,
        name=name,
        starred=False,
        author_kind=author_kind,
        author_ref=author_ref,
        cause=cause,
        status=status,
        proposal_id=proposal_id,
        restored_from_id=restored_from_id,
        engine_sync_event_id=engine_sync_event_id,
        content_hash=content_hash,
        run_id=run_id,
    )
    await insert_checkpoint_diffs(
        tx.session,
        [
            {
                "tenant_id": ctx.tenant_id,
                "checkpoint_id": checkpoint_id,
                "field_key": c.field_key,
                "old": dict(c.old) if c.old is not None else None,
                "new": dict(c.new) if c.new is not None else None,
                "cause": c.cause,
                "citation_ids": list(c.citation_ids),
                "delta_facts": dict(c.delta_facts) if c.delta_facts else None,
            }
            for c in changes
        ],
    )
    tx.emit(
        CheckpointRecorded(
            checkpoint_id=checkpoint_id,
            engagement_id=facts.engagement_id,
            target_type=facts.target_type,
            target_id=facts.target_id,
            seq=seq,
            status=status,
            cause=cause,
        )
    )
    return checkpoint_id, seq


def _scope(facts: ReviewableFacts) -> Scope:
    return Scope(engagement_id=facts.engagement_id, work_item_id=facts.work_item_id)


async def _card(ctx: Actor, checkpoint_id: UUID) -> CheckpointView:
    """One card as the drawer shows it, after a write."""
    return (await detail(ctx, checkpoint_id, "previous")).checkpoint


async def save(ctx: Actor, target_type: str, target_id: UUID, name: str | None) -> CheckpointView:
    """SHL-16 f, "Save checkpoint…": a person's checkpoint of the target as it is now (cause
    `manual_save`, status `saved`, no field changes: the content hash records the state)."""
    person = _human(ctx, CREATE)
    facts, resource = await _target(person, target_type, target_id)
    await authorise(person, CREATE, resource)
    async with uow(person.tenant) as tx:
        checkpoint_id, seq = await _insert(
            tx,
            person,
            facts,
            author_kind="person",
            author_ref=str(person.user_id),
            cause="manual_save",
            status="saved",
            content_hash=facts.content_hash,
            name=name,
        )
        tx.record(
            "checkpoint.saved",
            target=Target(SUBJECT, checkpoint_id),
            after=Ref(seq=seq, target=facts.target_id, content=facts.content_hash),
            scope=_scope(facts),
        )
    return await _card(person, checkpoint_id)


async def record_human_edit(
    tx: UnitOfWork,
    person: AuthContext,
    facts: ReviewableFacts,
    change: ProposedChange,
    *,
    content_hash: str,
) -> UUID:
    """P-04-T35 (SHL-09 c, SHL-16): where the owner checkpoints, a person's field edit is also
    a person's checkpoint (cause `human_edit`, status `saved`: in effect at once), in the edit's
    own unit of work. The field service has authorised `field.edit` on the target."""
    checkpoint_id, seq = await _insert(
        tx,
        person,
        facts,
        author_kind="person",
        author_ref=str(person.user_id),
        cause="human_edit",
        status="saved",
        content_hash=content_hash.removeprefix("sha256:"),
        changes=(change,),
    )
    tx.record(
        "checkpoint.saved",
        target=Target(SUBJECT, checkpoint_id),
        after=Ref(seq=seq, target=facts.target_id, changes=1),
        scope=_scope(facts),
    )
    return checkpoint_id


async def propose(
    ctx: Actor,
    target_type: str,
    target_id: UUID,
    changes: Sequence[ProposedChange],
    *,
    author_kind: Literal["agent", "import"],
    cause: Cause,
    content_hash: str,
    proposal_id: UUID | None = None,
    run_id: UUID | None = None,
    engine_sync_event_id: UUID | None = None,
) -> UUID:
    """Service-only (`checkpoint.propose`): the agent through its task scope, or the system for
    an engine import ("Import pending approval"). Never a decision: the checkpoint waits on a
    person (status `proposed`). A proposal's checkpoint is made after its proposal and names it
    (`proposal_id`): deciding the proposal decides the checkpoint."""
    if not changes:
        raise CheckpointInvalid(facts={"reason": "no_changes"})
    facts, resource = await _target(ctx, target_type, target_id)
    await authorise(ctx, PROPOSE, resource)
    if run_id is None and isinstance(ctx, AgentContext):
        run_id = ctx.agent_run_id
    author_ref = str(run_id) if author_kind == "agent" and run_id is not None else author_kind
    async with uow(ctx.tenant) as tx:
        checkpoint_id, seq = await _insert(
            tx,
            ctx,
            facts,
            author_kind=author_kind,
            author_ref=author_ref,
            cause=cause,
            status="proposed",
            content_hash=content_hash.removeprefix("sha256:"),
            proposal_id=proposal_id,
            run_id=run_id,
            engine_sync_event_id=engine_sync_event_id,
            changes=changes,
        )
        tx.record(
            "checkpoint.proposed",
            target=Target(SUBJECT, checkpoint_id),
            after=Ref(seq=seq, target=facts.target_id, changes=len(changes)),
            scope=_scope(facts),
        )
    return checkpoint_id


async def _locked_proposed(tx: UnitOfWork, checkpoint_id: UUID, seen_hash: str) -> Checkpoint:
    row = await lock_checkpoint(tx.session, checkpoint_id)
    if row is None:
        raise NotFound(SUBJECT)
    if row.status != "proposed" or row.content_hash != _hash_in(seen_hash):
        raise CheckpointChanged(facts={"status": row.status})
    return row


async def _decide(
    tx: UnitOfWork,
    person: AuthContext,
    row: Checkpoint,
    scope: Scope,
    decision: Literal["approved", "rejected"],
    *,
    reason: str | None,
    proposal_decision_id: UUID | None,
) -> UUID:
    note = (
        await seal_text(person.tenant, reason, NOTE_KIND, row.id) if reason is not None else None
    )
    decision_id = await insert_checkpoint_decision(
        tx.session,
        tenant_id=person.tenant_id,
        checkpoint_id=row.id,
        decision=decision,
        reason_code=None,
        note_sealed=note,
        proposal_decision_id=proposal_decision_id,
        decided_by=person.user_id,
    )
    await set_checkpoint(tx.session, row.id, status=decision)
    tx.record(
        f"checkpoint.{decision}",
        target=Target(SUBJECT, row.id),
        after=Ref(seq=row.seq, decision=decision_id, content=row.content_hash)
        if proposal_decision_id is None
        else Ref(
            seq=row.seq,
            decision=decision_id,
            content=row.content_hash,
            proposal_decision=proposal_decision_id,
        ),
        scope=scope,
    )
    if decision == "approved":
        own = list(await checkpoint_diffs_of(tx.session, [row.id]))
        tx.emit(
            CheckpointApproved(
                checkpoint_id=row.id,
                engagement_id=row.engagement_id,
                target_type=row.target_type,
                target_id=row.target_id,
                decided_by=person.user_id,
                proposal_decision_id=proposal_decision_id,
                has_deltas=bool(_deltas(own)),
            )
        )
    else:
        tx.emit(
            CheckpointRejected(
                checkpoint_id=row.id,
                engagement_id=row.engagement_id,
                target_type=row.target_type,
                target_id=row.target_id,
                decided_by=person.user_id,
            )
        )
    return decision_id


async def approve(ctx: Actor, checkpoint_id: UUID, seen_hash: str) -> CheckpointView:
    """SHL-16 b: a person approves a proposed checkpoint on the hash they saw; Current moves and
    `checkpoint.approved` carries the deltas. A proposal's checkpoint is approved through that
    proposal (its owner's hook), so SHL-10 and SHL-16 show the same decision."""
    person = _human(ctx, APPROVE)
    row, facts, resource = await _readable(person, checkpoint_id)
    await authorise(person, APPROVE, resource)
    if row.proposal_id is not None:
        if row.status != "proposed" or row.content_hash != _hash_in(seen_hash):
            raise CheckpointChanged(facts={"status": row.status})
        hooks = checkpoint_proposal_hooks()
        await hooks.approve(person, row.proposal_id)
        return await _card(person, checkpoint_id)
    async with uow(person.tenant) as tx:
        locked = await _locked_proposed(tx, checkpoint_id, seen_hash)
        await _decide(
            tx, person, locked, _scope(facts), "approved", reason=None, proposal_decision_id=None
        )
    return await _card(person, checkpoint_id)


async def reject(ctx: Actor, checkpoint_id: UUID, seen_hash: str, reason: str) -> CheckpointView:
    """SHL-16 e: "Reject…" with a reason (sealed); through the proposal when it came from one."""
    person = _human(ctx, REJECT)
    row, facts, resource = await _readable(person, checkpoint_id)
    await authorise(person, REJECT, resource)
    if row.proposal_id is not None:
        if row.status != "proposed" or row.content_hash != _hash_in(seen_hash):
            raise CheckpointChanged(facts={"status": row.status})
        hooks = checkpoint_proposal_hooks()
        await hooks.reject(person, row.proposal_id, reason)
        return await _card(person, checkpoint_id)
    async with uow(person.tenant) as tx:
        locked = await _locked_proposed(tx, checkpoint_id, seen_hash)
        await _decide(
            tx, person, locked, _scope(facts), "rejected", reason=reason, proposal_decision_id=None
        )
    return await _card(person, checkpoint_id)


async def follow_proposal_decision(
    tx: UnitOfWork,
    ctx: Actor,
    proposal_id: UUID,
    decision: Literal["approved", "rejected"],
    proposal_decision_id: UUID,
    *,
    checkpoint_id: UUID | None = None,
    reason: str | None = None,
) -> None:
    """The proposal service's call inside its own unit of work (P-04-T24 approve or reject): each
    proposed checkpoint naming the proposal (or the one it names) takes the same decision, naming
    the proposal decision. One already decided is left as it is."""
    person = _human(ctx, APPROVE if decision == "approved" else REJECT)
    for row in await lock_proposed_for(tx.session, proposal_id, checkpoint_id):
        await _decide(
            tx,
            person,
            row,
            Scope(engagement_id=row.engagement_id),
            decision,
            reason=reason,
            proposal_decision_id=proposal_decision_id,
        )


async def restore(ctx: Actor, checkpoint_id: UUID, seen_hash: str) -> CheckpointView:
    """SHL-16 c: restoring Checkpoint 3 creates a new checkpoint (Checkpoint 7) whose changes are
    every field that differs from Current back to Checkpoint 3's values; nothing is deleted. Only
    a checkpoint in effect that is not Current can be restored."""
    person = _human(ctx, RESTORE)
    row, facts, resource = await _readable(person, checkpoint_id)
    await authorise(person, RESTORE, resource)
    async with uow(person.tenant) as tx:
        await lock_target(tx.session, facts.target_type, facts.target_id)
        rows, diffs, _ = await _load_in(tx.session, facts.target_type, facts.target_id)
        source = next((r for r in rows if r.id == checkpoint_id), None)
        current = _current(rows)
        if source is None or source.content_hash != _hash_in(seen_hash):
            raise CheckpointChanged(facts={"status": row.status})
        if source.status not in IN_EFFECT or current is None or current.id == source.id:
            raise CheckpointInvalid(facts={"reason": "not_restorable"})
        then = _state_at(rows, diffs, source.seq)
        now = _state_at(rows, diffs, current.seq)
        changes = [
            ProposedChange(field_key=k, old=now.get(k), new=then.get(k), cause="restore")
            for k in _differing(then, now)
        ]
        new_id, seq = await _insert(
            tx,
            person,
            facts,
            author_kind="person",
            author_ref=str(person.user_id),
            cause="restore",
            status="saved",
            content_hash=source.content_hash,
            restored_from_id=source.id,
            changes=changes,
        )
        await insert_checkpoint_decision(
            tx.session,
            tenant_id=person.tenant_id,
            checkpoint_id=new_id,
            decision="restored",
            reason_code=None,
            note_sealed=None,
            proposal_decision_id=None,
            decided_by=person.user_id,
        )
        tx.record(
            "checkpoint.restored",
            target=Target(SUBJECT, new_id),
            after=Ref(seq=seq, restored_from=source.id, restored_seq=source.seq),
            scope=_scope(facts),
        )
    return await _card(person, new_id)


async def rename(
    ctx: Actor, checkpoint_id: UUID, *, name: str | None, starred: bool | None, fields: set[str]
) -> CheckpointView:
    """SHL-16 d: rename and star change only `name` and `starred` (the column grant holds)."""
    person = _human(ctx, RENAME)
    _, facts, resource = await _readable(person, checkpoint_id)
    await authorise(person, RENAME, resource)
    values: dict[str, object] = {}
    if "name" in fields:
        values["name"] = name
    if "starred" in fields and starred is not None:
        values["starred"] = starred
    if values:
        async with uow(person.tenant) as tx:
            row = await lock_checkpoint(tx.session, checkpoint_id)
            if row is None:
                raise NotFound(SUBJECT)
            await set_checkpoint(tx.session, checkpoint_id, **values)
            tx.record(
                "checkpoint.renamed",
                target=Target(SUBJECT, checkpoint_id),
                after=Ref(seq=row.seq),
                scope=_scope(facts),
            )
    return await _card(person, checkpoint_id)


__all__ = [
    "APPROVE",
    "CREATE",
    "PROPOSE",
    "READ",
    "REJECT",
    "RENAME",
    "RESTORE",
    "ApprovedValues",
    "CheckpointChanged",
    "CheckpointInvalid",
    "CheckpointList",
    "CheckpointView",
    "Detail",
    "DiffRow",
    "ProposedChange",
    "TotalRow",
    "approve",
    "approved_values",
    "checkpoint_deltas",
    "detail",
    "follow_proposal_decision",
    "list_checkpoints",
    "propose",
    "reject",
    "rename",
    "restore",
    "save",
]

"""Proposals and suggestions (P-04-T24, TASK-1460; ADR-161 clauses 1 and 2; SHL-10; DEC-600 to
DEC-608).

The agent proposes, through its task scope (`create_proposal`, `create_suggestion`). A named person
decides: approve (with edits, each carrying a citation note), reject with a reason code, route to
a named approver, or record a follow-up; or adopt or dismiss a single suggestion.

- Every decision is a person's own act (INV-1): a live human ctx first, then the matrix row, then
  the database (human-only CHECKs on both decision tables, 0095; the state guards, 0230; the
  human-only audit list, 0231). PROPOSAL-001 names the only files that reach the decision
  functions.
- 409 `proposal_changed` when the proposal moved past the version the person saw, or is no longer
  pending. 422 `uncited_change` while a row has no citation C4 still verifies (and the person did
  not edit it with a citation note). 403 `forbidden {routed_to}` when the threshold policy routed
  it to someone else.
- An approval writes one field value per row through the target owner's registered applier
  (`review.api.record_value`, cause `suggestion_adopted`, or `edit` for an edited row), linked
  to the proposal's checkpoint. No applier: 503 before anything is written (fail closed).
- Notes and citation notes are sealed; handing a note over is an access event.
- Undo is P-04-T29's (its route still answers 501), so `undo_until` stays null here.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid, NotFound
from abacus.kernel.subject_states import SubjectState, register_subject_state
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.agents.events import (
    ProposalCreated,
    ProposalDecided,
    ProposalRouted,
    SuggestionCreated,
    SuggestionResolved,
)
from abacus.modules.agents.models import Proposal, ProposalRow, Suggestion
from abacus.modules.agents.proposal_slots import (
    AdoptedValue,
    ApprovedChangeSet,
    ChangeSetApplier,
    ProposedValue,
    SuggestionApplier,
    ThresholdEvaluation,
    change_set_applier,
    check_suggestion_target,
    suggestion_applier,
    target_on_engagement,
    threshold_policy,
)
from abacus.modules.agents.proposal_store import (
    get_proposal,
    get_suggestion,
    insert_proposal,
    insert_proposal_decision,
    insert_proposal_row,
    insert_suggestion,
    insert_suggestion_decision,
    latest_decision,
    latest_suggestion_decision,
    lock_proposal,
    lock_suggestion,
    lock_suggestions,
    rows_of,
    run_of,
    run_output_text,
    set_proposal,
    set_suggestion,
)
from abacus.modules.agents.stages import starts_in_shadow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.evidence.api import citation_sources, screening_facts, supported_citations
from abacus.modules.identity.api import (
    Actor,
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    member_could,
    names_of,
)
from abacus.modules.review.api import (
    CheckpointProposalHooks,
    UncitedChange,
    UnregisteredKind,
    field_owner,
    follow_proposal_decision,
    open_text,
    record_text_reads,
    register_checkpoint_proposal_hooks,
    seal_text,
    typed_value,
)

SUBJECT: Final = "proposal"
SUGGESTION: Final = "suggestion"
FIELD_CHANGE_SET: Final = "field_change_set"
READ: Final = "proposal.read"
APPROVE: Final = "proposal.approve"
REJECT: Final = "proposal.reject"
ROUTE: Final = "proposal.route"
FOLLOW_UP: Final = "proposal.follow_up"
CREATE: Final = "proposal.create"
RESOLVE: Final = "suggestion.resolve"
# P-04-T24 security review M1 (DEC-609): a generic change set is decided, and routed, only by
# those holding this action too; staff's firm setting on `proposal.approve` covers the typed
# evidence adapters alone.
CHANGE_SET: Final = "proposal.decide_change_set"
_PENDING_ACTIONS: Final = (APPROVE, REJECT, ROUTE, FOLLOW_UP)
_CODE: Final = re.compile(r"[a-z][a-z_]{0,39}")
_FIELD: Final = re.compile(r"[A-Za-z0-9_.!:-]{1,80}")
_REF: Final = re.compile(r"[A-Za-z0-9_.:-]{1,200}")
_NOTE_LIMIT: Final = 2000
_MAX_ROWS: Final = 100
REASONS: Final = frozenset({"wrong_treatment", "unsupported_value", "needs_client_input", "other"})


class ProposalChanged(DomainConflict):
    """The proposal moved past the version the person saw, or is no longer pending (ADR-161
    clause 2; the existing evidence semantics)."""

    code = "proposal_changed"


class SuggestionChanged(DomainConflict):
    """The suggestion moved past the version the person saw, or is no longer pending."""

    code = "suggestion_changed"


class ProposalInvalid(DomainInvalid):
    """A row, edit, approver, reason or follow-up the proposal can't take."""

    code = "proposal_invalid"


class RoutedElsewhere(DomainForbidden):
    """The firm's threshold policy routed this proposal to another approver (SHL-10 d): the
    caller may send it on, not approve it."""

    code = "forbidden"


# --- What the agent proposes -------------------------------------------------------------------


@dataclass(frozen=True)
class ProposedRow:
    """One change: a target field's value before and after (`{t, v}`, or None for an empty
    cell), its cause code and the citations the agent claims for it."""

    target_type: str
    target_id: UUID
    field_key: str
    label: str
    before: Mapping[str, object] | None
    after: Mapping[str, object] | None
    cause: str
    citation_ids: tuple[UUID, ...] = ()
    rationale_ref: str | None = None
    confidence: Decimal | None = None


# --- Views (the C3 projection; `agents/contract.py` serialises them) ---------------------------


@dataclass(frozen=True)
class RowView:
    n: int
    suggestion_id: UUID | None
    field_key: str
    label: str
    before: str | None
    after: str | None
    cause: str | None
    citation_ids: list[UUID]
    unsupported: bool


@dataclass(frozen=True)
class TotalView:
    label: str
    value: str
    ties: bool


@dataclass(frozen=True)
class EvidenceView:
    evidence_version_id: UUID
    label: str
    citation_count: int


@dataclass(frozen=True)
class PolicyView:
    policy_name: str | None
    result: Literal["within_threshold", "review_required"] | None
    routed_to_user_id: UUID | None
    routed_to_name: str | None
    note: str | None


@dataclass(frozen=True)
class SetView:
    set_type: str
    set_id: UUID
    label: str
    results: int
    exceptions: int


@dataclass(frozen=True)
class DecisionView:
    id: UUID
    decision: str
    reason_code: str | None
    note: str | None
    decided_by_user_id: UUID
    decided_by_name: str
    decided_at: datetime
    routed_to_user_id: UUID | None
    undo_until: datetime | None


@dataclass(frozen=True)
class ProposalView:
    ref: str
    kind: str
    title: str
    context_label: str
    state: str
    version: int
    agent_run_id: UUID | None
    proposed_at: datetime
    change_count: int
    reasoning: str
    rows: list[RowView]
    totals: list[TotalView]
    evidence: list[EvidenceView]
    policy: PolicyView | None
    set: SetView | None
    checkpoint_id: UUID | None
    decision: DecisionView | None
    allowed_actions: list[str]


@dataclass(frozen=True)
class SuggestionView:
    id: UUID
    target_type: str
    target_id: UUID
    field_key: str
    proposed_value: str
    rationale: str | None
    citation_ids: list[UUID]
    status: str
    version: int
    agent_run_id: UUID | None
    decision: str | None
    decided_by_user_id: UUID | None
    decided_at: datetime | None
    allowed_actions: list[str]


@dataclass(frozen=True)
class Edit:
    """An edited After value (`after`, a string read in the row's type) and its citation note."""

    n: int
    after: str
    citation_note: str


# --- Helpers -----------------------------------------------------------------------------------


def _live_human(ctx: Actor) -> bool:
    """INV-1: a decision is a person's own act: never an agent, the platform, a client principal
    or a break-glass support session."""
    return (
        isinstance(ctx, AuthContext)
        and not ctx.client
        and ctx.tenant.actor_kind == "human"
        and not ctx.is_support
    )


def _human(ctx: Actor, action: str) -> AuthContext:
    if not _live_human(ctx):
        raise Forbidden(action, "role")
    return cast(AuthContext, ctx)


def as_person(ctx: Actor, action: str) -> AuthContext:
    """The typed adapters' first line, as every decision function's (INV-1)."""
    return _human(ctx, action)


def _text(value: Mapping[str, object] | None) -> str | None:
    """A typed value as the wire's string: decimals as their string, bools as true or false."""
    if value is None:
        return None
    raw = value.get("v")
    if raw is None:
        return None
    if isinstance(raw, bool):
        return "true" if raw else "false"
    return str(raw)


def _typed(kind: str, text: str) -> dict[str, object]:
    """An edit's string read in the row's type (refused when it doesn't read)."""
    if kind == "bool":
        if text not in ("true", "false"):
            raise ProposalInvalid(facts={"field": "after"})
        return {"t": "bool", "v": text == "true"}
    try:
        return typed_value({"t": kind, "v": text})
    except DomainInvalid:
        raise ProposalInvalid(facts={"field": "after"}) from None


def _kind_of(row: ProposalRow) -> str:
    for value in (row.after, row.before):
        if value is not None and isinstance(value.get("t"), str):
            return str(value["t"])
    return "text"


def _field(row: ProposalRow) -> tuple[str, UUID, str]:
    ref = row.field_ref
    return str(ref["target_type"]), UUID(str(ref["target_id"])), str(ref["field_key"])


async def _may(ctx: AuthContext, action: str, resource: Resource) -> bool:
    try:
        await authorise(ctx, action, resource)
    except Forbidden:
        return False
    return True


def _stored_evaluation(proposal: Proposal) -> ThresholdEvaluation | None:
    """The evaluation the server stored at create (`policy_eval` is not updatable: 0095)."""
    raw = proposal.policy_eval or {}
    if raw.get("result") != "review_required":
        return None
    approver = raw.get("approver_user_id")
    return ThresholdEvaluation(
        policy_id=UUID(str(raw["policy_id"])),
        policy_name=str(raw.get("policy_name") or ""),
        version=int(cast(int, raw.get("version") or 0)),
        result="review_required",
        approver_user_id=UUID(str(approver)) if approver else None,
    )


async def _preparer(tenant: TenantContext, proposal: Proposal) -> UUID | None:
    """The person the agent's run acted for: never the approver of an over-limit change."""
    async with tenant_session(tenant) as session:
        run = await run_of(session, proposal.agent_run_id)
    return run.initiator_user_id if run is not None else None


async def _current(
    tenant: TenantContext, target_type: str, target_id: UUID, field_key: str
) -> Mapping[str, object] | None:
    """M2 (re-review): the value the target's owner holds now, read on the server through
    review's field-owner slot; never the agent's `before`. Unknown: None."""
    try:
        owner = field_owner(target_type)
    except UnregisteredKind:
        return None
    try:
        return await owner.value_of(tenant, target_id, field_key)
    except Exception:
        return None


async def _weighed(
    tenant: TenantContext, changes: Sequence[tuple[str, UUID, str, Mapping[str, object] | None]]
) -> tuple[ProposedValue, ...]:
    """The changes as the threshold policy weighs them: the owner's current value before, the
    value that would be written after."""
    return tuple(
        [
            ProposedValue(t, i, f, await _current(tenant, t, i, f), after)
            for t, i, f, after in changes
        ]
    )


def _row_changes(
    rows: Sequence[ProposalRow], edited: Mapping[int, tuple[dict[str, object], str]]
) -> list[tuple[str, UUID, str, Mapping[str, object] | None]]:
    return [(*_field(r), _value_of(r, edited)[0]) for r in rows]


async def _refusal(
    tenant: TenantContext,
    engagement_id: UUID,
    kind: str,
    evaluations: Sequence[ThresholdEvaluation],
    user_id: UUID,
    preparer: UUID | None,
    waiting: UUID | None,
) -> UUID | None:
    """H (DEC-609): under `review_required`, only the named approver or a person whose own limit
    covers it, never the preparer. Every evaluation must pass (the stricter wins). Returns the
    approver to route to, else None."""
    policy = threshold_policy(kind)
    for evaluation in evaluations:
        if evaluation.result != "review_required":
            continue
        named = evaluation.approver_user_id
        refused = named or waiting or user_id
        if user_id == preparer:
            return refused
        if user_id == named:
            continue
        if policy is None or not await policy.covers(tenant, engagement_id, user_id, evaluation):
            return refused
    return None


async def _over_limit(
    tenant: TenantContext,
    proposal: Proposal,
    user_id: UUID,
    rows: Sequence[ProposalRow],
    edited: Mapping[int, tuple[dict[str, object], str]] | None = None,
) -> UUID | None:
    """H, M3 (DEC-609, re-review): the evaluation stored at create and the policy's evaluation
    now, on the values that would be written (edits applied) against the owner's current
    values, must both pass; so a tightened firm threshold applies to a pending proposal. With
    the kind's policy gone, only the stored named approver qualifies (fail closed)."""
    engagement_id = cast(UUID, proposal.engagement_id)
    evaluations = [e for e in (_stored_evaluation(proposal),) if e is not None]
    policy = threshold_policy(proposal.kind)
    if policy is not None:
        now = await policy.evaluate(
            tenant,
            engagement_id,
            proposal.kind,
            await _weighed(tenant, _row_changes(rows, edited or {})),
        )
        if now is not None:
            evaluations.append(now)
    if not any(e.result == "review_required" for e in evaluations):
        return None
    return await _refusal(
        tenant,
        engagement_id,
        proposal.kind,
        evaluations,
        user_id,
        await _preparer(tenant, proposal),
        proposal.routed_to_user_id,
    )


async def _rows(ctx: AuthContext, proposal: Proposal) -> list[ProposalRow]:
    async with tenant_session(ctx.tenant) as session:
        return list(await rows_of(session, proposal.id))


async def _hidden(tenant: TenantContext, run_id: UUID) -> bool:
    """ED-171 (SPEC-036 AC-5): a shadow run's output, or anything while the firm's stage for
    that agent is shadow, is never shown to the firm."""
    async with tenant_session(tenant) as session:
        run = await run_of(session, run_id)
        if run is None or run.shadow:
            return True
        return await starts_in_shadow(session, tenant, run.agent_id)


async def _readable(ctx: AuthContext, proposal_id: UUID) -> tuple[Proposal, Resource]:
    async with tenant_session(ctx.tenant) as session:
        proposal = await get_proposal(session, proposal_id)
    if proposal is None or proposal.engagement_id is None:
        raise NotFound(SUBJECT)
    if await _hidden(ctx.tenant, proposal.agent_run_id):  # ED-171: answered as the typed paths
        raise NotFound(SUBJECT)
    ref = await get_ref(ctx, proposal.engagement_id)
    resource = ref.resource()
    await authorise(ctx, READ, resource)  # a wall answers 404
    return proposal, resource


async def _supported(
    tenant: TenantContext, engagement_id: UUID, rows: Sequence[ProposalRow]
) -> tuple[list[int], frozenset[UUID]]:
    """INV-2: the rows with no citation that C4 still verifies on the engagement now (the agent's
    stored `unsupported` flag counts too), and the citations that do verify."""
    cited = sorted({c for r in rows for c in r.citation_ids})
    supported = await supported_citations(tenant, engagement_id, cited)
    return [
        r.n
        for r in rows
        if r.unsupported or not r.citation_ids or not set(r.citation_ids) <= supported
    ], supported


# --- Create (the agent, through its task scope) ------------------------------------------------


def _checked_row(row: ProposedRow) -> None:
    if not _CODE.fullmatch(row.target_type) or not _FIELD.fullmatch(row.field_key):
        raise ProposalInvalid(facts={"field": "field_ref"})
    if not 1 <= len(row.label) <= 200 or not _CODE.fullmatch(row.cause):
        raise ProposalInvalid(facts={"field": "rows"})
    if row.rationale_ref is not None and not _REF.fullmatch(row.rationale_ref):
        raise ProposalInvalid(facts={"field": "rationale_ref"})
    for value in (row.before, row.after):
        if value is not None:
            typed_value(value)
    check_suggestion_target(row.target_type)  # 422 unregistered_target (fail closed)


async def _on_engagement(
    tenant: TenantContext, engagement_id: UUID, targets: Sequence[tuple[str, UUID]]
) -> None:
    """M4 (DEC-609): every target is the engagement's, as its owner says (fail closed)."""
    for target_type, target_id in dict.fromkeys(targets):
        if not await target_on_engagement(tenant, target_type, target_id, engagement_id):
            raise ProposalInvalid(facts={"field": "target_id"})


async def _creator(ctx: Actor, action: str, engagement_id: UUID) -> tuple[Resource, UUID]:
    """The agent proposes on its own engagement, through its task scope; its run is the
    proposal's (ADR-161 clause 2)."""
    if not isinstance(ctx, AgentContext):
        raise Forbidden(action, "role")
    if ctx.engagement_id != engagement_id:
        raise Forbidden(action, "relationship")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    return ref.resource(), ctx.agent_run_id


async def create_proposal(
    ctx: Actor,
    *,
    engagement_id: UUID,
    kind: str,
    title: str,
    rows: Sequence[ProposedRow],
    reasoning_ref: str | None = None,
    policy_note_ref: str | None = None,
    set_ref: Mapping[str, object] | None = None,
    checkpoint_id: UUID | None = None,
) -> UUID:
    """`agents.api.create_proposal` (`proposal.create`, the agent through `task_scope`): a change
    set with one suggestion per row, on targets of the engagement. Code marks each row
    `unsupported` unless every citation it claims is verified on the engagement now (C4), and the
    server evaluates the kind's threshold policy (M2, DEC-609): the agent never states it.
    `policy_note_ref` names the agent's note on the policy in its run output."""
    resource, run_id = await _creator(ctx, CREATE, engagement_id)
    if not _CODE.fullmatch(kind) or not 1 <= len(title) <= 200:
        raise ProposalInvalid(facts={"field": "kind"})
    if not rows or len(rows) > _MAX_ROWS:
        raise ProposalInvalid(facts={"field": "rows"})
    if reasoning_ref is not None and not _REF.fullmatch(reasoning_ref):
        raise ProposalInvalid(facts={"field": "reasoning_ref"})
    if policy_note_ref is not None and not _REF.fullmatch(policy_note_ref):
        raise ProposalInvalid(facts={"field": "policy_note_ref"})
    for row in rows:
        _checked_row(row)
    await _on_engagement(ctx.tenant, engagement_id, [(r.target_type, r.target_id) for r in rows])
    found = threshold_policy(kind)
    policy = (
        await found.evaluate(
            ctx.tenant,
            engagement_id,
            kind,
            await _weighed(
                ctx.tenant, [(r.target_type, r.target_id, r.field_key, r.after) for r in rows]
            ),
        )
        if found is not None
        else None
    )
    approver = policy.approver_user_id if policy is not None else None
    if isinstance(ctx, AgentContext) and approver == ctx.initiator.user_id:
        approver = None  # L6: never routed to its own preparer, who may not approve it
    if approver is not None and not await member_could(
        ctx.tenant_id, approver, CHANGE_SET, resource, waive_fresh_mfa=True
    ):
        raise ProposalInvalid(facts={"field": "routed_to_user_id"})
    cited = sorted({c for r in rows for c in r.citation_ids})
    supported = await supported_citations(ctx.tenant, engagement_id, cited)
    policy_json: dict[str, object] | None = (
        {
            "policy_id": str(policy.policy_id),
            "policy_name": policy.policy_name,
            "version": policy.version,
            "result": policy.result,
            "approver_user_id": str(approver) if approver else None,
            "note_ref": policy_note_ref,
        }
        if policy is not None
        else None
    )
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        proposal_id = await insert_proposal(
            tx.session,
            {
                "tenant_id": ctx.tenant_id,
                "engagement_id": engagement_id,
                "kind": kind,
                "title": title,
                "reasoning_ref": reasoning_ref,
                "policy_eval": policy_json,
                "routed_to_user_id": approver,
                "set_ref": dict(set_ref) if set_ref is not None else None,
                "checkpoint_id": checkpoint_id,
                "agent_run_id": run_id,
            },
        )
        for n, row in enumerate(rows, start=1):
            suggestion_id = await insert_suggestion(
                tx.session,
                {
                    "tenant_id": ctx.tenant_id,
                    "engagement_id": engagement_id,
                    "target_type": row.target_type,
                    "target_id": row.target_id,
                    "field_key": row.field_key,
                    "proposed_value": dict(
                        row.after or {"t": (row.before or {}).get("t") or "text", "v": None}
                    ),
                    "rationale_ref": row.rationale_ref,
                    "citation_ids": list(row.citation_ids),
                    "confidence": row.confidence,
                    "agent_run_id": run_id,
                    "proposal_id": proposal_id,
                },
            )
            await insert_proposal_row(
                tx.session,
                {
                    "tenant_id": ctx.tenant_id,
                    "proposal_id": proposal_id,
                    "n": n,
                    "suggestion_id": suggestion_id,
                    "field_ref": {
                        "target_type": row.target_type,
                        "target_id": str(row.target_id),
                        "field_key": row.field_key,
                    },
                    "label": row.label,
                    "before": dict(row.before) if row.before is not None else None,
                    "after": dict(row.after) if row.after is not None else None,
                    "cause": row.cause,
                    "citation_ids": list(row.citation_ids),
                    "unsupported": not row.citation_ids or not set(row.citation_ids) <= supported,
                },
            )
        tx.record(
            "proposal.created",
            target=Target(SUBJECT, proposal_id),
            after=Ref(version=1),
            scope=Scope(engagement_id=engagement_id),
        )
        tx.emit(
            ProposalCreated(
                proposal_id=proposal_id,
                engagement_id=engagement_id,
                kind=kind,
                agent_run_id=run_id,
            )
        )
        if approver is not None:
            tx.emit(
                ProposalRouted(
                    proposal_id=proposal_id,
                    engagement_id=engagement_id,
                    approver_user_id=approver,
                    actor_kind="agent",
                )
            )
    return proposal_id


async def create_suggestion(
    ctx: Actor,
    *,
    engagement_id: UUID,
    target_type: str,
    target_id: UUID,
    field_key: str,
    proposed_value: Mapping[str, object],
    citation_ids: Sequence[UUID] = (),
    rationale_ref: str | None = None,
    confidence: Decimal | None = None,
) -> UUID:
    """`agents.api.create_suggestion` (`suggestion.create`, the agent through `task_scope`):
    one proposed value for one target field (C-31 Adopt)."""
    await _creator(ctx, "suggestion.create", engagement_id)
    if not _CODE.fullmatch(target_type) or not _FIELD.fullmatch(field_key):
        raise ProposalInvalid(facts={"field": "field_key"})
    if rationale_ref is not None and not _REF.fullmatch(rationale_ref):
        raise ProposalInvalid(facts={"field": "rationale_ref"})
    check_suggestion_target(target_type)
    await _on_engagement(ctx.tenant, engagement_id, [(target_type, target_id)])
    value = typed_value(proposed_value)
    run_id = cast(AgentContext, ctx).agent_run_id
    # M1 (re-review): a value the firm's threshold policy would send for review is proposed as a
    # change set (its named approver, its preparer rules), never as a standalone suggestion.
    found = threshold_policy(FIELD_CHANGE_SET)
    if found is not None:
        evaluation = await found.evaluate(
            ctx.tenant,
            engagement_id,
            FIELD_CHANGE_SET,
            await _weighed(ctx.tenant, [(target_type, target_id, field_key, value)]),
        )
        if evaluation is not None and evaluation.result == "review_required":
            raise ProposalInvalid(facts={"field": "threshold"})
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        suggestion_id = await insert_suggestion(
            tx.session,
            {
                "tenant_id": ctx.tenant_id,
                "engagement_id": engagement_id,
                "target_type": target_type,
                "target_id": target_id,
                "field_key": field_key,
                "proposed_value": value,
                "rationale_ref": rationale_ref,
                "citation_ids": list(citation_ids),
                "confidence": confidence,
                "agent_run_id": run_id,
                "proposal_id": None,
            },
        )
        tx.record(
            "suggestion.created",
            target=Target(SUGGESTION, suggestion_id),
            scope=Scope(engagement_id=engagement_id),
        )
        tx.emit(
            SuggestionCreated(
                suggestion_id=suggestion_id,
                engagement_id=engagement_id,
                target_type=target_type,
                target_id=target_id,
            )
        )
    return suggestion_id


# --- Read --------------------------------------------------------------------------------------


async def _evidence(
    tenant: TenantContext, engagement_id: UUID, rows: Sequence[ProposalRow]
) -> list[EvidenceView]:
    """The evidence versions the rows' supported citations point at, with their counts."""
    cited = sorted({c for r in rows for c in r.citation_ids})
    supported = await supported_citations(tenant, engagement_id, cited)
    sources = await citation_sources(tenant, sorted(supported))
    counts: dict[UUID, int] = {}
    for citation in supported:
        version = sources.get(citation)
        if version is not None:
            counts[version] = counts.get(version, 0) + 1
    facts = await screening_facts(tenant, sorted(counts))
    return [
        EvidenceView(v, facts[v].file_name if v in facts else "", counts[v])
        for v in sorted(counts, key=lambda v: (facts[v].file_name if v in facts else "", str(v)))
    ]


async def _decision_view(
    ctx: AuthContext, proposal: Proposal, resource: Resource
) -> DecisionView | None:
    async with tenant_session(ctx.tenant) as session:
        found = await latest_decision(session, proposal.id)
    if found is None:
        return None
    note: str | None = None
    if found.note_sealed is not None:
        await record_text_reads(
            ctx.tenant,
            "proposal_decision",
            [found.id],
            engagement_id=cast(UUID, proposal.engagement_id),
            client_id=resource.client_id,
        )
        note = await open_text(
            ctx.tenant, found.note_sealed, "proposal_decision", found.id, "note"
        )
    names = await names_of([found.decided_by])
    return DecisionView(
        id=found.id,
        decision=found.decision,
        reason_code=found.reason_code,
        note=note,
        decided_by_user_id=found.decided_by,
        decided_by_name=names.get(found.decided_by, "Former member"),
        decided_at=found.created_at,
        routed_to_user_id=found.routed_to_user_id,
        undo_until=None,  # P-04-T29 serves Undo; until then nothing offers it
    )


async def _allowed(
    ctx: AuthContext, proposal: Proposal, resource: Resource, rows: Sequence[ProposalRow]
) -> list[str]:
    if not _live_human(ctx) or proposal.state != "pending":
        return []
    found = await allowed_actions(ctx, resource, (*_PENDING_ACTIONS, CHANGE_SET))
    out = [a for a in _PENDING_ACTIONS if a in found]
    if CHANGE_SET not in found:  # a generic change set is decided by its own action's holders
        out = [a for a in out if a not in (APPROVE, REJECT)]
    if APPROVE in out and await _over_limit(ctx.tenant, proposal, ctx.user_id, rows) is not None:
        out.remove(APPROVE)  # SHL-10 d: the CTA becomes "Send to <approver> for approval"
    return out


async def proposal_view(ctx: AuthContext, proposal_id: UUID) -> ProposalView:
    """`GET /v1/proposals/{id}` (SHL-10 a to g): the projection and the caller's actions."""
    proposal, resource = await _readable(ctx, proposal_id)
    engagement_id = cast(UUID, proposal.engagement_id)
    async with tenant_session(ctx.tenant) as session:
        rows = list(await rows_of(session, proposal.id))
        reasoning = (
            await run_output_text(session, proposal.agent_run_id, proposal.reasoning_ref)
            if proposal.reasoning_ref
            else None
        )
        policy_json = proposal.policy_eval or {}
        note_ref = policy_json.get("note_ref")
        policy_note = (
            await run_output_text(session, proposal.agent_run_id, note_ref)
            if isinstance(note_ref, str)
            else None
        )
    unsupported = (
        set((await _supported(ctx.tenant, engagement_id, rows))[0])
        if proposal.state == "pending"
        else {r.n for r in rows if r.unsupported}
    )
    policy: PolicyView | None = None
    if proposal.policy_eval is not None:
        routed = proposal.routed_to_user_id
        names = await names_of([routed]) if routed else {}
        result = policy_json.get("result")
        policy = PolicyView(
            policy_name=str(policy_json.get("policy_name") or "") or None,
            result=result if result in ("within_threshold", "review_required") else None,
            routed_to_user_id=routed,
            routed_to_name=names.get(routed) if routed else None,
            note=policy_note,
        )
    set_view: SetView | None = None
    raw_set = proposal.set_ref or {}
    if {"type", "id", "label"} <= set(raw_set):
        set_view = SetView(
            set_type=str(raw_set["type"]),
            set_id=UUID(str(raw_set["id"])),
            label=str(raw_set["label"]),
            results=int(cast(int, raw_set.get("results", 0))),
            exceptions=int(cast(int, raw_set.get("exceptions", 0))),
        )
    return ProposalView(
        ref=str(proposal.id),
        kind=proposal.kind,
        title=proposal.title,
        context_label="",
        state=proposal.state,
        version=proposal.version,
        agent_run_id=proposal.agent_run_id,
        proposed_at=proposal.created_at,
        change_count=len(rows),
        reasoning=reasoning or "",
        rows=[
            RowView(
                n=r.n,
                suggestion_id=r.suggestion_id,
                field_key=_field(r)[2],
                label=r.label,
                before=_text(r.before),
                after=_text(r.after),
                cause=r.cause,
                citation_ids=list(r.citation_ids),
                unsupported=r.n in unsupported,
            )
            for r in rows
        ],
        totals=[],
        evidence=await _evidence(ctx.tenant, engagement_id, rows),
        policy=policy,
        set=set_view,
        checkpoint_id=proposal.checkpoint_id,
        decision=await _decision_view(ctx, proposal, resource),
        allowed_actions=await _allowed(ctx, proposal, resource, rows),
    )


# --- Decide ------------------------------------------------------------------------------------


async def _locked(
    tx: UnitOfWork, ctx: AuthContext, proposal: Proposal, action: str, seen_version: int | None
) -> Proposal:
    """The proposal locked under its engagement, `action` authorised, and still pending at the
    version the person saw (None: any version, a follow-up)."""
    engagement_id = cast(UUID, proposal.engagement_id)
    ref = await lock_ref(tx, engagement_id)
    await authorise(ctx, action, ref.resource())
    if action in (APPROVE, REJECT):
        await authorise(ctx, CHANGE_SET, ref.resource())
    locked = await lock_proposal(tx.session, proposal.id)
    if locked is None or locked.engagement_id != engagement_id:
        raise NotFound(SUBJECT)
    if locked.state != "pending" or (seen_version is not None and locked.version != seen_version):
        raise ProposalChanged(facts={"version": locked.version})
    return locked


def _edits(
    rows: Sequence[ProposalRow], edits: Sequence[Edit]
) -> dict[int, tuple[dict[str, object], str]]:
    by_n = {r.n: r for r in rows}
    out: dict[int, tuple[dict[str, object], str]] = {}
    for edit in edits:
        row = by_n.get(edit.n)
        note = edit.citation_note.strip()
        if row is None or edit.n in out:
            raise ProposalInvalid(facts={"field": "edits"})
        if not note or len(note) > _NOTE_LIMIT:
            raise ProposalInvalid(facts={"field": "citation_note"})
        out[edit.n] = (_typed(_kind_of(row), edit.after), note)
    return out


def _value_of(
    row: ProposalRow, edited: Mapping[int, tuple[dict[str, object], str]]
) -> tuple[dict[str, object], str | None]:
    """The row's value to write: the person's edit with its note, else the agent's After."""
    if row.n in edited:
        return edited[row.n]
    return dict(row.after or {"t": _kind_of(row), "v": None}), None


async def _appliers(
    kind: str, rows: Sequence[ProposalRow]
) -> tuple[dict[str, SuggestionApplier], ChangeSetApplier | None]:
    """Every owner that will write, found before anything is written (503 when one is missing)."""
    if kind != FIELD_CHANGE_SET:
        return {}, change_set_applier(kind)
    return {t: suggestion_applier(t) for t in sorted({_field(r)[0] for r in rows})}, None


async def approve_proposal(
    ctx: Actor, proposal_id: UUID, *, seen_version: int, edits: Sequence[Edit]
) -> ProposalView:
    """`POST /v1/proposals/{id}/approve`: approve, or approve with edits (SHL-10 a to c). Order:
    a non-person 403; the matrix; 409 `proposal_changed`; 403 `forbidden {routed_to}`; 422
    `proposal_invalid` for a bad edit; 422 `uncited_change {count, row}`; 503 with no owner to
    write a row. One proposal decision, one suggestion decision and one field value per row."""
    person = _human(ctx, APPROVE)
    proposal, _ = await _readable(person, proposal_id)
    engagement_id = cast(UUID, proposal.engagement_id)
    decision_id = uuid4()
    async with uow(person.tenant) as tx:
        locked = await _locked(tx, person, proposal, APPROVE, seen_version)
        rows = list(await rows_of(tx.session, locked.id))
        edited = _edits(rows, edits)
        elsewhere = await _over_limit(person.tenant, locked, person.user_id, rows, edited)
        if elsewhere is not None:
            raise RoutedElsewhere(facts={"routed_to": str(elsewhere)})
        await _on_engagement(person.tenant, engagement_id, [_field(r)[:2] for r in rows])
        unsupported, supported = await _supported(person.tenant, engagement_id, rows)
        uncited = [n for n in unsupported if n not in edited]
        if uncited:
            raise UncitedChange(facts={"count": len(uncited), "row": uncited[0]})
        appliers, set_applier = await _appliers(locked.kind, rows)
        decision: Literal["approved", "approved_with_edits"] = (
            "approved_with_edits" if edited else "approved"
        )
        await insert_proposal_decision(
            tx.session,
            {
                "id": decision_id,
                "tenant_id": person.tenant_id,
                "proposal_id": locked.id,
                "decision": decision,
                "edits": [{"n": n, "after": v} for n, (v, _) in sorted(edited.items())] or None,
                "seen_version": seen_version,
                "decided_by": person.user_id,
            },
        )
        suggestions = await lock_suggestions(
            tx.session, [r.suggestion_id for r in rows if r.suggestion_id is not None]
        )
        values: list[AdoptedValue] = []
        for row in rows:
            target_type, target_id, field_key = _field(row)
            value, note = _value_of(row, edited)
            suggestion = suggestions.get(row.suggestion_id) if row.suggestion_id else None
            if suggestion is not None and suggestion.status == "pending":
                await _resolve_suggestion(
                    tx,
                    person,
                    suggestion,
                    "edited" if note is not None else "adopted",
                    edited_value=value if note is not None else None,
                    note=note,
                )
            values.append(
                AdoptedValue(
                    engagement_id=engagement_id,
                    target_type=target_type,
                    target_id=target_id,
                    field_key=field_key,
                    value=value,
                    value_source="human" if note is not None else "agent_suggested",
                    cause="edit" if note is not None else "suggestion_adopted",
                    suggestion_id=row.suggestion_id,
                    # M3 (DEC-609): only the citations C4 verifies now reach the history.
                    citation_ids=tuple(c for c in row.citation_ids if c in supported),
                    citation_note=note,
                    checkpoint_id=locked.checkpoint_id,
                    proposal_id=locked.id,
                )
            )
        version = await set_proposal(tx.session, locked.id, state=decision)
        # P-04-T32 (DEC-804): the proposal's checkpoint, if any, takes this decision, naming it.
        await follow_proposal_decision(
            tx, person, locked.id, "approved", decision_id, checkpoint_id=locked.checkpoint_id
        )
        if set_applier is not None:
            await set_applier(
                tx,
                person,
                ApprovedChangeSet(locked.id, locked.kind, engagement_id, decision, tuple(values)),
            )
        else:
            for value in values:
                await appliers[value.target_type](tx, person, value)
        tx.record(
            f"proposal.{decision}",
            target=Target(SUBJECT, locked.id),
            after=Ref(decision=decision_id, version=version, edits=len(edited)),
            scope=Scope(engagement_id=engagement_id),
        )
        tx.emit(
            ProposalDecided(
                proposal_id=locked.id,
                decision_id=decision_id,
                engagement_id=engagement_id,
                decision=decision,
                by_user=person.user_id,
            )
        )
    return await proposal_view(person, proposal_id)


async def _resolve_suggestion(
    tx: UnitOfWork,
    person: AuthContext,
    suggestion: Suggestion,
    decision: Literal["adopted", "edited", "dismissed"],
    *,
    edited_value: Mapping[str, object] | None = None,
    note: str | None = None,
    reason_code: str | None = None,
) -> int:
    """The person's decision row on one suggestion, then its status (0230 holds the order)."""
    decision_id = uuid4()
    await insert_suggestion_decision(
        tx.session,
        {
            "id": decision_id,
            "tenant_id": person.tenant_id,
            "suggestion_id": suggestion.id,
            "decision": decision,
            "edited_value": dict(edited_value) if edited_value is not None else None,
            "citation_note_sealed": await seal_text(
                person.tenant, note, "suggestion_decision", decision_id, "citation_note"
            )
            if note
            else None,
            "reason_code": reason_code,
            "decided_by": person.user_id,
        },
    )
    return await set_suggestion(tx.session, suggestion.id, decision)


async def reject_proposal(
    ctx: Actor, proposal_id: UUID, *, seen_version: int, reason_code: str, note: str | None
) -> ProposalView:
    """`POST /v1/proposals/{id}/reject` (SHL-10 f): "Rejected by <person> · reason: <reason>".
    Its pending suggestions are dismissed with the same reason; nothing is written to a field."""
    person = _human(ctx, REJECT)
    if reason_code not in REASONS:
        raise ProposalInvalid(facts={"field": "reason_code"})
    text = (note or "").strip()
    if len(text) > _NOTE_LIMIT or (reason_code == "other" and not text):
        raise ProposalInvalid(facts={"field": "note"})
    proposal, _ = await _readable(person, proposal_id)
    engagement_id = cast(UUID, proposal.engagement_id)
    decision_id = uuid4()
    async with uow(person.tenant) as tx:
        locked = await _locked(tx, person, proposal, REJECT, seen_version)
        await insert_proposal_decision(
            tx.session,
            {
                "id": decision_id,
                "tenant_id": person.tenant_id,
                "proposal_id": locked.id,
                "decision": "rejected",
                "reason_code": reason_code,
                "note_sealed": await seal_text(
                    person.tenant, text, "proposal_decision", decision_id, "note"
                )
                if text
                else None,
                "seen_version": seen_version,
                "decided_by": person.user_id,
            },
        )
        rows = await rows_of(tx.session, locked.id)
        suggestions = await lock_suggestions(
            tx.session, [r.suggestion_id for r in rows if r.suggestion_id is not None]
        )
        for suggestion in suggestions.values():
            if suggestion.status == "pending":
                await _resolve_suggestion(
                    tx, person, suggestion, "dismissed", reason_code=reason_code
                )
        version = await set_proposal(tx.session, locked.id, state="rejected")
        await follow_proposal_decision(
            tx,
            person,
            locked.id,
            "rejected",
            decision_id,
            checkpoint_id=locked.checkpoint_id,
            reason=text or None,
        )
        tx.record(
            "proposal.rejected",
            target=Target(SUBJECT, locked.id),
            after=Ref(decision=decision_id, version=version),
            scope=Scope(engagement_id=engagement_id),
        )
        tx.emit(
            ProposalDecided(
                proposal_id=locked.id,
                decision_id=decision_id,
                engagement_id=engagement_id,
                decision="rejected",
                reason_code=reason_code,
                by_user=person.user_id,
            )
        )
    return await proposal_view(person, proposal_id)


async def route_proposal(
    ctx: Actor, proposal_id: UUID, *, seen_version: int, approver_user_id: UUID
) -> ProposalView:
    """`POST /v1/proposals/{id}/route` (SHL-10 d): "Send to <approver> for approval". The
    approver is another person who may decide the change set on this engagement, never the
    run's preparer, and, when the threshold policy requires review, its named approver or a
    person whose limit covers it (H, DEC-609); they are told (`proposal_routed`). The proposal
    stays pending."""
    person = _human(ctx, ROUTE)
    proposal, resource = await _readable(person, proposal_id)
    engagement_id = cast(UUID, proposal.engagement_id)
    if (
        approver_user_id == person.user_id
        or approver_user_id == await _preparer(person.tenant, proposal)
        or not await member_could(
            person.tenant_id, approver_user_id, CHANGE_SET, resource, waive_fresh_mfa=True
        )
        or await _over_limit(
            person.tenant, proposal, approver_user_id, await _rows(person, proposal)
        )
        is not None
    ):
        raise ProposalInvalid(facts={"field": "approver_user_id"})
    decision_id = uuid4()
    async with uow(person.tenant) as tx:
        locked = await _locked(tx, person, proposal, ROUTE, seen_version)
        await insert_proposal_decision(
            tx.session,
            {
                "id": decision_id,
                "tenant_id": person.tenant_id,
                "proposal_id": locked.id,
                "decision": "routed",
                "routed_to_user_id": approver_user_id,
                "seen_version": seen_version,
                "decided_by": person.user_id,
            },
        )
        version = await set_proposal(tx.session, locked.id, routed_to_user_id=approver_user_id)
        tx.record(
            "proposal.routed",
            target=Target(SUBJECT, locked.id),
            after=Ref(decision=decision_id, version=version, user_id=approver_user_id),
            scope=Scope(engagement_id=engagement_id),
        )
        tx.emit(
            ProposalRouted(
                proposal_id=locked.id,
                engagement_id=engagement_id,
                approver_user_id=approver_user_id,
                by_user=person.user_id,
                actor_kind="human",
            )
        )
    return await proposal_view(person, proposal_id)


async def record_follow_up(
    ctx: Actor, proposal_id: UUID, *, text: str, idempotency_key: str
) -> ProposalView:
    """`POST /v1/proposals/{id}/follow-up` ("Ask follow-up"): a sealed follow-up recorded for
    the originating run (P-10 delivers it). The proposal is unchanged. A retry with the same
    `Idempotency-Key` writes nothing again (DEC-507's claim row; DEC-609)."""
    person = _human(ctx, FOLLOW_UP)
    body = (text or "").strip()
    if not body or len(body) > _NOTE_LIMIT:
        raise ProposalInvalid(facts={"field": "text"})
    proposal, resource = await _readable(person, proposal_id)
    await authorise(person, FOLLOW_UP, resource)  # also for a replay, which writes nothing

    async def run() -> tuple[int, dict[str, object]]:
        await _write_follow_up(person, proposal, body)
        return 200, {"proposal_id": str(proposal_id)}

    await idempotent(
        person.tenant,
        route=FOLLOW_UP,
        key=idempotency_key,
        body={"proposal_id": str(proposal_id), "text": hashlib.sha256(body.encode()).hexdigest()},
        run=run,
    )
    return await proposal_view(person, proposal_id)


async def _write_follow_up(person: AuthContext, proposal: Proposal, body: str) -> None:
    engagement_id = cast(UUID, proposal.engagement_id)
    decision_id = uuid4()
    async with uow(person.tenant) as tx:
        locked = await _locked(tx, person, proposal, FOLLOW_UP, None)
        await insert_proposal_decision(
            tx.session,
            {
                "id": decision_id,
                "tenant_id": person.tenant_id,
                "proposal_id": locked.id,
                "decision": "follow_up",
                "note_sealed": await seal_text(
                    person.tenant, body, "proposal_decision", decision_id, "note"
                ),
                "seen_version": locked.version,
                "decided_by": person.user_id,
            },
        )
        tx.record(
            "proposal.follow_up_recorded",
            target=Target(SUBJECT, locked.id),
            after=Ref(decision=decision_id),
            scope=Scope(engagement_id=engagement_id),
        )


# --- Suggestions (C-31 Adopt) ------------------------------------------------------------------


async def _suggestion_readable(
    ctx: AuthContext, suggestion_id: UUID
) -> tuple[Suggestion, Resource]:
    async with tenant_session(ctx.tenant) as session:
        found = await get_suggestion(session, suggestion_id)
    if found is None or found.engagement_id is None:
        raise NotFound(SUGGESTION)
    if await _hidden(ctx.tenant, found.agent_run_id):  # ED-171 (SPEC-036 AC-5)
        raise NotFound(SUGGESTION)
    ref = await get_ref(ctx, found.engagement_id)
    await authorise(ctx, READ, ref.resource())  # a wall answers 404
    return found, ref.resource()


async def suggestion_view(ctx: AuthContext, suggestion_id: UUID) -> SuggestionView:
    found, resource = await _suggestion_readable(ctx, suggestion_id)
    async with tenant_session(ctx.tenant) as session:
        decision = await latest_suggestion_decision(session, found.id)
        rationale = (
            await run_output_text(session, found.agent_run_id, found.rationale_ref)
            if found.rationale_ref
            else None
        )
    may = (
        found.status == "pending"
        and found.proposal_id is None
        and _live_human(ctx)
        and await _may(ctx, RESOLVE, resource)
    )
    return SuggestionView(
        id=found.id,
        target_type=found.target_type,
        target_id=found.target_id,
        field_key=found.field_key,
        proposed_value=_text(found.proposed_value) or "",
        rationale=rationale,
        citation_ids=list(found.citation_ids),
        status=found.status,
        version=found.version,
        agent_run_id=found.agent_run_id,
        decision=decision.decision if decision else None,
        decided_by_user_id=decision.decided_by if decision else None,
        decided_at=decision.created_at if decision else None,
        allowed_actions=[RESOLVE] if may else [],
    )


async def _suggestion_locked(
    tx: UnitOfWork, ctx: AuthContext, found: Suggestion, seen_version: int
) -> Suggestion:
    engagement_id = cast(UUID, found.engagement_id)
    ref = await lock_ref(tx, engagement_id)
    await authorise(ctx, RESOLVE, ref.resource())
    locked = await lock_suggestion(tx.session, found.id)
    if locked is None or locked.engagement_id != engagement_id:
        raise NotFound(SUGGESTION)
    if locked.proposal_id is not None:
        # A change set's row is decided with its proposal, never alone.
        raise ProposalInvalid(facts={"field": "proposal_id"})
    if locked.status != "pending" or locked.version != seen_version:
        raise SuggestionChanged(facts={"version": locked.version})
    return locked


async def adopt_suggestion(
    ctx: Actor,
    suggestion_id: UUID,
    *,
    seen_version: int,
    edited_value: str | None,
    citation_note: str | None,
) -> SuggestionView:
    """`POST /v1/suggestions/{id}/adopt`: as proposed (its citations verified now, else 422
    `uncited_change`), or with an edited value and its citation note (decision `edited`). The
    target's owner writes the field value."""
    person = _human(ctx, RESOLVE)
    note = (citation_note or "").strip()
    if edited_value is not None and (not note or len(note) > _NOTE_LIMIT):
        raise ProposalInvalid(facts={"field": "citation_note"})
    found, _ = await _suggestion_readable(person, suggestion_id)
    engagement_id = cast(UUID, found.engagement_id)
    async with uow(person.tenant) as tx:
        locked = await _suggestion_locked(tx, person, found, seen_version)
        applier = suggestion_applier(locked.target_type)  # 503 before anything is written
        kind = str(locked.proposed_value.get("t") or "text")
        value = (
            _typed(kind, edited_value)
            if edited_value is not None
            else typed_value(locked.proposed_value)
        )
        await _on_engagement(
            person.tenant, engagement_id, [(locked.target_type, locked.target_id)]
        )
        # M1 (re-review): adopting is held to the firm's threshold policy as a change set is:
        # evaluated now against the owner's current value; under `review_required` only the
        # named approver or a covered person, never the run's preparer.
        found_policy = threshold_policy(FIELD_CHANGE_SET)
        if found_policy is not None:
            now = await found_policy.evaluate(
                person.tenant,
                engagement_id,
                FIELD_CHANGE_SET,
                await _weighed(
                    person.tenant,
                    [(locked.target_type, locked.target_id, locked.field_key, value)],
                ),
            )
            async with tenant_session(person.tenant) as session:
                run = await run_of(session, locked.agent_run_id)
            elsewhere = await _refusal(
                person.tenant,
                engagement_id,
                FIELD_CHANGE_SET,
                [now] if now is not None else [],
                person.user_id,
                run.initiator_user_id if run is not None else None,
                None,
            )
            if elsewhere is not None:
                raise RoutedElsewhere(facts={"routed_to": str(elsewhere)})
        supported = await supported_citations(
            person.tenant, engagement_id, list(locked.citation_ids)
        )
        if edited_value is None and (
            not locked.citation_ids or not set(locked.citation_ids) <= supported
        ):
            raise UncitedChange(facts={"count": 1})
        decision: Literal["adopted", "edited"] = (
            "edited" if edited_value is not None else "adopted"
        )
        version = await _resolve_suggestion(
            tx,
            person,
            locked,
            decision,
            edited_value=value if edited_value is not None else None,
            note=note or None,
        )
        await applier(
            tx,
            person,
            AdoptedValue(
                engagement_id=engagement_id,
                target_type=locked.target_type,
                target_id=locked.target_id,
                field_key=locked.field_key,
                value=value,
                value_source="human" if edited_value is not None else "agent_suggested",
                cause="edit" if edited_value is not None else "suggestion_adopted",
                suggestion_id=locked.id,
                # M3 (DEC-609): only the citations C4 verifies now reach the history.
                citation_ids=tuple(c for c in locked.citation_ids if c in supported),
                citation_note=note or None,
                checkpoint_id=None,
                proposal_id=None,
            ),
        )
        tx.record(
            f"suggestion.{decision}",
            target=Target(SUGGESTION, locked.id),
            after=Ref(version=version),
            scope=Scope(engagement_id=engagement_id),
        )
        tx.emit(
            SuggestionResolved(
                suggestion_id=locked.id,
                engagement_id=engagement_id,
                decision=decision,
                by_user=person.user_id,
            )
        )
    return await suggestion_view(person, suggestion_id)


async def dismiss_suggestion(
    ctx: Actor, suggestion_id: UUID, *, seen_version: int, reason_code: str | None
) -> SuggestionView:
    """`POST /v1/suggestions/{id}/dismiss`: nothing is written to the field."""
    person = _human(ctx, RESOLVE)
    if reason_code is not None and reason_code not in REASONS:
        raise ProposalInvalid(facts={"field": "reason_code"})
    found, _ = await _suggestion_readable(person, suggestion_id)
    engagement_id = cast(UUID, found.engagement_id)
    async with uow(person.tenant) as tx:
        locked = await _suggestion_locked(tx, person, found, seen_version)
        version = await _resolve_suggestion(
            tx, person, locked, "dismissed", reason_code=reason_code
        )
        tx.record(
            "suggestion.dismissed",
            target=Target(SUGGESTION, locked.id),
            after=Ref(version=version),
            scope=Scope(engagement_id=engagement_id),
        )
        tx.emit(
            SuggestionResolved(
                suggestion_id=locked.id,
                engagement_id=engagement_id,
                decision="dismissed",
                by_user=person.user_id,
            )
        )
    return await suggestion_view(person, suggestion_id)


# --- The notification drawer's read (P-04-T26; `kernel.subject_states`) ------------------------


async def proposal_state(
    tenant: TenantContext, user_id: UUID, proposal_id: UUID
) -> SubjectState | None:
    """A proposal waits on its routed approver (or, with none, whoever reads it) while pending;
    its facts are codes and counts only."""
    async with tenant_session(tenant) as session:
        found = await get_proposal(session, proposal_id)
    if found is None:
        return None
    return SubjectState(
        pending=found.state == "pending" and found.routed_to_user_id in (None, user_id),
        facts={"proposal_kind": found.kind, "state": found.state, "version": found.version},
    )


def register_proposal_state() -> None:
    register_subject_state(SUBJECT, proposal_state)


async def _version(person: AuthContext, proposal_id: UUID) -> int:
    async with tenant_session(person.tenant) as session:
        found = await get_proposal(session, proposal_id)
    if found is None:
        raise NotFound(SUBJECT)
    return found.version


async def _approve_for_checkpoint(ctx: object, proposal_id: UUID) -> None:
    """SHL-16 b on a proposal's checkpoint: the proposal is approved as it stands (no edits), so
    the one decision is the proposal's (P-04-T32, DEC-804)."""
    person = _human(cast(Actor, ctx), APPROVE)
    await approve_proposal(
        person, proposal_id, seen_version=await _version(person, proposal_id), edits=()
    )


async def _reject_for_checkpoint(ctx: object, proposal_id: UUID, reason: str) -> None:
    """SHL-16 e on a proposal's checkpoint: rejected with the person's reason as the note."""
    person = _human(cast(Actor, ctx), REJECT)
    await reject_proposal(
        person,
        proposal_id,
        seen_version=await _version(person, proposal_id),
        reason_code="other",
        note=reason,
    )


def register_checkpoint_hooks() -> None:
    register_checkpoint_proposal_hooks(
        CheckpointProposalHooks(approve=_approve_for_checkpoint, reject=_reject_for_checkpoint)
    )


__all__ = [
    "Edit",
    "ProposalChanged",
    "ProposalInvalid",
    "ProposalView",
    "ProposedRow",
    "RoutedElsewhere",
    "SuggestionChanged",
    "SuggestionView",
    "adopt_suggestion",
    "approve_proposal",
    "as_person",
    "create_proposal",
    "create_suggestion",
    "dismiss_suggestion",
    "proposal_view",
    "record_follow_up",
    "register_checkpoint_hooks",
    "reject_proposal",
    "route_proposal",
    "suggestion_view",
]

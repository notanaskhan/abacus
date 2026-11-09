"""C18's service: the portal's approvals, composed from the registered kinds (R-02-T11; R-02 §3.1;
SPEC-646 AC-1 to AC-7; DEC-63, DEC-3009). PROTECTED.
Contract: `docs/contracts/portal-approvals.md`.

The one file, beside each provider's record mode, that calls a provider's `decide()`
(CLIENT-DECISION-001). Every read and decision is the portal person's own:

- **Live client human** (AC-5): a human client context from a portal session. An agent, the
  system, support or a firm person is refused here as well as by the matrix (which denies them
  every approval action) and by each provider's human-only decision row.
- **Scope** (`scope_only`): an item is listed or shown only when its provider reports it
  `sent_to_client` and one of the person's active grants covers its scope; otherwise 404.
- **Decider** (DEC-63; OQ-1, DEC-2400): an owner grant covering the item or the approver-of-record
  designation on its engagement; for `fs_package` on an attest client also the SKE designee. In
  scope but not the decider: 403 `not_decider`.
- **Fresh second factor**: the matrix's `mfa_recent` on every decide action (401); the decision
  carries the person's actual MFA time (`ClientDecisionContext.mfa_verified_at`).
- **What you saw is what you decided** (AC-4): a stale `seen_hash` is 409 `item_changed`, nothing
  written. **Idempotency-Key**: the same key and body give one decision and the first answer.
- **Attribution** (AC-6): the provider receives the person's contact, grant, basis, MFA time and
  portal session; its row reads "Dana Kowalski (client)", never "via Agent".

Nothing here posts to a client ledger (AC-10) or carries an internal figure (AC-7).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.engagements.api import (
    ApprovalItem,
    ApprovalScope,
    ClientApprovalDecided,
    ClientApprovalKind,
    ClientDecision,
    ClientDecisionContext,
    ItemChanged,
    NotDecider,
    client_approval_kinds,
    client_approval_provider,
    covering_grant,
    decider_for,
    engagements_of_client,
    engagements_of_entity,
)
from abacus.modules.identity.api import AuthContext, Forbidden, active_grants, scope_facts
from abacus.modules.organisations.api import attest_client_of

ApprovalFilter = Literal["waiting", "posted", "approved", "declined"]
ApprovalAction = Literal["accept", "decline", "approve", "acknowledge", "ask"]
_WAITING: Final = frozenset({"waiting", "question_sent"})
_APPROVED: Final = frozenset({"approved", "accepted", "acknowledged"})
_DECLINED: Final = frozenset({"declined", "not_recorded"})
# What a decider may do on a waiting item of each kind; everyone in scope may ask.
_ACTIONS: Final[dict[str, tuple[ApprovalAction, ...]]] = {
    "proposed_entry": ("accept", "decline"),
    "uncorrected_misstatements": ("acknowledge",),
    "fs_draft": ("approve",),
    "fs_package": ("approve", "decline"),
}
# Where the trail places a client decision: the decided item's own target type (SPEC-304).
TARGET_OF: Final[dict[str, str]] = {
    "proposed_entry": "proposed_entry",
    "fs_draft": "statement_version",
    "fs_package": "statement_version",
    # uncorrected_misstatements: placed by its provider when R-02-T15 registers the kind.
}
ROUTES: Final[dict[str, str]] = {
    "proposed_entry": "portal.approvals.proposed_entry.decide",
    "uncorrected_misstatements": "portal.approvals.uncorrected.acknowledge",
    "fs_draft": "portal.approvals.fs_draft.approve",
    "fs_package": "portal.approvals.package.decide",
}


def live_client_human(ctx: AuthContext, action: str) -> None:
    """AC-5's service layer: a client person in a portal session, never anyone acting for one."""
    if ctx.tenant.actor_kind != "human" or not ctx.client or ctx.is_support:
        raise Forbidden(action, "role")
    if ctx.portal_session_id is None:
        raise Forbidden(action, "role")


async def _scope_of(ctx: AuthContext, item: ApprovalItem) -> ApprovalScope | None:
    facts = await scope_facts(ctx.tenant, item.scope_kind, item.scope_id)
    if facts is None:
        return None
    return ApprovalScope(facts.client_id, facts.engagement_id, facts.work_item_id)


@dataclass(frozen=True)
class Shown:
    item: ApprovalItem
    actions: tuple[ApprovalAction, ...]


async def _shown(ctx: AuthContext, item: ApprovalItem) -> Shown | None:
    """The item as this person may see it, or None when it isn't theirs to see."""
    if not item.sent_to_client:
        return None
    at = await _scope_of(ctx, item)
    if at is None or await covering_grant(ctx.tenant, ctx.user_id, at) is None:
        return None
    actions: tuple[ApprovalAction, ...] = ("ask",)
    if item.state in _WAITING:
        attest = bool(await attest_client_of(ctx.tenant, at.client_id))
        if await decider_for(ctx.tenant, ctx.user_id, item.kind, at, attest) is not None:
            actions = (*_ACTIONS[item.kind], "ask")
    return Shown(item, actions)


def _bucket(state: str) -> ApprovalFilter:
    if state in _APPROVED:
        return "approved"
    if state in _DECLINED:
        return "declined"
    return "waiting"


@dataclass(frozen=True)
class Listing:
    items: list[Shown]
    counts: dict[ApprovalFilter, int]


async def approvals(
    ctx: AuthContext, scope_id: UUID | None, filter: ApprovalFilter | None
) -> Listing:
    """POR-08: every registered kind's items on the person's covered scopes (one scope when
    `scope_id` is given), counted by state, filtered after counting."""
    live_client_human(ctx, "client_approval.read")
    scopes = await _covered_scopes(ctx, scope_id)
    shown: list[Shown] = []
    for kind in sorted(client_approval_kinds()):
        provider = client_approval_provider(kind)
        for scope in scopes:
            for item in await provider.items(ctx.tenant, scope):
                found = await _shown(ctx, item)
                if found is not None:
                    shown.append(found)
    counts: dict[ApprovalFilter, int] = {"waiting": 0, "posted": 0, "approved": 0, "declined": 0}
    for s in shown:
        counts[_bucket(s.item.state)] += 1
    if filter is not None:
        shown = [s for s in shown if _bucket(s.item.state) == filter]
    return Listing(sorted(shown, key=lambda s: (s.item.title, str(s.item.item_id))), counts)


async def _covered_scopes(ctx: AuthContext, scope_id: UUID | None) -> list[UUID]:
    """The scope ids the person's grants name (a grant on a work item names that item); one of
    them when asked for. Providers list their items per scope id."""
    grants = await active_grants(ctx.tenant, ctx.user_id)
    ids: list[UUID] = []
    for g in grants:
        # A client or entity grant covers its engagements (DEC-3025): providers list by an
        # engagement or work item, and `_shown` still judges each item by its covering grant.
        if g.scope_kind == "client":
            ids += await engagements_of_client(ctx.tenant, g.scope_id)
        elif g.scope_kind == "client_entity":
            ids += await engagements_of_entity(ctx.tenant, g.scope_id)
        ids.append(g.scope_id)
    ids = list(dict.fromkeys(ids))
    if scope_id is not None:
        return [scope_id] if scope_id in ids else []
    return ids


async def approval(ctx: AuthContext, kind: str, item_id: UUID) -> Shown:
    """One item's detail; 404 when it isn't sent or the person's grants don't cover it."""
    live_client_human(ctx, "client_approval.read")
    provider = client_approval_provider(kind)
    item = await provider.item(ctx.tenant, item_id)
    found = None if item is None else await _shown(ctx, item)
    if found is None:
        raise NotFound("client_approval")
    return found


async def client_decide(
    ctx: AuthContext,
    kind: ClientApprovalKind,
    item_id: UUID,
    decision: ClientDecision,
    *,
    action: str,
    idempotency_key: str | None,
) -> ApprovalItem:
    """Put the person's decision to the item's provider, once per key (module docstring)."""
    live_client_human(ctx, action)
    provider = client_approval_provider(kind)

    async def run() -> tuple[int, dict[str, object]]:
        item = await provider.item(ctx.tenant, item_id)
        if item is None or not item.sent_to_client:
            raise NotFound("client_approval")
        at = await _scope_of(ctx, item)
        if at is None or await covering_grant(ctx.tenant, ctx.user_id, at) is None:
            raise NotFound("client_approval")
        attest = bool(await attest_client_of(ctx.tenant, at.client_id))
        decider = await decider_for(ctx.tenant, ctx.user_id, kind, at, attest)
        if decider is None:
            raise NotDecider
        if item.state not in _WAITING or decision.decision not in _ACTIONS[kind]:
            raise ItemChanged
        if decision.seen_hash != item.seen_hash:
            raise ItemChanged
        if ctx.mfa_at is None or ctx.portal_session_id is None:
            raise Forbidden(action, "condition")
        context = ClientDecisionContext(
            contact_id=decider.contact_id,
            user_id=ctx.user_id,
            grant_id=decider.grant_id,
            designation_basis=decider.basis,
            mfa_verified_at=ctx.mfa_at,
            session_id=ctx.portal_session_id,
        )
        async with uow(ctx.tenant) as tx:
            decided = await provider.decide(tx, item_id, decision, context)
            tx.emit(ClientApprovalDecided(kind=kind, item_id=item_id, decision=decision.decision))
            # The trail places the decision on the item itself (a proposed entry, a statement
            # version); the provider's own row holds the word, basis and second-factor time.
            tx.record(
                "client_approval.decided",
                target=Target(TARGET_OF.get(kind, kind), item_id),
                after=Ref(grant=decider.grant_id, contact=decider.contact_id),
                scope=Scope(engagement_id=at.engagement_id, work_item_id=at.work_item_id),
            )
        return 200, {"item_id": str(decided.item_id), "state": decided.state}

    stored = await idempotent(
        ctx.tenant,
        route=ROUTES[kind],
        key=idempotency_key,
        body={
            "item": str(item_id),
            "decision": decision.decision,
            "seen": decision.seen_hash,
            "reason": decision.reason_code,
        },
        run=run,
    )
    del stored  # the item is read fresh either way: a replay answers its current state
    item = await provider.item(ctx.tenant, item_id)
    if item is None:
        raise NotFound("client_approval")
    return item


__all__: Sequence[str] = [
    "Listing",
    "Shown",
    "approval",
    "approvals",
    "client_decide",
    "live_client_human",
]

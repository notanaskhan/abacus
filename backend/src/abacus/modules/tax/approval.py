"""Final approval of a return (T-01-T18; T-01 §3.8; TAX-02, TAX-09 a/a2/b, TAX-12 b; SHL-12 h;
SPEC-501 AC-45 to AC-50). RED: the single owner of the L4 `final_approval` sign-off on a
`tax_return` (chapter 01 §1.3.1; the former T-02-T15 is folded in).

- **The signer** is BH-TAX-02's: the firm's `return_approval_policy` in effect today names the
  partner who gives final approval for the return's client (`methodology.api`); none named, nobody
  may approve (`policy_unassigned`).
- **Eligibility** is the list of blockers, each a code and the record it names, never prose:
  `sign_off_missing` (L1 to L3 not signed or stale on the current content),
  `issue_blocks_final_approval` (an open issue whose `blocks` name final approval),
  `import_pending_approval` (an engine import checkpoint a person has not decided),
  `no_checkpoint` (nothing saved to approve), and whatever the registered providers add
  (`register_final_approval_blocker`: T-02's draft K-1, T-01-T19's error diagnostics).
- **Approve** (`POST …/final-approval`): five layers keep it a person's (INV-1): the matrix (agent
  and system deny), the route's live-human check, this service's check, the status machine
  (`final_approved` is a human event) and the database (sign-offs carry `signed_by`, a person).
  The caller must be the named signer, see the current checkpoint and its content hash (409
  `content_changed` otherwise), and face no blocker (409 `final_approval_blocked`). One unit of
  work then records the L4 sign-off through `review.api.record_sign_off` on the checkpoint's
  content hash, moves the return to `approved`, emits `tax_return.approved` and issues exactly
  one export approval grant (`tax_return.approve`, `not_before` = now + 10 s, the Undo window,
  DEC-24).
- The return's reviewable facts (its current checkpoint's hash) and the gate kind
  `tax_final_approval` (every return on the engagement approved or further on).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Annotated, ClassVar, Final
from uuid import UUID

from pydantic import ValidationError

from abacus.kernel._statuses import ReturnStatus
from abacus.kernel.classification import classified
from abacus.kernel.clock import now, today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.engagements.api import work_item_engagement, work_item_facts
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    engagement_resource,
    issue_grant,
)
from abacus.modules.methodology.api import (
    ReturnApprovalPolicyPayload,
    current_version_of_kind,
    policy_payload,
    return_approval_policy,
)
from abacus.modules.review.api import (
    ReviewableFacts,
    blocking_issues,
    content_hash,
    current_checkpoint,
    pending_imports,
    record_sign_off,
    register_gate_kind,
    register_reviewable_facts,
    sign_off_states,
)
from abacus.modules.tax import repository
from abacus.modules.tax.status import StaleReturn, TransitionRefused, actor_may, next_status

TARGET: Final = "tax_return"
APPROVE: Final = "tax_return.approve"
FINAL_LEVEL: Final = 4
REQUIRED_BEFORE: Final = (1, 2, 3)
UNDO_WINDOW: Final = timedelta(seconds=10)
GRANT_LIFETIME: Final = timedelta(days=30)
GATE_KIND: Final = "tax_final_approval"
EMPTY_HASH: Final = content_hash({})


@dataclass(frozen=True)
class Blocker:
    kind: str
    ref_id: UUID | None = None


BlockerProvider = Callable[[TenantContext, UUID], Awaitable[list[Blocker]]]
_PROVIDERS: dict[str, BlockerProvider] = {}


def register_final_approval_blocker(kind: str, provider: BlockerProvider) -> None:
    """A blocker provider (T-02 the draft K-1; T-01-T19 the engine's error diagnostics). A
    provider that raises blocks (fail closed)."""
    known = _PROVIDERS.get(kind)
    if known is not None and known is not provider:
        raise RuntimeError(f"final-approval blocker {kind!r} is already registered")
    _PROVIDERS[kind] = provider


class NotSigner(Forbidden):
    def __init__(self) -> None:
        super().__init__(APPROVE, "condition")


class FinalApprovalBlocked(DomainConflict):
    code = "final_approval_blocked"


class ContentChanged(DomainConflict):
    """The checkpoint or its content moved since the approver read it."""

    code = "content_changed"


class TaxReturnApproved(DomainEvent):
    """The signer gave final approval (identifiers only)."""

    event_type: ClassVar[str] = "tax_return.approved"

    work_item_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    approved_by: Annotated[UUID, classified("internal")]
    checkpoint_id: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class Eligibility:
    return_id: UUID
    engagement_id: UUID
    client_id: UUID
    signer: UUID | None
    checkpoint_id: UUID | None
    content_hash: str | None
    blockers: list[Blocker]

    @property
    def eligible(self) -> bool:
        return not self.blockers


async def _facts(ctx: AuthContext, return_id: UUID) -> tuple[UUID, UUID]:
    """The return's engagement and client, as the viewer may see it (404 otherwise, INV-3)."""
    for item in await work_item_facts(ctx, "tax_return"):
        if item.work_item_id == return_id:
            return item.engagement_id, item.client_id
    raise NotFound(TARGET)


async def signer_for(tenant_id: UUID, client_id: UUID) -> UUID | None:
    """BH-TAX-02's partner for the client today, or None."""
    on = await today(TenantContext(tenant_id, "system", "tax:approval"))
    policy = await current_version_of_kind(tenant_id, "return_approval_policy", on)
    if policy is None:
        return None
    try:
        payload = ReturnApprovalPolicyPayload.model_validate(
            await policy_payload(tenant_id, policy, "return_approval_policy")
        )
    except ValidationError:
        return None
    return return_approval_policy(payload, policy, client_id=client_id).approver_user_id


async def eligibility(ctx: AuthContext, return_id: UUID) -> Eligibility:
    """The facts TAX-02, TAX-09 b and TAX-12 b show, and every blocker."""
    engagement_id, client_id = await _facts(ctx, return_id)
    tenant = ctx.tenant
    blockers: list[Blocker] = []
    signer = await signer_for(ctx.tenant_id, client_id)
    if signer is None:
        blockers.append(Blocker("policy_unassigned"))
    checkpoint = await current_checkpoint(tenant, TARGET, return_id)
    if checkpoint is None:
        blockers.append(Blocker("no_checkpoint"))
    else:
        states = (await sign_off_states(tenant, TARGET, [return_id], {return_id: checkpoint[1]}))[
            return_id
        ]
        for state in states:
            if state.level in REQUIRED_BEFORE and (state.signed_by is None or state.stale):
                blockers.append(Blocker(f"sign_off_missing_l{state.level}"))
    blockers += [
        Blocker("issue_blocks_final_approval", i)
        for i in await blocking_issues(tenant, return_id, "final_approval")
    ]
    blockers += [
        Blocker("import_pending_approval", c)
        for c in await pending_imports(tenant, TARGET, return_id)
    ]
    for kind, provider in sorted(_PROVIDERS.items()):
        try:
            blockers += await provider(tenant, return_id)
        except Exception:  # a provider that cannot answer blocks (fail closed)
            blockers.append(Blocker(kind))
    return Eligibility(
        return_id,
        engagement_id,
        client_id,
        signer,
        checkpoint[0] if checkpoint else None,
        checkpoint[1] if checkpoint else None,
        blockers,
    )


async def _resource(ctx: AuthContext, engagement_id: UUID, return_id: UUID) -> Resource:
    """The engagement, with the return as the work item (`function_in(signer)` reads it)."""
    return replace(await engagement_resource(ctx.tenant, engagement_id), work_item_id=return_id)


def _human(ctx: AuthContext) -> None:
    """Layer 3 of 5: a live person, never an agent, the system or support."""
    if ctx.client:
        raise NotFound(TARGET)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(APPROVE, "role")


async def approve(
    ctx: AuthContext, return_id: UUID, seen_checkpoint_id: UUID, content_hash: str
) -> Eligibility:
    """The signer's final approval (TAX-09 b, SHL-12 h)."""
    _human(ctx)
    if not actor_may("final_approved", ctx.tenant.actor_kind):  # layer 4: the status machine
        raise Forbidden(APPROVE, "role")
    found = await eligibility(ctx, return_id)
    resource = await _resource(ctx, found.engagement_id, return_id)
    await authorise(ctx, APPROVE, resource)
    if found.signer != ctx.user_id:
        raise NotSigner
    if found.checkpoint_id != seen_checkpoint_id or found.content_hash != content_hash:
        raise ContentChanged(facts={"work_item_id": str(return_id)})
    if found.blockers:
        raise FinalApprovalBlocked(
            facts={"work_item_id": str(return_id), "blockers": len(found.blockers)}
        )
    at = await now(ctx.tenant)
    keys = {"tenant_id": ctx.tenant_id, "work_item_id": return_id}
    async with uow(ctx.tenant) as tx:
        status = await repository.status_of(tx.session, keys)
        if status is None:
            raise NotFound(TARGET)
        current, version = ReturnStatus(status[0]), status[1]
        to = next_status(current, "final_approved")
        await record_sign_off(
            tx, ctx, resource, found.engagement_id, TARGET, return_id, FINAL_LEVEL, content_hash
        )
        if not await repository.move_status(
            tx.session, {**keys, "to_status": to.value, "seen": version}
        ):
            raise StaleReturn(facts={"work_item_id": str(return_id)})
        await repository.insert_status_event(
            tx.session,
            {
                **keys,
                "from_status": current.value,
                "to_status": to.value,
                "event": "final_approved",
                "actor_kind": "human",
                "actor_id": str(ctx.user_id),
                "on_behalf_of": None,
                "reason": None,
            },
        )
        await issue_grant(
            tx,
            ctx,
            action=APPROVE,
            resource=resource,
            subject=Target(TARGET, return_id),
            payload_sha256=content_hash.removeprefix("sha256:"),
            not_before=at + UNDO_WINDOW,
            expires_at=at + GRANT_LIFETIME,
        )
        tx.record(
            "tax_return.approved",
            target=Target(TARGET, return_id),
            after=Ref(checkpoint=seen_checkpoint_id, content_hash=content_hash),
        )
        tx.emit(
            TaxReturnApproved(
                work_item_id=return_id,
                engagement_id=found.engagement_id,
                approved_by=ctx.user_id,
                checkpoint_id=seen_checkpoint_id,
            )
        )
    return found


# --- the review grammar's view of a return ----------------------------------------------------


async def _reviewable_facts(tenant: TenantContext, return_id: UUID) -> ReviewableFacts:
    """The return's current checkpoint hash; before its first checkpoint, the hash of nothing
    (T-01-T19: an engine import can be a return's first checkpoint)."""
    engagement_id = await _engagement_of(tenant, return_id)
    checkpoint = await current_checkpoint(tenant, TARGET, return_id)
    return ReviewableFacts(
        target_type=TARGET,
        target_id=return_id,
        engagement_id=engagement_id,
        content_hash=checkpoint[1] if checkpoint else EMPTY_HASH,
        version_no=1,
        preparer_user_ids=frozenset(),
        required_levels=(1, 2, 3, 4),
    )


async def _engagement_of(tenant: TenantContext, return_id: UUID) -> UUID:
    found = await work_item_engagement(tenant, return_id)
    if found is None:
        raise NotFound(TARGET)
    return found


_APPROVED_OR_LATER: Final = frozenset(
    {
        ReturnStatus.APPROVED,
        ReturnStatus.AWAITING_SIGNATURE,
        ReturnStatus.FILED,
        ReturnStatus.ACCEPTED,
    }
)


async def final_approval_gate(tenant: TenantContext, engagement_id: UUID) -> bool:
    """`tax_final_approval`: met when the engagement has returns and every one is approved or
    further on (a rejected or fixing return needs a new approval)."""
    async with tenant_session(tenant) as session:
        found = await repository.statuses_on(
            session, {"tenant_id": tenant.tenant_id, "engagement_id": engagement_id}
        )
    return bool(found) and all(ReturnStatus(s) in _APPROVED_OR_LATER for s in found)


def register() -> None:
    register_reviewable_facts(TARGET, _reviewable_facts)
    register_gate_kind(GATE_KIND, final_approval_gate)


__all__ = [
    "Blocker",
    "ContentChanged",
    "Eligibility",
    "FinalApprovalBlocked",
    "NotSigner",
    "TaxReturnApproved",
    "TransitionRefused",
    "approve",
    "eligibility",
    "register",
    "register_final_approval_blocker",
    "signer_for",
]

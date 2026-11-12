"""TAX-04's review tree and document approvals (T-04-T17; SPEC-649; DEC-37; ADR-005; DEC-3210).

- **Levels by function.** The viewer's level comes from their functions on the return's work item
  (`work_item_assignments.function`): preparer → `preparer`; first-level and detail reviewers →
  `detail`; manager reviewer and signer → `manager`. The tree's "Review n" is the documents not yet
  approved at that level (Samuel at detail: Review 37 of 41, then 36 after one approval).
- **Approve and reverse** are insert-only rows (DEC-37), each a person's (the table refuses any
  other actor): approve at a level the viewer holds (403 `level_not_permitted`: Kevin cannot
  approve at manager level), on the document's current version (409 `version_superseded` when a
  newer version of it exists, or `seen_version` is stale); reverse only the viewer's own level,
  once, with an optional sealed reason. Nothing is deleted.
- **The final-approval request** refuses while the return has a draft K-1 (409, blocker
  `draft_k1`) or a document is unapproved at manager level (`unapproved_documents`); otherwise it
  is recorded and the gate projection picks it up (`tax_return.final_approval_requested`).
- **The workspace summary** counts the viewer's review, the K-1 dependency and what they may do,
  and names BH-TAX-02's signer for a viewer who may request final approval (TASK-7322).
- **Unapprove from the tree.** Each document carries its live approval at the shown level (the
  latest, when several people approved there), so Unapprove reaches an approval made in another
  session or by a colleague at the same level; `reverse` still checks the viewer holds the level.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Annotated, ClassVar, Final, Literal, cast
from uuid import UUID, uuid5

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.clock import now
from abacus.kernel.crypto import seal
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainForbidden, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, uow
from abacus.modules.engagements.api import functions_on, get_ref, work_item_engagement
from abacus.modules.evidence.api import engagement_documents
from abacus.modules.identity.api import AuthContext, Resource, allowed_actions, authorise, names_of

Level = Literal["preparer", "detail", "manager"]
LEVELS: Final[tuple[Level, ...]] = ("preparer", "detail", "manager")
_LEVEL_OF: Final[dict[str, Level]] = {
    "preparer": "preparer",
    "first_level_reviewer": "detail",
    "detail_reviewer": "detail",
    "manager_reviewer": "manager",
    "signer": "manager",
}
WORKSPACE_ACTIONS: Final = (
    "document.approve",
    "tax_return.request_approval",
    "tax_return.draft_run",
    "k1_treatment.resolve",
    "k1_treatment.approve",
    "k1_treatment.override",
    "residency.request_proposal",
    "residency.confirm",
)


class DocumentApprovalChanged(DomainEvent):
    """A document was approved or unapproved at a level (T-04-T29): the invalidation stream
    refetches the return's "Review n" on a second tab. Identifiers only."""

    event_type: ClassVar[str] = "document_approval.changed"

    approval_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    kind: Annotated[Literal["approve", "reverse"], classified("internal")]


class LevelNotPermitted(DomainForbidden):
    code = "level_not_permitted"


class VersionSuperseded(DomainConflict):
    code = "version_superseded"


class AlreadyReversed(DomainConflict):
    code = "already_reversed"


class ApprovalBlocked(DomainConflict):
    """The final approval waits on these blockers (identifiers only)."""

    code = "final_approval_blocked"


def levels_held(functions: frozenset[str]) -> frozenset[Level]:
    return frozenset(_LEVEL_OF[f] for f in functions if f in _LEVEL_OF)


def viewer_level(held: frozenset[Level]) -> Level | None:
    for level in reversed(LEVELS):
        if level in held:
            return level
    return None


@dataclass(frozen=True)
class Doc:
    evidence_version_id: UUID
    title: str
    category: str
    approval: Literal["unapproved", "approved", "mismatch"]
    approvals_count: int
    version: int
    # TASK-7322: the live approval at the shown level (the latest), for Unapprove.
    approval_id: UUID | None = None


@dataclass(frozen=True)
class Approval:
    id: UUID
    evidence_version_id: UUID
    level: Level
    approved_by_name: str
    approved_at: datetime
    reversed: bool


async def _return(ctx: AuthContext, return_id: UUID, action: str) -> tuple[UUID, Resource]:
    if ctx.client:
        raise NotFound("tax_return")
    engagement = await work_item_engagement(ctx.tenant, return_id)
    if engagement is None:
        raise NotFound("tax_return")
    resource = replace((await get_ref(ctx, engagement)).resource(), work_item_id=return_id)
    await authorise(ctx, action, resource)
    return engagement, resource


_LIVE: Final = text(
    "SELECT a.evidence_version_id, a.level, count(*) AS n FROM document_approvals a "
    "WHERE a.tax_return_id = :r AND a.kind = 'approve' AND NOT EXISTS (SELECT 1 FROM "
    "document_approvals b WHERE b.reverses_id = a.id) GROUP BY a.evidence_version_id, a.level"
)


async def _live(ctx: AuthContext, return_id: UUID) -> dict[tuple[UUID, str], int]:
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_LIVE, {"r": return_id})).all()
    return {(r.evidence_version_id, r.level): int(r.n) for r in rows}


LIVE_APPROVAL_IDS: Final = text(
    "SELECT DISTINCT ON (a.evidence_version_id) a.evidence_version_id, a.id "
    "FROM document_approvals a WHERE a.tax_return_id = :r AND a.level = :l "
    "AND a.kind = 'approve' AND NOT EXISTS (SELECT 1 FROM document_approvals b "
    "WHERE b.reverses_id = a.id) ORDER BY a.evidence_version_id, a.decided_at DESC, a.id DESC"
)


async def _live_ids(ctx: AuthContext, return_id: UUID, level: Level) -> dict[UUID, UUID]:
    """Each version's latest live approval at `level` (TASK-7322)."""
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(LIVE_APPROVAL_IDS, {"r": return_id, "l": level})).all()
    return {r.evidence_version_id: r.id for r in rows}


async def tree(
    ctx: AuthContext, return_id: UUID, *, level: Level | None, q: str | None, category: str | None
) -> tuple[list[Doc], int, Level | None]:
    """The current versions, their approval at `level` (the viewer's when not given), and how
    many still need review there."""
    engagement, _ = await _return(ctx, return_id, "tax_return.read")
    held = levels_held(await functions_on(ctx.tenant, return_id, ctx.user_id))
    at = level or viewer_level(held)
    live = await _live(ctx, return_id)
    ids = {} if at is None else await _live_ids(ctx, return_id, at)
    docs: list[Doc] = []
    needle = (q or "").strip().casefold()
    for version_id, _item, title, folder, number, latest in await engagement_documents(
        ctx.tenant, engagement
    ):
        if not latest:
            continue
        if needle and needle not in title.casefold():
            continue
        if category and category != folder:
            continue
        approved = at is not None and (version_id, at) in live
        total = sum(n for (v, _lv), n in live.items() if v == version_id)
        docs.append(
            Doc(
                version_id,
                title,
                folder,
                "approved" if approved else "unapproved",
                total,
                number,
                ids.get(version_id) if approved else None,
            )
        )
    review = sum(1 for d in docs if d.approval != "approved")
    return docs, review, at


async def approve(
    ctx: AuthContext,
    return_id: UUID,
    *,
    evidence_version_id: UUID,
    level: Level,
    seen_version: int,
) -> Approval:
    engagement, _ = await _return(ctx, return_id, "document.approve")
    held = levels_held(await functions_on(ctx.tenant, return_id, ctx.user_id))
    if level not in held:
        raise LevelNotPermitted(facts={"level": level})
    current = {
        v: (number, latest)
        for v, _i, _t, _f, number, latest in await engagement_documents(ctx.tenant, engagement)
    }
    found = current.get(evidence_version_id)
    if found is None:
        raise NotFound("evidence_version")
    number, latest = found
    if not latest or number != seen_version:
        raise VersionSuperseded
    fn = next(
        (
            f
            for f in await functions_on(ctx.tenant, return_id, ctx.user_id)
            if _LEVEL_OF.get(f) == level
        ),
        None,
    )
    async with uow(ctx.tenant) as tx:
        approval_id = cast(
            UUID,
            await tx.session.scalar(
                text(
                    "INSERT INTO document_approvals (tenant_id, engagement_id, tax_return_id, "
                    "evidence_version_id, level, kind, actor_user_id, function_at_time, "
                    "seen_version) VALUES (:t, :e, :r, :v, :l, 'approve', :u, :fn, :seen) "
                    "RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement,
                    "r": return_id,
                    "v": evidence_version_id,
                    "l": level,
                    "u": ctx.user_id,
                    "fn": fn,
                    "seen": seen_version,
                },
            ),
        )
        tx.record(
            "document.approved",
            target=Target("tax_return", return_id),
            after=Ref(approval=approval_id, evidence_version_id=evidence_version_id),
            scope=Scope(engagement_id=engagement, work_item_id=return_id),
        )
        tx.emit(
            DocumentApprovalChanged(
                approval_id=approval_id,
                engagement_id=engagement,
                work_item_id=return_id,
                kind="approve",
            )
        )
    names = await names_of([ctx.user_id])
    return Approval(
        approval_id,
        evidence_version_id,
        level,
        names.get(ctx.user_id, ""),
        await now(ctx.tenant),
        False,
    )


async def reverse(ctx: AuthContext, approval_id: UUID, reason: str | None) -> Approval:
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT tax_return_id, evidence_version_id, level, kind, seen_version, "
                    "actor_user_id, decided_at FROM document_approvals WHERE id = :a"
                ),
                {"a": approval_id},
            )
        ).first()
    if row is None or row.kind != "approve":
        raise NotFound("document_approval")
    engagement, _ = await _return(ctx, row.tax_return_id, "document.approve")
    held = levels_held(await functions_on(ctx.tenant, row.tax_return_id, ctx.user_id))
    if row.level not in held:
        raise LevelNotPermitted(facts={"level": str(row.level)})
    sealed: bytes | None = None
    if reason and reason.strip():
        text_ = reason.strip()
        sealed = await seal(
            ctx.tenant_id, text_.encode(), hashlib.sha256(text_.encode()).hexdigest()
        )
    async with uow(ctx.tenant) as tx:
        made = await tx.session.scalar(
            text(
                "INSERT INTO document_approvals (tenant_id, engagement_id, tax_return_id, "
                "evidence_version_id, level, kind, reverses_id, actor_user_id, reason_sealed, "
                "seen_version) VALUES (:t, :e, :r, :v, :l, 'reverse', :a, :u, :reason, :seen) "
                "ON CONFLICT (reverses_id) DO NOTHING RETURNING id"
            ),
            {
                "t": ctx.tenant_id,
                "e": engagement,
                "r": row.tax_return_id,
                "v": row.evidence_version_id,
                "l": row.level,
                "a": approval_id,
                "u": ctx.user_id,
                "reason": sealed,
                "seen": row.seen_version,
            },
        )
        if made is None:
            raise AlreadyReversed
        tx.record(
            "document.approval_reversed",
            target=Target("tax_return", row.tax_return_id),
            after=Ref(approval=approval_id),
            scope=Scope(engagement_id=engagement, work_item_id=row.tax_return_id),
        )
        tx.emit(
            DocumentApprovalChanged(
                approval_id=approval_id,
                engagement_id=engagement,
                work_item_id=row.tax_return_id,
                kind="reverse",
            )
        )
    names = await names_of([row.actor_user_id])
    return Approval(
        approval_id,
        row.evidence_version_id,
        row.level,
        names.get(row.actor_user_id, ""),
        row.decided_at,
        True,
    )


async def blockers(ctx: AuthContext, return_id: UUID, engagement: UUID) -> list[str]:
    async with tenant_session(ctx.tenant) as session:
        drafts = await session.scalar(
            text(
                "SELECT count(*) FROM k1_activities WHERE tax_return_id = :r "
                "AND k1_state = 'draft_pre_release'"
            ),
            {"r": return_id},
        )
    found: list[str] = []
    if int(drafts or 0):
        found.append("draft_k1")
    live = await _live(ctx, return_id)
    current = [
        v for v, *_rest, latest in await engagement_documents(ctx.tenant, engagement) if latest
    ]
    if any((v, "manager") not in live for v in current):
        found.append("unapproved_documents")
    return found


async def request_final_approval(
    ctx: AuthContext, return_id: UUID, assignee_user_id: UUID
) -> tuple[UUID, datetime]:
    """409 `final_approval_blocked` with `blockers` while any holds; else recorded."""
    engagement, _ = await _return(ctx, return_id, "tax_return.request_approval")
    found = await blockers(ctx, return_id, engagement)
    if found:
        raise ApprovalBlocked(facts={"blockers": ",".join(found)})
    gate_id = uuid5(return_id, f"final_approval:{assignee_user_id}")
    at = await now(ctx.tenant)
    async with uow(ctx.tenant) as tx:
        tx.record(
            "tax_return.final_approval_requested",
            target=Target("tax_return", return_id),
            after=Ref(assignee=assignee_user_id, gate=gate_id),
            scope=Scope(engagement_id=engagement, work_item_id=return_id),
        )
    return gate_id, at


@dataclass(frozen=True)
class Summary:
    review_count: int
    viewer_level: Level | None
    k1_dependency: str | None
    allowed: list[str]
    # TASK-7322: BH-TAX-02's signer, for a viewer who may request final approval; else None.
    final_approver_user_id: UUID | None = None


async def summary(ctx: AuthContext, return_id: UUID) -> Summary:
    from abacus.modules.tax.approval import signer_for

    engagement, resource = await _return(ctx, return_id, "tax_return.read")
    _docs, review, level = await tree(ctx, return_id, level=None, q=None, category=None)
    async with tenant_session(ctx.tenant) as session:
        state = await session.scalar(
            text(
                "SELECT k1_state FROM k1_activities WHERE tax_return_id = :r ORDER BY "
                "CASE k1_state WHEN 'draft_pre_release' THEN 0 WHEN 'released' THEN 1 ELSE 2 END "
                "LIMIT 1"
            ),
            {"r": return_id},
        )
    held = await allowed_actions(ctx, resource, WORKSPACE_ACTIONS)
    signer = (
        await signer_for(ctx.tenant_id, (await get_ref(ctx, engagement)).client_id)
        if "tax_return.request_approval" in held
        else None
    )
    return Summary(
        review,
        level,
        cast(str | None, state),
        [a for a in WORKSPACE_ACTIONS if a in held],
        signer,
    )

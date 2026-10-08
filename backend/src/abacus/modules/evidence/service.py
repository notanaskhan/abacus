"""Evidence rules (ADR-004, ADR-016, ADR-104). PROTECTED. TASK-009 design §5, revision 1.

Two steps, so no transaction is held across network I/O:

    stored = await stage_content(tenant_id, content)        # before the unit of work
    async with uow(ctx) as tx:
        ref = await add_version(tx, engagement_id=…, item=NewItem("Trial balance"), stored=stored,
                                media_type=…, provenance=…, idempotency_key=…)

Versions are only ever added. Staged content that no version ends up referencing is harmless: it
is content-addressed and reused by the next attempt.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session, transaction_context
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound, ServiceUnavailable
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.evidence import storage
from abacus.modules.evidence.events import EvidenceVersionCreated, ReviewAssigned
from abacus.modules.evidence.models import EvidenceVersion
from abacus.modules.evidence.repository import (
    assignment_for,
    clear_assignment,
    decision_for,
    get_item,
    get_version,
    insert_decision,
    insert_item,
    insert_version,
    list_review_state,
    list_versions,
    next_version_no,
    put_assignment,
    reason_codes,
    release_assignments_of,
    snapshots_of_engagement,
    take_assignment,
    version_for_key,
)
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    authorise,
    could,
    serving_request,
)
from abacus.modules.requests.api import (
    FulfilledVersion,
    ReviewTarget,
    fulfilled_versions,
    move_after_review,
    review_targets,
)

Method = Literal["retrieved", "uploaded"]
StoredObject = storage.StoredObject


class EngagementArchived(DomainConflict):
    """Archived engagements are read-only (`archived_write: deny`)."""

    code = "engagement_archived"


@dataclass(frozen=True)
class Provenance:
    """Where a version came from (AC-10). `pulled_at` is required for retrieved evidence."""

    source: str
    method: Method
    pulled_at: datetime | None = None
    period_start: date | None = None
    period_end: date | None = None
    client_entity_id: UUID | None = None
    snapshot_id: UUID | None = None


@dataclass(frozen=True)
class NewItem:
    title: str


@dataclass(frozen=True)
class EvidenceVersionRef:
    id: UUID
    evidence_item_id: UUID
    engagement_id: UUID
    version_no: int
    fingerprint: str
    size_bytes: int
    media_type: str
    created: bool  # False when an idempotency key matched an existing version


def _ref(version: EvidenceVersion, *, created: bool) -> EvidenceVersionRef:
    return EvidenceVersionRef(
        version.id,
        version.evidence_item_id,
        version.engagement_id,
        version.version_no,
        version.fingerprint,
        version.size_bytes,
        version.media_type,
        created,
    )


async def stage_content(tenant_id: UUID, content: bytes) -> StoredObject:
    """Store content write-once and encrypted under the tenant's key, outside any transaction.
    Also the store for raw connector payloads (AC-9), which aren't evidence versions."""
    return await storage.put(tenant_id, content)


async def read_content(tenant: TenantContext, stored: StoredObject) -> bytes:
    """Verified plaintext for callers that authorised under their own context (the system actor
    in workflows). Request handlers use `read_version`, which authorises and audits."""
    return await storage.get(tenant.tenant_id, stored)


async def add_version(
    tx: UnitOfWork,
    *,
    engagement_id: UUID,
    item: UUID | NewItem,
    stored: StoredObject,
    media_type: str,
    provenance: Provenance,
    idempotency_key: str | None = None,
    requested_by: UUID | None = None,
) -> EvidenceVersionRef:
    """Add the next version inside the caller's unit of work. The tenant and actor are the
    transaction's own. The caller has authorised `evidence.upload` for its actor.

    With an `idempotency_key` already used in this tenant, returns that version
    (`created=False`) and records nothing: the caller's unit of work must then record its own
    event, or skip the unit of work after checking `created`. `requested_by` is the person the
    version is added for (published on `evidence_version.created`)."""
    tenant = await transaction_context(tx.session)
    if stored.key != storage.object_key(tenant.tenant_id, stored.fingerprint):
        raise storage.IntegrityError("staged content belongs to another tenant")
    if idempotency_key is not None:
        existing = await version_for_key(tx.session, idempotency_key)
        if existing is not None:
            if (
                existing.fingerprint != stored.fingerprint
                or existing.engagement_id != engagement_id
            ):
                raise ValueError("idempotency key reused for different content or engagement")
            return _ref(existing, created=False)
    engagement = await lock_ref(tx, engagement_id)  # 404 outside the tenant; locked until commit
    if engagement.archived:
        raise EngagementArchived("engagement is archived")
    if not 1 <= len(media_type) <= 100:
        raise ValueError("media_type must be 1-100 characters")
    if isinstance(item, NewItem):
        item_id = uuid4()
        await insert_item(
            tx.session,
            item_id=item_id,
            tenant_id=tenant.tenant_id,
            engagement_id=engagement_id,
            title=item.title,
            created_by_kind=tenant.actor_kind,
            created_by_id=tenant.actor_id,
        )
        tx.record(
            "evidence_item.created",
            target=Target("evidence_item", item_id),
            after=Ref(engagement_id=engagement_id),
        )
    else:
        existing_item = await get_item(tx.session, item)
        if existing_item is None or existing_item.engagement_id != engagement_id:
            raise NotFound("evidence_item")
        item_id = item
    version = await insert_version(
        tx.session,
        version_id=uuid4(),
        tenant_id=tenant.tenant_id,
        engagement_id=engagement_id,
        evidence_item_id=item_id,
        version_no=await next_version_no(tx.session, item_id),
        fingerprint=stored.fingerprint,
        storage_key=stored.key,
        storage_version_id=stored.version_id,
        size_bytes=stored.size,
        media_type=media_type,
        source=provenance.source,
        method=provenance.method,
        pulled_at=provenance.pulled_at,
        period_start=provenance.period_start,
        period_end=provenance.period_end,
        client_entity_id=provenance.client_entity_id,
        snapshot_id=provenance.snapshot_id,
        idempotency_key=idempotency_key,
    )
    tx.record(
        "evidence_version.created",
        target=Target("evidence_version", version.id),
        after=Ref(evidence_item_id=item_id, fingerprint=stored.fingerprint),
    )
    tx.emit(
        EvidenceVersionCreated(
            evidence_version_id=version.id,
            evidence_item_id=item_id,
            engagement_id=engagement_id,
            requested_by=requested_by,
        )
    )
    return _ref(version, created=True)


async def read_version(ctx: AuthContext, version_id: UUID) -> bytes:
    """The version's content for an actor allowed `evidence.read`: authorised, audited
    (`evidence_version.read`, ADR-104) and fingerprint-verified."""
    async with tenant_session(ctx.tenant) as session:
        version = await get_version(session, version_id)
    if version is None:
        raise NotFound("evidence_version")
    engagement = await get_ref(ctx, version.engagement_id)
    await authorise(ctx, "evidence.read", engagement.resource())
    async with uow(ctx.tenant) as tx:
        tx.record("evidence_version.read", target=Target("evidence_version", version.id))
    return await storage.get(
        ctx.tenant_id,
        StoredObject(
            version.storage_key,
            version.storage_version_id,
            version.fingerprint,
            version.size_bytes,
        ),
    )


@dataclass(frozen=True)
class EvidenceVersionView:
    id: UUID
    engagement_id: UUID
    evidence_item_id: UUID
    stored: StoredObject
    snapshot_id: UUID | None
    media_type: str
    period_start: date | None
    period_end: date | None


async def version_view(tenant: TenantContext, version_id: UUID) -> EvidenceVersionView:
    """A version's metadata for a caller that has authorised under its own context (`NotFound`
    outside the tenant)."""
    async with tenant_session(tenant) as session:
        version = await get_version(session, version_id)
    if version is None:
        raise NotFound("evidence_version")
    return EvidenceVersionView(
        version.id,
        version.engagement_id,
        version.evidence_item_id,
        StoredObject(
            version.storage_key,
            version.storage_version_id,
            version.fingerprint,
            version.size_bytes,
        ),
        version.snapshot_id,
        version.media_type,
        version.period_start,
        version.period_end,
    )


@dataclass(frozen=True)
class EvidenceVersionSummary:
    """What the evidence board shows of a version (TASK-012 Q1): provenance, never content."""

    id: UUID
    evidence_item_id: UUID
    version_no: int
    method: str  # retrieved | uploaded
    source: str
    pulled_at: datetime | None
    period_start: date | None
    period_end: date | None
    created_at: datetime


async def evidence_versions_for(
    ctx: AuthContext, engagement_id: UUID
) -> list[EvidenceVersionSummary]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "evidence.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        versions = await list_versions(session, ctx, engagement_id)
    return [
        EvidenceVersionSummary(
            v.id,
            v.evidence_item_id,
            v.version_no,
            v.method,
            v.source,
            v.pulled_at,
            v.period_start,
            v.period_end,
            v.created_at,
        )
        for v in versions
    ]


# --- Review queues and decisions (SPEC-004; TASK-019 design) -------------------------------------

Decision = Literal["accept", "reject", "send_back"]
_DECISION_ACTION: dict[str, str] = {
    "accept": "evidence.accept",
    "reject": "evidence.reject",
    "send_back": "evidence.reject",
}
# What each decision moves the version's items to (SPEC-004 §6, Q2). A rejected item awaits new
# evidence: the rejected version was its newest (else the decision is `superseded`), so nothing
# older is reviewable any more (TASK-019 reviews B1/M1).
_ITEM_AFTER: dict[str, str] = {
    "accept": "accepted",
    "reject": "open",
    "send_back": "needs_revision",
}
_ONE_DECISION = "review_decisions_once"
_CHECK_VIOLATION = "23514"
_log = get_logger(__name__)
_decisions = meter(__name__).create_counter(
    "abacus.review.decisions", description="Review decisions by kind and reason or agreement"
)


@dataclass(frozen=True)
class Proposal:
    """What an agent proposed about a version (the screener's latest result)."""

    screening_result_id: UUID
    action: str  # ready_for_review | needs_revision
    confidence: Decimal
    rationale: str
    citations: list[dict[str, object]]
    unverified: list[str]


ProposalsFor = Callable[[AuthContext, UUID], Awaitable[dict[UUID, Proposal]]]
ProposalOf = Callable[[AsyncSession, UUID], Awaitable[Proposal | None]]
# The agents module tells evidence what agents proposed (TASK-019 D1; ADR-106): agents already
# depends on evidence, so evidence can't import agents. Unregistered, the queue shows no proposals
# and a decision is refused (503): whether it corrects a proposal is never guessed.
_proposals: tuple[ProposalsFor, ProposalOf] | None = None


def register_proposal_source(for_engagement: ProposalsFor, for_version: ProposalOf) -> None:
    global _proposals
    if _proposals is not None and _proposals != (for_engagement, for_version):
        raise RuntimeError("the proposal source is already registered")
    _proposals = (for_engagement, for_version)


class AlreadyTaken(DomainConflict):
    code = "already_taken"


class AlreadyDecided(DomainConflict):
    code = "already_decided"


class Superseded(DomainConflict):
    """A newer version of the same item has arrived: decide that one."""

    code = "superseded"


class ProposalChanged(DomainConflict):
    """The agent's proposal changed since the reviewer saw it: look again (AC-10)."""

    code = "proposal_changed"


class InvalidReason(DomainInvalid):
    """A reason code missing, unknown, retired, not for this decision, or `other` without a
    note."""

    code = "invalid_reason_code"


@dataclass(frozen=True)
class QueueEntry:
    evidence_version: EvidenceVersionSummary
    request_item_id: UUID
    item_description: str
    item_audit_area: str
    proposal: Proposal | None
    assignee_user_id: UUID | None


@dataclass(frozen=True)
class ReasonCode:
    code: str
    label: str
    description: str
    requires_note: bool


@dataclass(frozen=True)
class DecisionView:
    id: UUID
    evidence_version_id: UUID
    request_item_ids: list[UUID]
    decision: str
    reason_code: str | None
    corrects_proposal: bool
    item_status: str


def _summary(v: EvidenceVersion) -> EvidenceVersionSummary:
    return EvidenceVersionSummary(
        v.id,
        v.evidence_item_id,
        v.version_no,
        v.method,
        v.source,
        v.pulled_at,
        v.period_start,
        v.period_end,
        v.created_at,
    )


def _order(entry: QueueEntry) -> tuple[int, int, Decimal, datetime, UUID]:
    """Q3: proposals needing revision first, then lowest confidence (none last), then oldest."""
    p = entry.proposal
    return (
        0 if p is not None and p.action == "needs_revision" else 1,
        0 if p is not None else 1,
        p.confidence if p is not None else Decimal(1),
        entry.evidence_version.created_at,
        entry.evidence_version.id,
    )


async def review_queue(ctx: AuthContext, engagement_id: UUID) -> list[QueueEntry]:
    """Per request item, its newest fulfilled version, if undecided (AC-1, AC-2). A version
    fulfilling several items is listed once; deciding it moves all of them."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "review.read", ref.resource())
    fulfilled = await fulfilled_versions(ctx, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        versions, decided, taken = await list_review_state(session, ctx, engagement_id)
    by_id = {v.id: v for v in versions}
    newest: dict[UUID, FulfilledVersion] = {}
    for f in fulfilled:  # newest fulfilment per item: latest time, then fulfilment id
        held = newest.get(f.request_item_id)
        if held is None or (f.fulfilled_at, f.fulfilment_id) > (
            held.fulfilled_at,
            held.fulfilment_id,
        ):
            newest[f.request_item_id] = f
    queued: dict[UUID, FulfilledVersion] = {}
    for f in newest.values():
        if f.evidence_version_id in by_id and f.evidence_version_id not in decided:
            queued.setdefault(f.evidence_version_id, f)
    proposals = await _proposals[0](ctx, engagement_id) if _proposals and queued else {}
    entries = [
        QueueEntry(
            _summary(by_id[version_id]),
            f.request_item_id,
            f.description,
            f.audit_area,
            proposals.get(version_id),
            taken.get(version_id),
        )
        for version_id, f in queued.items()
    ]
    return sorted(entries, key=_order)


async def reason_codes_for(
    ctx: AuthContext, engagement_id: UUID, applies_to: Literal["reject", "send_back"]
) -> list[ReasonCode]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "review.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        rows = await reason_codes(session, applies_to)
    return [ReasonCode(*row) for row in rows]


async def _reviewable(tx: UnitOfWork, engagement_id: UUID, version_id: UUID) -> list[ReviewTarget]:
    """The version's items, locked, if it belongs to this engagement, is undecided, and is the
    newest evidence of every item it fulfils; else `NotFound`, `AlreadyDecided` or `Superseded`."""
    version = await get_version(tx.session, version_id)
    if version is None or version.engagement_id != engagement_id:
        raise NotFound("evidence_version")
    targets = await review_targets(tx, version_id)
    if not targets:
        raise NotFound("review_queue_entry")
    if await decision_for(tx.session, version_id) is not None:
        raise AlreadyDecided
    if not all(t.newest for t in targets):
        raise Superseded
    return targets


async def take(ctx: AuthContext, engagement_id: UUID, version_id: UUID) -> None:
    """Take a queued version (advisory, Q3): 409 `already_taken` if someone else has it."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "review.take", ref.resource())
        await _reviewable(tx, engagement_id, version_id)
        if not await take_assignment(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            version_id=version_id,
            me=ctx.user_id,
        ):
            raise AlreadyTaken
        tx.record("review.taken", target=Target("evidence_version", version_id))
    _log.info("review.taken", evidence_version_id=version_id)


async def release(ctx: AuthContext, engagement_id: UUID, version_id: UUID) -> None:
    """Release a taken version of this engagement: its taker, or a partner or manager
    (`review.assign`)."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "review.take", ref.resource())
        current = await assignment_for(tx.session, engagement_id, version_id)
        if current is None or current.assignee_user_id is None:
            raise NotFound("review_assignment")
        if current.assignee_user_id != ctx.user_id:
            await authorise(ctx, "review.assign", ref.resource())
        await clear_assignment(tx.session, engagement_id, version_id, ctx.user_id)
        tx.record("review.released", target=Target("evidence_version", version_id))


async def assign(ctx: AuthContext, engagement_id: UUID, version_id: UUID, user_id: UUID) -> None:
    """Give a queued version to someone who could decide it now (`review.assign`; the assignee
    must be allowed `evidence.accept` or `evidence.reject` on the engagement, walls included)."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "review.assign", ref.resource())
        await _reviewable(tx, engagement_id, version_id)
        resource = ref.resource()
        if not (
            await could(ctx, user_id, "evidence.accept", resource)
            or await could(ctx, user_id, "evidence.reject", resource)
        ):
            raise NotFound("reviewer")
        await put_assignment(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            version_id=version_id,
            assignee=user_id,
            assigned_by=ctx.user_id,
        )
        tx.record(
            "review.assigned",
            target=Target("evidence_version", version_id),
            after=Ref(user_id=user_id),
        )
        tx.emit(
            ReviewAssigned(
                engagement_id=engagement_id,
                evidence_version_id=version_id,
                assignee_user_id=user_id,
            )
        )


def _corrects(decision: str, proposal: Proposal | None) -> bool:
    """AC-10: accepting what the agent said needs revision, or rejecting or sending back what it
    called ready."""
    if proposal is None:
        return False
    if decision == "accept":
        return proposal.action == "needs_revision"
    return proposal.action == "ready_for_review"


async def decide(
    ctx: AuthContext,
    engagement_id: UUID,
    version_id: UUID,
    decision: Decision,
    *,
    reason_code: str | None,
    note: str | None,
    seen_proposal: UUID | None,
) -> DecisionView:
    """A person's decision on a queued version (SPEC-004 AC-6 to AC-13; ADR-005). Only a person,
    in a request they are making themself, decides:
    - only an `AuthContext`, and only while serving an API request (`serving_request`: workers,
      agents and scripts never are, whatever context they hold);
    - the matrix denies agents;
    - the database binds the row to the session's actor and refuses any but a human;
    - REVIEW-001 lets only the evidence routes reference `decide`.

    `seen_proposal` is the screening result the reviewer was shown (None: none was): if the
    agent's latest proposal differs, the decision is refused (`proposal_changed`), so a recorded
    correction is always against what the person saw."""
    if not isinstance(ctx, AuthContext) or not serving_request():  # pyright: ignore[reportUnnecessaryIsInstance] -- ADR-005 at runtime too
        raise Forbidden(_DECISION_ACTION.get(decision, "evidence.accept"), "role")
    decision_id = uuid4()
    try:
        async with uow(ctx.tenant) as tx:
            ref = await lock_ref(tx, engagement_id)
            await authorise(ctx, _DECISION_ACTION[decision], ref.resource())
            if (decision == "accept") != (reason_code is None):
                raise InvalidReason
            if _proposals is None:
                raise ServiceUnavailable("no proposal source registered")
            targets = await _reviewable(tx, engagement_id, version_id)
            proposal = await _proposals[1](tx.session, version_id)
            if (proposal.screening_result_id if proposal else None) != seen_proposal:
                raise ProposalChanged
            corrects = _corrects(decision, proposal)
            item_ids = [t.request_item_id for t in targets]
            await insert_decision(
                tx.session,
                values={
                    "id": decision_id,
                    "tenant_id": ctx.tenant_id,
                    "engagement_id": engagement_id,
                    "evidence_version_id": version_id,
                    "request_item_id": item_ids[0],
                    "decision": decision,
                    "reason_code": reason_code,
                    "note": note,
                    "screening_result_id": proposal.screening_result_id if proposal else None,
                    "corrects_proposal": corrects,
                    # The session's actor: the database checks the row against it (0015).
                    "actor_kind": ctx.tenant.actor_kind,
                    "actor_id": ctx.tenant.actor_id,
                },
            )
            to = _ITEM_AFTER[decision]
            for item_id in item_ids:
                await move_after_review(tx, item_id, to)
            if await assignment_for(tx.session, engagement_id, version_id) is not None:
                await clear_assignment(tx.session, engagement_id, version_id, ctx.user_id)
            refs = (
                Ref(
                    evidence_version_id=version_id,
                    screening_result_id=proposal.screening_result_id,
                )
                if proposal is not None
                else Ref(evidence_version_id=version_id)
            )
            tx.record(
                "review_decision.created",
                target=Target("review_decision", decision_id),
                after=refs,
            )
    except IntegrityError as exc:
        constraint = getattr(exc.orig, "constraint_name", None)
        if constraint == _ONE_DECISION:
            raise AlreadyDecided from None
        state = getattr(exc.orig, "sqlstate", None)
        if state == _CHECK_VIOLATION and constraint is None:  # the reason-code trigger
            raise InvalidReason from None
        raise
    _decisions.add(
        1,
        {
            "outcome": decision,
            "reason": reason_code or ("correction" if corrects else "agreement"),
        },
    )
    _log.info(
        "review.decided",
        evidence_version_id=version_id,
        decision=decision,
        reason_code=reason_code,
        corrects_proposal=corrects,
    )
    return DecisionView(decision_id, version_id, item_ids, decision, reason_code, corrects, to)


async def engagement_snapshots(tenant: TenantContext, engagement_id: UUID) -> list[UUID]:
    """The ledger snapshots behind the engagement's evidence (SPEC-006), for a caller that has
    authorised on the engagement."""
    async with tenant_session(tenant) as session:
        return await snapshots_of_engagement(session, engagement_id)


async def release_member_assignments(
    tx: UnitOfWork, engagement_id: UUID, user_id: UUID, by: UUID
) -> None:
    """Identity's member-removed hook (SPEC-017 AC-5; TASK-032 D2), in the removal's unit of
    work: the removed person's queued reviews go back to the queue, each audited."""
    for version_id in await release_assignments_of(tx.session, engagement_id, user_id, by):
        tx.record(
            "review.released",
            target=Target("evidence_version", version_id),
            after=Ref(user_id=user_id),
        )

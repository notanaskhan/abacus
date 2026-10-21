"""Completion, release and archive, first slice (SPEC-314; TASK-332; A-07 in record mode).

The firm drafts the report and the representation letter outside Abacus and records them here
(the final documents are evidence versions); everything that decides is a named person's act:
- G6: the engagement quality reviewer concurs over a digest code built from the significant
  judgments (`engagements.judgments_of`), attesting they weren't involved; a changed digest
  makes the concurrence stale. Without an EQR on the team, G6 isn't required.
- The engagement partner decides going concern and approves the report record.
- G7: the signed representation letter is dated the report date.
- G8: the partner releases, attesting; the server re-checks G5, G6, G7, going concern and the
  approved report in the same unit, records the gate facts and starts the 60-day clock.
- G9: after release, a manager or the partner locks the archive: the seal is a SHA-256 Merkle
  root over every content hash the binder holds; the engagement becomes archived, which
  `authorise` already makes read-only.
Code states facts and computes hashes; it never decides (ADR-005). No model is called.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.assurance.completion_models import (
    Archive,
    CompletionRecord,
    EqrConcurrence,
    Release,
)
from abacus.modules.assurance.completion_repository import (
    archive_of,
    insert_row,
    newest_concurrence,
    records_of,
    release_of,
)
from abacus.modules.engagements.api import (
    GateFact,
    Judgment,
    gate_fact,
    get_ref,
    judgments_of,
    lock_engagement,
    lock_ref,
    set_assurance_phase,
)
from abacus.modules.evidence.api import version_view
from abacus.modules.identity.api import AuthContext, authorise, engagement_eqrs, engagement_team
from abacus.modules.review.api import Reviewable, reviewables_of
from abacus.modules.review.api import open_note_counts as review_open_notes

DOCUMENTATION_DAYS: Final = 60  # AU-C 230: the documentation completion date
GOING_CONCERN: Final = ("no_substantial_doubt", "doubt_alleviated", "doubt_exists")
OPINIONS: Final = ("unmodified", "qualified", "adverse", "disclaimer")
Opinion = Literal["unmodified", "qualified", "adverse", "disclaimer"]
GoingConcern = Literal["no_substantial_doubt", "doubt_alleviated", "doubt_exists"]


class CompletionInvalid(DomainInvalid):
    code = "completion_invalid"


class NotTheEqr(DomainConflict):
    code = "not_the_eqr"


class CompletionBlocked(DomainConflict):
    """Something the step needs isn't there yet; the detail names it."""

    code = "completion_blocked"


class AlreadyReleased(DomainConflict):
    code = "already_released"


class AlreadyLocked(DomainConflict):
    code = "archive_locked"


@dataclass(frozen=True)
class DigestCard:
    kind: str
    title: str
    facts: list[tuple[str, str]]
    decided: bool


@dataclass(frozen=True)
class Concurrence:
    by_name: str
    at: datetime
    current: bool


@dataclass(frozen=True)
class EqrView:
    required: bool
    eqr_names: list[str]
    is_me: bool
    digest: list[DigestCard]
    digest_hash: str
    concurrence: Concurrence | None
    open_notes: int


@dataclass(frozen=True)
class RecordView:
    id: UUID
    choice: str | None
    emphasis: bool | None
    document_date: date | None
    evidence_version_id: UUID | None
    rationale: str | None
    by_name: str
    at: datetime


@dataclass(frozen=True)
class ReportView:
    record: RecordView
    approved_by_name: str | None
    approved_at: datetime | None


@dataclass(frozen=True)
class ReleaseView:
    report_date: date
    documentation_due: date
    released_by_name: str
    at: datetime


@dataclass(frozen=True)
class ArchiveView:
    seal: str
    leaf_count: int
    locked_by_name: str
    at: datetime


@dataclass(frozen=True)
class ChecklistItem:
    key: str
    done: bool
    applicable: bool
    gate: str | None
    blockers: list[str]


@dataclass(frozen=True)
class CompletionView:
    checklist: list[ChecklistItem]
    eqr: EqrView
    going_concern: RecordView | None
    report: ReportView | None
    rep_letter: RecordView | None
    release: ReleaseView | None
    archive: ArchiveView | None
    can_release: bool
    release_blockers: list[str]
    can_lock: bool
    lock_blockers: list[str]


# --- pure ------------------------------------------------------------------------------------


def digest_hash(judgments: list[Judgment]) -> str:
    payload = [[j.kind, j.title, [list(f) for f in j.facts], j.decided] for j in judgments]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


def merkle_root(leaves: list[str]) -> str:
    """SHA-256 Merkle root over sorted leaf hashes (an odd node is carried up as is)."""
    level = sorted(hashlib.sha256(leaf.encode()).hexdigest() for leaf in leaves)
    if not level:
        raise CompletionBlocked("empty_binder")
    while len(level) > 1:
        nxt = [
            hashlib.sha256((level[i] + level[i + 1]).encode()).hexdigest()
            for i in range(0, len(level) - 1, 2)
        ]
        if len(level) % 2:
            nxt.append(level[-1])
        level = nxt
    return level[0]


def documentation_due(report_date: date) -> date:
    return report_date + timedelta(days=DOCUMENTATION_DAYS)


def _newest(records: list[CompletionRecord], kind: str) -> CompletionRecord | None:
    return next((r for r in records if r.kind == kind), None)


# --- gates (tenant level; callers authorised) -------------------------------------------------


@dataclass(frozen=True)
class CompletionState:
    records: list[CompletionRecord]
    concurrence: EqrConcurrence | None
    release: Release | None
    archive: Archive | None
    judgments: list[Judgment]
    eqrs: list[UUID]


async def _state(tenant: TenantContext, engagement_id: UUID) -> CompletionState:
    async with tenant_session(tenant) as session:
        records = list(await records_of(session, engagement_id))
        concurrence = await newest_concurrence(session, engagement_id)
        release = await release_of(session, engagement_id)
        archive = await archive_of(session, engagement_id)
    return CompletionState(
        records,
        concurrence,
        release,
        archive,
        await judgments_of(tenant, engagement_id),
        await engagement_eqrs(tenant.tenant_id, engagement_id),
    )


def g6_of(state: CompletionState) -> GateFact:
    if not state.eqrs:
        return GateFact(met=True, blockers=())
    if state.concurrence is None:
        return GateFact(met=False, blockers=("eqr_not_concurred",))
    if state.concurrence.digest_hash != digest_hash(state.judgments):
        return GateFact(met=False, blockers=("eqr_digest_changed",))
    return GateFact(met=True)


def g7_of(state: CompletionState) -> GateFact:
    report = _newest(state.records, "report")
    letter = _newest(state.records, "rep_letter")
    blockers: list[str] = []
    if report is None:
        blockers.append("no_report")
    if letter is None:
        blockers.append("no_rep_letter")
    if report is not None and letter is not None and letter.document_date != report.document_date:
        blockers.append("rep_letter_date_mismatch")
    return GateFact(met=not blockers, blockers=tuple(blockers))


def approved_report(state: CompletionState) -> CompletionRecord | None:
    report = _newest(state.records, "report")
    approval = _newest(state.records, "report_approval")
    if report is None or approval is None or approval.report_record_id != report.id:
        return None
    return report


async def g6(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    return g6_of(await _state(tenant, engagement_id))


async def g7(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    return g7_of(await _state(tenant, engagement_id))


async def g8(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    state = await _state(tenant, engagement_id)
    return GateFact(
        met=state.release is not None, blockers=() if state.release else ("not_released",)
    )


async def g9(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    state = await _state(tenant, engagement_id)
    return GateFact(
        met=state.archive is not None, blockers=() if state.archive else ("not_locked",)
    )


def release_blockers(state: CompletionState, g5: GateFact) -> list[str]:
    blockers = [f"G5:{b}" for b in g5.blockers] if not g5.met else []
    blockers += [f"G6:{b}" for b in g6_of(state).blockers]
    blockers += [f"G7:{b}" for b in g7_of(state).blockers]
    if _newest(state.records, "going_concern") is None:
        blockers.append("going_concern_not_decided")
    if approved_report(state) is None:
        blockers.append("report_not_approved")
    if state.release is not None:
        blockers.append("already_released")
    return blockers


def lock_blockers(state: CompletionState, g5: GateFact) -> list[str]:
    blockers: list[str] = []
    if state.release is None:
        blockers.append("not_released")
    if not g5.met:
        blockers.extend(f"G5:{b}" for b in g5.blockers)
    if state.archive is not None:
        blockers.append("already_locked")
    return blockers


# --- read --------------------------------------------------------------------------------------


async def completion_for(ctx: AuthContext, engagement_id: UUID) -> CompletionView:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "completion.read", ref.resource())
    state = await _state(ctx.tenant, engagement_id)
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    facts = {g: await gate_fact(ctx.tenant, engagement_id, g) for g in ("G1", "G2", "G3", "G5")}
    g6f, g7f = g6_of(state), g7_of(state)
    gc = _newest(state.records, "going_concern")
    report = _newest(state.records, "report")
    approved = approved_report(state)
    letter = _newest(state.records, "rep_letter")
    approval = _newest(state.records, "report_approval")

    def record(r: CompletionRecord | None) -> RecordView | None:
        if r is None:
            return None
        return RecordView(
            r.id,
            r.choice,
            r.emphasis,
            r.document_date,
            r.evidence_version_id,
            r.rationale,
            names.get(r.recorded_by, "Former member"),
            r.created_at,
        )

    checklist = [
        ChecklistItem("accepted", facts["G1"].met, True, "G1", list(facts["G1"].blockers)),
        ChecklistItem("independence", facts["G2"].met, True, "G2", list(facts["G2"].blockers)),
        ChecklistItem(
            "engagement_letter", facts["G3"].met, True, "G3", list(facts["G3"].blockers)
        ),
        ChecklistItem("review_complete", facts["G5"].met, True, "G5", list(facts["G5"].blockers)),
        ChecklistItem("eqr_concurred", g6f.met, bool(state.eqrs), "G6", list(g6f.blockers)),
        ChecklistItem("going_concern", gc is not None, True, None, []),
        ChecklistItem("report_approved", approved is not None, True, None, []),
        ChecklistItem("rep_letter", g7f.met, True, "G7", list(g7f.blockers)),
        ChecklistItem("released", state.release is not None, True, "G8", []),
        ChecklistItem("archived", state.archive is not None, True, "G9", []),
    ]
    concurrence = None
    if state.concurrence is not None:
        concurrence = Concurrence(
            names.get(state.concurrence.concurred_by, "Former member"),
            state.concurrence.created_at,
            state.concurrence.digest_hash == digest_hash(state.judgments),
        )
    notes = await review_open_notes(ctx.tenant, engagement_id)
    rb = release_blockers(state, facts["G5"])
    lb = lock_blockers(state, facts["G5"])
    return CompletionView(
        checklist,
        EqrView(
            bool(state.eqrs),
            [names.get(u, "Former member") for u in state.eqrs],
            ctx.user_id in state.eqrs,
            [DigestCard(j.kind, j.title, list(j.facts), j.decided) for j in state.judgments],
            digest_hash(state.judgments),
            concurrence,
            sum(notes.values()),
        ),
        record(gc),
        ReportView(
            record(report),  # type: ignore[arg-type]  # report is not None here
            names.get(approval.recorded_by, "Former member") if approved and approval else None,
            approval.created_at if approved and approval else None,
        )
        if report is not None
        else None,
        record(letter),
        ReleaseView(
            state.release.report_date,
            state.release.documentation_due,
            names.get(state.release.released_by, "Former member"),
            state.release.created_at,
        )
        if state.release
        else None,
        ArchiveView(
            state.archive.seal,
            state.archive.leaf_count,
            names.get(state.archive.locked_by, "Former member"),
            state.archive.created_at,
        )
        if state.archive
        else None,
        not rb,
        rb,
        not lb,
        lb,
    )


# --- acts --------------------------------------------------------------------------------------


async def _not_released(tenant: TenantContext, engagement_id: UUID) -> None:
    async with tenant_session(tenant) as session:
        if await release_of(session, engagement_id) is not None:
            raise AlreadyReleased(str(engagement_id))


async def concur(ctx: AuthContext, engagement_id: UUID, not_involved: bool) -> None:
    """G6: the EQR concurs over the current digest."""
    if not not_involved:
        raise CompletionInvalid("not_involved")
    state = await _state(ctx.tenant, engagement_id)
    if ctx.user_id not in state.eqrs:
        raise NotTheEqr(str(engagement_id))
    if sum((await review_open_notes(ctx.tenant, engagement_id)).values()):
        raise CompletionBlocked("review_notes_open")
    await _not_released(ctx.tenant, engagement_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "eqr.concur", ref.resource())
        digest = digest_hash(state.judgments)
        await insert_row(
            tx.session,
            EqrConcurrence,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            digest_hash=digest,
            not_involved=True,
            concurred_by=ctx.user_id,
            actor_kind=ctx.tenant.actor_kind,
        )
        tx.record(
            "eqr.concurred", target=Target("engagement", engagement_id), after=Ref(digest=digest)
        )


async def _record(
    ctx: AuthContext, engagement_id: UUID, action: str, event: str, **values: object
) -> None:
    await _not_released(ctx.tenant, engagement_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, action, ref.resource())
        await insert_row(
            tx.session,
            CompletionRecord,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            recorded_by=ctx.user_id,
            actor_kind=ctx.tenant.actor_kind,
            **values,
        )
        tx.record(event, target=Target("engagement", engagement_id))


def _rationale(text: str | None, required: bool) -> str | None:
    value = (text or "").strip() or None
    if required and value is None:
        raise CompletionInvalid("rationale")
    if value is not None and len(value) > 1000:
        raise CompletionInvalid("rationale")
    return value


async def decide_going_concern(
    ctx: AuthContext, engagement_id: UUID, choice: str, rationale: str | None
) -> None:
    """Reserved to the engagement partner (the matrix)."""
    if choice not in GOING_CONCERN:
        raise CompletionInvalid("choice")
    await _record(
        ctx,
        engagement_id,
        "completion.decide",
        "going_concern.decided",
        kind="going_concern",
        choice=choice,
        rationale=_rationale(rationale, choice != "no_substantial_doubt"),
    )


async def _engagement_version(ctx: AuthContext, engagement_id: UUID, version_id: UUID) -> None:
    if (await version_view(ctx.tenant, version_id)).engagement_id != engagement_id:
        raise NotFound("evidence_version")


async def record_report(
    ctx: AuthContext,
    engagement_id: UUID,
    opinion: str,
    emphasis: bool,
    report_date: date,
    evidence_version_id: UUID,
) -> None:
    """The report as issued from the firm's template: its opinion form, date and document."""
    if opinion not in OPINIONS:
        raise CompletionInvalid("opinion")
    state = await _state(ctx.tenant, engagement_id)
    gc = _newest(state.records, "going_concern")
    if gc is not None and gc.choice == "doubt_exists" and not emphasis:
        raise CompletionInvalid("going_concern_paragraph")
    await _engagement_version(ctx, engagement_id, evidence_version_id)
    await _record(
        ctx,
        engagement_id,
        "completion.record",
        "report.recorded",
        kind="report",
        choice=opinion,
        emphasis=emphasis,
        document_date=report_date,
        evidence_version_id=evidence_version_id,
    )


async def approve_report(ctx: AuthContext, engagement_id: UUID) -> None:
    """The engagement partner approves the newest report record."""
    state = await _state(ctx.tenant, engagement_id)
    report = _newest(state.records, "report")
    if report is None:
        raise CompletionBlocked("no_report")
    await _record(
        ctx,
        engagement_id,
        "report.approve",
        "report.approved",
        kind="report_approval",
        report_record_id=report.id,
    )


async def record_rep_letter(
    ctx: AuthContext, engagement_id: UUID, letter_date: date, evidence_version_id: UUID
) -> None:
    await _engagement_version(ctx, engagement_id, evidence_version_id)
    await _record(
        ctx,
        engagement_id,
        "completion.record",
        "rep_letter.recorded",
        kind="rep_letter",
        document_date=letter_date,
        evidence_version_id=evidence_version_id,
    )


async def release(ctx: AuthContext, engagement_id: UUID, attest: bool) -> None:
    """G8: the partner releases; every gate is checked again in the same unit."""
    if not attest:
        raise CompletionInvalid("attest")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "report.release", ref.resource())
        state = await _state(ctx.tenant, engagement_id)
        g5 = await gate_fact(ctx.tenant, engagement_id, "G5")
        blockers = release_blockers(state, g5)
        if blockers:
            raise CompletionBlocked(",".join(blockers)[:500])
        report = approved_report(state)
        if report is None or report.document_date is None:
            raise CompletionBlocked("report_not_approved")
        gates = {
            "G5": True,
            "G6": g6_of(state).met,
            "G7": True,
            "eqr_digest": digest_hash(state.judgments),
        }
        await insert_row(
            tx.session,
            Release,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            report_record_id=report.id,
            report_date=report.document_date,
            documentation_due=documentation_due(report.document_date),
            gates=gates,
            released_by=ctx.user_id,
            actor_kind=ctx.tenant.actor_kind,
        )
        await set_assurance_phase(tx, engagement_id, "released")
        tx.record(
            "report.released",
            target=Target("engagement", engagement_id),
            after=Ref(report=report.id),
        )


async def _leaves(
    ctx: AuthContext, engagement_id: UUID, state: CompletionState
) -> list[tuple[str, str]]:
    """(kind:id, hash) for everything the binder holds."""
    found: list[Reviewable] = await reviewables_of(ctx.tenant, engagement_id)
    leaves = [(f"{r.target_type}:{r.target_id}", r.content_hash) for r in found]
    for r in state.records:
        if r.evidence_version_id is not None:
            view = await version_view(ctx.tenant, r.evidence_version_id)
            leaves.append((f"evidence_version:{view.id}", view.stored.fingerprint))
    if state.concurrence is not None:
        leaves.append((f"eqr_concurrence:{state.concurrence.id}", state.concurrence.digest_hash))
    if state.release is not None:
        leaves.append((f"release:{state.release.id}", str(state.release.report_record_id)))
    return sorted(set(leaves))


async def lock_archive(ctx: AuthContext, engagement_id: UUID, attest: bool) -> None:
    """G9: a manager or the partner locks the archive after release."""
    if not attest:
        raise CompletionInvalid("attest")
    state = await _state(ctx.tenant, engagement_id)
    g5 = await gate_fact(ctx.tenant, engagement_id, "G5")
    blockers = lock_blockers(state, g5)
    if blockers:
        raise CompletionBlocked(",".join(blockers)[:500])
    leaves = await _leaves(ctx, engagement_id, state)
    seal = merkle_root([f"{k}={h}" for k, h in leaves])
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "archive.lock", ref.resource())
        async with tenant_session(ctx.tenant) as session:
            if await archive_of(session, engagement_id) is not None:
                raise AlreadyLocked(str(engagement_id))
        await insert_row(
            tx.session,
            Archive,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            seal=seal,
            leaf_count=len(leaves),
            manifest={"leaves": [{"ref": k, "hash": h} for k, h in leaves]},
            locked_by=ctx.user_id,
            actor_kind=ctx.tenant.actor_kind,
        )
        await set_assurance_phase(tx, engagement_id, "archived")
        await lock_engagement(tx, engagement_id, datetime.now(UTC))
        tx.record(
            "archive.locked", target=Target("engagement", engagement_id), after=Ref(seal=seal)
        )

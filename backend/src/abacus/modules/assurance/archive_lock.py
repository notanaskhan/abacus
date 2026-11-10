"""G9: the archive lock and its seal (A-07-T37; A-07 F8, AUD-25 b2, c; SPEC-644 AC-37;
ADR-159 proposed; ADR-090, ADR-071; AU-C 230). PROTECTED (red path).

1. **The decision (a person's).** A manager or the engagement partner (`archive.lock`, fresh MFA by
   the matrix), at 9 of 9 with the checklist hash they saw, attests "Assembly is complete". One
   `archive_lock_decisions` row (the database refuses one that is not a person's) moves the
   archive to `locking`; `ArchiveLockWorkflow` (`archive_lock:<tenant>:<work_item>`, batch) does
   the rest. A second decision answers 409; a changed checklist 409 `checklist_changed`.
2. **The seal (code).** One snapshot: every evidence version's SHA-256, the deterministic row
   export of the binder's reviewables, the run records' hashes and the firm's newest audit
   checkpoint, built into the canonical manifest (`archive_seal.build`). Its SHA-256 is the seal.
3. **Retention.** The manifest goes to the records bucket in COMPLIANCE mode until release + 5
   years (no one can shorten it); every evidence object's GOVERNANCE retain-until is extended to
   the archive's `retention_until` (release + the firm's policy, at least 5 years).
4. **The lock.** The archive `locked` with its seal and `archive.locked` on the outbox and in the
   trail; G9 then derives the phase (Archived); last, every work item's `archive_locked_at` and
   the engagement archived (read-only through `authorise` and `archived_guard`).

Every activity is idempotent, so a crashed run resumes: the manifest version is unique per
archive, a records object is written once per digest, and the lock refuses a locked archive.
History: `archive-lock-v1.json`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Final, cast
from uuid import UUID

from temporalio import activity, workflow
from temporalio.common import RetryPolicy, WorkflowIDConflictPolicy, WorkflowIDReusePolicy

with workflow.unsafe.imports_passed_through():
    from sqlalchemy import text

    from abacus.kernel import clock
    from abacus.kernel.db import TenantContext, tenant_session
    from abacus.kernel.errors import DomainConflict, NotFound
    from abacus.kernel.uow import Ref, Scope, Target, uow
    from abacus.modules.assurance.archive_records import five_year_floor
    from abacus.modules.assurance.archive_seal import Leaf, build
    from abacus.modules.assurance.events import ArchiveLocked
    from abacus.modules.identity.api import AuthContext

ID_PREFIX: Final = "archive_lock:"
_RETRY = RetryPolicy(maximum_attempts=20, initial_interval=timedelta(seconds=10))
_SHORT = timedelta(minutes=5)


class ArchiveNotReady(DomainConflict):
    """Not 9 of 9, not assembling, or no release yet."""

    code = "checklist_incomplete"


class ChecklistChanged(DomainConflict):
    """The checklist moved since the person looked (`seen_checklist_hash`): reload."""

    code = "checklist_changed"


class AlreadyLocking(DomainConflict):
    code = "archive_locked"


def workflow_id(tenant_id: UUID, work_item_id: UUID) -> str:
    return f"{ID_PREFIX}{tenant_id}:{work_item_id}"


# --- the decision (the route) --------------------------------------------------------------------


async def decide_lock(
    ctx: AuthContext,
    work_item_id: UUID,
    *,
    then_roll_forward: bool,
    seen_checklist_hash: str,
) -> UUID:
    """After the route's `archive.lock` (manager or EP, fresh MFA). Answers the archive id."""
    from abacus.modules.assurance.archive_gate import archive_state

    state = await archive_state(ctx.tenant, work_item_id)
    archive = state.archive
    if archive is None or archive.status != "assembling":
        if archive is not None and archive.status in ("locking", "locked"):
            raise AlreadyLocking
        raise ArchiveNotReady
    if state.done != len(state.items):
        raise ArchiveNotReady
    if state.checklist_sha256 != seen_checklist_hash:
        raise ChecklistChanged
    snapshot = [{"key": i.key, "done": i.done} for i in state.items]
    async with uow(ctx.tenant) as tx:
        decision = cast(
            UUID,
            await tx.session.scalar(
                text(
                    "INSERT INTO archive_lock_decisions (tenant_id, engagement_id, work_item_id, "
                    "archive_id, decided_by, assembly_complete_attested, then_roll_forward, "
                    "checklist_snapshot, checklist_sha256, mfa_verified_at) VALUES (:t, :e, :wi, "
                    ":a, :by, true, :roll, CAST(:snap AS jsonb), :sha, :mfa) RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": archive.engagement_id,
                    "wi": work_item_id,
                    "a": archive.id,
                    "by": ctx.user_id,
                    "roll": then_roll_forward,
                    "snap": json.dumps(snapshot),
                    "sha": state.checklist_sha256,
                    "mfa": ctx.mfa_at or datetime.now(UTC),
                },
            ),
        )
        moved = await tx.session.scalar(
            text(
                "UPDATE archives SET status = 'locking', lock_decision_id = :d "
                "WHERE id = :a AND status = 'assembling' RETURNING id"
            ),
            {"d": decision, "a": archive.id},
        )
        if moved is None:
            raise AlreadyLocking
        tx.record(
            "archive.lock_decided",
            target=Target("archive", archive.id),
            after=Ref(decision=decision, checklist=state.checklist_sha256),
            scope=Scope(engagement_id=archive.engagement_id, work_item_id=work_item_id),
        )
    return archive.id


async def start_lock(tenant_id: UUID, work_item_id: UUID, archive_id: UUID) -> str:
    """Dispatch after the decision committed (one run per work item)."""
    from abacus.kernel.dispatch import dispatch

    run_id = workflow_id(tenant_id, work_item_id)
    await dispatch(
        ArchiveLockWorkflow,
        LockInput(str(tenant_id), str(work_item_id), str(archive_id)),
        id=run_id,
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return run_id


# --- the workflow --------------------------------------------------------------------------------


@dataclass(frozen=True)
class LockInput:
    tenant_id: str
    work_item_id: str
    archive_id: str


@dataclass(frozen=True)
class SealResult:
    manifest_id: str
    seal: str
    already_locked: bool


@workflow.defn(name="ArchiveLockWorkflow")
class ArchiveLockWorkflow:
    @workflow.run
    async def run(self, p: LockInput) -> str:
        sealed = await workflow.execute_activity(
            "assurance.archive_lock.seal",
            args=[p.tenant_id, p.work_item_id, p.archive_id],
            result_type=SealResult,
            start_to_close_timeout=_SHORT,
            retry_policy=_RETRY,
        )
        if sealed.already_locked:
            return sealed.seal
        await workflow.execute_activity(
            "assurance.archive_lock.extend_evidence",
            args=[p.tenant_id, p.work_item_id, p.archive_id],
            result_type=int,
            start_to_close_timeout=_SHORT,
            retry_policy=_RETRY,
        )
        await workflow.execute_activity(
            "assurance.archive_lock.finish",
            args=[p.tenant_id, p.work_item_id, p.archive_id, sealed.manifest_id],
            result_type=str,
            start_to_close_timeout=_SHORT,
            retry_policy=_RETRY,
        )
        return sealed.seal


def _tenant(tenant_id: str, work_item_id: str) -> TenantContext:
    return TenantContext(UUID(tenant_id), "system", f"archive_lock:{work_item_id}")


_ARCHIVE: Final = (
    "SELECT a.id, a.engagement_id, a.status, a.release_id, a.release_date, a.retention_until, "
    "a.lock_decision_id, a.seal_sha256, d.checklist_sha256 FROM archives a "
    "JOIN archive_lock_decisions d ON d.id = a.lock_decision_id WHERE a.id = :a"
)


@dataclass(frozen=True)
class LockRow:
    id: UUID
    engagement_id: UUID
    status: str
    release_id: UUID
    release_date: date
    retention_until: date
    lock_decision_id: UUID
    seal_sha256: str | None
    checklist_sha256: str


async def _archive_row(tenant: TenantContext, archive_id: UUID) -> LockRow:
    async with tenant_session(tenant) as session:
        row = (await session.execute(text(_ARCHIVE), {"a": archive_id})).first()
    if row is None:
        raise NotFound("archive")
    return LockRow(*row)


def _end_of(day: date) -> datetime:
    return datetime.combine(day, time(23, 59, 59), tzinfo=clock.FIRM_ZONE)


@activity.defn(name="assurance.archive_lock.seal")
async def seal_activity(tenant_id: str, work_item_id: str, archive_id: str) -> SealResult:
    """The snapshot, the manifest row (version 1) and the COMPLIANCE records object."""
    from abacus.kernel.uow.chain import latest_checkpoint
    from abacus.modules.agents.api import run_record_hashes
    from abacus.modules.evidence.api import engagement_version_leaves, put_record
    from abacus.modules.review.api import reviewables_of

    tenant = _tenant(tenant_id, work_item_id)
    row = await _archive_row(tenant, UUID(archive_id))
    status = str(row.status)
    if status == "locked":
        return SealResult("", str(row.seal_sha256), True)
    engagement_id = row.engagement_id
    release_date = row.release_date
    retention_until = row.retention_until
    found = await _manifest_of(tenant, UUID(archive_id))
    if found is not None:
        return SealResult(str(found[0]), found[1], False)  # a resumed run: sealed already
    leaves = [
        Leaf("evidence_version", str(v), sha)
        for v, sha, _, _ in await engagement_version_leaves(tenant, engagement_id)
    ]
    leaves += [
        Leaf("row", f"{r.target_type}:{r.target_id}", r.content_hash)
        for r in await reviewables_of(tenant, engagement_id)
    ]
    leaves += [
        Leaf("run_record", str(run), sha)
        for run, sha in await run_record_hashes(tenant, engagement_id)
    ]
    checkpoint = await latest_checkpoint(tenant.tenant_id)
    compliance_until = five_year_floor(release_date)
    manifest = build(
        tenant_id=tenant_id,
        engagement_id=str(engagement_id),
        work_item_id=work_item_id,
        archive_id=archive_id,
        release_id=str(row.release_id),
        release_date=release_date,
        retention_until=retention_until,
        compliance_retain_until=compliance_until,
        leaves=leaves,
        audit_checkpoint_seq_to=checkpoint.seq_to if checkpoint is not None else None,
        audit_checkpoint_root=checkpoint.merkle_root.hex() if checkpoint is not None else None,
        checklist_sha256=str(row.checklist_sha256),
    )
    stored = await put_record(
        tenant.tenant_id, "seal_manifest", manifest.body, _end_of(compliance_until)
    )
    async with uow(tenant) as tx:
        manifest_id = await tx.session.scalar(
            text(
                "INSERT INTO archive_manifests (tenant_id, engagement_id, work_item_id, "
                "archive_id, manifest_version, evidence_leaf_count, row_leaf_count, "
                "run_record_count, audit_checkpoint_seq_to, audit_checkpoint_root, "
                "merkle_root, manifest_sha256, records_object_key, records_version_id, "
                "compliance_retain_until) VALUES (:t, :e, :wi, :a, 1, :ev, :rows, :runs, "
                ":seq, :root, :merkle, :sha, :key, :ver, :until) "
                "ON CONFLICT (tenant_id, archive_id, manifest_version) DO NOTHING RETURNING id"
            ),
            {
                "t": tenant.tenant_id,
                "e": engagement_id,
                "wi": UUID(work_item_id),
                "a": UUID(archive_id),
                "ev": manifest.evidence_leaf_count,
                "rows": manifest.row_leaf_count,
                "runs": manifest.run_record_count,
                "seq": checkpoint.seq_to if checkpoint is not None else None,
                "root": checkpoint.merkle_root.hex() if checkpoint is not None else None,
                "merkle": manifest.merkle_root,
                "sha": manifest.sha256,
                "key": stored.key,
                "ver": stored.version_id,
                "until": compliance_until,
            },
        )
        if manifest_id is None:  # another delivery wrote it between the read and here
            again = await _manifest_of(tenant, UUID(archive_id))
            if again is None:
                raise NotFound("archive_manifest")
            return SealResult(str(again[0]), again[1], False)
        tx.record(
            "archive.sealed",
            target=Target("archive", UUID(archive_id)),
            after=Ref(seal=manifest.sha256, leaves=len(leaves)),
            scope=Scope(engagement_id=engagement_id, work_item_id=UUID(work_item_id)),
        )
    return SealResult(str(manifest_id), manifest.sha256, False)


async def _manifest_of(tenant: TenantContext, archive_id: UUID) -> tuple[UUID, str] | None:
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT id, manifest_sha256 FROM archive_manifests WHERE archive_id = :a "
                    "AND manifest_version = 1"
                ),
                {"a": archive_id},
            )
        ).first()
    return None if row is None else (row.id, row.manifest_sha256)


@activity.defn(name="assurance.archive_lock.extend_evidence")
async def extend_evidence_activity(tenant_id: str, work_item_id: str, archive_id: str) -> int:
    """GOVERNANCE retain-until of every evidence object extended to the archive's retention."""
    from abacus.modules.evidence.api import engagement_version_leaves, extend_versions_until

    tenant = _tenant(tenant_id, work_item_id)
    row = await _archive_row(tenant, UUID(archive_id))
    engagement_id = row.engagement_id
    until = _end_of(row.retention_until)
    objects = [
        (key, ver) for _, _, key, ver in await engagement_version_leaves(tenant, engagement_id)
    ]
    return await extend_versions_until(tenant, objects, until)


@activity.defn(name="assurance.archive_lock.finish")
async def finish_activity(
    tenant_id: str, work_item_id: str, archive_id: str, manifest_id: str
) -> str:
    """The archive locked with its seal, the engagement archived, G9 derived."""
    from abacus.modules.assurance.phase import derive_phase
    from abacus.modules.engagements.api import lock_engagement

    tenant = _tenant(tenant_id, work_item_id)
    row = await _archive_row(tenant, UUID(archive_id))
    if str(row.status) == "locked":
        return str(row.seal_sha256)
    engagement_id = row.engagement_id
    at = await clock.now(tenant)
    async with uow(tenant) as tx:
        manifest = (
            await tx.session.execute(
                text(
                    "SELECT manifest_sha256, records_object_key, records_version_id "
                    "FROM archive_manifests WHERE id = :m"
                ),
                {"m": UUID(manifest_id)},
            )
        ).one()
        decided_by = await tx.session.scalar(
            text("SELECT decided_by FROM archive_lock_decisions WHERE id = :d"),
            {"d": row.lock_decision_id},
        )
        await tx.session.execute(
            text(
                "UPDATE archives SET status = 'locked', locked_at = :at, locked_by = :by, "
                "manifest_id = :m, seal_sha256 = :seal, records_object_key = :key, "
                "records_version_id = :ver WHERE id = :a AND status = 'locking'"
            ),
            {
                "at": at,
                "by": decided_by,
                "m": UUID(manifest_id),
                "seal": manifest.manifest_sha256,
                "key": manifest.records_object_key,
                "ver": manifest.records_version_id,
                "a": UUID(archive_id),
            },
        )
        tx.record(
            "archive.locked",
            target=Target("archive", UUID(archive_id)),
            after=Ref(seal=manifest.manifest_sha256),
            scope=Scope(engagement_id=engagement_id, work_item_id=UUID(work_item_id)),
        )
        tx.emit(
            ArchiveLocked(
                archive_id=UUID(archive_id),
                engagement_id=engagement_id,
                work_item_id=UUID(work_item_id),
                seal_sha256=manifest.manifest_sha256,
            )
        )
    await derive_phase(tenant, engagement_id, "G9")  # G9 is met now: Archived
    async with uow(tenant) as tx:
        # Last: from here the engagement is read-only (`authorise`, `archived_guard`).
        await lock_engagement(tx, engagement_id, at)
        tx.record(
            "archive.engagement_archived",
            target=Target("engagement", engagement_id),
            after=Ref(archive=UUID(archive_id)),
            scope=Scope(engagement_id=engagement_id, work_item_id=UUID(work_item_id)),
        )
    return str(manifest.manifest_sha256)


WORKFLOWS: Final[dict[type, str]] = {ArchiveLockWorkflow: "batch"}
ACTIVITIES: Final[tuple[object, ...]] = (seal_activity, extend_evidence_activity, finish_activity)

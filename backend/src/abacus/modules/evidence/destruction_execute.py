"""Destruction approvals and execution (Q-05-T15; SPEC-711 AC-22 to AC-26; ADR-179 as amended by
OQ-1; DEC-5824). PROTECTED (red).

- **Two approvals.** A firm admin and a security admin, distinct people and roles, each with a
  fresh MFA (`destruction.approve`; the database refuses a third, the same person twice and the
  same role twice). The second must type the batch's phrase exactly ("DESTROY 2026-Q3"; 409
  `batch_phrase_mismatch`); it moves the batch to Approved, issues the execution grant and starts
  `DestructionExecuteWorkflow` in the batch class.
- **Execution** (the activity, as the system on the second approver's behalf): per item, the hold
  is re-checked in the database and on S3 (`held`), the observed retain-until is re-read
  (`retention_extended`), an object key another live version still uses is kept
  (`shared_object`), then the version is deleted on the primary and the replica under the
  destruction role (S3 still refuses a held or retained version: `missing_object` never deletes
  what S3 refused), every registered derived store is purged, and the evidence version is
  tombstoned (`destroyed_at`, `destruction_certificate_id`) under `destruction_tombstone`.
  Exclusions only shrink the batch. The kill switch `destruction_execute` stops the next item.
- **The certificate** (OQ-10): batch, scope, counts, approvers, the hold re-check time, exclusions,
  the manifest's SHA-256, the audit checkpoint root and the 35-day backup statement, as canonical
  JSON (deterministic: the same batch gives the same bytes) written to the records bucket in
  COMPLIANCE mode for 7 years. Reads of a destroyed version answer 410 citing `DC-2026-Q3`.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, Forbidden, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Resource, authorise

MFA_WINDOW: Final = timedelta(minutes=10)
EXECUTE: Final = "evidence.execute_destruction"
CERTIFICATE_YEARS: Final = 7
BACKUP_STATEMENT: Final = (
    "Encrypted backups that may hold these records expire within 35 days of this certificate and "
    "are never restored to read them."
)
_NAMESPACE: Final = uuid.UUID("6f1c0a52-9d3a-4b8e-9a51-5c2b8d7e4f10")

DerivedStore = Callable[[TenantContext, UUID], Awaitable[int]]
_derived: dict[str, DerivedStore] = {}


def register_derived_store(name: str, purge: DerivedStore) -> None:
    """A module that keeps something derived from an evidence version (OCR text, previews, search
    rows, embeddings) registers its purge; execution calls each per destroyed version."""
    _derived[name] = purge


class PhraseMismatch(DomainConflict):
    code = "batch_phrase_mismatch"
    message = "Type the batch's phrase exactly to approve and destroy."


class SameApprover(DomainConflict):
    code = "same_approver"
    message = "The second approval must be another person in the other role."


class MfaRequired(DomainConflict):
    code = "mfa_required"
    message = "Confirm it's you to approve destruction."


class BatchNotOpen(DomainConflict):
    code = "batch_not_open"
    message = "The batch is no longer awaiting approval."


_BATCH = text(
    "SELECT id, ref, status, confirmation_phrase, eligible_count, scope_description "
    "FROM destruction_batches WHERE id = :b"
)
_APPROVALS = text(
    "SELECT approver_user_id, approver_role FROM destruction_approvals WHERE batch_id = :b"
)


def _role_of(ctx: AuthContext) -> str:
    """The approver's firm role: security_admin or firm_admin (the matrix lets these act)."""
    if ctx.firm_role in ("security_admin", "firm_admin"):
        return str(ctx.firm_role)
    raise Forbidden("destruction.approve", "role")


async def approve(
    ctx: AuthContext, batch_id: UUID, *, items_seen: int, confirmation: str | None
) -> str:
    """One approval; the second (with the phrase) approves the batch and answers 'approved'."""
    await authorise(ctx, "destruction.approve", Resource.firm(ctx.tenant_id))
    if ctx.mfa_at is None or await clock.now(ctx.tenant) - ctx.mfa_at > MFA_WINDOW:
        raise MfaRequired
    role = _role_of(ctx)
    async with tenant_session(ctx.tenant) as session:
        batch = (await session.execute(_BATCH, {"b": batch_id})).first()
        prior = list((await session.execute(_APPROVALS, {"b": batch_id})).all())
    if batch is None:
        raise NotFound("destruction_batch")
    if batch.status != "awaiting_approval":
        raise BatchNotOpen(facts={"status": str(batch.status)})
    if any(p.approver_user_id == ctx.user_id or p.approver_role == role for p in prior):
        raise SameApprover
    second = len(prior) == 1
    if second and confirmation != batch.confirmation_phrase:
        raise PhraseMismatch
    phrase = hashlib.sha256(confirmation.encode()).hexdigest() if second and confirmation else None
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO destruction_approvals (tenant_id, batch_id, approver_user_id, "
                "approver_role, mfa_verified_at, phrase_sha256, items_seen) VALUES (:t, :b, :u, "
                ":r, :mfa, :p, :n)"
            ),
            {"t": ctx.tenant_id, "b": batch_id, "u": ctx.user_id, "r": role, "mfa": ctx.mfa_at,
             "p": phrase, "n": items_seen},
        )  # fmt: skip
        if second:
            await tx.session.execute(
                text(
                    "UPDATE destruction_batches SET status = 'approved', version = version + 1 "
                    "WHERE id = :b AND status = 'awaiting_approval'"
                ),
                {"b": batch_id},
            )
        tx.record(
            "destruction_batch.approved" if second else "destruction_batch.first_approval",
            target=Target("destruction_batch", batch_id),
            after=Ref(role=0 if role == "firm_admin" else 1),
        )
    if second:
        await start_execution(ctx.tenant_id, batch_id, ctx.user_id)
        return "approved"
    return "awaiting_approval"


async def cancel(ctx: AuthContext, batch_id: UUID, reason: str) -> None:
    """Before execution only (OQ-12: API and runbook)."""
    await authorise(ctx, "destruction.approve", Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        done = await tx.session.scalar(
            text(
                "UPDATE destruction_batches SET status = 'cancelled', version = version + 1 "
                "WHERE id = :b AND status IN ('awaiting_approval', 'approved') RETURNING id"
            ),
            {"b": batch_id},
        )
        if done is None:
            raise BatchNotOpen
        tx.record("destruction_batch.cancelled", target=Target("destruction_batch", batch_id))
    del reason  # kept in the audit trail's sealed note by the route (confidential)


# --- execution -----------------------------------------------------------------------------------

_ITEMS = text(
    "SELECT i.id, i.evidence_version_id, i.object_key, i.object_version_id, i.replica_version_id, "
    "i.retain_until_observed FROM destruction_batch_items i WHERE i.batch_id = :b AND NOT EXISTS "
    "(SELECT 1 FROM destruction_item_exclusions x WHERE x.item_id = i.id) ORDER BY i.id"
)
_HELD = text(
    "SELECT 1 FROM hold_objects h JOIN legal_holds l ON l.id = h.hold_id WHERE "
    "h.evidence_version_id = :v AND l.status IN ('applying', 'active') LIMIT 1"
)
_SHARED = text(
    "SELECT 1 FROM evidence_versions WHERE storage_key = :k AND id <> :v AND destroyed_at IS NULL "
    "LIMIT 1"
)


async def _exclude(tenant: TenantContext, item_id: UUID, reason: str) -> None:
    async with uow(tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO destruction_item_exclusions (tenant_id, item_id, reason) VALUES "
                "(:t, :i, :r) ON CONFLICT (item_id) DO NOTHING"
            ),
            {"t": tenant.tenant_id, "i": item_id, "r": reason},
        )
        tx.record("destruction_item.excluded", target=Target("destruction_batch_item", item_id))


async def execute(tenant_id: UUID, batch_id: UUID, approver: UUID) -> str:
    """The activity: every remaining item, then the certificate. Re-running continues where it
    stopped (excluded and tombstoned items are skipped)."""
    from abacus.kernel.controls import control_active_now
    from abacus.modules.evidence import storage

    tenant = TenantContext(tenant_id, "system", f"destruction:{batch_id}", on_behalf_of_user_id=approver)
    async with tenant_session(tenant) as session:
        batch = (await session.execute(_BATCH, {"b": batch_id})).first()
        items = list((await session.execute(_ITEMS, {"b": batch_id})).all())
    if batch is None:
        raise NotFound("destruction_batch")
    if batch.status == "destroyed":
        return "destroyed"
    async with uow(tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE destruction_batches SET status = 'destroying', hold_recheck_at = "
                "clock_timestamp(), version = version + 1 WHERE id = :b AND status = 'approved'"
            ),
            {"b": batch_id},
        )
        tx.record("destruction_batch.destroying", target=Target("destruction_batch", batch_id))
    certificate_id = uuid.uuid5(_NAMESPACE, f"{tenant_id}:{batch_id}")
    destroyed = 0
    for item in items:
        if await control_active_now("destruction_execute", tenant_id):
            raise DomainConflict(facts={"reason": "kill_switch"})
        async with tenant_session(tenant) as session:
            gone = await session.scalar(
                text("SELECT destroyed_at FROM evidence_versions WHERE id = :v"),
                {"v": item.evidence_version_id},
            )
            held = await session.scalar(_HELD, {"v": item.evidence_version_id})
            shared = await session.scalar(
                _SHARED, {"k": item.object_key, "v": item.evidence_version_id}
            )
        if gone is not None:
            destroyed += 1
            continue
        stored = storage.StoredObject(item.object_key, item.object_version_id, "", 0)
        if held is not None or await storage.legal_hold_on(stored):
            await _exclude(tenant, item.id, "held")
            continue
        observed = await storage.observed_retain_until(item.object_key, item.object_version_id)
        now = await clock.now(tenant)
        if observed is not None and observed > now:
            await _exclude(tenant, item.id, "retention_extended")
            continue
        if shared is not None:
            await _exclude(tenant, item.id, "shared_object")
            continue
        if not await storage.delete_version(str(batch.ref), item.object_key, item.object_version_id):
            await _exclude(tenant, item.id, "missing_object")  # S3 refused: never forced
            continue
        if item.replica_version_id:
            await storage.delete_version(
                str(batch.ref), item.object_key, item.replica_version_id, replica=True
            )
        for purge in _derived.values():
            await purge(tenant, item.evidence_version_id)
        async with uow(tenant) as tx:
            await tx.allow_archived_write("destruction_tombstone")
            await tx.session.execute(
                text(
                    "UPDATE evidence_versions SET destroyed_at = clock_timestamp(), "
                    "destruction_certificate_id = :c WHERE id = :v AND destroyed_at IS NULL"
                ),
                {"c": certificate_id, "v": item.evidence_version_id},
            )
            tx.record(
                "evidence_version.destroyed",
                target=Target("evidence_version", item.evidence_version_id),
                after=Ref(batch=batch_id),
            )
        destroyed += 1
    await certify(tenant, batch_id, certificate_id, destroyed)
    return "destroyed"


def certificate_body(
    *, ref: str, scope: str, eligible: int, destroyed: int, excluded: list[tuple[str, str]],
    approvers: list[tuple[str, str]], hold_recheck_at: str, manifest_sha256: str, checkpoint_root: str,
) -> bytes:
    """Canonical JSON (sorted keys, no whitespace variance): the same batch, the same bytes."""
    return json.dumps(
        {
            "certificate": f"DC-{ref}",
            "batch": ref,
            "scope": scope,
            "counts": {"eligible": eligible, "destroyed": destroyed, "excluded": len(excluded)},
            "exclusions": sorted(excluded),
            "approvers": sorted(approvers),
            "hold_recheck_at": hold_recheck_at,
            "manifest_sha256": manifest_sha256,
            "audit_checkpoint_root": checkpoint_root,
            "backup_statement": BACKUP_STATEMENT,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


async def certify(tenant: TenantContext, batch_id: UUID, certificate_id: UUID, destroyed: int) -> None:
    from abacus.kernel.uow.chain import latest_checkpoint
    from abacus.modules.evidence.records import put_record

    async with tenant_session(tenant) as session:
        batch = (await session.execute(
            text("SELECT ref, scope_description, eligible_count, hold_recheck_at FROM destruction_batches WHERE id = :b"),
            {"b": batch_id},
        )).first()  # fmt: skip
        items = [str(r[0]) for r in (await session.execute(
            text("SELECT evidence_version_id FROM destruction_batch_items WHERE batch_id = :b ORDER BY evidence_version_id"),
            {"b": batch_id},
        )).all()]  # fmt: skip
        excluded = [(str(r[0]), str(r[1])) for r in (await session.execute(
            text("SELECT i.evidence_version_id, x.reason FROM destruction_item_exclusions x JOIN destruction_batch_items i ON i.id = x.item_id WHERE i.batch_id = :b"),
            {"b": batch_id},
        )).all()]  # fmt: skip
        approvers = [(str(r[0]), str(r[1])) for r in (await session.execute(_APPROVALS, {"b": batch_id})).all()]
    if batch is None:
        raise NotFound("destruction_batch")
    manifest = hashlib.sha256("\n".join(items).encode()).hexdigest()
    checkpoint = await latest_checkpoint(tenant.tenant_id)
    root = checkpoint.merkle_root.hex() if checkpoint is not None else "0" * 64
    body = certificate_body(
        ref=str(batch.ref), scope=str(batch.scope_description), eligible=int(batch.eligible_count),
        destroyed=destroyed, excluded=excluded, approvers=approvers,
        hold_recheck_at=batch.hold_recheck_at.isoformat() if batch.hold_recheck_at else "",
        manifest_sha256=manifest, checkpoint_root=str(root),
    )  # fmt: skip
    now = await clock.now(tenant)
    stored = await put_record(
        tenant.tenant_id, "destruction_certificate", body,
        now + timedelta(days=round(365.25 * CERTIFICATE_YEARS)),
    )  # fmt: skip
    async with uow(tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO destruction_certificates (id, tenant_id, batch_id, ref, "
                "document_version_id, manifest_object_key, manifest_sha256, audit_checkpoint_root) "
                "VALUES (:id, :t, :b, :ref, :doc, :key, :sha, :root) ON CONFLICT DO NOTHING"
            ),
            {"id": certificate_id, "t": tenant.tenant_id, "b": batch_id, "ref": f"DC-{batch.ref}",
             "doc": uuid.uuid5(_NAMESPACE, stored.sha256), "key": stored.key, "sha": manifest,
             "root": str(root)},
        )  # fmt: skip
        await tx.session.execute(
            text(
                "UPDATE destruction_batches SET status = 'destroyed', destroyed_count = :n, "
                "held_excluded_count = :x, certificate_id = :c, version = version + 1 WHERE id = :b "
                "AND status = 'destroying'"
            ),
            {"n": destroyed, "x": len(excluded), "c": certificate_id, "b": batch_id},
        )
        tx.record("destruction_batch.destroyed", target=Target("destruction_batch", batch_id), after=Ref(n=destroyed))


async def certificate(tenant: TenantContext, certificate_id: UUID) -> dict[str, object]:
    async with tenant_session(tenant) as session:
        row = (await session.execute(
            text("SELECT c.id, c.ref, c.batch_id, c.manifest_sha256, c.audit_checkpoint_root, c.generated_at, b.destroyed_count, b.held_excluded_count, b.eligible_count FROM destruction_certificates c JOIN destruction_batches b ON b.id = c.batch_id WHERE c.id = :c"),
            {"c": certificate_id},
        )).mappings().first()  # fmt: skip
    if row is None:
        raise NotFound("destruction_certificate")
    return dict(row)


async def destroyed_reference(tenant: TenantContext, version_id: UUID) -> str | None:
    """`DC-2026-Q3` when the evidence version was destroyed (its reads answer 410), else None."""
    async with tenant_session(tenant) as session:
        return cast(str | None, await session.scalar(
            text("SELECT c.ref FROM evidence_versions v JOIN destruction_certificates c ON c.id = v.destruction_certificate_id WHERE v.id = :v AND v.destroyed_at IS NOT NULL"),
            {"v": version_id},
        ))  # fmt: skip


# --- DestructionExecuteWorkflow (worker-batch) ----------------------------------------------------


@activity.defn(name=EXECUTE)
async def execute_activity(given: list[str]) -> str:
    tenant_id, batch_id, approver = given
    return await execute(UUID(tenant_id), UUID(batch_id), UUID(approver))


@workflow.defn(name="DestructionExecuteWorkflow")
class DestructionExecuteWorkflow:
    """`destruction:<tenant>:<batch>`, batch class: one activity that resumes where it stopped."""

    @workflow.run
    async def run(self, given: list[str]) -> str:
        return cast(
            str,
            await workflow.execute_activity(
                EXECUTE, given, result_type=str,
                start_to_close_timeout=timedelta(hours=2),
                heartbeat_timeout=None,
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=30), maximum_attempts=10,
                    non_retryable_error_types=["NotFound", "DomainConflict"],
                ),
            ),
        )  # fmt: skip


async def start_execution(tenant_id: UUID, batch_id: UUID, approver: UUID) -> None:
    from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

    from abacus.kernel.dispatch import dispatch

    await dispatch(
        DestructionExecuteWorkflow,
        [str(tenant_id), str(batch_id), str(approver)],
        id=f"destruction:{tenant_id}:{batch_id}",
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


ACTIVITIES: tuple[object, ...] = (execute_activity,)

__all__ = [
    "ACTIVITIES", "BACKUP_STATEMENT", "DestructionExecuteWorkflow", "PhraseMismatch", "SameApprover",
    "approve", "cancel", "certificate", "certificate_body", "certify", "destroyed_reference",
    "execute", "register_derived_store", "start_execution",
]  # fmt: skip

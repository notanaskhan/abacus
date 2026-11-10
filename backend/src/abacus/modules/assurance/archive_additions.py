"""Post-lock additions and seal verification (A-07-T42; A-07 F7, F8; ADR-159 proposed, P-43;
AU-C 230 ¶.16–.17). PROTECTED (red path).

**Additions.** After lock, a manager or senior adds a document with a reason code
(`au_c_585_omitted_procedure`, `au_c_560_subsequently_discovered_fact`, `other`) and an evidence
version; the row is pending. The engagement partner approves (fresh MFA, the matrix's
`mfa_recent`) or rejects it with a reason. Only an approval appends anything:

1. The addition manifest (canonical JSON: the archive, the **original seal**, the evidence
   version and its fingerprint, the reason code, the description's SHA-256, who added it and when)
   is written to `records` in COMPLIANCE mode until the archive's five-year floor. Its SHA-256 is
   the addition hash (`content_sha256`), fixed when the addition is created, and its key is
   content-addressed, so the row (insert-only) names it from the start.
2. The decision row (human-only by CHECK) under the `archive_addition` exception kind, and
   `archive.addition_logged` on the archive (AUD-25 d: "Addition logged").

The original seal (`archives.seal_sha256`, `archive_manifests` v1) is never touched.

**Verification.** `POST …/archive/verify` starts `SealVerifyWorkflow`; a monthly platform Schedule
sweeps every locked archive; a restore drill calls `seal_matches`. Each rebuilds the seal's leaves
from the database (`archive_lock.seal_leaves`, the lock's own collector) and compares their Merkle
root with the stored manifest's, and reads the COMPLIANCE manifest back by its digest. A mismatch
records `archive.seal_mismatch` and logs the RB-29 alarm event; a match records
`archive.seal_verified`. Metadata only: no leaf, value or document leaves the database in either.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from abacus.kernel import clock
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import PlatformSchedule, dispatch
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, names_of

AdditionReason = Literal[
    "au_c_585_omitted_procedure", "au_c_560_subsequently_discovered_fact", "other"
]
RECORD_CLASS: Final = "addition_manifest"
SWEEP_ID: Final = "seal_verify:platform"
_log = get_logger(__name__)
_mismatches = meter(__name__).create_counter(
    "abacus.archive.seal_mismatch", description="RB-29: a locked archive's seal no longer matches"
)


class ArchiveNotLocked(DomainConflict):
    """Additions and verification are for a locked archive."""

    code = "archive_not_locked"


class AdditionDecided(DomainConflict):
    code = "addition_already_decided"


class EvidenceNotFound(DomainInvalid):
    code = "evidence_version_invalid"


@dataclass(frozen=True)
class LockedArchive:
    id: UUID
    engagement_id: UUID
    work_item_id: UUID
    seal_sha256: str
    retention_until: date
    release_date: date


_LOCKED: Final = text(
    "SELECT id, engagement_id, work_item_id, seal_sha256, retention_until, release_date, status "
    "FROM archives WHERE work_item_id = :wi"
)


async def locked_archive(tenant: TenantContext, work_item_id: UUID) -> LockedArchive:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_LOCKED, {"wi": work_item_id})).first()
    if row is None:
        raise NotFound("archive")
    if row.status != "locked" or row.seal_sha256 is None:
        raise ArchiveNotLocked(facts={"status": str(row.status)})
    return LockedArchive(
        row.id, row.engagement_id, row.work_item_id, row.seal_sha256, row.retention_until,
        row.release_date,
    )  # fmt: skip


def _context(addition_id: UUID, field: str) -> str:
    """What a sealed field is bound to: its own addition, so it opens only as that addition's."""
    return f"archive_addition:{addition_id}:{field}"


def addition_manifest(
    *,
    addition_id: UUID,
    archive: LockedArchive,
    evidence_version_id: UUID,
    evidence_sha256: str,
    reason_code: str,
    description: str,
    added_by: UUID,
) -> bytes:
    """The appended manifest's canonical bytes (sorted keys, no spaces, UTF-8, no floats)."""
    body = {
        "addition_id": str(addition_id),
        "archive_id": str(archive.id),
        "engagement_id": str(archive.engagement_id),
        "work_item_id": str(archive.work_item_id),
        "original_seal_sha256": archive.seal_sha256,
        "evidence_version_id": str(evidence_version_id),
        "evidence_sha256": evidence_sha256,
        "reason_code": reason_code,
        "description_sha256": hashlib.sha256(description.encode()).hexdigest(),
        "added_by": str(added_by),
        "kind": RECORD_CLASS,
        "version": 1,
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


async def _evidence_sha(tenant: TenantContext, version_id: UUID) -> str:
    from abacus.modules.evidence.api import version_fingerprint

    found = await version_fingerprint(tenant, version_id)
    if found is None:
        raise EvidenceNotFound(facts={"field": "evidence_version_id"})
    return found


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden(action, "role")  # INV-1: never the agent, a system or a client


async def create_addition(
    ctx: AuthContext,
    work_item_id: UUID,
    *,
    description: str,
    reason_code: AdditionReason,
    evidence_version_id: UUID,
) -> UUID:
    """ "Add after lock…": pending until the EP decides. The route authorised
    `archive_addition.create` (manager or senior)."""
    from abacus.modules.evidence.api import record_key

    _person(ctx, "archive_addition.create")
    archive = await locked_archive(ctx.tenant, work_item_id)
    evidence_sha = await _evidence_sha(ctx.tenant, evidence_version_id)
    addition_id = uuid4()
    body = addition_manifest(
        addition_id=addition_id,
        archive=archive,
        evidence_version_id=evidence_version_id,
        evidence_sha256=evidence_sha,
        reason_code=reason_code,
        description=description,
        added_by=ctx.user_id,
    )
    digest = hashlib.sha256(body).hexdigest()
    sealed = await seal(ctx.tenant_id, description.encode(), _context(addition_id, "description"))
    async with uow(ctx.tenant) as tx:
        await tx.allow_archived_write("archive_addition")
        await tx.session.execute(
            text(
                "INSERT INTO archive_additions (id, tenant_id, engagement_id, work_item_id, "
                "archive_id, description_sealed, reason_code, evidence_version_id, "
                "content_sha256, added_by, addition_manifest_key) VALUES (:id, :t, :e, :wi, :a, "
                ":d, :reason, :ev, :sha, :by, :key)"
            ),
            {
                "id": addition_id,
                "t": ctx.tenant_id,
                "e": archive.engagement_id,
                "wi": work_item_id,
                "a": archive.id,
                "d": sealed,
                "reason": reason_code,
                "ev": evidence_version_id,
                "sha": digest,
                "by": ctx.user_id,
                "key": record_key(ctx.tenant_id, RECORD_CLASS, digest),
            },
        )
        tx.record(
            "archive_addition.created",
            target=Target("archive", archive.id),
            after=Ref(addition=addition_id, content=digest, evidence=evidence_version_id),
            scope=Scope(engagement_id=archive.engagement_id, work_item_id=work_item_id),
        )
    return addition_id


@dataclass(frozen=True)
class AdditionRow:
    id: UUID
    archive_id: UUID
    engagement_id: UUID
    work_item_id: UUID
    description: str
    reason_code: str
    evidence_version_id: UUID
    content_sha256: str
    added_by: UUID
    added_at: object
    decision: str | None
    decided_by: UUID | None
    decided_at: object


_ADDITIONS: Final = text(
    "SELECT a.id, a.archive_id, a.engagement_id, a.work_item_id, a.description_sealed, "
    "a.reason_code, a.evidence_version_id, a.content_sha256, a.added_by, a.created_at, "
    "d.decision, d.decided_by, d.created_at AS decided_at FROM archive_additions a "
    "LEFT JOIN archive_addition_decisions d ON d.addition_id = a.id "
    "WHERE a.work_item_id = :wi ORDER BY a.created_at, a.id"
)


async def additions_of(tenant: TenantContext, work_item_id: UUID) -> list[AdditionRow]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_ADDITIONS, {"wi": work_item_id})).all()
    out: list[AdditionRow] = []
    for r in rows:
        text_ = (
            await open_sealed(
                tenant.tenant_id, r.description_sealed, _context(r.id, "description")
            )
        ).decode()
        out.append(
            AdditionRow(
                r.id,
                r.archive_id,
                r.engagement_id,
                r.work_item_id,
                text_,
                r.reason_code,
                r.evidence_version_id,
                r.content_sha256,
                r.added_by,
                r.created_at,
                r.decision,
                r.decided_by,
                r.decided_at,
            )  # fmt: skip
        )
    return out


async def names_for(rows: list[AdditionRow]) -> dict[UUID, str]:
    people = {r.added_by for r in rows} | {r.decided_by for r in rows if r.decided_by}
    return await names_of(sorted(people, key=str)) if people else {}


async def _one(tenant: TenantContext, work_item_id: UUID, addition_id: UUID) -> AdditionRow:
    for row in await additions_of(tenant, work_item_id):
        if row.id == addition_id:
            return row
    raise NotFound("archive_addition")


async def decide_addition(
    ctx: AuthContext,
    work_item_id: UUID,
    addition_id: UUID,
    *,
    approve: bool,
    reason: str | None = None,
) -> AdditionRow:
    """The EP's decision (the route authorised `archive_addition.approve`, fresh MFA). An approval
    writes the addition manifest to `records` (COMPLIANCE) first, then the decision row; a
    rejection writes only the decision, with its reason sealed."""
    from abacus.modules.assurance.archive_seal import five_year_floor
    from abacus.modules.evidence.api import put_record

    _person(ctx, "archive_addition.approve")
    archive = await locked_archive(ctx.tenant, work_item_id)
    row = await _one(ctx.tenant, work_item_id, addition_id)
    if row.decision is not None:
        raise AdditionDecided(facts={"decision": row.decision})
    if row.added_by == ctx.user_id:
        raise Forbidden(
            "archive_addition.approve", "relationship"
        )  # never the person who added it
    if approve:
        body = await _manifest_bytes(ctx.tenant, archive, row)
        if hashlib.sha256(body).hexdigest() != row.content_sha256:
            raise AdditionDecided(facts={"decision": "content_changed"})
        until = five_year_floor(archive.release_date)
        await put_record(
            ctx.tenant_id, RECORD_CLASS, body, datetime.combine(until, time(23, 59), UTC)
        )
    reason_sealed = (
        await seal(ctx.tenant_id, reason.encode(), _context(addition_id, "reason"))
        if reason
        else None
    )
    async with uow(ctx.tenant) as tx:
        await tx.allow_archived_write("archive_addition")
        inserted = await tx.session.scalar(
            text(
                "INSERT INTO archive_addition_decisions (tenant_id, engagement_id, work_item_id, "
                "addition_id, decision, decided_by, reason_sealed, mfa_verified_at) VALUES "
                "(:t, :e, :wi, :add, :decision, :by, :reason, :mfa) "
                "ON CONFLICT (tenant_id, addition_id) DO NOTHING RETURNING id"
            ),
            {
                "t": ctx.tenant_id,
                "e": archive.engagement_id,
                "wi": work_item_id,
                "add": addition_id,
                "decision": "approved" if approve else "rejected",
                "by": ctx.user_id,
                "reason": reason_sealed,
                "mfa": ctx.mfa_at or clock.system_now(),
            },
        )
        if inserted is None:
            raise AdditionDecided(facts={"decision": "decided"})
        tx.record(
            "archive_addition.decided",
            target=Target("archive", archive.id),
            after=Ref(addition=addition_id, approved=1 if approve else 0),
            scope=Scope(engagement_id=archive.engagement_id, work_item_id=work_item_id),
        )
        if approve:
            tx.record(
                "archive.addition_logged",
                target=Target("archive", archive.id),
                after=Ref(addition=addition_id, content=row.content_sha256),
                scope=Scope(engagement_id=archive.engagement_id, work_item_id=work_item_id),
            )
    return await _one(ctx.tenant, work_item_id, addition_id)


async def _manifest_bytes(
    tenant: TenantContext, archive: LockedArchive, row: AdditionRow
) -> bytes:
    """The manifest's bytes, rebuilt from the row (a pure function of it): the same bytes the
    creation hashed, or the digest check refuses the approval."""
    evidence_sha = await _evidence_sha(tenant, row.evidence_version_id)
    return addition_manifest(
        addition_id=row.id,
        archive=archive,
        evidence_version_id=row.evidence_version_id,
        evidence_sha256=evidence_sha,
        reason_code=row.reason_code,
        description=row.description,
        added_by=row.added_by,
    )


# --- verification -------------------------------------------------------------------------------


@dataclass(frozen=True)
class VerifyResult:
    archive_id: str
    matched: bool
    reason: str | None = None  # seal_mismatch · manifest_missing


_MANIFEST: Final = text(
    "SELECT m.merkle_root, m.manifest_sha256 FROM archive_manifests m "
    "WHERE m.archive_id = :a ORDER BY m.manifest_version LIMIT 1"
)


async def seal_matches(tenant: TenantContext, archive_id: UUID) -> VerifyResult:
    """The restore-drill hook and the verify run's check: the leaves rebuilt from the database
    against the stored manifest's Merkle root, and the COMPLIANCE manifest read back."""
    from abacus.modules.assurance.archive_lock import seal_leaves
    from abacus.modules.assurance.archive_seal import merkle_root
    from abacus.modules.evidence.api import get_record

    async with tenant_session(tenant) as session:
        stored = (await session.execute(_MANIFEST, {"a": archive_id})).first()
        engagement = await session.scalar(
            text("SELECT engagement_id FROM archives WHERE id = :a"), {"a": archive_id}
        )
    if stored is None or engagement is None:
        return VerifyResult(str(archive_id), False, "manifest_missing")
    leaves = await seal_leaves(tenant, cast(UUID, engagement))
    if merkle_root(leaves) != stored.merkle_root:
        return VerifyResult(str(archive_id), False, "seal_mismatch")
    body = await get_record(tenant.tenant_id, "seal_manifest", stored.manifest_sha256)
    if body is None:
        return VerifyResult(str(archive_id), False, "manifest_missing")
    return VerifyResult(str(archive_id), True)


async def _record_result(tenant: TenantContext, archive_id: UUID, result: VerifyResult) -> None:
    async with tenant_session(tenant) as session:
        scope = (
            await session.execute(
                text("SELECT engagement_id, work_item_id FROM archives WHERE id = :a"),
                {"a": archive_id},
            )
        ).first()
    async with uow(tenant) as tx:
        if result.matched:
            tx.record(
                "archive.seal_verified",
                target=Target("archive", archive_id),
                scope=Scope(
                    engagement_id=scope.engagement_id if scope else None,
                    work_item_id=scope.work_item_id if scope else None,
                ),
            )
        else:
            tx.record(
                "archive.seal_mismatch",
                target=Target("archive", archive_id),
                scope=Scope(
                    engagement_id=scope.engagement_id if scope else None,
                    work_item_id=scope.work_item_id if scope else None,
                ),
            )
    if not result.matched:
        _mismatches.add(1, {"reason": result.reason or "seal_mismatch"})
        # RB-29: the integrity alarm reads this event (metadata only).
        _log.error(
            "archive.seal_mismatch",
            tenant_id=str(tenant.tenant_id),
            archive_id=str(archive_id),
            reason=result.reason,
        )


def _system(tenant_id: str, archive_id: str) -> TenantContext:
    return TenantContext(UUID(tenant_id), "system", f"seal-verify:{archive_id}")


@activity.defn(name="assurance.archive.verify_seal")
async def verify_seal_activity(tenant_id: str, archive_id: str) -> VerifyResult:
    tenant = _system(tenant_id, archive_id)
    result = await seal_matches(tenant, UUID(archive_id))
    await _record_result(tenant, UUID(archive_id), result)
    return result


@activity.defn(name="assurance.archive.verify_all")
async def verify_all_activity() -> int:
    """The monthly sweep: every locked archive of every firm; one failure never stops the rest."""
    from abacus.modules.identity.api import firm_tenant_ids

    checked = 0
    for tenant_id in await firm_tenant_ids():
        tenant = TenantContext(tenant_id, "system", "seal-verify:sweep")
        async with tenant_session(tenant) as session:
            archives = list(
                (
                    await session.scalars(text("SELECT id FROM archives WHERE status = 'locked'"))
                ).all()
            )
        for archive in archives:
            try:
                await verify_seal_activity(str(tenant_id), str(archive))
                checked += 1
            except Exception as exc:  # one firm's failure is logged; the sweep goes on
                _log.error(
                    "archive.seal_verify_failed",
                    tenant_id=str(tenant_id),
                    error=type(exc).__name__,
                )
    return checked


@dataclass(frozen=True)
class SealVerifyInput:
    tenant_id: str
    archive_id: str


_VERIFY_RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=10))


@workflow.defn(name="SealVerifyWorkflow")
class SealVerifyWorkflow:
    @workflow.run
    async def run(self, p: SealVerifyInput) -> bool:
        result = await workflow.execute_activity(
            "assurance.archive.verify_seal",
            args=[p.tenant_id, p.archive_id],
            result_type=VerifyResult,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=_VERIFY_RETRY,
        )
        return result.matched


@workflow.defn(name="SealVerifySweepWorkflow")
class SealVerifySweepWorkflow:
    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "assurance.archive.verify_all",
            result_type=int,
            start_to_close_timeout=timedelta(hours=2),
            retry_policy=_VERIFY_RETRY,
        )


async def start_verify(ctx: AuthContext, work_item_id: UUID) -> UUID:
    """`POST …/archive/verify` (the route authorised `archive.verify`): one run per request; the
    run id names the workflow (`seal_verify:<tenant>:<archive>:<run>`)."""
    archive = await locked_archive(ctx.tenant, work_item_id)
    run = uuid4()
    await dispatch(
        SealVerifyWorkflow,
        SealVerifyInput(str(ctx.tenant_id), str(archive.id)),
        id=f"seal_verify:{ctx.tenant_id}:{archive.id}:{run}",
    )
    return run


WORKFLOWS: Final[dict[type, str]] = {
    SealVerifyWorkflow: "batch",
    SealVerifySweepWorkflow: "batch",
}
ACTIVITIES: Final[tuple[object, ...]] = (verify_seal_activity, verify_all_activity)
SCHEDULES: Final[tuple[PlatformSchedule, ...]] = (
    PlatformSchedule(
        id=SWEEP_ID,
        workflow=SealVerifySweepWorkflow,
        every=timedelta(days=30),
        note="A-07-T42: verify every locked archive's seal monthly; a mismatch raises RB-29",
    ),
)

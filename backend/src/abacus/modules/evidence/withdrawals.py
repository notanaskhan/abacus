"""A client's withdrawal of an upload the firm never accepted (P-06-T19; ADR-162; DEC-298).

    view = await withdraw(ctx, engagement_id, version_id)      # void and hide at once
    wait = await erase_withdrawn(tenant_id, version_id)       # the purge's activity body

- **Who:** `evidence.withdraw` on the version's request item with its client facts: a client
  admin of the scope (any client principal's upload there), a contributor only for its own
  uploads (else 403 `not_your_upload`); every firm role, the agent and the system are denied by
  the matrix. Only a detached-key version a client uploaded is withdrawable (ADR-162 §8): any
  other answers 409 `evidence_not_withdrawable`.
- **Accepted means ever accepted:** an `accept` decision, even undone, or a retained key answers
  409 `evidence_accepted`. The withdrawal insert locks the key row first and the accept trigger
  takes the same lock, so a race is decided by whichever commits first (0144).
- **Void and hide, in one unit of work:** the `evidence_withdrawals` row (`erase_after` = the
  business clock + 30 days), the version's fulfilments voided by requests (an item it was the
  only fulfilment of goes back to `requested`), the audit event `evidence_version.withdrawn`
  (identifiers only: never the file name) and the outbox event that starts the purge. From that
  commit every evidence read leaves the version out (`repository.not_withdrawn`).
- **Purge** (`EvidenceWithdrawalPurge`, `withdrawal:<tenant>:<version>`): after the window, a
  legal hold on the version blocks the erase (`erase_blocked`, `legal_hold`), and so does a
  missing hold check (`no_hold_check`: fail closed); otherwise `evidence_key_destroy` crypto-
  erases the key and every object sealed under it, and `erased_at` is stamped. The ciphertext
  stays in the bucket, unreadable, until its Object Lock retention lapses.
"""

from __future__ import annotations

import math
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import DBAPIError
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel.clock import now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import DomainConflict, DomainForbidden, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.holds import HoldCheckMissing, held_versions
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Handler, OutboxEvent, Ref, Target, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.evidence.events import EvidenceVersionWithdrawn, EvidenceWithdrawalErased
from abacus.modules.evidence.models import (
    EvidenceItem,
    EvidenceObjectKey,
    EvidenceVersion,
    EvidenceWithdrawal,
    ReviewDecision,
)
from abacus.modules.evidence.repository import is_withdrawn
from abacus.modules.evidence.uploads import SOURCE, item_resource
from abacus.modules.evidence.workflow_types import WithdrawalPurgeInput
from abacus.modules.evidence.workflows import EvidenceWithdrawalPurge
from abacus.modules.identity.api import AuthContext, authorise, engagement_role_of
from abacus.modules.requests.api import items_of_version, read_item, withdraw_upload

_log = get_logger(__name__)

WINDOW: Final = timedelta(days=30)  # ADR-162 §4: erase after 30 days on the business clock
RETRY: Final = timedelta(days=1)  # §7: a blocked erase is tried again each day
PURGE_ACTOR: Final = "evidence.withdrawal_purge"  # bound in migration 0144's guards
ACTION: Final = "evidence.withdraw"
_ADMIN: Final = "client_admin"

WORKFLOWS: dict[type, WorkClass] = {EvidenceWithdrawalPurge: "batch"}
register_work_classes(WORKFLOWS)


class EvidenceAccepted(DomainConflict):
    """The firm accepted this version (ever): it is never withdrawn (ADR-162 §2)."""

    code = "evidence_accepted"


class EvidenceNotWithdrawable(DomainConflict):
    """Not a client's detached-key upload (a firm upload, or one stored before detached-key
    mode): nothing can erase it, so it is not withdrawn (ADR-162 §8)."""

    code = "evidence_not_withdrawable"


class NotYourUpload(DomainForbidden):
    """A contributor withdraws only its own uploads (ADR-162 §3)."""

    code = "not_your_upload"


@dataclass(frozen=True)
class WithdrawalView:
    evidence_version_id: UUID
    request_item_id: UUID | None
    withdrawn_at: datetime
    erase_after: datetime


def purge_workflow_id(tenant_id: UUID, version_id: UUID) -> str:
    return f"withdrawal:{tenant_id}:{version_id}"


@dataclass(frozen=True)
class _Target:
    version: EvidenceVersion
    uploader: str
    item_id: UUID | None
    withdrawal: EvidenceWithdrawal | None


async def _target(ctx: AuthContext, engagement_id: UUID, version_id: UUID) -> _Target:
    """The version (withdrawn or not), its uploader, its item and any withdrawal of it."""
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                select(EvidenceVersion, EvidenceItem.created_by_id)
                .join(EvidenceItem, EvidenceItem.id == EvidenceVersion.evidence_item_id)
                .where(
                    EvidenceVersion.id == version_id,
                    EvidenceVersion.engagement_id == engagement_id,
                )
            )
        ).one_or_none()
        withdrawal = (
            await session.execute(
                select(EvidenceWithdrawal).where(
                    EvidenceWithdrawal.evidence_version_id == version_id
                )
            )
        ).scalar_one_or_none()
    if row is None:
        raise NotFound("evidence_version")
    version, uploader = row[0], str(row[1])
    if withdrawal is not None:
        item_id = withdrawal.request_item_id
    else:
        items = await items_of_version(ctx.tenant, version_id)
        item_id = items[0].id if items else None
    return _Target(version, uploader, item_id, withdrawal)


async def check_withdraw(ctx: AuthContext, engagement_id: UUID, version_id: UUID) -> None:
    """`evidence.withdraw` on the version's item with its facts, before any replay is answered
    (ED-023's shape), and the contributor's own-upload rule (403 `not_your_upload`)."""
    target = await _target(ctx, engagement_id, version_id)
    if target.item_id is None:
        raise NotFound("evidence_version")  # a version no request holds was never a client's
    engagement = await get_ref(ctx, engagement_id)
    item = await read_item(ctx.tenant, engagement_id, target.item_id)
    await authorise(ctx, ACTION, item_resource(item, engagement.resource()))
    role = await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id)
    if role != _ADMIN and target.uploader != str(ctx.user_id):
        raise NotYourUpload


async def withdraw(ctx: AuthContext, engagement_id: UUID, version_id: UUID) -> WithdrawalView:
    """Void and hide the version at once (ADR-162 §4)."""
    await check_withdraw(ctx, engagement_id, version_id)
    target = await _target(ctx, engagement_id, version_id)
    if target.withdrawal is not None:
        raise NotFound("evidence_version")  # already withdrawn: as if it never arrived
    version, item_id = target.version, target.item_id
    if item_id is None:
        raise NotFound("evidence_version")
    if version.storage_mode != "detached_key" or version.source != SOURCE:
        raise EvidenceNotWithdrawable
    at = await now(ctx.tenant)
    erase_after = at + WINDOW
    try:
        async with uow(ctx.tenant) as tx:
            await lock_ref(tx, engagement_id)
            key = (
                await tx.session.execute(
                    select(EvidenceObjectKey)
                    .where(EvidenceObjectKey.evidence_version_id == version_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if key is None or key.destroyed_at is not None:
                raise EvidenceNotWithdrawable
            accepted = (
                await tx.session.execute(
                    select(ReviewDecision.id)
                    .where(
                        ReviewDecision.evidence_version_id == version_id,
                        ReviewDecision.decision == "accept",
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if key.retained_at is not None or accepted is not None:
                raise EvidenceAccepted
            await tx.session.execute(
                insert(EvidenceWithdrawal).values(
                    tenant_id=ctx.tenant_id,
                    evidence_version_id=version_id,
                    engagement_id=engagement_id,
                    request_item_id=item_id,
                    withdrawn_by_user_id=ctx.user_id,
                    withdrawn_at=at,
                    erase_after=erase_after,
                )
            )
            await withdraw_upload(tx, evidence_version_id=version_id, withdrawn_by=ctx.user_id)
            # Identifiers only: the Activity tab says the client withdrew an upload, never which.
            tx.record(
                "evidence_version.withdrawn",
                target=Target("evidence_version", version_id),
                after=Ref(request_item_id=item_id),
            )
            tx.emit(
                EvidenceVersionWithdrawn(
                    engagement_id=engagement_id,
                    evidence_version_id=version_id,
                    request_item_id=item_id,
                )
            )
    except DBAPIError as exc:  # the database decided a race with an accept (0144's guard)
        if "evidence_accepted" in str(exc.orig):
            raise EvidenceAccepted from None
        raise
    return WithdrawalView(version_id, item_id, at, erase_after)


# --- The purge (ADR-162 §7) ----------------------------------------------------------------------


def _purge(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", PURGE_ACTOR)


async def _block(tenant: TenantContext, version_id: UUID, at: datetime, reason: str) -> None:
    async with uow(tenant) as tx:
        await tx.session.execute(
            update(EvidenceWithdrawal)
            .where(EvidenceWithdrawal.evidence_version_id == version_id)
            .values(erase_blocked_at=at, block_reason=reason)
        )
        tx.record(
            "evidence_withdrawal.erase_blocked",
            target=Target("evidence_version", version_id),
            after=Ref(held=int(reason == "legal_hold")),
        )
    _log.info("evidence_withdrawal.erase_blocked", reason=reason)


async def erase_withdrawn(tenant_id: UUID, version_id: UUID) -> int:
    """One erase attempt: 0 when the key is destroyed (or there is nothing to do), else the
    seconds to wait before the next attempt. Repeat-safe."""
    tenant = _purge(tenant_id)
    async with tenant_session(tenant) as session:
        withdrawal = (
            await session.execute(
                select(EvidenceWithdrawal).where(
                    EvidenceWithdrawal.evidence_version_id == version_id
                )
            )
        ).scalar_one_or_none()
    if withdrawal is None or withdrawal.erased_at is not None:
        return 0
    at = await now(tenant)
    if at < withdrawal.erase_after:  # the business clock decides, not the timer (P-37)
        return max(1, math.ceil((withdrawal.erase_after - at).total_seconds()))
    try:
        held = await held_versions(tenant, [version_id])
    except HoldCheckMissing:
        await _block(tenant, version_id, at, "no_hold_check")  # fail closed (ADR-162 §7)
        return int(RETRY.total_seconds())
    if version_id in held:
        await _block(tenant, version_id, at, "legal_hold")
        return int(RETRY.total_seconds())
    async with uow(tenant) as tx:
        destroyed = (
            await tx.session.execute(
                text("SELECT evidence_key_destroy(:version)"), {"version": version_id}
            )
        ).scalar_one()
        await tx.session.execute(
            update(EvidenceWithdrawal)
            .where(EvidenceWithdrawal.evidence_version_id == version_id)
            .values(erased_at=at)
        )
        # The ciphertext stays under its Object Lock retention, unreadable (RB-13's wording).
        tx.record(
            "evidence_withdrawal.erased",
            target=Target("evidence_version", version_id),
            after=Ref(key_destroyed=int(bool(destroyed))),
        )
        tx.emit(
            EvidenceWithdrawalErased(
                engagement_id=withdrawal.engagement_id, evidence_version_id=version_id
            )
        )
    return 0


@activity.defn(name="evidence_withdrawal.erase")
async def erase_activity(given: WithdrawalPurgeInput) -> int:
    return await erase_withdrawn(UUID(given.tenant_id), UUID(given.evidence_version_id))


ACTIVITIES = (erase_activity,)


async def on_withdrawn(event: OutboxEvent) -> None:
    """`evidence_version.withdrawn` starts the purge, once per version (reuse rejected). The
    purge is never flagged off once a withdrawal exists: the flag gates the route only."""
    version_id = UUID(str(event.payload["evidence_version_id"]))
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            EvidenceWithdrawalPurge,
            WithdrawalPurgeInput(
                str(event.tenant_id), str(version_id), int(WINDOW.total_seconds())
            ),
            id=purge_workflow_id(event.tenant_id, version_id),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )


SUBSCRIPTIONS: dict[str, Handler] = {EvidenceVersionWithdrawn.event_type: on_withdrawn}


async def withdrawal_enabled(ctx: AuthContext) -> bool:
    from abacus.kernel._flags import EVIDENCE_WITHDRAWAL

    return await flag_enabled(ctx.tenant, EVIDENCE_WITHDRAWAL)


async def is_version_withdrawn(tenant: TenantContext, version_id: UUID) -> bool:
    """For agents and other modules' system runs: whether the client withdrew the version, so an
    in-flight run records nothing for it (ADR-162 §4)."""
    async with tenant_session(tenant) as session:
        return await is_withdrawn(session, version_id)

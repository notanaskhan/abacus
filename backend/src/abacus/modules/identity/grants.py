"""Approval grants (P-04-T10; ADR-126, ADR-161; DEC-24). PROTECTED.

A human decision whose effect leaves the firm (a client-visible notice, a send) is written at once,
and the effect waits on a grant. The grant names the approver, the action and the subject, and is
bound to the SHA-256 of the effect's payload. `consume_grant` is the single gate every dispatcher
calls: the outbox relay for held events, and later a Temporal effect hold. It refuses:
- before `not_before`;
- a second time (except a retry of the same effect);
- after a void (an Undo) or after `expires_at`;
- for a different payload;
- when the approver no longer holds the action.

`issue_grant` and `void_grant` run inside the caller's unit of work, with the decision they belong
to. `consume_grant` runs on its own, as the system. Times are business time (`abacus_now()`), the
clock the Undo window uses.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import MissingAuditEvent, Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.identity.authz import Resource, allowed_actions, authorise
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.service import member_context
from abacus.modules.identity.slots import engagement_resource

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_SUBJECT: Final = re.compile(r"[a-z][a-z_]{0,39}")
_log = get_logger(__name__)


class GrantNotYetDue(Exception):
    """Consumed before `not_before`: the dispatcher retries later (never a void)."""


_ISSUE = text(
    "INSERT INTO approval_grants (tenant_id, subject_type, subject_id, action, approver_user_id, "
    "engagement_id, work_item_id, payload_sha256, not_before, expires_at) VALUES (:tenant, "
    ":subject_type, :subject_id, :action, :approver, :engagement, :work_item, :digest, "
    ":not_before, :expires_at) RETURNING id"
)
_READ = text(
    "SELECT action, approver_user_id, engagement_id, work_item_id, payload_sha256, "
    "used_at, consumer_ref, voided_at, abacus_now() < not_before AS early, "
    "abacus_now() >= expires_at AS expired FROM approval_grants WHERE id = :id"
)
_CONSUME = text(
    "UPDATE approval_grants SET used_at = abacus_now(), consumer_ref = :consumer "
    "WHERE id = :id AND used_at IS NULL AND voided_at IS NULL AND payload_sha256 = :digest "
    "AND abacus_now() >= not_before AND abacus_now() < expires_at RETURNING id"
)
_VOID = text(
    "UPDATE approval_grants SET voided_at = abacus_now() "
    "WHERE id = :id AND used_at IS NULL AND voided_at IS NULL RETURNING id"
)


async def issue_grant(
    tx: UnitOfWork,
    ctx: AuthContext,
    *,
    action: str,
    resource: Resource,
    subject: Target,
    payload_sha256: str,
    not_before: datetime,
    expires_at: datetime,
) -> UUID:
    """A grant for the effect of `ctx`'s decision, issued in the decision's unit of work. The
    approver must hold `action` on `resource` now, by the same `authorise` the decision passed."""
    if ctx.is_support or ctx.tenant.actor_kind != "human":
        raise ValueError("only a person's own decision is granted")
    if not _SHA256.fullmatch(payload_sha256) or not _SUBJECT.fullmatch(subject.type):
        raise ValueError("a grant needs a payload SHA-256 and a subject type")
    if not_before.tzinfo is None or expires_at <= not_before:
        raise ValueError("a grant needs a time-zoned window that ends after it starts")
    await authorise(ctx, action, resource)
    grant_id = cast(
        UUID,
        (
            await tx.session.execute(
                _ISSUE,
                {
                    "tenant": ctx.tenant_id,
                    "subject_type": subject.type,
                    "subject_id": subject.id,
                    "action": action,
                    "approver": ctx.user_id,
                    "engagement": resource.engagement_id,
                    "work_item": resource.work_item_id,
                    "digest": payload_sha256,
                    "not_before": not_before,
                    "expires_at": expires_at,
                },
            )
        ).scalar_one(),
    )
    return grant_id


async def void_grant(tx: UnitOfWork, grant_id: UUID) -> bool:
    """An Undo: True if the grant was live and is now void, False if it was already used (the
    effect started; the caller answers `effect_started`) or already void. Audited when voided."""
    voided = (await tx.session.execute(_VOID, {"id": grant_id})).first() is not None
    if voided:
        tx.record("approval_grant.voided", target=Target("approval_grant", grant_id))
    return voided


async def _approver_still_holds(
    tenant: TenantContext, approver: UUID, action: str, engagement: UUID | None, item: UUID | None
) -> bool:
    """The approver is still an active member who may take `action` on the subject now, by every
    layer of `authorise` except fresh MFA, which they passed when they decided."""
    ctx = await member_context(tenant.tenant_id, approver)
    if ctx is None:
        return False
    try:
        resource = (
            await engagement_resource(tenant, engagement)
            if engagement is not None
            else Resource.firm(tenant.tenant_id)
        )
    except NotFound:
        return False
    if item is not None:
        resource = replace(resource, work_item_id=item)
    return action in await allowed_actions(ctx, resource, [action])


async def consume_grant(
    tenant_id: UUID, grant_id: UUID, consumer_ref: UUID, payload_sha256: str
) -> bool:
    """The single gate for a held effect: True to deliver it now, False never to (void, spent by
    another effect, expired, another payload, or the approver lost the action). Raises
    `GrantNotYetDue` before `not_before`, so the dispatcher retries rather than drops it."""
    system = TenantContext(tenant_id, "system", f"approval_grant:{grant_id}")
    async with tenant_session(system) as session:
        row = (await session.execute(_READ, {"id": grant_id})).first()
    if row is None:
        return False
    if row.used_at is not None:
        return row.consumer_ref == consumer_ref  # a retried delivery of the same effect
    if row.voided_at is not None or row.expired or row.payload_sha256 != payload_sha256:
        return False
    if row.early:
        raise GrantNotYetDue
    approver = cast(UUID, row.approver_user_id)
    if not await _approver_still_holds(
        system, approver, str(row.action), row.engagement_id, row.work_item_id
    ):
        _log.info("approval_grant.approver_lost_action", grant_id=grant_id)
        return False
    try:
        acting = TenantContext(tenant_id, "system", system.actor_id, on_behalf_of_user_id=approver)
        async with uow(acting) as tx:
            if (
                await tx.session.execute(
                    _CONSUME, {"id": grant_id, "consumer": consumer_ref, "digest": payload_sha256}
                )
            ).first() is not None:
                tx.record(
                    "approval_grant.consumed",
                    target=Target("approval_grant", grant_id),
                    after=Ref(consumer=consumer_ref),
                    scope=Scope(engagement_id=cast(UUID | None, row.engagement_id)),
                )
        return True
    except MissingAuditEvent:  # nothing was consumed, so nothing is recorded
        pass
    # Lost a race: another dispatcher consumed or voided it between the read and the update.
    async with tenant_session(system) as session:
        again = (await session.execute(_READ, {"id": grant_id})).first()
    return again is not None and again.consumer_ref == consumer_ref

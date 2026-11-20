"""Release, client approval, lock and reopen (C-02-T29; SPEC-701 F7 US-7.3, US-7.4; ADR-344 §8;
DEC-5820). PROTECTED (red-adjacent: a client deliverable leaves the firm here).

- **Release** (`close_package.release`: an engagement partner, a live human, a fresh MFA): in one
  sequence under the close's row lock, the preconditions are re-checked (409
  `release_preconditions_unmet` with the blockers), the partner's reviewer sign-off (P-04 L2 on
  the `close` reviewable, the package's content hash) moves the close to Approved, a single-use
  grant is issued and consumed for the final render (C11 without the watermark, approved through
  this module's provider), and the deliverable is marked released. `PackageAssemblyWorkflow`
  (mode `release`) waits for the final render, then publishes to Portal > Deliverables (C10, kind
  `close_package`, AR-C 70 legend), opens the `fs_package` approval item (C18) for the owner and
  the approver of record, sends the firm's "Deliverable ready" template row and moves the close to
  Delivered.
- **Client approval** (`fs_package` provider, C18): the owner's or the approver of record's
  decision in POR-08, as the client (never via Agent); the deliverable reads Approved by client
  and the releasing partner hears `package_client_approved`.
- **Lock** (`close.lock`, fresh MFA): 409 `client_approval_required` before the client approves;
  then the close is Locked (C-01's period lock reads it).
- **Reopen** (`close.reopen`, a partner, a reason): `close_reopenings` row, the close back to In
  review, `close.reopened` emitted (a hand-off from it is marked for supersession, F8).
"""

from __future__ import annotations

import contextvars
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Final, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel import clock
from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.closes import repository as repo
from abacus.modules.identity.api import AuthContext, Forbidden, authorise

if TYPE_CHECKING:
    from abacus.modules.engagements.api import (
        ApprovalItem,
        ClientDecision,
        ClientDecisionContext,
    )

ACTION: Final = "close_package.release"
MFA_WINDOW: Final = timedelta(minutes=10)
APPROVAL_KIND: Final = "fs_package"
GRANT_TTL: Final = timedelta(minutes=5)
DELIVERABLE_READY: Final = (
    "deliverable_ready"  # the firm's POR-20 row (communications template key)
)

_approving: contextvars.ContextVar[tuple[object, UUID] | None] = contextvars.ContextVar(
    "close_release_approving", default=None
)


class PreconditionsUnmet(DomainConflict):
    code = "release_preconditions_unmet"
    message = "The close is not ready to release."


class ClientApprovalRequired(DomainConflict):
    code = "client_approval_required"
    message = "The client has not approved the package yet."


class MfaRequired(DomainConflict):
    code = "mfa_required"
    message = "Confirm it's you to release."


class CloseReopened(DomainEvent):
    event_type: ClassVar[str] = "close.reopened"

    close_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]


class PackageClientApproved(DomainEvent):
    """C16 `package_client_approved` to the releasing partner."""

    event_type: ClassVar[str] = "close_deliverable.client_approved"

    close_id: Annotated[UUID, classified("internal")]
    recipient_user_ids: Annotated[list[UUID], classified("internal")]


async def _fresh(ctx: AuthContext) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(ACTION, "role")
    if ctx.mfa_at is None or await clock.now(ctx.tenant) - ctx.mfa_at > MFA_WINDOW:
        raise MfaRequired


async def release_approval(ref: object) -> tuple[UUID, str] | None:
    """C11's approval provider for `close_package`: the release this request is making, for the
    draft hash it names; None at any other time."""
    held = _approving.get()
    if held is None or held[0] != ref:
        return None
    return held[1], cast(str, cast(Any, ref).content_hash)  # Any: C11's approval request


@dataclass(frozen=True)
class Released:
    close_id: UUID
    document_id: UUID
    final_version_no: int
    run_id: UUID


async def release(ctx: AuthContext, close_id: UUID, *, seen_version: int) -> Released:
    from abacus.modules.agents.api import open_deterministic_run
    from abacus.modules.closes import package_render
    from abacus.modules.closes.package_service import get_package
    from abacus.modules.engagements.api import get_ref
    from abacus.modules.identity.api import consume_grant, issue_grant
    from abacus.modules.reporting import api as c11
    from abacus.modules.review.api import record_sign_off

    await _fresh(ctx)
    package = await get_package(ctx, close_id)
    async with tenant_session(ctx.tenant) as session:
        close = await repo.close_row(session, close_id)
    if close is None:
        raise NotFound("close")
    ref = await get_ref(ctx, close.engagement_id)
    await authorise(ctx, ACTION, ref.resource())
    blockers = [p.blocker for p in package.preconditions if not p.done]
    if blockers:
        raise PreconditionsUnmet(facts={"blockers": ",".join(blockers)})
    if package.version != seen_version:
        raise DomainConflict(facts={"reason": "stale_version"})
    document = await package_render.document_of(ctx.tenant, close_id)
    latest = None if document is None else await c11.latest_document_version(ctx.tenant, document)
    if document is None or latest is None:
        raise PreconditionsUnmet(facts={"blockers": "package_not_generated"})
    _, draft_hash = latest
    now = await clock.now(ctx.tenant)
    package_render.ensure_kind()
    async with uow(ctx.tenant) as tx:
        locked = await repo.close_row(tx.session, close_id, lock=True)
        if locked is None or locked.status in ("delivered", "locked"):
            raise DomainConflict(facts={"status": "" if locked is None else locked.status})
        await record_sign_off(
            tx, ctx, ref.resource(), close.engagement_id, "close", close_id, 2,
            package.content_hash,
        )  # fmt: skip
        if await repo.update_status(
            tx.session, close_id, status="approved", on_hold=False, reason=None,
            seen=locked.row_version,
        ) is None:  # fmt: skip
            raise DomainConflict(facts={"reason": "stale_close"})
        grant_id = await issue_grant(
            tx, ctx, action=ACTION, resource=ref.resource(), subject=Target("close", close_id),
            payload_sha256=draft_hash, not_before=now, expires_at=now + GRANT_TTL,
        )  # fmt: skip
        run_id = await open_deterministic_run(
            tx, tenant_id=ctx.tenant_id, agent_id=package_render.AGENT,
            engagement_id=close.engagement_id, initiator=ctx.user_id,
            task_scope=("close_package.read",),
        )  # fmt: skip
        await tx.session.execute(
            text(
                "UPDATE close_deliverables SET status = 'released', released_by = :u, "
                "released_at = clock_timestamp() WHERE close_id = :c AND released_at IS NULL"
            ),
            {"u": ctx.user_id, "c": close_id},
        )
        tx.record(
            "close_package.released",
            target=Target("close", close_id),
            after=Ref(document=document),
            scope=Scope(engagement_id=close.engagement_id, work_item_id=close_id),
        )
    if not await consume_grant(ctx.tenant_id, grant_id, close_id, draft_hash):
        raise DomainConflict(facts={"reason": "grant_refused"})
    approval = c11.ApprovalRef("close_release", grant_id, draft_hash)
    token = _approving.set((approval, ctx.user_id))
    try:
        async with uow(ctx.tenant) as tx:
            ticket = await c11.render_final(
                tx, document, approval, c11.Requester("human", user_id=ctx.user_id)
            )
    finally:
        _approving.reset(token)
    await package_render.start_assembly(
        ctx.tenant_id, close_id, run_id, document, ticket.version_no, mode="release"
    )
    return Released(close_id, document, ticket.version_no, run_id)


async def deliver(tenant_id: UUID, close_id: UUID, document_id: UUID, version_no: int) -> str:
    """The release workflow's last step, once the final render is filed: publish (C10), the C18
    item, the Deliverable ready email from the firm's row, Delivered."""
    from abacus.modules.closes.package_service import LEGENDS
    from abacus.modules.communications.api import RecipientRef, SendScope, send_templated
    from abacus.modules.engagements.api import (
        client_contact_names,
        engagement_contacts,
        engagement_hold_facts,
    )
    from abacus.modules.identity.api import firm_name, member_context
    from abacus.modules.reporting.api import (
        DeliverableAudience,
        DeliverableSpec,
        publish_deliverable,
        render_outcome,
    )

    system = TenantContext(tenant_id, "system", f"close_release:{close_id}")
    outcome = await render_outcome(system, document_id, version_no)
    if outcome.status in ("queued", "running"):
        raise RuntimeError("render_pending")
    if outcome.status != "succeeded" or outcome.evidence_version_id is None:
        return "failed"
    async with tenant_session(system) as session:
        close = await repo.close_row(session, close_id)
        row = (
            await session.execute(
                text(
                    "SELECT d.id, d.released_by, v.legend_key FROM close_deliverables d LEFT JOIN "
                    "close_deliverable_versions v ON v.deliverable_id = d.id AND v.version_no = "
                    "d.current_version_no WHERE d.close_id = :c"
                ),
                {"c": close_id},
            )
        ).first()
    if close is None or row is None or row.released_by is None:
        raise NotFound("close_deliverable")
    partner = await member_context(tenant_id, cast(UUID, row.released_by))
    facts = await engagement_hold_facts(system, close.engagement_id)
    if partner is None or facts is None:
        raise NotFound("release_partner")
    async with uow(partner.tenant) as tx:
        published = await publish_deliverable(
            tx,
            DeliverableSpec(
                client_id=facts.client_id,
                kind="close_package",
                title=f"Financial statements · {close.period}",
                source_module="closes",
                source_ref=f"close_deliverable:{row.id}",
                evidence_version_id=outcome.evidence_version_id,
                render_hash=outcome.render_hash or "",
                page_count=outcome.page_count or 1,
                audiences=[DeliverableAudience("work_item", close_id)],
                published_by_user_id=partner.user_id,
                client_entity_id=close.client_entity_id,
                engagement_id=close.engagement_id,
                work_item_id=close_id,
                generated_document_id=document_id,
                legend_kind="ar_c_70" if row.legend_key in LEGENDS else None,
                approval_kind=APPROVAL_KIND,
                approval_item_id=close_id,
            ),
        )
        await tx.session.execute(
            text(
                "UPDATE close_deliverables SET c10_deliverable_ref = :d, c18_approval_ref = :c "
                "WHERE id = :id"
            ),
            {"d": published.deliverable_id, "c": close_id, "id": row.id},
        )
        fresh = await repo.close_row(tx.session, close_id, lock=True)
        if fresh is not None and fresh.status == "approved":
            await repo.update_status(
                tx.session, close_id, status="delivered", on_hold=False, reason=None,
                seen=fresh.row_version,
            )  # fmt: skip
        tx.record("close.delivered", target=Target("close", close_id))
    firm = await firm_name(tenant_id)
    wanted = [
        c.contact_id
        for c in await engagement_contacts(partner, close.engagement_id)
        if c.designation in ("approver_of_record", "owner")
    ]
    names = await client_contact_names(partner.tenant, close.engagement_id, wanted)
    for contact in wanted:
        await send_templated(
            partner,
            DELIVERABLE_READY,
            RecipientRef("contact", contact),
            {
                "client_first_name": (names.get(contact) or "").split(" ")[0] or "there",
                "firm_name": firm,
                "deliverable_title": "Financial statements",
                "portal_link": "",
            },
            scope=SendScope(close.engagement_id),
            idempotency_key=f"close_release:{close_id}:{contact}",
        )
    return "delivered"


async def lock(ctx: AuthContext, close_id: UUID) -> str:
    from abacus.modules.engagements.api import get_ref

    await _fresh(ctx)
    async with tenant_session(ctx.tenant) as session:
        close = await repo.close_row(session, close_id)
        approved = await session.scalar(
            text("SELECT client_approved_at FROM close_deliverables WHERE close_id = :c"),
            {"c": close_id},
        )
    if close is None:
        raise NotFound("close")
    await authorise(ctx, "close.lock", (await get_ref(ctx, close.engagement_id)).resource())
    if approved is None:
        raise ClientApprovalRequired
    async with uow(ctx.tenant) as tx:
        locked = await repo.close_row(tx.session, close_id, lock=True)
        if locked is None or await repo.update_status(
            tx.session, close_id, status="locked", on_hold=False, reason=None,
            seen=locked.row_version,
        ) is None:  # fmt: skip
            raise DomainConflict(facts={"reason": "stale_close"})
        tx.record("close.locked", target=Target("close", close_id))
    return "locked"


async def reopen(ctx: AuthContext, close_id: UUID, reason: str) -> str:
    from abacus.modules.engagements.api import get_ref

    await _fresh(ctx)
    async with tenant_session(ctx.tenant) as session:
        close = await repo.close_row(session, close_id)
    if close is None:
        raise NotFound("close")
    await authorise(ctx, "close.reopen", (await get_ref(ctx, close.engagement_id)).resource())
    if close.status != "locked":
        raise DomainConflict(facts={"status": close.status})
    async with uow(ctx.tenant) as tx:
        locked = await repo.close_row(tx.session, close_id, lock=True)
        await tx.session.execute(
            text(
                "INSERT INTO close_reopenings (tenant_id, close_id, reopened_by, reason) "
                "VALUES (:t, :c, :u, :r)"
            ),
            {"t": ctx.tenant_id, "c": close_id, "u": ctx.user_id, "r": reason.strip()},
        )
        if locked is None or await repo.update_status(
            tx.session, close_id, status="in_review", on_hold=False, reason=None,
            seen=locked.row_version,
        ) is None:  # fmt: skip
            raise DomainConflict(facts={"reason": "stale_close"})
        tx.record("close.reopened", target=Target("close", close_id))
        tx.emit(CloseReopened(close_id=close_id, engagement_id=close.engagement_id))
    return "in_review"


async def state_of(tenant: TenantContext, close_id: UUID) -> tuple[str, int]:
    async with tenant_session(tenant) as session:
        close = await repo.close_row(session, close_id)
    if close is None:
        raise NotFound("close")
    return close.status, close.row_version


# --- C18's fs_package provider: the client's decision in POR-08 ---------------------------------


_PACKAGE_ITEM = text(
    "SELECT d.status, d.released_by, d.released_at, d.client_approved_at, "
    "v.content_hash FROM close_deliverables d JOIN close_deliverable_versions "
    "v ON v.deliverable_id = d.id AND v.version_no = d.current_version_no "
    "WHERE d.close_id = :c AND d.released_at IS NOT NULL"
)


async def _package_item(session: AsyncSession, item_id: UUID) -> ApprovalItem | None:
    """The released package as the portal approval reads it, in the caller's session (the
    provider's decide runs inside the unit of work, which has a session and no tenant)."""
    from abacus.modules.engagements.api import ApprovalItem

    row = (await session.execute(_PACKAGE_ITEM, {"c": item_id})).first()
    if row is None:
        return None
    return ApprovalItem(
        kind=APPROVAL_KIND, item_id=item_id, scope_kind="work_item", scope_id=item_id,
        sent_to_client=True, title="Financial statements",
        state="approved" if row.client_approved_at is not None else "waiting",
        seen_hash=str(row.content_hash), legend="No assurance is provided.",
        released_by_user_id=row.released_by, released_at=row.released_at,
        decided_at=row.client_approved_at,
    )  # fmt: skip


class FsPackageApprovals:
    """C18 kind `fs_package` for a released close package (owner or approver of record decides;
    an attest client's also needs the SKE designee, DeciderRule)."""

    async def items(self, tenant: TenantContext, scope_id: UUID) -> Sequence[object]:
        found = await self.item(tenant, scope_id)
        return [] if found is None else [found]

    async def item(self, tenant: TenantContext, item_id: UUID) -> ApprovalItem | None:
        async with tenant_session(tenant) as session:
            return await _package_item(session, item_id)

    async def decide(
        self,
        tx: UnitOfWork,
        item_id: UUID,
        decision: ClientDecision,
        context: ClientDecisionContext,
    ) -> ApprovalItem:
        from abacus.modules.engagements.api import ItemChanged

        current = await _package_item(tx.session, item_id)
        if current is None:
            raise NotFound("close_package")
        if decision.seen_hash != current.seen_hash:
            raise ItemChanged
        contact = context.contact_id
        released_by = await tx.session.scalar(
            text(
                "UPDATE close_deliverables SET status = 'approved_by_client', "
                "client_approved_by_contact_id = :k, client_approved_at = clock_timestamp() WHERE "
                "close_id = :c AND client_approved_at IS NULL RETURNING released_by"
            ),
            {"k": contact, "c": item_id},
        )
        tx.record("close_package.client_approved", target=Target("close", item_id))
        if released_by is not None:
            tx.emit(
                PackageClientApproved(
                    close_id=item_id, recipient_user_ids=[cast(UUID, released_by)]
                )
            )
        return await _package_item(tx.session, item_id) or current

    async def facts(self, tenant: TenantContext, item_id: UUID) -> object:
        from abacus.modules.engagements.api import ApprovalFacts, attest_of

        async with tenant_session(tenant) as session:
            close = await repo.close_row(session, item_id)
        if close is None:
            raise NotFound("close")
        return ApprovalFacts(await attest_of(tenant, close.engagement_id) is True, item_id)


PROVIDER: Final = FsPackageApprovals()


def register() -> None:
    from abacus.modules.engagements.api import register_client_approval_kind

    register_client_approval_kind(APPROVAL_KIND, PROVIDER)  # type: ignore[arg-type] -- C18 provider


__all__ = [
    "ClientApprovalRequired",
    "FsPackageApprovals",
    "PreconditionsUnmet",
    "deliver",
    "lock",
    "register",
    "release",
    "release_approval",
    "reopen",
    "state_of",
]

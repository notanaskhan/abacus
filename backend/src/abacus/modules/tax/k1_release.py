"""The K-1 release gate and `K1ReleaseWorkflow`'s activities (T-02-T21; T-02 §3.6, §4.9, §4.11;
DEC-24, DEC-34, DEC-53, DEC-78, DEC-79, DEC-88; DEC-1476). RED: what reaches recipients.

The only file that writes `k1_releases` (K1RELEASE-001).

- **Eligibility** (`eligibility`): T-02-T20's release check (final approval recorded, a final set
  imported, something to release) plus the firm's release condition, BH-TAX-02: its signer is
  named for the client (the condition is "after final approval", the policy's only export
  condition; OQ-1 decided so in DEC-1476), and every package to release has a contact to deliver
  to (`recipient_contact_missing`). Codes, never prose.
- **Release** (`request_release`, `k1_package.release`: manager or partner, fresh second factor,
  a person; agent, system and policy principals are refused before anything): the packages must
  be the release check's ready ones at the version the person saw, and the "Deliverable ready"
  template the firm's version in use. One unit of work writes the `k1_releases` row (the
  database accepts it only from the session's own person), a single-use approval grant bound to
  the release's payload with `not_before` = now + 10 s, the per-package ledger rows, the audit
  row and the event that starts the workflow. Nothing leaves the firm yet.
- **Undo** (`undo`): the requester, before `not_before`: the grant is voided and the release
  `undone`; no grant, invitation, email or portal change follows. Later, 409
  `undo_window_closed`; once the workflow consumed the grant, 409 `effect_started`.
- **The workflow's activities**: `start` consumes the grant (an Undo or a refusal ends the run);
  `deliver` is idempotent per package through `k1_release_deliveries`, one stamped step at a
  time: the contact; the `k1_recipient` grant on the package (or a pending grant and its
  invitation, `identity.api.grant_k1_recipient`); `released` (the database lets a package move
  only while a release naming it runs); the "Deliverable ready" email from the database template
  (`send_templated`, no amounts; its message id is derived from the release and package, so a
  replay answers what the first send recorded and sends nothing again); and the hand-off drafts
  on other returns replaced by the final, its K-1 box values copied (DEC-88). Then `complete`.
- **Resend** (`schedule_k_package.resend_requested`, T-02-T20): the corrected contact gets the
  grant or invitation and a new "Deliverable ready" email, keyed by the request.

Human only (INV-1) at five layers: the matrix (agent and system deny), the live-person check
here, the database (`k1_releases_guard`), the human-only audit register
(`schedule_k_release.requested`, `.undone`, 0566) and the grant itself. Box values are TRI and
never logged or carried in an error's facts.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated, ClassVar, Final, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import ApplicationError, WorkflowAlreadyStartedError

from abacus.kernel import clock
from abacus.kernel.classification import classified
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, uow
from abacus.kernel.uow.idempotency import idempotent
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.communications.api import (
    RecipientRef,
    SendScope,
    send_templated,
    template_version_in_use,
)
from abacus.modules.evidence.api import file_handoff_copy
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    GrantNotYetDue,
    K1Access,
    consume_grant,
    firm_name,
    grant_k1_recipient,
    issue_grant,
    member_context,
    void_grant,
)
from abacus.modules.organisations.api import contact_facts, signer_contacts
from abacus.modules.requests.api import fulfil_by_rule, k1_request_for
from abacus.modules.tax import k1_packages as k1
from abacus.modules.tax.approval import signer_for
from abacus.modules.tax.k1_release_workflow import (
    K1DeliveryInput,
    K1ReleaseFailure,
    K1ReleaseInput,
    K1ReleaseWorkflow,
    workflow_id,
)

ACTION: Final = "k1_package.release"
SUBJECT: Final = "schedule_k_release"  # the grant's subject (digit-free, as the audit's)
KIND: Final = "tax_return"
TEMPLATE_KEY: Final = "deliverable_ready"
UNDO_WINDOW: Final = timedelta(seconds=10)
GRANT_LIFETIME: Final = timedelta(days=1)
_FINAL_VALUES_BYTES: Final = 4096

WORKFLOWS: dict[type, WorkClass] = {K1ReleaseWorkflow: "time_sensitive"}
register_work_classes(WORKFLOWS)


class K1ReleaseIneligible(DomainConflict):
    """The release check fails, or the packages asked are not its ready ones (`facts.failing`)."""

    code = "k1_release_ineligible"


class K1ReleaseStale(DomainConflict):
    """A newer K-1 set or "Deliverable ready" version arrived since the person looked."""

    code = "stale_version"


class K1UndoClosed(DomainConflict):
    """Undo is possible for 10 seconds after the release, by the person who released."""

    code = "undo_window_closed"


class K1EffectStarted(DomainConflict):
    """The release has started (its grant was consumed): it can no longer be undone."""

    code = "effect_started"


class K1ReleaseRequested(DomainEvent):
    """A person released K-1s; the workflow waits out the Undo window, then delivers."""

    event_type: ClassVar[str] = "schedule_k_release.requested"

    release_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    packages: Annotated[int, classified("internal")]


class K1ReleaseUndone(DomainEvent):
    event_type: ClassVar[str] = "schedule_k_release.undone"

    release_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class ReleaseView:
    id: UUID
    status: str
    not_before: datetime


def _person(ctx: AuthContext) -> None:
    # DEC-53: the policy principal never releases; agents and the system never do (ADR-005).
    if ctx.client or ctx.is_support or ctx.tenant.actor_kind != "human":
        raise Forbidden(ACTION, "role")


# --- eligibility -------------------------------------------------------------------------------


async def _contacts(tenant: TenantContext, package_ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """Each package's delivery contact: the one a person named, else the recipient's."""
    if not package_ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT p.id, coalesce(p.delivery_contact_id, r.contact_id) AS contact "
                    "FROM k1_packages p JOIN k1_recipients r ON r.id = p.recipient_id "
                    "WHERE p.id = ANY(:ids)"
                ),
                {"ids": list(package_ids)},
            )
        ).all()
    return {r.id: r.contact for r in rows if r.contact is not None}


async def eligibility(ctx: AuthContext, return_id: UUID) -> k1.ReleaseCheck:
    """T-02-T20's codes plus BH-TAX-02's release condition and a contact for every package
    (`no_release_policy`, `recipient_contact_missing`)."""
    found = await k1.release_check(ctx, return_id)
    issuer = await k1.issuer_for(ctx, return_id, k1.READ)
    failing = list(found.failing)
    if await signer_for(ctx.tenant_id, issuer.client_id) is None:
        failing.append("no_release_policy")
    contacts = await _contacts(ctx.tenant, found.package_ids)
    if any(p not in contacts for p in found.package_ids):
        failing.append("recipient_contact_missing")
    return k1.ReleaseCheck(not failing, tuple(failing), found.package_ids)


async def template_in_use(ctx: AuthContext) -> UUID | None:
    """T-02-T25: the "Deliverable ready" version a release names (the confirm's letter)."""
    return await template_version_in_use(ctx.tenant, TEMPLATE_KEY)


# --- release and undo ----------------------------------------------------------------------------


def grant_digest(
    release_id: UUID, return_id: UUID, package_ids: Sequence[UUID], template_version_id: UUID
) -> str:
    payload = {
        "release": str(release_id),
        "return": str(return_id),
        "packages": sorted(str(p) for p in package_ids),
        "template": str(template_version_id),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


async def request_release(
    ctx: AuthContext,
    return_id: UUID,
    package_ids: Sequence[UUID],
    email_template_version_id: UUID,
    seen_version: int,
    idempotency_key: str | None,
) -> ReleaseView:
    """`POST /v1/tax-returns/{id}/k1-packages:release` (202): the release waits out its window."""
    _person(ctx)
    issuer = await k1.issuer_for(ctx, return_id, ACTION)
    if ctx.mfa_at is None:  # authorise demanded a fresh factor; the row records when
        raise Forbidden(ACTION, "condition")
    asked = tuple(dict.fromkeys(package_ids))

    async def run() -> tuple[int, dict[str, object]]:
        check = await eligibility(ctx, return_id)
        if not check.eligible:
            raise K1ReleaseIneligible(facts={"failing": ",".join(check.failing)})
        if not asked or any(p not in check.package_ids for p in asked):
            raise K1ReleaseIneligible(facts={"failing": "packages_not_ready"})
        async with tenant_session(ctx.tenant) as session:
            newest = await session.scalar(
                text("SELECT max(version_no) FROM k1_packages WHERE id = ANY(:ids)"),
                {"ids": list(asked)},
            )
        if newest is None or int(newest) > seen_version:
            raise K1ReleaseStale(facts={"seen_version": seen_version})
        if await template_version_in_use(ctx.tenant, TEMPLATE_KEY) != email_template_version_id:
            raise K1ReleaseStale(facts={"template": TEMPLATE_KEY})
        release_id = await _write(ctx, issuer, asked, email_template_version_id)
        return 202, {"release_id": str(release_id)}

    stored = await idempotent(
        ctx.tenant,
        route="schedule_k_release.create",
        key=idempotency_key,
        body={
            "return": str(return_id),
            "packages": sorted(str(p) for p in asked),
            "template": str(email_template_version_id),
            "seen_version": seen_version,
        },
        run=run,
    )
    return await read(ctx, UUID(str(stored.body["release_id"])))


async def _write(
    ctx: AuthContext,
    issuer: k1.Issuer,
    package_ids: Sequence[UUID],
    template_version_id: UUID,
) -> UUID:
    release_id = uuid4()
    not_before = await clock.now(ctx.tenant) + UNDO_WINDOW
    scope = Scope(engagement_id=issuer.engagement_id, work_item_id=issuer.return_id)
    async with uow(ctx.tenant) as tx:
        grant = await issue_grant(
            tx,
            ctx,
            action=ACTION,
            resource=issuer.resource,
            subject=Target(SUBJECT, release_id),
            payload_sha256=grant_digest(
                release_id, issuer.return_id, package_ids, template_version_id
            ),
            not_before=not_before,
            expires_at=not_before + GRANT_LIFETIME,
        )
        await tx.session.execute(
            text(
                "INSERT INTO k1_releases (id, tenant_id, engagement_id, work_item_id, "
                "package_ids, grant_id, not_before, requested_by, mfa_at, "
                "email_template_version_id) VALUES (:id, :t, :e, :w, :p, :g, :nb, :by, :mfa, "
                ":tv)"
            ),
            {
                "id": release_id,
                "t": ctx.tenant_id,
                "e": issuer.engagement_id,
                "w": issuer.return_id,
                "p": list(package_ids),
                "g": grant,
                "nb": not_before,
                "by": ctx.user_id,
                "mfa": ctx.mfa_at,
                "tv": template_version_id,
            },
        )
        for package_id in package_ids:
            await tx.session.execute(
                text(
                    "INSERT INTO k1_release_deliveries (tenant_id, release_id, package_id) "
                    "VALUES (:t, :r, :p)"
                ),
                {"t": ctx.tenant_id, "r": release_id, "p": package_id},
            )
        tx.record(
            "schedule_k_release.requested",
            target=Target(KIND, issuer.return_id),
            after=Ref(release=release_id, grant=grant, packages=len(package_ids)),
            scope=scope,
        )
        tx.emit(
            K1ReleaseRequested(
                release_id=release_id, work_item_id=issuer.return_id, packages=len(package_ids)
            )
        )
    return release_id


@dataclass(frozen=True)
class _Release:
    id: UUID
    work_item_id: UUID
    engagement_id: UUID
    package_ids: tuple[UUID, ...]
    grant_id: UUID
    not_before: datetime
    status: str
    requested_by: UUID
    email_template_version_id: UUID


_RELEASE = text(
    "SELECT id, work_item_id, engagement_id, package_ids, grant_id, not_before, status, "
    "requested_by, email_template_version_id FROM k1_releases WHERE id = :id"
)


async def _release_row(tenant: TenantContext, release_id: UUID) -> _Release | None:
    async with tenant_session(tenant) as session:
        r = (await session.execute(_RELEASE, {"id": release_id})).first()
    if r is None:
        return None
    return _Release(
        r.id,
        r.work_item_id,
        r.engagement_id,
        tuple(r.package_ids),
        r.grant_id,
        r.not_before,
        r.status,
        r.requested_by,
        r.email_template_version_id,
    )


async def read(ctx: AuthContext, release_id: UUID) -> ReleaseView:
    if ctx.client:
        raise NotFound(SUBJECT)
    row = await _release_row(ctx.tenant, release_id)
    if row is None:
        raise NotFound(SUBJECT)
    await k1.issuer_for(ctx, row.work_item_id, k1.READ)
    return ReleaseView(release_id, row.status, row.not_before)


async def undo(ctx: AuthContext, release_id: UUID) -> ReleaseView:
    """Inside the window, by the requester: the grant voided, the release `undone`."""
    _person(ctx)
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                text("SELECT * FROM k1_releases WHERE id = :id FOR UPDATE"), {"id": release_id}
            )
        ).first()
        if row is None:
            raise NotFound(SUBJECT)
        issuer = await k1.issuer_for(ctx, row.work_item_id, ACTION)
        at = await clock.now(ctx.tenant)
        if row.status != "pending" or row.requested_by != ctx.user_id or at >= row.not_before:
            raise K1UndoClosed
        if not await void_grant(tx, row.grant_id):
            raise K1EffectStarted
        try:
            await tx.session.execute(
                text(
                    "UPDATE k1_releases SET status = 'undone', undone_at = :at, undone_by = :by "
                    "WHERE id = :id"
                ),
                {"at": at, "by": ctx.user_id, "id": release_id},
            )
        except DBAPIError as exc:  # the guard's own window check, on the database's clock
            if "undo_window_closed" in str(exc.orig):
                raise K1UndoClosed from None
            raise
        tx.record(
            "schedule_k_release.undone",
            target=Target(KIND, issuer.return_id),
            after=Ref(release=release_id, grant=row.grant_id),
            scope=Scope(engagement_id=issuer.engagement_id, work_item_id=issuer.return_id),
        )
        tx.emit(K1ReleaseUndone(release_id=release_id, work_item_id=issuer.return_id))
    return await read(ctx, release_id)


# --- the workflow's start ------------------------------------------------------------------------


def _system(tenant_id: UUID, release_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", f"k1_release:{release_id}")


async def on_requested(event: OutboxEvent) -> None:
    """`schedule_k_release.requested` starts the release's workflow once (reuse rejected)."""
    release_id = UUID(str(event.payload["release_id"]))
    system = _system(event.tenant_id, release_id)
    row = await _release_row(system, release_id)
    if row is None or row.status != "pending":
        return  # undone already, or not this tenant's
    left = (row.not_before - await clock.now(system)).total_seconds()
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            K1ReleaseWorkflow,
            K1ReleaseInput(str(event.tenant_id), str(release_id), max(0, math.ceil(left))),
            id=workflow_id(str(event.tenant_id), str(row.work_item_id), str(release_id)),
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )


async def start(tenant_id: UUID, release_id: UUID) -> str:
    """`running` once the grant is consumed; `undone` when an Undo voided it; `failed` when it
    was refused (expired, or the person no longer holds the action). Raises `GrantNotYetDue`."""
    system = _system(tenant_id, release_id)
    row = await _release_row(system, release_id)
    if row is None:
        raise ApplicationError("release_missing", type="DeliveryRefused", non_retryable=True)
    if row.status != "pending":
        return row.status
    digest = grant_digest(
        release_id, row.work_item_id, row.package_ids, row.email_template_version_id
    )
    if not await consume_grant(tenant_id, row.grant_id, release_id, digest):
        again = await _release_row(system, release_id)
        if again is not None and again.status == "pending":
            return await fail(tenant_id, release_id, "grant_refused")
        return "failed" if again is None else again.status
    async with uow(system) as tx:
        moved = (
            await tx.session.execute(
                text(
                    "UPDATE k1_releases SET status = 'running', started_at = :at "
                    "WHERE id = :id AND status = 'pending' RETURNING work_item_id"
                ),
                {"at": await clock.now(system), "id": release_id},
            )
        ).first()
        if moved is not None:
            tx.record(
                "schedule_k_release.started",
                target=Target(KIND, moved.work_item_id),
                after=Ref(release=release_id),
            )
    return "running"


async def packages(tenant_id: UUID, release_id: UUID) -> list[str]:
    row = await _release_row(_system(tenant_id, release_id), release_id)
    return [] if row is None else [str(p) for p in row.package_ids]


async def _finish(tenant_id: UUID, release_id: UUID, status: str, code: str | None) -> str:
    system = _system(tenant_id, release_id)
    async with uow(system) as tx:
        moved = (
            await tx.session.execute(
                text(
                    "UPDATE k1_releases SET status = :s, completed_at = :at, failure_code = :c "
                    "WHERE id = :id AND status IN ('pending', 'running') RETURNING work_item_id"
                ),
                {"s": status, "at": await clock.now(system), "c": code, "id": release_id},
            )
        ).first()
        if moved is not None:
            tx.record(
                f"schedule_k_release.{status}",
                target=Target(KIND, moved.work_item_id),
                after=Ref(release=release_id),  # the failure code is on the row
            )
    return status


async def complete(tenant_id: UUID, release_id: UUID) -> str:
    return await _finish(tenant_id, release_id, "completed", None)


async def fail(tenant_id: UUID, release_id: UUID, code: str) -> str:
    return await _finish(tenant_id, release_id, "failed", code)


# --- one recipient's delivery --------------------------------------------------------------------


@dataclass(frozen=True)
class _Delivery:
    tenant_id: UUID
    release_id: UUID
    package_id: UUID
    return_id: UUID
    engagement_id: UUID
    requested_by: UUID
    recipient_id: UUID
    contact_id: UUID | None
    access_done: bool
    released_at: datetime | None
    emailed_at: datetime | None
    handoffs_at: datetime | None


async def _delivery(system: TenantContext, release_id: UUID, package_id: UUID) -> _Delivery:
    async with tenant_session(system) as session:
        row = (
            await session.execute(
                text(
                    "SELECT r.status, r.work_item_id, r.engagement_id, r.requested_by, "
                    "p.recipient_id, d.contact_id, d.access_at, "
                    "d.released_at, d.emailed_at, d.handoffs_at FROM k1_release_deliveries d "
                    "JOIN k1_releases r ON r.id = d.release_id "
                    "JOIN k1_packages p ON p.id = d.package_id "
                    "WHERE d.release_id = :r AND d.package_id = :p"
                ),
                {"r": release_id, "p": package_id},
            )
        ).first()
    if row is None or row.status != "running":
        raise ApplicationError("not_running", type="DeliveryRefused", non_retryable=True)
    return _Delivery(
        system.tenant_id,
        release_id,
        package_id,
        row.work_item_id,
        row.engagement_id,
        row.requested_by,
        row.recipient_id,
        row.contact_id,
        row.access_at is not None,
        row.released_at,
        row.emailed_at,
        row.handoffs_at,
    )


async def _acting(d: _Delivery) -> AuthContext:
    """The person who released, as they are now: their consumed grant is the authority."""
    ctx = await member_context(d.tenant_id, d.requested_by)
    if ctx is None:
        raise ApplicationError("releaser_gone", type="DeliveryRefused", non_retryable=True)
    return ctx


async def _contact_step(system: TenantContext, d: _Delivery) -> UUID:
    if d.contact_id is not None:
        return d.contact_id
    contact = (await _contacts(system, [d.package_id])).get(d.package_id)
    if contact is None:
        raise ApplicationError("contact_missing", type="DeliveryRefused", non_retryable=True)
    async with uow(system) as tx:
        await tx.session.execute(
            text("UPDATE k1_recipients SET contact_id = :c WHERE id = :r AND contact_id IS NULL"),
            {"c": contact, "r": d.recipient_id},
        )
        await tx.session.execute(
            text(
                "UPDATE k1_release_deliveries SET contact_id = :c "
                "WHERE release_id = :release AND package_id = :package"
            ),
            {"c": contact, "release": d.release_id, "package": d.package_id},
        )
        tx.record(
            "schedule_k_release.contact_resolved",
            target=Target(KIND, d.return_id),
            after=Ref(release=d.release_id, package=d.package_id, contact_id=contact),
        )
    return contact


async def _access_step(
    system: TenantContext, d: _Delivery, contact: UUID, client_id: UUID
) -> None:
    if d.access_done:
        return
    await _access_for(
        system,
        return_id=d.return_id,
        engagement_id=d.engagement_id,
        client_id=client_id,
        contact=contact,
        package_id=d.package_id,
        granted_by=d.requested_by,
        release_id=d.release_id,
    )


async def _released_step(system: TenantContext, d: _Delivery) -> None:
    if d.released_at is not None:
        return
    at = await clock.now(system)
    async with uow(system) as tx:
        await tx.session.execute(
            text(
                "UPDATE k1_packages SET status = 'released', released_at = :at "
                "WHERE id = :p AND status = 'draft'"
            ),
            {"at": at, "p": d.package_id},
        )
        await k1.record_event(
            tx, d.tenant_id, d.package_id, "released", None, {"release": d.release_id}
        )
        await tx.session.execute(
            text(
                "UPDATE k1_release_deliveries SET released_at = :at "
                "WHERE release_id = :release AND package_id = :package"
            ),
            {"at": at, "release": d.release_id, "package": d.package_id},
        )
        tx.record(
            "schedule_k_package.released",
            target=Target(KIND, d.return_id),
            after=Ref(release=d.release_id, package=d.package_id),
        )


async def _variables(tenant_id: UUID, first_name: str) -> dict[str, str]:
    """The "Deliverable ready" values: names and the portal's home, never an amount."""
    return {
        "client_first_name": first_name,
        "firm_name": await firm_name(tenant_id),
        "deliverable_title": "Schedule K-1",
        "portal_link": f"{settings().app_base_url.rstrip('/')}/portal",
    }


async def _email_step(system: TenantContext, d: _Delivery, contact: UUID, key: str) -> None:
    if d.emailed_at is not None:
        return
    ctx = await _acting(d)
    async with tenant_session(system) as session:
        person = (await contact_facts(session, [contact])).get(contact)
    if person is None:
        raise ApplicationError("contact_missing", type="DeliveryRefused", non_retryable=True)
    recipient = (
        RecipientRef("user", person.user_id)
        if person.user_id is not None
        else RecipientRef("contact", contact)
    )
    sent = await send_templated(
        ctx,
        TEMPLATE_KEY,
        recipient,
        await _variables(d.tenant_id, person.display_name.split(" ")[0] or "there"),
        scope=SendScope(engagement_id=d.engagement_id),
        idempotency_key=key,
    )
    async with uow(system) as tx:
        await tx.session.execute(
            text(
                "UPDATE k1_release_deliveries SET message_id = :m, emailed_at = :at "
                "WHERE release_id = :release AND package_id = :package"
            ),
            {
                "m": sent.message_id,
                "at": await clock.now(system),
                "release": d.release_id,
                "package": d.package_id,
            },
        )
        tx.record(
            "schedule_k_package.deliverable_emailed",
            target=Target(KIND, d.return_id),
            after=Ref(release=d.release_id, package=d.package_id, message=sent.message_id),
        )


async def _final_values(system: TenantContext, package_id: UUID) -> str:
    """The final K-1's box values, copied to the hand-off (DEC-88), within the column's cap."""
    async with tenant_session(system) as session:
        lines = (
            await session.execute(
                text(
                    "SELECT box_code, amount FROM k1_box_lines WHERE package_id = :p "
                    "AND document_kind = 'k1' ORDER BY position"
                ),
                {"p": package_id},
            )
        ).all()
    values: dict[str, str] = {}
    for code, amount in lines:
        values[str(code)] = str(amount)
        if len(json.dumps(values, sort_keys=True)) > _FINAL_VALUES_BYTES:
            values.pop(str(code))
            break
    return json.dumps(values, sort_keys=True)


async def _handoffs_step(system: TenantContext, d: _Delivery, issuer_name: str) -> None:
    """Every draft this recipient's K-1 was shared as is replaced by the final (DEC-88)."""
    if d.handoffs_at is not None:
        return
    ctx = await _acting(d)
    async with tenant_session(system) as session:
        drafts = (
            await session.execute(
                text(
                    "SELECT h.id, h.target_work_item_id FROM k1_handoffs h JOIN k1_packages p "
                    "ON p.id = h.package_id WHERE p.recipient_id = :r AND p.work_item_id = :w "
                    "AND h.status = 'draft_shared' ORDER BY h.shared_at, h.id"
                ),
                {"r": d.recipient_id, "w": d.return_id},
            )
        ).all()
        final = await session.scalar(
            text(
                "SELECT evidence_version_id FROM k1_documents WHERE package_id = :p "
                "AND kind = 'k1' AND NOT is_draft ORDER BY created_at DESC LIMIT 1"
            ),
            {"p": d.package_id},
        )
    values = await _final_values(system, d.package_id)
    at = await clock.now(system)
    async with uow(system) as tx:
        for handoff, target in drafts:
            target_ctx = await _target_facts(ctx, target)
            copy: UUID | None = None
            request: UUID | None = None
            if final is not None and target_ctx is not None:
                copy = await file_handoff_copy(
                    tx,
                    source_version_id=cast(UUID, final),
                    tenant_id=d.tenant_id,
                    client_id=target_ctx.client_id,
                    engagement_id=target_ctx.engagement_id,
                    work_item_id=target,
                    title=f"Schedule K-1 · {issuer_name}",
                    actor_id=str(d.requested_by),
                )
                request = await k1_request_for(system, target, issuer_name)
                if request is not None:
                    await fulfil_by_rule(
                        tx, ctx, request_item_id=request, evidence_version_id=copy
                    )
            await tx.session.execute(
                text(
                    "UPDATE k1_handoffs SET status = 'final_replaced', replaced_at = :at, "
                    "final_values = CAST(:v AS jsonb), "
                    "target_evidence_version_id = coalesce(:c, target_evidence_version_id), "
                    "target_request_item_id = coalesce(:q, target_request_item_id) "
                    "WHERE id = :h AND status = 'draft_shared'"
                ),
                {"at": at, "v": values, "c": copy, "q": request, "h": handoff},
            )
            tx.record(
                "schedule_k_package.handoff_replaced",
                target=Target(KIND, d.return_id),
                after=Ref(release=d.release_id, handoff=cast(UUID, handoff), target=target),
            )
        await tx.session.execute(
            text(
                "UPDATE k1_release_deliveries SET handoffs_at = :at "
                "WHERE release_id = :release AND package_id = :package"
            ),
            {"at": at, "release": d.release_id, "package": d.package_id},
        )


async def _target_facts(ctx: AuthContext, target: UUID) -> k1.Issuer | None:
    """The receiving return as the releaser reads it; a return they can't read keeps no copy."""
    try:
        return await k1.issuer_for(ctx, target, k1.CONTENT)
    except (Forbidden, NotFound):
        return None


async def deliver(tenant_id: UUID, release_id: UUID, package_id: UUID) -> str:
    """One recipient, each step once (the ledger's stamps); a replay resumes where it stopped."""
    system = _system(tenant_id, release_id)
    d = await _delivery(system, release_id, package_id)
    ctx = await _acting(d)
    issuer = await k1.issuer_for(ctx, d.return_id, k1.READ)
    contact = await _contact_step(system, d)
    await _access_step(system, d, contact, issuer.client_id)
    await _released_step(system, d)
    await _email_step(system, d, contact, f"schedule_k_release:{release_id}:{package_id}")
    await _handoffs_step(system, d, issuer.client_name)
    return "released"


# --- resend (T-02-T20's request) -----------------------------------------------------------------


async def _access_for(
    tx_tenant: TenantContext,
    *,
    return_id: UUID,
    engagement_id: UUID,
    client_id: UUID,
    contact: UUID,
    package_id: UUID,
    granted_by: UUID,
    release_id: UUID | None = None,
) -> tuple[K1Access, RecipientRef, str]:
    """The `k1_recipient` access a contact is given, and whom the email goes to. A release's
    ledger is stamped in the same unit of work, so a replay never grants or invites twice."""
    async with tenant_session(tx_tenant) as session:
        person = (await contact_facts(session, [contact])).get(contact)
    # Security review (S19 batch 5): a K-1 goes only to a contact of the issuing client; a
    # contact of another client (a mistaken or hostile resend) is refused, never invited.
    if person is None or person.client_id != client_id:
        raise ApplicationError("contact_missing", type="DeliveryRefused", non_retryable=True)
    email = None
    if person.user_id is None:
        found = (await signer_contacts(tx_tenant, [contact])).get(contact)
        email = None if found is None else found.email
    async with uow(tx_tenant) as tx:
        given = await grant_k1_recipient(
            tx,
            tx_tenant,
            engagement_id=engagement_id,
            client_id=client_id,
            contact_id=contact,
            user_id=person.user_id,
            email=email,
            package_id=package_id,
            granted_by=granted_by,
        )
        tx.record(
            "schedule_k_package.access_given",
            target=Target(KIND, return_id),
            after=Ref(
                package=package_id,
                contact_id=contact,
                invited=int(given.invitation_id is not None),
            ),
        )
        if release_id is not None:
            await tx.session.execute(
                text(
                    "UPDATE k1_release_deliveries SET access_grant_id = :g, "
                    "invitation_id = :i, access_at = :at "
                    "WHERE release_id = :release AND package_id = :package"
                ),
                {
                    "g": given.grant_id,
                    "i": given.invitation_id,
                    "at": await clock.now(tx_tenant),
                    "release": release_id,
                    "package": package_id,
                },
            )
    recipient = (
        RecipientRef("user", person.user_id)
        if person.user_id is not None
        else RecipientRef("contact", contact)
    )
    return given, recipient, person.display_name.split(" ")[0] or "there"


async def on_resend_requested(event: OutboxEvent) -> None:
    """The corrected contact gets access and a new "Deliverable ready" email, keyed by the
    request, so a redelivered event sends nothing twice."""
    package_id = UUID(str(event.payload["package_id"]))
    contact = UUID(str(event.payload["contact_id"]))
    by_user = UUID(str(event.payload["by_user"]))
    system = TenantContext(event.tenant_id, "system", f"k1_resend:{package_id}")
    async with tenant_session(system) as session:
        row = (
            await session.execute(
                text("SELECT work_item_id, status FROM k1_packages WHERE id = :p"),
                {"p": package_id},
            )
        ).first()
    ctx = await member_context(event.tenant_id, by_user)
    if row is None or row.status not in k1.RELEASED or ctx is None:
        return
    issuer = await k1.issuer_for(ctx, row.work_item_id, k1.READ)
    _, recipient, first = await _access_for(
        system,
        return_id=row.work_item_id,
        engagement_id=issuer.engagement_id,
        client_id=issuer.client_id,
        contact=contact,
        package_id=package_id,
        granted_by=by_user,
    )
    await send_templated(
        ctx,
        TEMPLATE_KEY,
        recipient,
        await _variables(event.tenant_id, first),
        scope=SendScope(engagement_id=issuer.engagement_id),
        idempotency_key=f"schedule_k_resend:{event.event_id}",
        authority=k1.RESEND,  # DEC-1583: client service resends without `message.send`
    )


# --- a bounced "Deliverable ready" (POR-13's Bounced, TXP-12 B) ---------------------------------


async def on_message_bounced(event: OutboxEvent) -> None:
    """A release's email bounced: the package reads Bounced until a person resends it."""
    message_id = UUID(str(event.payload["message_id"]))
    system = TenantContext(event.tenant_id, "system", f"k1_bounce:{message_id}")
    async with uow(system) as tx:
        found = (
            await tx.session.execute(
                text(
                    "SELECT d.package_id, r.work_item_id FROM k1_release_deliveries d "
                    "JOIN k1_releases r ON r.id = d.release_id WHERE d.message_id = :m"
                ),
                {"m": message_id},
            )
        ).first()
        if found is None:
            return  # not a K-1 email
        moved = (
            await tx.session.execute(
                text(
                    "UPDATE k1_packages SET status = 'bounced' WHERE id = :p "
                    "AND status IN ('released', 'viewed') RETURNING id"
                ),
                {"p": found.package_id},
            )
        ).first()
        if moved is None:
            return
        await k1.record_event(tx, event.tenant_id, found.package_id, "bounced", None, {})
        tx.record(
            "schedule_k_package.bounced",
            target=Target(KIND, found.work_item_id),
            after=Ref(package=found.package_id, message=message_id),
        )


# --- activities ----------------------------------------------------------------------------------


def _refused(error: Exception) -> ApplicationError:
    return ApplicationError(type(error).__name__, type="DeliveryRefused", non_retryable=True)


@activity.defn(name="schedule_k_release.start")
async def start_activity(given: K1ReleaseInput) -> str:
    try:
        return await start(UUID(given.tenant_id), UUID(given.release_id))
    except GrantNotYetDue:
        raise ApplicationError("not_yet_due", type="GrantNotYetDue") from None


@activity.defn(name="schedule_k_release.packages")
async def packages_activity(given: K1ReleaseInput) -> list[str]:
    return await packages(UUID(given.tenant_id), UUID(given.release_id))


@activity.defn(name="schedule_k_release.deliver")
async def deliver_activity(given: K1DeliveryInput) -> str:
    try:
        return await deliver(UUID(given.tenant_id), UUID(given.release_id), UUID(given.package_id))
    except (Forbidden, NotFound) as error:
        raise _refused(error) from None


@activity.defn(name="schedule_k_release.complete")
async def complete_activity(given: K1ReleaseInput) -> str:
    return await complete(UUID(given.tenant_id), UUID(given.release_id))


@activity.defn(name="schedule_k_release.fail")
async def fail_activity(given: K1ReleaseFailure) -> str:
    return await fail(UUID(given.tenant_id), UUID(given.release_id), given.failure_code)


ACTIVITIES = (
    start_activity,
    packages_activity,
    deliver_activity,
    complete_activity,
    fail_activity,
)
SUBSCRIPTIONS = {
    K1ReleaseRequested.event_type: on_requested,
    k1.K1ResendRequested.event_type: on_resend_requested,
    "message.bounced": on_message_bounced,  # T-02-T26: POR-13's Bounced
}

__all__ = [
    "ACTION",
    "ACTIVITIES",
    "SUBSCRIPTIONS",
    "UNDO_WINDOW",
    "WORKFLOWS",
    "K1EffectStarted",
    "K1ReleaseIneligible",
    "K1ReleaseRequested",
    "K1ReleaseStale",
    "K1ReleaseUndone",
    "K1UndoClosed",
    "ReleaseView",
    "complete",
    "deliver",
    "eligibility",
    "fail",
    "grant_digest",
    "packages",
    "read",
    "request_release",
    "start",
    "undo",
]

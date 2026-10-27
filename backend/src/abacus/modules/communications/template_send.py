"""`send_templated`: one firm template to one person outside the firm (R-01-T19; C16 v1.1;
DEC-378, DEC-379, DEC-449). The contract is the docstring of `template_registry.send_templated`.

In one unit of work: the engagement is locked and, for a person, `message.send` is authorised on
it; then the key's version in use is resolved (the firm's published, else the platform default)
and the send is refused, recorded `blocked`, with the first reason that applies:
`template_missing` (no published block version), `template_lint_failed` (a value outside the
key's whitelist, a missing value, or a value with an amount, TIN or account-number shape),
`out_of_scope` (the rendered text names another client, entity, account or amount) or
`suppressed` (no deliverable address, or a bounced or complained one). Otherwise the message is
recorded `sent` with its `template_version_id` and handed to delivery after the commit.

The stored body is the text part with the secure link removed, so the token is never stored.
The message id is derived from the firm, the key, the recipient, the engagement and the
idempotency key: a retry answers what the first call recorded and sends nothing again, after
authorising on the stored message's engagement. A recipient must be someone the engagement
concerns (its team, or a client grant covering it), and only for a key whose audience matches
how they relate to it, read under the firm's row-level security, else 404 (security review H).
The system's Reminder is checked as its publisher could send it
(security review M2), and the database refuses any other non-person templated message. The
client-mail gate (`firm_not_client_facing`) arrives with R-01-T27, the policy's mode with T24.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.communications import template_store
from abacus.modules.communications.deliveries import deliver, is_suppressed
from abacus.modules.communications.lint import lint_template
from abacus.modules.communications.models import Message
from abacus.modules.communications.render import RenderedEmail, render_email
from abacus.modules.communications.repository import insert_message
from abacus.modules.communications.scope import check_scope
from abacus.modules.communications.template_registry import (
    VARIABLES,
    EmailTemplateRegistration,
    RecipientRef,
    SendOutcome,
    SendRefusal,
    SendScope,
    SystemSendContext,
    lint_values,
    registration_of,
    scheduled_send_enabled,
)
from abacus.modules.communications.template_service import person_of
from abacus.modules.communications.template_store import StoredVersion
from abacus.modules.communications.templates import TemplateInvalid, UnknownTemplateVariable
from abacus.modules.engagements.api import EngagementRef, get_ref, lock_ref
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    authorise,
    contact_emails,
    firm_name,
    member_context,
    member_could,
    recipient_relations,
)

_NAMESPACE: Final = uuid.UUID("6f1d6c2e-8d0c-4f0e-9b5a-0c16e7a1a019")
_LINK_REMOVED: Final = "[link removed]"
_BLOCK_VARIABLES: Final = frozenset(n for n, v in VARIABLES.items() if v.block)
_log = get_logger(__name__)


def message_id_for(
    tenant_id: UUID,
    key: str,
    recipient: RecipientRef,
    engagement_id: UUID,
    idempotency_key: str,
) -> UUID:
    """One message per firm, key, recipient, engagement and idempotency key (security review
    M4): the same key reused for another person or engagement is another message."""
    name = f"{tenant_id}:{key}:{recipient.kind}:{recipient.id}:{engagement_id}:{idempotency_key}"
    return uuid.uuid5(_NAMESPACE, name)


async def _recorded(tenant: TenantContext, message_id: UUID) -> tuple[SendOutcome, UUID] | None:
    """What the first call recorded, and the engagement it is about."""
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                select(Message.status, Message.violations, Message.engagement_id).where(
                    Message.id == message_id
                )
            )
        ).one_or_none()
    if row is None:
        return None
    return _outcome(message_id, row.status, row.violations), row.engagement_id


def _outcome(message_id: UUID, status: str, violations: list[dict[str, str]]) -> SendOutcome:
    if status == "sent":
        return SendOutcome(message_id, "queued", None)
    row_violations = violations
    kinds = {v.get("kind") for v in row_violations}
    reason: SendRefusal = "out_of_scope"
    for candidate in ("template_missing", "template_lint_failed", "suppressed"):
        if candidate in kinds:
            reason = cast(SendRefusal, candidate)
    return SendOutcome(message_id, "blocked", reason)


async def _address(recipient: RecipientRef) -> str | None:
    """Where the message goes. A firm user or client user by their account's address; other
    recipient kinds resolve through their own epics (a contact, a third party, a respondent)."""
    if recipient.kind != "user":
        return None
    return (await contact_emails([recipient.id])).get(recipient.id)


def _values_findings(
    registration: EmailTemplateRegistration, values: Mapping[str, str]
) -> list[dict[str, str]]:
    findings = [
        {"kind": "template_lint_failed", "ref": f"{f.code}:{f.variable}"}
        for f in lint_values({k: v for k, v in values.items() if k != "portal_link"})
    ]
    if not set(values) <= set(registration.variables):
        findings.append({"kind": "template_lint_failed", "ref": "unregistered_variable"})
    return findings


def _render(
    registration: EmailTemplateRegistration, version: StoredVersion, values: Mapping[str, str]
) -> RenderedEmail | None:
    if version.content is None:
        return None
    try:
        return render_email(
            version.content,
            values,
            allowed=frozenset(registration.variables),
            block_variables=_BLOCK_VARIABLES,
        )
    except (UnknownTemplateVariable, TemplateInvalid):
        return None


async def _authorise_send(ctx: AuthContext, ref: EngagementRef) -> None:
    """A person sends: `message.send` on the engagement the message is about."""
    await authorise(ctx, "message.send", ref.resource())


async def _authorise_system(person: AuthContext, ref: EngagementRef) -> None:
    """The scheduled reminder is attributed to its version's publisher, so it goes only where
    that person could send it themself (walls, independence, the team; review M2)."""
    if not await member_could(person.tenant_id, person.user_id, "message.send", ref.resource()):
        raise Forbidden("message.send", "role")


async def _system_sender(ctx: SystemSendContext, key: str) -> tuple[AuthContext, StoredVersion]:
    """The scheduled reminder (DEC-74): only with its flag, only `reminder`, only from a version
    the firm published, attributed to its publisher, who must still be a member (INV-5)."""
    if ctx.reason != "scheduled_follow_up" or key != "reminder":
        raise Forbidden("message.send", "role")
    if not await scheduled_send_enabled(ctx.tenant):
        raise Forbidden("message.send", "role")
    async with tenant_session(ctx.tenant) as session:
        version = await template_store.resolve(session, ctx.tenant.tenant_id, key)
    publisher = person_of(version.published_by) if version is not None else None
    if version is None or not version.firm or publisher is None:
        raise Forbidden("message.send", "role")
    member = await member_context(ctx.tenant.tenant_id, publisher)
    if member is None:
        raise Forbidden("message.send", "role")
    return member, version


async def send(
    ctx: AuthContext | SystemSendContext,
    key: str,
    recipient: RecipientRef,
    variables: Mapping[str, str],
    *,
    scope: SendScope,
    idempotency_key: str,
) -> SendOutcome:
    if isinstance(ctx, SystemSendContext):
        person, _ = await _system_sender(ctx, key)
        tenant = TenantContext(
            ctx.tenant.tenant_id,
            "system",
            "follow_up:scheduled",
            on_behalf_of_user_id=person.user_id,
        )
        checker = person
    else:
        if ctx.tenant.actor_kind != "human" or ctx.client:
            raise Forbidden("message.send", "role")  # ADR-005: agents draft, people send
        tenant, checker = ctx.tenant, ctx
    if not 1 <= len(idempotency_key) <= 255:
        raise TemplateInvalid
    message_id = message_id_for(
        tenant.tenant_id, key, recipient, scope.engagement_id, idempotency_key
    )
    already = await _recorded(tenant, message_id)
    if already is not None:
        outcome, engagement_id = already
        # A replay still authorises (ED-026), on the stored message's engagement (review M4).
        replayed = await get_ref(checker, engagement_id)
        if isinstance(ctx, SystemSendContext):
            await _authorise_system(checker, replayed)
        else:
            await _authorise_send(ctx, replayed)
        return outcome
    registration = registration_of(key)
    if registration is not None and not registration.firm_editable:
        registration = None  # send_templated sends firm-editable keys only (review M1)
    address: str | None = None
    values = dict(variables)
    link = values.get("portal_link")
    rendered: RenderedEmail | None = None
    body = ""
    async with uow(tenant) as tx:
        ref = await lock_ref(tx, scope.engagement_id)
        if isinstance(ctx, SystemSendContext):
            await _authorise_system(checker, ref)
        else:
            await _authorise_send(ctx, ref)
        # Security review H: only someone the engagement concerns may be written to about it.
        # The re-review: and only for a key whose audience matches how they relate to it (a
        # third party never gets `deliverable_ready`).
        if recipient.kind == "user":
            relations = await recipient_relations(tenant, recipient.id, ref.id)
            audience = set(registration.audience) if registration is not None else set(relations)
            if not relations & audience:
                raise NotFound("recipient")
            address = await _address(recipient)
        version = await template_store.resolve(tx.session, tenant.tenant_id, key)
        violations: list[dict[str, str]] = []
        reason: SendRefusal | None = None
        if registration is None or version is None or version.content is None:
            reason, violations = "template_missing", [{"kind": "template_missing", "ref": ""}]
        else:
            violations = _values_findings(registration, values)
            if isinstance(ctx, SystemSendContext):
                # Security review M1: no person reads a scheduled Reminder before it goes, so the
                # version itself is linted again (a version published before a rule existed).
                violations += [
                    {"kind": "template_lint_failed", "ref": f.fact()}
                    for f in lint_template(version.content, registration)
                ]
            rendered = None if violations else _render(registration, version, values)
            if violations or rendered is None:
                reason = "template_lint_failed"
                violations = violations or [{"kind": "template_lint_failed", "ref": "render"}]
        if rendered is not None:
            body = rendered.text.replace(link, _LINK_REMOVED) if link else rendered.text
            try:
                scope_hits = await check_scope(checker, ref, f"{rendered.subject}\n{body}")
            except Exception as exc:  # fail closed, as `send` does
                _log.warning("message.checker_failed", error=exc)
                scope_hits = []
                violations = [{"kind": "checker_error", "ref": ""}]
                reason = "out_of_scope"
            if scope_hits:
                reason = "out_of_scope"
                violations = [{"kind": v.kind, "ref": v.ref} for v in scope_hits]
            elif reason is None and (
                address is None or await is_suppressed(tenant.tenant_id, address)
            ):
                reason, violations = "suppressed", [{"kind": "suppressed", "ref": ""}]
        status: Literal["sent", "blocked"] = "blocked" if reason is not None else "sent"
        audience = registration.audience if registration is not None else ()
        await insert_message(
            tx.session,
            message_id=message_id,
            tenant_id=tenant.tenant_id,
            engagement_id=scope.engagement_id,
            channel="email",
            recipient_ref=f"{recipient.kind}:{recipient.id}",
            body=(body or f"[not sent: {reason}]")[:20000],
            status=status,
            violations=violations,
            created_by=checker.user_id,
            template_version_id=version.version_id if version is not None else None,
            kind="staff" if audience == ("staff",) else "client",
        )
        tx.record(
            f"message.{status}",
            target=Target("message", message_id),
            after=Ref(template_version_id=version.version_id) if version is not None else None,
        )
    if reason is not None or rendered is None or address is None:
        _log.info("message.blocked", message_id=message_id, reason=reason)
        return SendOutcome(message_id, "blocked", reason)
    refused = await deliver(
        tenant_id=tenant.tenant_id,
        message_id=message_id,
        to=address,
        subject=rendered.subject,
        body=rendered.text,
        sender_name=await firm_name(tenant.tenant_id),
    )
    if refused is not None:  # paused or the sink refused after the checks: logged, by kind
        _log.warning("message.delivery_refused", message_id=message_id, kind=refused["kind"])
    return SendOutcome(message_id, "queued", None)


async def templated_outcome(
    ctx: AuthContext,
    key: str,
    recipient: RecipientRef,
    *,
    scope: SendScope,
    idempotency_key: str,
) -> SendOutcome | None:
    """What a `send_templated` with these arguments recorded, without sending; None when it
    never ran (A-02-T23 review L1: a caller resending only what never went out). Authorised as
    a replay is: `message.send` on the stored message's engagement."""
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden("message.send", "role")
    message_id = message_id_for(
        ctx.tenant.tenant_id, key, recipient, scope.engagement_id, idempotency_key
    )
    found = await _recorded(ctx.tenant, message_id)
    if found is None:
        return None
    outcome, engagement_id = found
    await _authorise_send(ctx, await get_ref(ctx, engagement_id))
    return outcome

"""Secure links for portal emails (P-08-T21; SPEC-320 AC-14; epic Story 5.1; DEC-35).

R-01's POR-20 emails (Reminder, Invitation, Signature request, Deliverable ready, Reconnect) carry
one link each, made here at send time with `issue_secure_link`: 256 random bits, kept only as a
SHA-256, lasting 14 days, single use, for one contact and the address the email goes to. The
email's URL is the firm's portal host `/sign-in#link=<token>` (a fragment: never in a log).

- **Sign-in** (`claim`, identity's start through its slot): a link that can't be used (unknown,
  another firm's, used, revoked, expired) gets one answer for every reason; a usable one is used
  when the typed address is the one it was sent to.
- **Renewal** (`POST /v1/portal/links/renew`, pre-session): always 202 with one body, padded to
  one duration. A link of the host's firm that isn't revoked gets a new one (same contact,
  purpose, target and address), at most 3 per link per hour; its token is issued at delivery
  (`deliver_renewed_link`) and sent only to the address the old link went to, from the firm's
  C16 template `portal.link_renewed` (imported per environment; without it nothing is sent and
  the miss is logged). A token that is an invitation's renews the expired invitation instead, at
  most twice (identity). While the firm's portal sign-in is paused nothing is renewed.
- **R-01** reads a link server-side with `resolve_secure_link` (live links only).
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel.db import TenantContext, platform_transaction, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import MissingAuditEvent, OutboxEvent, Ref, Target, uow
from abacus.modules.communications.deliveries import send_email
from abacus.modules.communications.events import PortalLinkRenewRequested
from abacus.modules.communications.templates import current_version, render
from abacus.modules.identity.api import (
    LinkOutcome,
    SignInPaused,
    check_not_paused,
    firm_name,
    renew_invitation,
)

LINK_DAYS: Final = 14
RENEWALS_PER_HOUR: Final = 3
# Every renewal answer takes at least this long, so a real link can't be told by its timing.
FLOOR_SECONDS: Final = 0.5
TEMPLATE_KEY: Final = "portal.link_renewed"
Purpose = Literal["reminder", "invitation", "signature_request", "deliverable_ready", "reconnect"]
_log = get_logger(__name__)


@dataclass(frozen=True)
class IssuedLink:
    """The token goes in the one email and nowhere else (Restricted)."""

    link_id: UUID
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class SecureLinkView:
    link_id: UUID
    contact_id: UUID
    purpose: str
    target_kind: str | None
    target_id: UUID | None
    expires_at: datetime


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _address(email: str) -> str:
    return email.strip().lower()


async def issue_secure_link(
    tenant_id: UUID,
    *,
    contact_id: UUID,
    purpose: Purpose,
    recipient_email: str,
    issued_by: UUID | None = None,
    host: str | None = None,
    target_kind: str | None = None,
    target_id: UUID | None = None,
) -> IssuedLink:
    """`communications.api.issue_secure_link`: a new 14-day link for one email, at send time.
    Audited `secure_link.issued`."""
    token = secrets.token_urlsafe(32)
    ctx = TenantContext(tenant_id, "system", f"secure_link:{purpose}", issued_by)
    async with uow(ctx) as tx:
        row = (
            await tx.session.execute(
                text(
                    "INSERT INTO secure_links (tenant_id, contact_id, purpose, target_kind, "
                    "target_id, recipient_email, host, token_sha256, issued_by, expires_at) "
                    "VALUES (:tenant, :contact, :purpose, :kind, :target, :email, :host, :sha, "
                    ":by, clock_timestamp() + make_interval(days => :days)) "
                    "RETURNING id, expires_at"
                ),
                {
                    "tenant": tenant_id,
                    "contact": contact_id,
                    "purpose": purpose,
                    "kind": target_kind,
                    "target": target_id,
                    "email": _address(recipient_email),
                    "host": host.lower() if host else None,
                    "sha": digest(token),
                    "by": issued_by,
                    "days": LINK_DAYS,
                },
            )
        ).one()
        tx.record(
            "secure_link.issued",
            target=Target("secure_link", row.id),
            after=Ref(contact_id=contact_id),
        )
    return IssuedLink(row.id, token, row.expires_at)


async def resolve_secure_link(tenant_id: UUID, token: str) -> SecureLinkView | None:
    """`communications.api.resolve_secure_link`: a live link of the firm (unused, unrevoked,
    within its 14 days), or None for every other token."""
    async with tenant_session(TenantContext(tenant_id, "system", "secure_links")) as session:
        row = (
            await session.execute(
                text(
                    "SELECT id, contact_id, purpose, target_kind, target_id, expires_at "
                    "FROM secure_links WHERE token_sha256 = :sha AND used_at IS NULL "
                    "AND revoked_at IS NULL AND expires_at > clock_timestamp()"
                ),
                {"sha": digest(token)},
            )
        ).first()
    if row is None:
        return None
    return SecureLinkView(
        row.id, row.contact_id, row.purpose, row.target_kind, row.target_id, row.expires_at
    )


async def claim(host: str, token_sha256: str, email: str) -> LinkOutcome:
    """Identity's start, through its slot: `bad`, `other` or `claimed` (which uses the link)."""
    async with platform_transaction("portal:links") as conn:
        found = (
            await conn.execute(
                text("SELECT portal_link_claim(:host, :sha, :email)"),
                {"host": host, "sha": token_sha256, "email": email},
            )
        ).scalar_one()
    return cast(LinkOutcome, str(found))


async def _floor(began: float) -> None:
    left = FLOOR_SECONDS - (time.monotonic() - began)
    if left > 0:
        await asyncio.sleep(left)


def _host(host: str | None) -> str:
    return (host or "").split(":", 1)[0].strip().lower()[:253]


async def renew_link(host: str | None, token: str) -> None:
    """The renewal route's work; it answers the same whatever happens here."""
    began = time.monotonic()
    try:
        await _renew(_host(host), token)
    finally:
        await _floor(began)


async def _renew(host: str, token: str) -> None:
    if not host or not token:
        return
    try:
        await check_not_paused(host)
    except SignInPaused:
        return
    sha = digest(token)
    async with platform_transaction("portal:links") as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM portal_link_renew(:host, :sha, :per_hour, :days)"),
                {"host": host, "sha": sha, "per_hour": RENEWALS_PER_HOUR, "days": LINK_DAYS},
            )
        ).first()
    if row is None:
        await renew_invitation(host, sha)
        return
    tenant_id, link_id = UUID(str(row.tenant_id)), UUID(str(row.link_id))
    ctx = TenantContext(tenant_id, "system", f"secure_link:{row.renewed_from_id}")
    async with uow(ctx) as tx:
        tx.record(
            "secure_link.renewed",
            target=Target("secure_link", link_id),
            after=Ref(renewed_from_id=UUID(str(row.renewed_from_id))),
        )
        tx.emit(PortalLinkRenewRequested(secure_link_id=link_id))


async def deliver_renewed_link(event: OutboxEvent) -> None:
    """On `portal.link_renew_requested`: the new link's token, issued now and never stored
    (only its hash), sent to the address the old link went to, in the firm's name."""
    link_id = UUID(str(event.payload["secure_link_id"]))
    version = await current_version(TEMPLATE_KEY)
    if version is None:
        _log.warning("secure_link.no_template", secure_link_id=link_id)
        return
    token = secrets.token_urlsafe(32)
    ctx = TenantContext(event.tenant_id, "system", f"secure_link:{link_id}")
    try:
        async with uow(ctx) as tx:
            row = (
                await tx.session.execute(
                    text(
                        "UPDATE secure_links SET token_sha256 = :sha WHERE id = :id "
                        "AND token_sha256 IS NULL AND revoked_at IS NULL AND used_at IS NULL "
                        "AND expires_at > clock_timestamp() RETURNING recipient_email, host"
                    ),
                    {"sha": digest(token), "id": link_id},
                )
            ).first()
            if row is None:
                return  # sent, revoked or expired meanwhile: nothing to send
            tx.record("secure_link.token_issued", target=Target("secure_link", link_id))
    except MissingAuditEvent:
        return
    if row.host is None:
        _log.warning("secure_link.no_host", secure_link_id=link_id)
        return
    firm = await firm_name(event.tenant_id)
    values = {"firm_name": firm, "app_link": f"https://{row.host}/sign-in#link={token}"}
    rendered = render(version, {k: values.get(k, "") for k in version.variables})
    message_id = uuid4()
    sent = await send_email(
        tenant_id=event.tenant_id,
        message_id=message_id,
        to=str(row.recipient_email),
        subject=rendered.subject,
        body=rendered.body_text,
        sender_name=firm,
    )
    _log.info("secure_link.renewal_sent", secure_link_id=link_id, message_id=message_id, sent=sent)

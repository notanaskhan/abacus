"""Secure links for portal emails (P-08-T21; SPEC-320 AC-14; epic Story 5.1; DEC-35).

R-01's POR-20 emails (Reminder, Invitation, Signature request, Deliverable ready, Reconnect) carry
one link each, made here at send time with `issue_secure_link`: 256 random bits, kept only as a
SHA-256, lasting 14 days, single use, for one contact and the address the email goes to. The
email's URL is the firm's portal host `/sign-in#link=<token>` (a fragment: never in a log).

- **Sign-in** (`claim`, identity's start through its slot): a link that can't be used (unknown,
  another firm's, used, revoked, expired) gets one answer for every reason; a usable one is used
  when the typed address is the one it was sent to.
- **Renewal** (`POST /v1/portal/links/renew`, pre-session): always 202 with one body, padded to
  one duration. A link of the host's firm that isn't revoked, for a contact who still signs in
  (`active` or `locked`) at the very address the link went to, gets a new one (same contact,
  purpose, target and address). Caps (DEC-329): 3 per link an hour; 3 an hour and 10 a day per
  contact across all their links; a chain ends after 5 renewals or 60 days from its first link.
  Its token is issued at delivery (`deliver_renewed_link`) and sent from the firm's C16 template
  `portal.link_renewed` (imported per environment; without it nothing is sent and the miss is
  logged). An `invitation` link, or a token that is an invitation's, defers to the invitation's
  own state and its two-renewal cap (identity). Nothing is renewed while sign-in is paused.
- **Revocation** (`revoke_links_of`, through identity's slot): organisations revokes a contact's
  links where their access ends (a revoked invitation) or their address changes, and
  `client_access.revoked` revokes the person's contacts' links, so no link outlives its access.
- **R-01** reads a link server-side with `resolve_secure_link` (live links only).
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel.db import TenantContext, platform_transaction, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import MissingAuditEvent, OutboxEvent, Ref, Target, UnitOfWork, uow
from abacus.modules.communications.deliveries import send_email
from abacus.modules.communications.events import PortalLinkRenewRequested
from abacus.modules.communications.templates import current_version, render
from abacus.modules.identity.api import (
    LinkOutcome,
    SignInPaused,
    check_not_paused,
    firm_name,
    renew_invitation,
    renew_invitation_by_id,
)
from abacus.modules.organisations.api import contact_portal_facts, contacts_of_user

LINK_DAYS: Final = 14
# Renewal caps (P-08-T21 security review, DEC-329): per link, per contact across all of their
# links, and per chain over its whole life (from the first link's issue).
RENEWALS_PER_HOUR: Final = 3
CONTACT_RENEWALS_PER_HOUR: Final = 3
CONTACT_RENEWALS_PER_DAY: Final = 10
CHAIN_MAX_DAYS: Final = 60
CHAIN_MAX_LENGTH: Final = 5
# A contact a renewal may still reach: one who signs in to the portal.
_REACHABLE: Final = frozenset({"active", "locked"})
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


class _NotRenewed(Exception):
    """A renewal the rules refuse after the firm was found; rolled back, nothing written."""


async def _renew(host: str, token: str) -> None:
    if not host or not token:
        return
    try:
        await check_not_paused(host)
    except SignInPaused:
        return
    sha = digest(token)
    async with platform_transaction("portal:links") as conn:
        found = (
            await conn.execute(
                text("SELECT * FROM portal_link_find(:host, :sha)"), {"host": host, "sha": sha}
            )
        ).first()
    if found is None:
        await renew_invitation(host, sha)
        return
    tenant_id, link_id = UUID(str(found.tenant_id)), UUID(str(found.link_id))
    tenant = TenantContext(tenant_id, "system", f"secure_link:{link_id}")
    async with tenant_session(tenant) as session:
        link = (
            await session.execute(
                text(
                    "SELECT contact_id, purpose, target_kind, target_id, recipient_email, "
                    "revoked_at FROM secure_links WHERE id = :id"
                ),
                {"id": link_id},
            )
        ).one()
    if link.revoked_at is not None:
        return
    if link.purpose == "invitation":
        # The invitation's own state and two-renewal cap decide (identity).
        if link.target_kind == "client_invitation" and link.target_id is not None:
            await renew_invitation_by_id(tenant_id, UUID(str(link.target_id)))
        return
    facts = await contact_portal_facts(tenant, UUID(str(link.contact_id)))
    if facts is None or facts[0] not in _REACHABLE or facts[2] != link.recipient_email:
        return  # the contact no longer signs in, or no longer at that address
    try:
        await _insert_renewal(tenant, link_id, host)
    except _NotRenewed:
        return


async def _insert_renewal(tenant: TenantContext, link_id: UUID, host: str) -> None:
    """In the firm, serialised per contact (an advisory lock): the caps checked, then a new
    link for the same contact, purpose, target and address, its token issued at delivery."""
    async with uow(tenant) as tx:
        old = (
            await tx.session.execute(
                text(
                    "SELECT id, contact_id, purpose, target_kind, target_id, recipient_email, "
                    "revoked_at, chain_started_at, chain_length FROM secure_links "
                    "WHERE id = :id FOR UPDATE"
                ),
                {"id": link_id},
            )
        ).one()
        await tx.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:contact, 0))"),
            {"contact": f"secure_links:{old.contact_id}"},
        )
        counts = (
            await tx.session.execute(
                text(
                    "SELECT count(*) FILTER (WHERE renewed_from_id = :id "
                    "AND issued_at > clock_timestamp() - interval '1 hour') AS link_hour, "
                    "count(*) FILTER (WHERE issued_at > clock_timestamp() - interval '1 hour') "
                    "AS contact_hour, "
                    "count(*) FILTER (WHERE issued_at > clock_timestamp() - interval '1 day') "
                    "AS contact_day "
                    "FROM secure_links WHERE contact_id = :contact AND renewed_from_id IS NOT NULL"
                ),
                {"id": link_id, "contact": old.contact_id},
            )
        ).one()
        aged = await tx.session.scalar(
            text(
                "SELECT clock_timestamp() > "
                "CAST(:started AS timestamptz) + make_interval(days => :days)"
            ),
            {"started": old.chain_started_at, "days": CHAIN_MAX_DAYS},
        )
        if (
            old.revoked_at is not None
            or aged
            or old.chain_length >= CHAIN_MAX_LENGTH
            or counts.link_hour >= RENEWALS_PER_HOUR
            or counts.contact_hour >= CONTACT_RENEWALS_PER_HOUR
            or counts.contact_day >= CONTACT_RENEWALS_PER_DAY
        ):
            raise _NotRenewed
        new_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO secure_links (tenant_id, contact_id, purpose, target_kind, "
                    "target_id, recipient_email, host, expires_at, renewed_from_id, "
                    "chain_started_at, chain_length) VALUES (:tenant, :contact, :purpose, "
                    ":kind, :target, :email, :host, "
                    "clock_timestamp() + make_interval(days => :link_days), :old, :started, "
                    ":length) RETURNING id"
                ),
                {
                    "tenant": tenant.tenant_id,
                    "contact": old.contact_id,
                    "purpose": old.purpose,
                    "kind": old.target_kind,
                    "target": old.target_id,
                    "email": old.recipient_email,
                    "host": host,
                    "link_days": LINK_DAYS,
                    "old": old.id,
                    "started": old.chain_started_at,
                    "length": old.chain_length + 1,
                },
            )
        ).scalar_one()
        tx.record(
            "secure_link.renewed",
            target=Target("secure_link", new_id),
            after=Ref(renewed_from_id=old.id, chain_length=old.chain_length + 1),
        )
        tx.emit(PortalLinkRenewRequested(secure_link_id=new_id))


async def revoke_links_of(tx: UnitOfWork, contact_ids: Sequence[UUID]) -> int:
    """Identity's slot (organisations calls it where a contact's access ends or their address
    changes): every live link of these contacts revoked in the caller's unit of work."""
    rows = await tx.session.execute(
        text(
            "UPDATE secure_links SET revoked_at = clock_timestamp() "
            "WHERE contact_id = ANY(:ids) AND revoked_at IS NULL RETURNING id"
        ),
        {"ids": list(contact_ids)},
    )
    revoked = [UUID(str(r.id)) for r in rows]
    for link in revoked:
        tx.record("secure_link.revoked", target=Target("secure_link", link))
    return len(revoked)


async def revoke_links_on_access_revoked(event: OutboxEvent) -> None:
    """On `client_access.revoked`: the person's contacts in the firm lose their links (a
    renewal must never outlive the access it leads to)."""
    user_id = UUID(str(event.payload["user_id"]))
    ctx = TenantContext(event.tenant_id, "system", "secure_links:access_revoked")
    try:
        async with uow(ctx) as tx:
            contacts = await contacts_of_user(tx.session, user_id)
            await revoke_links_of(tx, contacts)
    except MissingAuditEvent:
        return  # nothing to revoke


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

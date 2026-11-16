"""Link principals (A-08-T15; ADR-146 P-09; the ADR-152 amendment; SPEC-657 F6, F7; red).

A public page (`/v1/confirm/{token}…`) acts as exactly one link principal: a firm mints it for one
registered purpose (`register_link_purpose`), one subject and one address, and the raw token
travels only in the link the firm sends. Only SHA-256 digests are stored.

- **Uniform answers.** An unknown, expired, revoked or locked token resolves to nothing, through
  one definer and one code path, so the caller answers each the same (status, body and the padded
  time floor are the caller's, `PAD_SECONDS`). The `confirmation_links` platform control (P-66,
  ADR-157) turns every link off at once: nothing resolves while it is active.
- **Email code.** Asking for a code makes a challenge only when the typed address is the link's
  (never says which); communications issues the 10-minute code at delivery and sends it from the
  firm's template, so the code itself is never stored. Five wrong codes lock the link for 15
  minutes and void its open challenges.
- **Page credential.** A verified code mints a `__Host-` page credential and a CSRF value (both
  stored as SHA-256, 30 minutes); a write on the page needs both.

Nothing is logged with a token, a code or an address. Audit and access events are written in the
link's firm for a known link only.
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.clock import now as business_now
from abacus.kernel.controls import control_active
from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, platform_transaction
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.events import LinkCodeRequested
from abacus.modules.identity.portal_idp import email_code_matches, issue_email_code

COOKIE_NAME: Final = "__Host-abacus-link"
CODE_SECONDS: Final = 10 * 60
RESEND_SECONDS: Final = 60
MAX_TRIES: Final = 5
LOCK_SECONDS: Final = 15 * 60
CREDENTIAL_SECONDS: Final = 30 * 60
PAD_SECONDS: Final = 0.35
CONTROL: Final = "confirmation_links"
EMAIL_AAD: Final = "identity.link_principal.email"
_ACTOR: Final = "link_principal"


def sha256(value: str) -> bytes:
    return hashlib.sha256(value.encode()).digest()


def _email_key(email: str) -> bytes:
    return sha256(email.strip().casefold())


@dataclass(frozen=True)
class LinkPrincipal:
    tenant_id: UUID
    principal_id: UUID
    purpose: str
    subject_id: UUID
    verified: bool


# --- the purpose slot (ADR-106) ----------------------------------------------------------------

PurposeCheck = Callable[[TenantContext, UUID], Awaitable[bool]]
_PURPOSES: dict[str, PurposeCheck] = {}


def register_link_purpose(purpose: str, live: PurposeCheck) -> None:
    """A module that sends links registers its purpose and how to tell its subject is still live
    (a confirmation not yet answered or withdrawn). An unregistered purpose never resolves."""
    known = _PURPOSES.get(purpose)
    if known is not None and known is not live:
        raise ValueError(f"link purpose {purpose!r} is already registered")
    _PURPOSES[purpose] = live


def link_purposes() -> frozenset[str]:
    return frozenset(_PURPOSES)


# --- minting -----------------------------------------------------------------------------------


async def mint_link(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    purpose: str,
    subject_id: UUID,
    email: str,
    created_by: UUID,
    valid_for: timedelta,
) -> str:
    """A new link principal in the caller's unit of work; returns the raw token (for the link
    only: never stored, never logged)."""
    if purpose not in _PURPOSES:
        raise ValueError(f"unknown link purpose {purpose!r}")
    token = secrets.token_urlsafe(32)
    expires = await business_now() + valid_for
    principal = await tx.session.scalar(
        text(
            "INSERT INTO link_principals (tenant_id, purpose, subject_id, token_sha256, "
            "email_sha256, email_sealed, expires_at, created_by) VALUES (:t, :p, :s, :tok, :e, "
            ":sealed, :x, :u) RETURNING id"
        ),
        {
            "t": tenant_id,
            "p": purpose,
            "s": subject_id,
            "tok": sha256(token),
            "e": _email_key(email),
            "sealed": await seal(tenant_id, email.strip().encode(), EMAIL_AAD),
            "x": expires,
            "u": created_by,
        },
    )
    tx.record(
        "link_principal.minted",
        target=Target("link_principal", cast(UUID, principal)),
        after=Ref(subject_id=subject_id),
    )
    return token


async def live_principal(tx: UnitOfWork, purpose: str, subject_id: UUID) -> UUID | None:
    """The subject's newest unrevoked link principal for the purpose, in the caller's unit of
    work (A-08-T16: a confirmation's link row names the principal it minted)."""
    found = await tx.session.scalar(
        text(
            "SELECT id FROM link_principals WHERE purpose = :p AND subject_id = :s "
            "AND revoked_at IS NULL ORDER BY created_at DESC LIMIT 1"
        ),
        {"p": purpose, "s": subject_id},
    )
    return cast(UUID | None, found)


async def revoke_link(tx: UnitOfWork, principal_id: UUID) -> None:
    await tx.session.execute(
        text(
            "UPDATE link_principals SET revoked_at = clock_timestamp() WHERE id = :i AND "
            "revoked_at IS NULL"
        ),
        {"i": principal_id},
    )
    tx.record("link_principal.revoked", target=Target("link_principal", principal_id))


# --- resolution (uniform) -----------------------------------------------------------------------


async def resolve_link(token: str) -> LinkPrincipal | None:
    """The open link a token names, or None for unknown, expired, revoked, locked, an
    unregistered or dead purpose, or the platform control on (all the same to the caller)."""
    if not token or len(token) > 128:
        return None
    async with platform_transaction(_ACTOR) as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM link_principal_resolve(:t)"), {"t": sha256(token)}
            )
        ).first()
    if row is None:
        return None
    found = LinkPrincipal(
        row.tenant_id, row.principal_id, row.purpose, row.subject_id, bool(row.verified)
    )
    if await control_active(CONTROL, found.tenant_id):
        return None
    live = _PURPOSES.get(found.purpose)
    if live is None or not await live(
        TenantContext(found.tenant_id, "system", _ACTOR), found.subject_id
    ):
        return None
    return found


# --- the email code ------------------------------------------------------------------------------


async def request_code(token: str, email: str) -> None:
    """A challenge when the address is the link's; nothing tells the caller which (the route
    answers 202 after the floor either way)."""
    found = await resolve_link(token)
    if found is None:
        return
    async with platform_transaction(_ACTOR) as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM link_principal_challenge(:t, :e, :c, :r)"),
                {
                    "t": sha256(token),
                    "e": _email_key(email),
                    "c": CODE_SECONDS,
                    "r": RESEND_SECONDS,
                },
            )
        ).first()
    if row is None:
        return
    tenant = TenantContext(found.tenant_id, "system", _ACTOR)
    async with uow(tenant) as tx:
        tx.emit(LinkCodeRequested(challenge_id=row.challenge_id, principal_id=found.principal_id))
        tx.record(
            "link_principal.code_requested", target=Target("link_principal", found.principal_id)
        )


@dataclass(frozen=True)
class IssuedLinkCode:
    tenant_id: UUID
    principal_id: UUID
    code: str
    expires_at: datetime
    email_sealed: bytes


async def issue_link_code(challenge_id: UUID) -> IssuedLinkCode | None:
    """Communications, at delivery: a fresh code for a live challenge that has none yet."""
    code = issue_email_code()
    async with platform_transaction(_ACTOR) as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM link_principal_issue(:id, :salt, :digest)"),
                {"id": challenge_id, "salt": code.salt, "digest": code.digest},
            )
        ).first()
    if row is None:
        return None
    return IssuedLinkCode(
        row.tenant_id, row.principal_id, code.code, row.code_expires_at, bytes(row.email_sealed)
    )


@dataclass(frozen=True)
class Verified:
    credential: str  # the `__Host-` cookie value
    csrf: str
    expires_at: datetime


async def verify_code(token: str, code: str) -> Verified | None:
    """A right code mints the page credential; a wrong one counts, and the fifth locks the link
    for 15 minutes. None for every failure, so the caller answers them the same."""
    if await resolve_link(token) is None:
        return None
    async with platform_transaction(_ACTOR) as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM link_principal_attempt(:t, :m, :l)"),
                {"t": sha256(token), "m": MAX_TRIES, "l": LOCK_SECONDS},
            )
        ).first()
        if row is None or row.outcome != "ok":
            return None
        if not email_code_matches(bytes(row.code_salt), bytes(row.code_digest), code):
            await conn.execute(
                text("SELECT * FROM link_principal_missed(:p, :c, :m, :l)"),
                {"p": row.principal_id, "c": row.challenge_id, "m": MAX_TRIES, "l": LOCK_SECONDS},
            )
            return None
        credential, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        minted = (
            await conn.execute(
                text("SELECT * FROM link_principal_credential(:p, :c, :cred, :csrf, :s)"),
                {
                    "p": row.principal_id,
                    "c": row.challenge_id,
                    "cred": sha256(credential),
                    "csrf": sha256(csrf),
                    "s": CREDENTIAL_SECONDS,
                },
            )
        ).first()
    if minted is None:
        return None
    tenant = TenantContext(row.tenant_id, "system", _ACTOR)
    async with uow(tenant) as tx:
        tx.record("link_principal.verified", target=Target("link_principal", row.principal_id))
    return Verified(credential, csrf, minted.expires_at)


async def credential_principal(credential: str | None, csrf: str | None) -> LinkPrincipal | None:
    """The principal a page credential and its CSRF value prove (both, or nothing)."""
    if not credential or not csrf:
        return None
    async with platform_transaction(_ACTOR) as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM link_principal_credential_resolve(:c, :x)"),
                {"c": sha256(credential), "x": sha256(csrf)},
            )
        ).first()
    if row is None or await control_active(CONTROL, row.tenant_id):
        return None
    return LinkPrincipal(row.tenant_id, row.principal_id, row.purpose, row.subject_id, True)

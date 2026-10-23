"""Portal sign-in by emailed code, and the portal session (P-08-T10; ADR-168; DEC-155). PROTECTED.

Sign-in never says whether an email has an account. `start_sign_in` answers the same shape for
every email on every host, after the same minimum time, and writes a challenge either way; only a
challenge for an active client of the host's firm emits `portal.sign_in_code_requested`, and
communications then issues the code at delivery (`issue_sign_in_code`), so only its salted digest
is ever kept. Codes live 10 minutes; the third wrong code locks the host and email for 15
minutes; a resend waits 60 seconds and keeps the tries.

A verified code starts an `auth_sessions` row on the portal surface, pinned to the host's firm and
the host itself. The browser gets an opaque access token (15 minutes, kept in memory) and a
`__Host-` refresh cookie; both are stored only as SHA-256. A token is resolved only on the host it
was minted on (ADR-168 §3); another host gets exactly what no token gets.

Audit events are written in the firm only for a known person; an unknown email writes none.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._flags import PORTAL_SIGN_IN_V2
from abacus.kernel.db import TenantContext, platform_transaction
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.client_access import FULL_ROLES, active_grants
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import PortalSignInCodeRequested
from abacus.modules.identity.portal_idp import email_code_matches, issue_email_code
from abacus.modules.identity.repository import active_memberships
from abacus.modules.identity.service import portal_member_context
from abacus.modules.identity.staff_session import ABSOLUTE_SECONDS, IDLE_SECONDS, end_session

COOKIE_NAME: Final = "__Host-abacus-portal"
CODE_SECONDS: Final = 10 * 60
RESEND_SECONDS: Final = 60
MAX_TRIES: Final = 3
LOCK_SECONDS: Final = 15 * 60
ACCESS_SECONDS: Final = 15 * 60
# Every start answers after at least this long, so a known email can't be told by its timing.
START_FLOOR_SECONDS: Final = 0.35
# A portal access token is told from a provider JWT by its prefix: no dots, no claims.
PORTAL_MARK: Final = "pst_"
_MAX_TOKEN: Final = 64
_log = get_logger(__name__)


class CodeMismatch(Exception):
    def __init__(self, tries_left: int) -> None:
        super().__init__("code_mismatch")
        self.tries_left = tries_left


class SignInLocked(Exception):
    def __init__(self, locked_until: datetime) -> None:
        super().__init__("sign_in_locked")
        self.locked_until = locked_until


class CodeExpired(Exception):
    """The code is older than 10 minutes, or the challenge is used up or unknown."""


class ResendTooSoon(Exception):
    def __init__(self, resend_available_at: datetime) -> None:
        super().__init__("resend_too_soon")
        self.resend_available_at = resend_available_at


class PortalSessionEnded(Exception):
    """The refresh cookie names no live portal session on this host (or was reused)."""


@dataclass(frozen=True)
class Challenge:
    challenge_id: UUID
    code_expires_at: datetime
    resend_available_at: datetime


@dataclass(frozen=True)
class IssuedCode:
    """For communications only: the code goes in the email and nowhere else."""

    tenant_id: UUID
    user_id: UUID
    code: str
    expires_at: datetime


@dataclass(frozen=True)
class PortalTokens:
    access_token: str
    expires_in: int
    cookie: str
    landing: str
    session_id: UUID


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _access_token() -> str:
    return PORTAL_MARK + secrets.token_urlsafe(32)


def is_portal_token(token: str) -> bool:
    return token.startswith(PORTAL_MARK) and len(token) <= _MAX_TOKEN


def _host(host: str | None) -> str:
    """The request's host without a port; the empty string when absent (matches no domain)."""
    return (host or "").split(":", 1)[0].strip().lower()[:253]


async def _audit(
    tenant_id: UUID, user_id: UUID, action: str, target: Target, after: Ref | None = None
) -> None:
    async with uow(TenantContext(tenant_id, "human", str(user_id))) as tx:
        tx.record(action, target=target, after=after)


async def _requested(tenant_id: UUID, user_id: UUID, challenge_id: UUID) -> None:
    """The code email, only where the firm has the portal sign-in on (`portal.sign_in_v2`)."""
    if not await flag_enabled(
        TenantContext(tenant_id, "system", "portal:sign_in"), PORTAL_SIGN_IN_V2
    ):
        return
    async with uow(TenantContext(tenant_id, "human", str(user_id))) as tx:
        tx.record("portal_sign_in.code_requested", target=Target("user", user_id))
        tx.emit(PortalSignInCodeRequested(challenge_id=challenge_id))


async def start_sign_in(host: str | None, email: str) -> Challenge:
    """Always a challenge, for any email on any host (no oracle)."""
    began = time.monotonic()
    async with platform_transaction("portal:sign_in") as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM portal_sign_in_start(:host, :email, :code, :resend)"),
                {
                    "host": _host(host),
                    "email": email[:320],
                    "code": CODE_SECONDS,
                    "resend": RESEND_SECONDS,
                },
            )
        ).one()
    if row.user_id is not None and not row.locked:
        await _requested(cast(UUID, row.tenant_id), cast(UUID, row.user_id), row.challenge_id)
    left = START_FLOOR_SECONDS - (time.monotonic() - began)
    if left > 0:
        await asyncio.sleep(left)
    return Challenge(row.challenge_id, row.code_expires_at, row.resend_available_at)


async def resend_code(host: str | None, challenge_id: UUID) -> Challenge:
    """A new code; the old one is void and the tries are kept. 429 inside the 60 seconds."""
    async with platform_transaction("portal:sign_in") as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM portal_sign_in_resend(:id, :host, :code, :resend)"),
                {
                    "id": challenge_id,
                    "host": _host(host),
                    "code": CODE_SECONDS,
                    "resend": RESEND_SECONDS,
                },
            )
        ).one()
    if row.outcome == "unknown":
        raise CodeExpired
    if row.outcome == "too_soon":
        raise ResendTooSoon(row.resend_available_at)
    if row.user_id is not None and not row.locked:
        await _requested(cast(UUID, row.tenant_id), cast(UUID, row.user_id), challenge_id)
    return Challenge(challenge_id, row.code_expires_at, row.resend_available_at)


async def issue_sign_in_code(challenge_id: UUID) -> IssuedCode | None:
    """Communications, at delivery: a fresh code for a live challenge that has none yet; None when
    the challenge is used, expired, already issued or has no person (nothing to send)."""
    code = issue_email_code()
    async with platform_transaction("portal:sign_in") as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM portal_sign_in_issue(:id, :salt, :digest)"),
                {"id": challenge_id, "salt": code.salt, "digest": code.digest},
            )
        ).first()
    if row is None:
        return None
    return IssuedCode(
        cast(UUID, row.tenant_id), cast(UUID, row.user_id), code.code, row.code_expires_at
    )


def landing_of(roles: Iterable[str]) -> str:
    """P-08 Story 2.3 (SPEC-320 AC-8): where the role union lands after sign-in."""
    held = set(roles)
    if held & FULL_ROLES:
        return "home"
    if held and held <= {"k1_recipient"}:
        return "k1s"
    for role, landing in (
        ("third_party", "requests"),
        ("tcwg", "governance"),
        ("prospect", "intake"),
        ("component_auditor", "component_room"),
    ):
        if role in held:
            return landing
    return "none"


async def verify_code(host: str | None, challenge_id: UUID, code: str) -> PortalTokens:
    """The code against its challenge on this host; a session on success."""
    pinned = _host(host)
    async with platform_transaction("portal:sign_in") as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM portal_sign_in_check(:id, :host)"),
                {"id": challenge_id, "host": pinned},
            )
        ).first()
    if row is None:
        raise CodeExpired
    if row.locked_until is not None:
        raise SignInLocked(row.locked_until)
    if row.expired:
        raise CodeExpired
    matched = row.code_digest is not None and email_code_matches(
        bytes(row.code_salt), bytes(row.code_digest), code
    )
    tenant_id, user_id = cast(UUID | None, row.tenant_id), cast(UUID | None, row.user_id)
    if not matched:
        async with platform_transaction("portal:sign_in") as conn:
            failed = (
                await conn.execute(
                    text("SELECT * FROM portal_sign_in_fail(:id, :max, :lock)"),
                    {"id": challenge_id, "max": MAX_TRIES, "lock": LOCK_SECONDS},
                )
            ).first()
        if failed is None:
            raise CodeExpired
        if tenant_id is not None and user_id is not None:
            target = Target("user", user_id)
            await _audit(tenant_id, user_id, "portal_sign_in.failed", target)
            if failed.locked_until is not None:
                await _audit(tenant_id, user_id, "portal_sign_in.locked", target)
        if failed.locked_until is not None:
            raise SignInLocked(failed.locked_until)
        raise CodeMismatch(int(failed.tries_left))
    if tenant_id is None or user_id is None:  # a digest only exists for a known person
        raise CodeExpired
    access, cookie = _access_token(), secrets.token_urlsafe(32)
    async with platform_transaction(f"user:{user_id}") as conn:
        if not (
            await conn.execute(text("SELECT portal_sign_in_consume(:id)"), {"id": challenge_id})
        ).scalar_one():
            raise CodeExpired  # used by a concurrent verify
        session_id = cast(
            UUID,
            (
                await conn.execute(
                    text(
                        "SELECT portal_session_start(:user, :tenant, :host, :access, "
                        ":access_seconds, :cookie, :idle, :absolute)"
                    ),
                    {
                        "user": user_id,
                        "tenant": tenant_id,
                        "host": pinned,
                        "access": _sha(access),
                        "access_seconds": ACCESS_SECONDS,
                        "cookie": _sha(cookie),
                        "idle": IDLE_SECONDS,
                        "absolute": ABSOLUTE_SECONDS,
                    },
                )
            ).scalar_one(),
        )
    await _audit(tenant_id, user_id, "portal_sign_in.succeeded", Target("user", user_id))
    await _audit(tenant_id, user_id, "session.started", Target("auth_session", session_id))
    grants = await active_grants(TenantContext(tenant_id, "human", str(user_id)), user_id)
    landing = landing_of(g.role for g in grants)
    return PortalTokens(access, ACCESS_SECONDS, cookie, landing, session_id)


async def portal_context(token: str, host: str | None) -> AuthContext | None:
    """The person behind a portal access token on this host, or None (no session: 401)."""
    if not is_portal_token(token):
        return None
    async with platform_transaction("portal:session") as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM portal_session_resolve(:access, :host)"),
                {"access": _sha(token), "host": _host(host)},
            )
        ).first()
    if row is None:
        return None
    user_id, tenant_id = cast(UUID, row.user_id), cast(UUID, row.tenant_id)
    found = [
        m
        for m in await active_memberships(user_id)
        if m.tenant_id == tenant_id and m.kind == "client"
    ]
    if not found:
        return None  # the membership ended after sign-in
    return portal_member_context(user_id, found[0])


async def refresh_portal_session(cookie: str | None, host: str | None) -> PortalTokens:
    """Rotate the cookie and mint a new access token, on the session's own host only."""
    if not cookie or len(cookie) > 256:
        raise PortalSessionEnded
    access, next_cookie = _access_token(), secrets.token_urlsafe(32)
    async with platform_transaction("portal:refresh") as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT * FROM portal_session_rotate(:cookie, :next, :host, :access, "
                    ":access_seconds, :idle)"
                ),
                {
                    "cookie": _sha(cookie),
                    "next": _sha(next_cookie),
                    "host": _host(host),
                    "access": _sha(access),
                    "access_seconds": ACCESS_SECONDS,
                    "idle": IDLE_SECONDS,
                },
            )
        ).one()
    if row.outcome != "ok":
        if row.outcome in ("reused", "idle", "absolute"):
            reason = "reuse_detected" if row.outcome == "reused" else row.outcome
            action = "session.refresh_reused" if row.outcome == "reused" else "session.ended"
            await _audit(
                cast(UUID, row.tenant_id),
                cast(UUID, row.user_id),
                action,
                Target("auth_session", cast(UUID, row.session_id)),
                Ref(reason={"reuse_detected": 4, "idle": 2, "absolute": 3}[reason]),
            )
        raise PortalSessionEnded
    tenant_id, user_id = cast(UUID, row.tenant_id), cast(UUID, row.user_id)
    grants = await active_grants(TenantContext(tenant_id, "human", str(user_id)), user_id)
    return PortalTokens(
        access, ACCESS_SECONDS, next_cookie, landing_of(g.role for g in grants), row.session_id
    )


async def sign_out_portal(ctx: AuthContext, cookie: str | None) -> bool:
    """End the person's own session behind the cookie; its access token stops at once."""
    return await end_session(ctx.user_id, cookie)

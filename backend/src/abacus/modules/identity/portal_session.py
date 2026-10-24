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

A person the MFA floor covers (P-08-T17, `mfa_floor`) gets no session from the code alone: the
code's challenge is used and `SecondStepRequired` hands back a 5-minute single-use `mfa_token`
for the second step or its first-time setup (`portal_mfa`), unless a trusted device of theirs
for this firm is presented.

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
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import TextClause, text

from abacus.kernel._flags import PORTAL_SIGN_IN_V2
from abacus.kernel.db import TenantContext, platform_transaction
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.client_access import FULL_ROLES, active_grants
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import PortalSignInCodeRequested
from abacus.modules.identity.mfa_floor import mfa_required, portal_security_policy
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
MFA_TOKEN_SECONDS: Final = 5 * 60
# Every pre-session answer that a known email changes (start, resend, a wrong code) takes at
# least this long, so a known email can't be told by its timing.
FLOOR_SECONDS: Final = 0.5
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


class SecondStepRequired(Exception):
    """The code was right, and the MFA floor covers the person: no session yet. `mfa_token` is
    Restricted (single use, 5 minutes) and goes only into the response."""

    state: Literal["mfa_required", "mfa_setup_required"]

    def __init__(self, state: Literal["mfa_required", "mfa_setup_required"], token: str) -> None:
        super().__init__(state)
        self.state = state
        self.mfa_token = token


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


def sha256_hex(value: str) -> str:
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


async def _floor(began: float) -> None:
    """Pad an answer to the floor, so a known email's extra work can't be timed."""
    left = FLOOR_SECONDS - (time.monotonic() - began)
    if left > 0:
        await asyncio.sleep(left)


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
    if row.send:
        await _requested(cast(UUID, row.tenant_id), cast(UUID, row.user_id), row.challenge_id)
    await _floor(began)
    return Challenge(row.challenge_id, row.code_expires_at, row.resend_available_at)


async def resend_code(host: str | None, challenge_id: UUID) -> Challenge:
    """A new code; the old one is void and the tries are kept. 429 inside the 60 seconds."""
    began = time.monotonic()
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
    if row.send:
        await _requested(cast(UUID, row.tenant_id), cast(UUID, row.user_id), challenge_id)
    await _floor(began)
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


async def trusted_until(
    tenant_id: UUID, user_id: UUID, device_cookie: str | None
) -> datetime | None:
    """Until when the presented device cookie skips the second step for this person in this
    firm, under the firm's current days; None when it doesn't."""
    if not device_cookie or len(device_cookie) > 256:
        return None
    days = (await portal_security_policy(tenant_id)).trusted_device_days
    if days <= 0:
        return None
    async with platform_transaction("portal:mfa") as conn:
        return cast(
            datetime | None,
            (
                await conn.execute(
                    text("SELECT portal_device_check(:tenant, :user, :device, :days)"),
                    {
                        "tenant": tenant_id,
                        "user": user_id,
                        "device": sha256_hex(device_cookie),
                        "days": days,
                    },
                )
            ).scalar_one(),
        )


async def factor_enrolled(user_id: UUID) -> bool:
    """Whether the person has an enrolled second-step factor (`/v1/me.mfa.enrolled`)."""
    async with platform_transaction("portal:mfa") as conn:
        return bool(
            (
                await conn.execute(text("SELECT portal_mfa_enrolled(:user)"), {"user": user_id})
            ).scalar_one()
        )


async def _second_step_needed(
    tenant_id: UUID, user_id: UUID, device_cookie: str | None
) -> Literal["mfa_required", "mfa_setup_required"] | None:
    if not await mfa_required(tenant_id, user_id):
        return None
    if not await factor_enrolled(user_id):
        return "mfa_setup_required"
    if await trusted_until(tenant_id, user_id, device_cookie) is not None:
        return None
    return "mfa_required"


async def open_session(
    tenant_id: UUID,
    user_id: UUID,
    host: str,
    claim: TextClause,
    params: dict[str, object],
    *,
    previous_cookie: str | None = None,
    mfa: bool = False,
) -> PortalTokens | None:
    """A portal session for the person, pinned to the firm and host, in the same transaction as
    `claim` (which must answer true: the code's challenge or the second-step token, used once).
    None when the claim was already spent by a concurrent request."""
    access, cookie = _access_token(), secrets.token_urlsafe(32)
    async with platform_transaction(f"user:{user_id}") as conn:
        if not (await conn.execute(claim, params)).scalar_one():
            return None
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
                        "host": host,
                        "access": sha256_hex(access),
                        "access_seconds": ACCESS_SECONDS,
                        "cookie": sha256_hex(cookie),
                        "idle": IDLE_SECONDS,
                        "absolute": ABSOLUTE_SECONDS,
                    },
                )
            ).scalar_one(),
        )
        if mfa:
            await conn.execute(
                text("SELECT portal_session_mark_mfa(:id, :user)"),
                {"id": session_id, "user": user_id},
            )
    await _audit(tenant_id, user_id, "portal_sign_in.succeeded", Target("user", user_id))
    await _audit(tenant_id, user_id, "session.started", Target("auth_session", session_id))
    if previous_cookie is not None:  # a second sign-in in the same browser replaces the old one
        await end_session(user_id, previous_cookie, reason="revoked")
    grants = await active_grants(TenantContext(tenant_id, "human", str(user_id)), user_id)
    landing = landing_of(g.role for g in grants)
    return PortalTokens(access, ACCESS_SECONDS, cookie, landing, session_id)


async def verify_code(
    host: str | None,
    challenge_id: UUID,
    code: str,
    *,
    previous_cookie: str | None = None,
    device_cookie: str | None = None,
) -> PortalTokens:
    """The code against its challenge on this host; a session on success, or
    `SecondStepRequired` for a person the MFA floor covers. Each guess is counted before it is
    compared (`portal_sign_in_attempt`)."""
    began = time.monotonic()
    pinned = _host(host)
    async with platform_transaction("portal:sign_in") as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM portal_sign_in_attempt(:id, :host, :max, :lock)"),
                {"id": challenge_id, "host": pinned, "max": MAX_TRIES, "lock": LOCK_SECONDS},
            )
        ).one()
    if row.outcome == "locked":
        await _floor(began)
        raise SignInLocked(row.locked_until)
    if row.outcome != "ok":
        await _floor(began)
        raise CodeExpired
    matched = row.code_digest is not None and email_code_matches(
        bytes(row.code_salt), bytes(row.code_digest), code
    )
    tenant_id, user_id = cast(UUID | None, row.tenant_id), cast(UUID | None, row.user_id)
    if not matched:
        async with platform_transaction("portal:sign_in") as conn:
            locked_until = cast(
                datetime | None,
                (
                    await conn.execute(
                        text("SELECT portal_sign_in_missed(:id, :max, :lock)"),
                        {"id": challenge_id, "max": MAX_TRIES, "lock": LOCK_SECONDS},
                    )
                ).scalar_one(),
            )
        if tenant_id is not None and user_id is not None:
            target = Target("user", user_id)
            await _audit(tenant_id, user_id, "portal_sign_in.failed", target)
            if locked_until is not None:
                await _audit(tenant_id, user_id, "portal_sign_in.locked", target)
        await _floor(began)
        if locked_until is not None:
            raise SignInLocked(locked_until)
        raise CodeMismatch(int(row.tries_left))
    if tenant_id is None or user_id is None:  # a digest only exists for a known person
        raise CodeExpired
    step = await _second_step_needed(tenant_id, user_id, device_cookie)
    if step is not None:
        token = secrets.token_urlsafe(32)
        async with platform_transaction("portal:sign_in") as conn:
            begun = (
                await conn.execute(
                    text("SELECT portal_mfa_begin(:id, :token, :kind, :seconds)"),
                    {
                        "id": challenge_id,
                        "token": sha256_hex(token),
                        "kind": "verify" if step == "mfa_required" else "setup",
                        "seconds": MFA_TOKEN_SECONDS,
                    },
                )
            ).scalar_one()
        if not begun:
            raise CodeExpired  # used by a concurrent verify
        raise SecondStepRequired(step, token)
    tokens = await open_session(
        tenant_id,
        user_id,
        pinned,
        text("SELECT portal_sign_in_consume(:id)"),
        {"id": challenge_id},
        previous_cookie=previous_cookie,
    )
    if tokens is None:
        raise CodeExpired  # used by a concurrent verify
    return tokens


async def portal_context(token: str, host: str | None) -> AuthContext | None:
    """The person behind a portal access token on this host, or None (no session: 401)."""
    if not is_portal_token(token):
        return None
    async with platform_transaction("portal:session") as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM portal_session_resolve(:access, :host)"),
                {"access": sha256_hex(token), "host": _host(host)},
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
    if not await active_grants(TenantContext(tenant_id, "human", str(user_id)), user_id):
        return None  # every grant was revoked or expired after sign-in
    return portal_member_context(user_id, found[0], cast(UUID, row.session_id))


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
                    "cookie": sha256_hex(cookie),
                    "next": sha256_hex(next_cookie),
                    "host": _host(host),
                    "access": sha256_hex(access),
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
    """End the person's own session: the one their access token resolved to (its token stops at
    once), and the cookie's if it names another."""
    ended = None
    if ctx.portal_session_id is not None:
        async with platform_transaction(f"user:{ctx.user_id}") as conn:
            ended = (
                await conn.execute(
                    text("SELECT portal_session_end_id(:id, :user)"),
                    {"id": ctx.portal_session_id, "user": ctx.user_id},
                )
            ).scalar_one()
    if ended is not None:
        await _audit(
            ctx.tenant_id,
            ctx.user_id,
            "session.ended",
            Target("auth_session", ended),
            Ref(reason=1),
        )
    by_cookie = await end_session(ctx.user_id, cookie)
    return ended is not None or by_cookie

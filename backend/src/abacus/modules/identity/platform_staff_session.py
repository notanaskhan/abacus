"""The console BFF: Accrued platform staff sessions (G-04-T14; TASK-8548; DEC-5532). PROTECTED.

The firm BFF's shape (staff_session.py; ADR-141, ADR-165) on the *staff* issuer. Sign-in runs
authorization code with PKCE on the server: `begin_sign_in` keeps the verifier and a safe return
path under the SHA-256 of `state` (0101's `auth_state_put`); `complete_sign_in` exchanges the code,
verifies the access token with the staff verifier, refuses a session without a second factor or
without a console role (`platform_admin`, `platform_support_desk`), and starts a
`platform_staff_sessions` row (0969). The provider's refresh token is sealed with the platform key.

The browser holds one opaque `__Host-abacus-console` cookie, stored only as a SHA-256 and rotated
on every refresh; a rotated-out value presented again is reuse and ends the session. Sessions end
after 30 minutes idle or 12 hours in all (DEC-140). Every refresh re-verifies the same staff
subject with MFA and a console role; anything else ends the session. Platform staff are never firm
members (ADR-028): no firm is touched, and the session's audit events go to the platform trail,
identifiers only.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Final, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import text

from abacus.kernel.config import settings
from abacus.kernel.crypto import DecryptionError, open_sealed, seal
from abacus.kernel.db import TenantContext, platform_transaction
from abacus.kernel.errors import ServiceUnavailable
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.staff_session import (
    ABSOLUTE_SECONDS,
    END_REASONS,
    IDLE_SECONDS,
    OidcStaffIdp,
    ProviderRefused,
    RefreshReused,
    SessionExpired,
    SignInRefused,
    StaffIdp,
    safe_return_to,
)
from abacus.modules.identity.tokens import InvalidToken, VerifiedIdentity, staff_verifier

COOKIE_NAME: Final = "__Host-abacus-console"
CALLBACK_PATH: Final = "/v1/platform/auth/callback"
SPA_CALLBACK_PATH: Final = "/signin/callback"
CONSOLE_ROLES: Final = frozenset({"platform_admin", "platform_support_desk"})
_PLATFORM: Final = UUID(int=0)
_REFRESH_FINGERPRINT: Final = "platform_staff_session.provider_refresh"
_REFUSALS: Final = {"mfa_required_at_sign_in": 1, "sign_in_failed": 3, "no_console_role": 5}
_log = get_logger(__name__)

_idp: StaffIdp | None = None


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def configure_platform_staff_idp(idp: StaffIdp | None) -> None:
    """Local runs and tests only: an in-process staff provider (None resets to settings)."""
    if settings().environment not in ("local", "test"):
        raise RuntimeError("configure_platform_staff_idp is for local runs and tests only")
    global _idp
    _idp = idp


def platform_staff_idp() -> StaffIdp:
    if _idp is not None:
        return _idp
    s = settings()
    if (
        s.platform_staff_client_id is None
        or s.platform_staff_authorize_url is None
        or s.platform_staff_exchange_url is None
    ):
        raise ServiceUnavailable("console sign-in is not configured")
    return OidcStaffIdp(
        client_id=s.platform_staff_client_id,
        authorize_url=s.platform_staff_authorize_url,
        token_url=s.platform_staff_exchange_url,
    )


def console_origin() -> str:
    origin = settings().console_origin
    if origin is None:
        raise ServiceUnavailable("console sign-in is not configured")
    return origin.rstrip("/")


def staff_id_of(identity: VerifiedIdentity) -> UUID:
    """The staff member's stable id, as `support.staff_from_token` derives it."""
    return uuid5(NAMESPACE_URL, f"{identity.issuer}#{identity.subject}")


def _console_staff(identity: VerifiedIdentity) -> bool:
    return identity.mfa_at is not None and bool(identity.platform_roles & CONSOLE_ROLES)


async def begin_sign_in(return_to: str | None, *, reauthenticate: bool = False) -> str:
    """Where to send the browser: the staff provider's authorize page, fresh state and PKCE."""
    idp = platform_staff_idp()
    redirect_uri = console_origin() + CALLBACK_PATH
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    async with platform_transaction("console:sign_in") as conn:
        await conn.execute(
            text("SELECT auth_state_put(:state, :verifier, :return_to)"),
            {
                "state": _digest(state),
                "verifier": verifier,
                "return_to": safe_return_to(return_to),
            },
        )
    return idp.authorize_url(
        state=state,
        challenge=_s256(verifier),
        redirect_uri=redirect_uri,
        reauthenticate=reauthenticate,
    )


@dataclass(frozen=True)
class StartedConsoleSession:
    cookie: str
    return_to: str
    session_id: UUID


async def complete_sign_in(
    code: str | None, state: str | None, *, previous_cookie: str | None = None
) -> StartedConsoleSession:
    """Every failure is a `SignInRefused`; the state is single use either way."""
    if not code or not state or len(code) > 2048 or len(state) > 256:
        raise SignInRefused("sign_in_failed")
    async with platform_transaction("console:callback") as conn:
        taken = (
            await conn.execute(
                text("SELECT * FROM auth_state_take(:state)"), {"state": _digest(state)}
            )
        ).first()
    if taken is None:
        raise SignInRefused("sign_in_failed")
    try:
        tokens = await platform_staff_idp().exchange(
            code=code,
            verifier=str(taken.code_verifier),
            redirect_uri=console_origin() + CALLBACK_PATH,
        )
        identity = staff_verifier().verify(tokens.access_token)
    except (ProviderRefused, InvalidToken):
        await _refused(None, "sign_in_failed")
        raise SignInRefused("sign_in_failed") from None
    staff_id = staff_id_of(identity)
    if identity.mfa_at is None:
        await _refused(staff_id, "mfa_required_at_sign_in")
        raise SignInRefused("mfa_required_at_sign_in")
    if not identity.platform_roles & CONSOLE_ROLES:
        await _refused(staff_id, "no_console_role")
        raise SignInRefused("no_console_role")
    if previous_cookie is not None:  # a second sign-in replaces the session behind the old cookie
        await end_session(previous_cookie, reason="revoked")
    cookie = secrets.token_urlsafe(32)
    sealed = (
        await seal(_PLATFORM, tokens.refresh_token.encode(), _REFRESH_FINGERPRINT)
        if tokens.refresh_token is not None
        else None
    )
    async with platform_transaction(f"staff:{staff_id}") as conn:
        session_id = cast(
            UUID,
            (
                await conn.execute(
                    text(
                        "SELECT platform_staff_session_start(:issuer, :subject, :refresh, "
                        ":mfa_at, :cookie, :idle, :absolute)"
                    ),
                    {
                        "issuer": identity.issuer,
                        "subject": identity.subject,
                        "refresh": sealed,
                        "mfa_at": identity.mfa_at,
                        "cookie": _digest(cookie),
                        "idle": IDLE_SECONDS,
                        "absolute": ABSOLUTE_SECONDS,
                    },
                )
            ).scalar_one(),
        )
    await _audit(staff_id, "session.started", session_id)
    return StartedConsoleSession(cookie, str(taken.return_to), session_id)


@dataclass(frozen=True)
class RefreshedConsoleSession:
    cookie: str
    access_token: str
    expires_in: int
    identity: VerifiedIdentity


async def refresh_session(cookie: str | None, *, active: bool = False) -> RefreshedConsoleSession:
    """Rotate the cookie and hand back a fresh staff access token from the provider. Only a
    refresh the person's own activity caused (`active`) moves the idle clock."""
    if not cookie or len(cookie) > 256:
        raise SessionExpired
    next_cookie = secrets.token_urlsafe(32)
    async with platform_transaction("console:refresh") as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT * FROM platform_staff_session_rotate(:cookie, :next, :idle, :active)"
                ),
                {
                    "cookie": _digest(cookie),
                    "next": _digest(next_cookie),
                    "idle": IDLE_SECONDS,
                    "active": active,
                },
            )
        ).one()
    if row.outcome == "unknown" or row.outcome == "ended":
        raise SessionExpired
    session_id = cast(UUID, row.session_id)
    staff_id = uuid5(NAMESPACE_URL, f"{row.staff_issuer}#{row.staff_subject}")
    if row.outcome == "reused":
        await _audit(staff_id, "session.refresh_reused", session_id)
        raise RefreshReused
    if row.outcome in ("idle", "absolute"):
        await _audit(staff_id, "session.ended", session_id, reason=str(row.outcome))
        raise SessionExpired
    if row.outcome != "ok" or row.provider_refresh_enc is None:
        raise SessionExpired
    try:
        refresh_token = (
            await open_sealed(_PLATFORM, bytes(row.provider_refresh_enc), _REFRESH_FINGERPRINT)
        ).decode()
        tokens = await platform_staff_idp().refresh(refresh_token)
        identity = staff_verifier().verify(tokens.access_token)
        if (identity.issuer, identity.subject) != (row.staff_issuer, row.staff_subject):
            raise ProviderRefused("identity changed")
        if not _console_staff(identity):
            raise ProviderRefused("no longer console staff")
    except (ProviderRefused, InvalidToken, DecryptionError):
        await _revoke(session_id, staff_id)
        raise SessionExpired from None
    if tokens.refresh_token is not None and tokens.refresh_token != refresh_token:
        sealed = await seal(_PLATFORM, tokens.refresh_token.encode(), _REFRESH_FINGERPRINT)
        async with platform_transaction(f"staff:{staff_id}") as conn:
            await conn.execute(
                text("SELECT platform_staff_session_set_refresh(:id, :refresh)"),
                {"id": session_id, "refresh": sealed},
            )
    return RefreshedConsoleSession(next_cookie, tokens.access_token, tokens.expires_in, identity)


async def end_session(cookie: str | None, *, reason: str = "sign_out") -> bool:
    """End the session behind this (live) cookie. False if there was none; signing out is still
    a success."""
    if not cookie or len(cookie) > 256:
        return False
    async with platform_transaction("console:sign_out") as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM platform_staff_session_end(:cookie, :reason)"),
                {"cookie": _digest(cookie), "reason": reason},
            )
        ).first()
    if row is None:
        return False
    if row.provider_refresh_enc is not None:
        try:
            refresh_token = await open_sealed(
                _PLATFORM, bytes(row.provider_refresh_enc), _REFRESH_FINGERPRINT
            )
            await platform_staff_idp().revoke(refresh_token.decode())
        except (DecryptionError, ServiceUnavailable, ProviderRefused) as exc:
            # The row has ended, so the cookie no longer works; the provider session times out.
            _log.warning("console.provider_revoke_failed", error=type(exc).__name__)
    session_id = cast(UUID, row.session_id)
    await _audit(
        uuid5(NAMESPACE_URL, f"{row.staff_issuer}#{row.staff_subject}"),
        "session.ended",
        session_id,
        reason=reason,
    )
    return True


async def _revoke(session_id: UUID, staff_id: UUID) -> None:
    async with platform_transaction(f"staff:{staff_id}") as conn:
        await conn.execute(text("SELECT platform_staff_session_revoke(:id)"), {"id": session_id})
    await _audit(staff_id, "session.ended", session_id, reason="revoked")


async def _audit(
    staff_id: UUID, action: str, session_id: UUID, *, reason: str | None = None
) -> None:
    """The platform trail only: a platform staff member is no firm's member (ADR-028)."""
    after = Ref(reason=END_REASONS[reason]) if reason is not None else None
    async with uow(TenantContext(_PLATFORM, "support", f"staff:{staff_id}")) as tx:
        tx.record(action, target=Target("auth_session", session_id), after=after)


async def _refused(staff_id: UUID | None, code: str) -> None:
    """`auth.sign_in_refused`, to the platform: identifier-only facts, no session to name."""
    async with uow(TenantContext(_PLATFORM, "system", "console:callback")) as tx:
        tx.record(
            "auth.sign_in_refused",
            target=Target("user", staff_id or _PLATFORM),
            after=Ref(reason=_REFUSALS[code]),
        )

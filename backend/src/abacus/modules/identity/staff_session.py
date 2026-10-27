"""The staff session behind the BFF (P-01-T09; ADR-141, ADR-165; DEC-140). PROTECTED.

The browser never holds a refresh token. Sign-in runs authorization code with PKCE on the
server: `begin_sign_in` keeps the verifier and safe return path under the SHA-256 of `state`, and
`complete_sign_in` exchanges the code, verifies the access token like any bearer token, refuses
a session without a second factor (FTC Safeguards 314.4(c)(5)) or for someone with no account,
and starts an `auth_sessions` row. The provider's refresh token is sealed with the platform key.

The browser holds one opaque `__Host-` cookie, stored only as a SHA-256. Each refresh rotates it.
A rotated-out value presented again is reuse, and the whole session ends (AC 5.1.4). Sessions end
after 30 minutes idle or 12 hours in all (DEC-140), or sooner when one of the person's firms set
shorter limits (G-02-T14, DEC-524: the strictest of their firms, checked at sign-in and every
refresh); no workflow runs. A firm that requires SSO refuses any other sign-in method, except a
passkey sign-in by its one SSO-exempt account (AC-15, AC-18), whose sign-in stamps "last tested".

Session audit events go to every firm the person is an active member of, because a session spans
memberships; with none, to the platform. Facts are identifiers only.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Final, Protocol, cast
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy import text

from abacus.kernel.config import settings
from abacus.kernel.crypto import DecryptionError, open_sealed, seal
from abacus.kernel.db import TenantContext, platform_transaction
from abacus.kernel.errors import ServiceUnavailable
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.repository import active_memberships, find_user
from abacus.modules.identity.security_policies import (
    AUTH_METHODS,
    StaffLimits,
    record_exempt_sign_in,
    signed_out_everywhere,
    staff_limits,
)
from abacus.modules.identity.tokens import InvalidToken, VerifiedIdentity, token_verifier

COOKIE_NAME: Final = "__Host-abacus-session"
CSRF_HEADER: Final = "X-Abacus-CSRF"
CALLBACK_PATH: Final = "/v1/auth/callback"
SPA_CALLBACK_PATH: Final = "/signin/callback"
IDLE_SECONDS: Final = 30 * 60  # DEC-140
ABSOLUTE_SECONDS: Final = 12 * 60 * 60  # DEC-140
PROVIDER: Final = "oidc"
MAX_RETURN_TO: Final = 512
_PLATFORM: Final = UUID(int=0)
_REFRESH_FINGERPRINT: Final = "auth_session.provider_refresh"
_HTTP_TIMEOUT: Final = 10.0
# Audit references carry integers, never text (kernel.uow.Ref).
END_REASONS: Final = {"sign_out": 1, "idle": 2, "absolute": 3, "reuse_detected": 4, "revoked": 5}
REFUSALS: Final = {
    "mfa_required_at_sign_in": 1,
    "unknown_staff_user": 2,
    "sign_in_failed": 3,
    "sso_required": 4,
}
# How WorkOS names the method a person used (its authenticate response), as `auth_sessions`
# records it; anything else is unknown (None), which never passes an SSO requirement.
_PROVIDER_METHODS: Final = {
    "sso": "sso",
    "magicauth": "email_code",
    "magic_auth": "email_code",
    "email_code": "email_code",
    "passkey": "passkey",
    "totp": "totp",
}
_log = get_logger(__name__)


class SignInRefused(Exception):
    """The callback can't start a session; `code` is what the sign-in page shows."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SessionExpired(Exception):
    """No live session behind this cookie (unknown, ended, idle or past its absolute limit)."""


class RefreshReused(Exception):
    """A rotated-out cookie came back: the session has been ended (AC 5.1.4)."""


@dataclass(frozen=True)
class ProviderTokens:
    access_token: str
    expires_in: int
    refresh_token: str | None
    # How the person signed in, when the provider says (`sso`, `email_code`, `passkey`, `totp`).
    auth_method: str | None = None
    # The organisation whose connection the person signed in through (WorkOS
    # `organization_id`), when the provider says: Require SSO matches it to the firm's own.
    organization_id: str | None = None


def _org_of(reported: object) -> str | None:
    """A provider organisation id as `auth_sessions.idp_org`: an identifier, at most 128."""
    if not isinstance(reported, str):
        return None
    org = reported.strip()
    return org if 0 < len(org) <= 128 and org.isascii() and org.isprintable() else None


def auth_method_of(reported: object) -> str | None:
    """The provider's method name as `auth_sessions.auth_method`, or None when unknown."""
    if not isinstance(reported, str):
        return None
    method = _PROVIDER_METHODS.get(reported.strip().lower())
    return method if method in AUTH_METHODS else None


class StaffIdp(Protocol):
    """The identity provider's half of the BFF. The generic OIDC client below serves the local
    fake; the WorkOS adapter (Q-01-T17) adds its session revoke."""

    def authorize_url(
        self, *, state: str, challenge: str, redirect_uri: str, reauthenticate: bool
    ) -> str: ...

    async def exchange(self, *, code: str, verifier: str, redirect_uri: str) -> ProviderTokens: ...

    async def refresh(self, refresh_token: str) -> ProviderTokens: ...

    async def revoke(self, refresh_token: str) -> None: ...


class ProviderRefused(Exception):
    """The provider answered, and said no (an invalid grant or refresh token)."""


class OidcStaffIdp:
    """Authorization code with PKCE (S256) and the refresh grant, as a public client."""

    def __init__(self, *, client_id: str, authorize_url: str, token_url: str) -> None:
        self._client_id = client_id
        self._authorize_url = authorize_url
        self._token_url = token_url

    def authorize_url(
        self, *, state: str, challenge: str, redirect_uri: str, reauthenticate: bool
    ) -> str:
        query = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": "openid email offline_access",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        if reauthenticate:
            query["prompt"] = "login"  # step-up (AC 5.1.5)
        return f"{self._authorize_url}?{urlencode(query)}"

    async def exchange(self, *, code: str, verifier: str, redirect_uri: str) -> ProviderTokens:
        return await self._token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": redirect_uri,
            }
        )

    async def refresh(self, refresh_token: str) -> ProviderTokens:
        return await self._token({"grant_type": "refresh_token", "refresh_token": refresh_token})

    async def revoke(self, refresh_token: str) -> None:
        """Plain OIDC has no session revoke; ending our row is enough for the local fake."""

    async def _token(self, form: dict[str, str]) -> ProviderTokens:
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                response = await client.post(
                    self._token_url, data={**form, "client_id": self._client_id}
                )
        except httpx.HTTPError as exc:
            raise ServiceUnavailable("identity provider unreachable") from exc
        if response.status_code in (400, 401):
            raise ProviderRefused(form["grant_type"])
        if response.status_code != 200:
            raise ServiceUnavailable("identity provider error")
        body = cast(object, response.json())
        if not isinstance(body, dict):
            raise ServiceUnavailable("identity provider answered badly")
        fields = cast(dict[str, object], body)
        access, expires, refresh = (
            fields.get("access_token"),
            fields.get("expires_in"),
            fields.get("refresh_token"),
        )
        if not isinstance(access, str) or isinstance(expires, bool):
            raise ServiceUnavailable("identity provider answered badly")
        if not isinstance(expires, int):
            raise ServiceUnavailable("identity provider answered badly")
        return ProviderTokens(
            access,
            expires,
            refresh if isinstance(refresh, str) else None,
            auth_method_of(fields.get("authentication_method")),
            _org_of(fields.get("organization_id")),
        )


_idp: StaffIdp | None = None


def configure_staff_idp(idp: StaffIdp | None) -> None:
    """Local runs and tests only: an in-process provider (None resets to settings)."""
    if settings().environment not in ("local", "test"):
        raise RuntimeError("configure_staff_idp is for local runs and tests only")
    global _idp
    _idp = idp


def staff_idp() -> StaffIdp:
    if _idp is not None:
        return _idp
    s = settings()
    if s.identity_client_id is None or s.identity_authorize_url is None:
        raise ServiceUnavailable("staff sign-in is not configured")
    if s.identity_exchange_url is None:
        raise ServiceUnavailable("staff sign-in is not configured")
    return OidcStaffIdp(
        client_id=s.identity_client_id,
        authorize_url=s.identity_authorize_url,
        token_url=s.identity_exchange_url,
    )


def web_origin() -> str:
    origin = settings().web_origin
    if origin is None:
        raise ServiceUnavailable("staff sign-in is not configured")
    return origin.rstrip("/")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def safe_return_to(value: str | None) -> str:
    """A same-origin path, or `/`: never another host (`//x`, `/\\x`), never control characters."""
    if (
        value is None
        or not value.startswith("/")
        or value.startswith(("//", "/\\"))
        or len(value) > MAX_RETURN_TO
        or any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value)
    ):
        return "/"
    return value


async def begin_sign_in(return_to: str | None, *, reauthenticate: bool = False) -> str:
    """Where to send the browser: the provider's authorize page, with fresh state and PKCE."""
    idp = staff_idp()
    redirect_uri = web_origin() + CALLBACK_PATH
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    async with platform_transaction("auth:sign_in") as conn:
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
class StartedSession:
    cookie: str
    return_to: str
    session_id: UUID


async def complete_sign_in(
    code: str | None, state: str | None, *, previous_cookie: str | None = None
) -> StartedSession:
    """AC 5.1.2. Every failure is a `SignInRefused`; the state is single use either way."""
    if not code or not state or len(code) > 2048 or len(state) > 256:
        raise SignInRefused("sign_in_failed")
    async with platform_transaction("auth:callback") as conn:
        taken = (
            await conn.execute(
                text("SELECT * FROM auth_state_take(:state)"), {"state": _digest(state)}
            )
        ).first()
    if taken is None:
        raise SignInRefused("sign_in_failed")
    idp = staff_idp()
    try:
        tokens = await idp.exchange(
            code=code, verifier=str(taken.code_verifier), redirect_uri=web_origin() + CALLBACK_PATH
        )
        identity = token_verifier().verify(tokens.access_token)
    except (ProviderRefused, InvalidToken):
        raise SignInRefused("sign_in_failed") from None
    user = await find_user(identity.issuer, identity.subject)
    if user is None:
        await _refused(None, "unknown_staff_user")
        raise SignInRefused("unknown_staff_user")
    if identity.mfa_at is None:
        await _refused(user.id, "mfa_required_at_sign_in")
        raise SignInRefused("mfa_required_at_sign_in")
    limits = await staff_limits(user.id)
    if limits.refuses(tokens.auth_method, tokens.organization_id):
        await _refused(user.id, "sso_required")
        raise SignInRefused("sso_required")
    if previous_cookie is not None:  # step-up or a second sign-in replaces the old session
        await end_session(user.id, previous_cookie, reason="revoked")
    cookie = secrets.token_urlsafe(32)
    sealed = (
        await seal(_PLATFORM, tokens.refresh_token.encode(), _REFRESH_FINGERPRINT)
        if tokens.refresh_token is not None
        else None
    )
    async with platform_transaction(f"user:{user.id}") as conn:
        session_id = cast(
            UUID,
            (
                await conn.execute(
                    text(
                        "SELECT auth_session_start(:user_id, :provider, :refresh, :mfa_at, "
                        ":cookie, :idle, :absolute, :method, :org)"
                    ),
                    {
                        "user_id": user.id,
                        "provider": PROVIDER,
                        "refresh": sealed,
                        "mfa_at": identity.mfa_at,
                        "cookie": _digest(cookie),
                        "idle": limits.idle_seconds,
                        "absolute": limits.absolute_seconds,
                        "method": tokens.auth_method,
                        "org": tokens.organization_id,
                    },
                )
            ).scalar_one(),
        )
    await _audit(user.id, "session.started", session_id)
    if limits.exempt_in:
        await record_exempt_sign_in(user.id, limits.exempt_in)
    return StartedSession(cookie, str(taken.return_to), session_id)


@dataclass(frozen=True)
class RefreshedSession:
    cookie: str
    access_token: str
    expires_in: int
    identity: VerifiedIdentity


async def refresh_session(cookie: str | None, *, active: bool = False) -> RefreshedSession:
    """AC 5.1.4: rotate the cookie and hand back a fresh access token from the provider. Only a
    refresh the person's own activity caused (`active`) moves the idle clock (G-02-T14, security
    review M3); a session signed out of every firm it could act in gets none (H1)."""
    if not cookie or len(cookie) > 256:
        raise SessionExpired
    next_cookie = secrets.token_urlsafe(32)
    async with platform_transaction("auth:refresh") as conn:
        owner = await conn.scalar(
            text("SELECT auth_session_owner(:cookie)"), {"cookie": _digest(cookie)}
        )
    limits = await staff_limits(cast(UUID, owner)) if owner is not None else StaffLimits()
    async with platform_transaction("auth:refresh") as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT * FROM auth_session_rotate(:cookie, :next, :idle, :absolute, :active)"
                ),
                {
                    "cookie": _digest(cookie),
                    "next": _digest(next_cookie),
                    "idle": limits.idle_seconds,
                    "absolute": limits.absolute_seconds,
                    "active": active,
                },
            )
        ).one()
    if row.outcome == "reused":
        await _audit(cast(UUID, row.user_id), "session.refresh_reused", cast(UUID, row.session_id))
        raise RefreshReused
    if row.outcome in ("idle", "absolute"):
        user_id = cast(UUID, row.user_id)
        await _audit(user_id, "session.ended", cast(UUID, row.session_id), reason=row.outcome)
        raise SessionExpired
    if row.outcome != "ok" or row.provider_refresh_enc is None:
        raise SessionExpired
    session_id, user_id = cast(UUID, row.session_id), cast(UUID, row.user_id)
    if user_id != owner or limits.refuses(
        cast(str | None, row.auth_method), cast(str | None, row.idp_org)
    ):
        # SSO is now required where this session's method no longer passes (AC-15).
        await _revoke(session_id, user_id)
        raise SessionExpired
    if await signed_out_everywhere(user_id, session_id):
        # Signed out of every firm the person is staff of: nothing left to mint a token for.
        await _revoke(session_id, user_id)
        raise SessionExpired
    try:
        refresh_token = (
            await open_sealed(_PLATFORM, bytes(row.provider_refresh_enc), _REFRESH_FINGERPRINT)
        ).decode()
        tokens = await staff_idp().refresh(refresh_token)
        identity = token_verifier().verify(tokens.access_token)
        user = await find_user(identity.issuer, identity.subject)
        if user is None or user.id != user_id or identity.mfa_at is None:
            raise ProviderRefused("identity changed")
    except (ProviderRefused, InvalidToken, DecryptionError):
        await _revoke(session_id, user_id)
        raise SessionExpired from None
    if tokens.refresh_token is not None and tokens.refresh_token != refresh_token:
        sealed = await seal(_PLATFORM, tokens.refresh_token.encode(), _REFRESH_FINGERPRINT)
        async with platform_transaction(f"user:{user_id}") as conn:
            await conn.execute(
                text("SELECT auth_session_set_refresh(:id, :refresh)"),
                {"id": session_id, "refresh": sealed},
            )
    return RefreshedSession(next_cookie, tokens.access_token, tokens.expires_in, identity)


async def end_session(user_id: UUID, cookie: str | None, *, reason: str = "sign_out") -> bool:
    """AC 2.1.6: end the signed-in person's own session behind this cookie. False if there was
    none (no cookie, someone else's, or already ended); signing out is still a success."""
    if not cookie or len(cookie) > 256:
        return False
    async with platform_transaction(f"user:{user_id}") as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM auth_session_end(:cookie, :reason, :user_id)"),
                {"cookie": _digest(cookie), "reason": reason, "user_id": user_id},
            )
        ).first()
    if row is None:
        return False
    if row.provider_refresh_enc is not None:
        try:
            refresh_token = await open_sealed(
                _PLATFORM, bytes(row.provider_refresh_enc), _REFRESH_FINGERPRINT
            )
            await staff_idp().revoke(refresh_token.decode())
        except (DecryptionError, ServiceUnavailable, ProviderRefused) as exc:
            # The row has ended, so the cookie no longer works; the provider session times out.
            _log.warning("auth.provider_revoke_failed", error=type(exc).__name__)
    await _audit(user_id, "session.ended", cast(UUID, row.session_id), reason=reason)
    return True


async def _revoke(session_id: UUID, user_id: UUID) -> None:
    async with platform_transaction(f"user:{user_id}") as conn:
        await conn.execute(text("SELECT auth_session_revoke(:id)"), {"id": session_id})
    await _audit(user_id, "session.ended", session_id, reason="revoked")


async def _audit(
    user_id: UUID, action: str, session_id: UUID, *, reason: str | None = None
) -> None:
    after = Ref(reason=END_REASONS[reason]) if reason is not None else None
    tenants = sorted({m.tenant_id for m in await active_memberships(user_id)}) or [_PLATFORM]
    for tenant_id in tenants:
        actor = TenantContext(tenant_id, "human", str(user_id))
        async with uow(actor) as tx:
            tx.record(action, target=Target("auth_session", session_id), after=after)


async def _refused(user_id: UUID | None, code: str) -> None:
    """`auth.sign_in_refused`, to the platform: identifier-only facts, no session to name."""
    async with uow(TenantContext(_PLATFORM, "system", "auth:callback")) as tx:
        tx.record(
            "auth.sign_in_refused",
            target=Target("user", user_id or _PLATFORM),
            after=Ref(reason=REFUSALS[code]),
        )

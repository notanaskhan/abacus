"""The portal's identity provider port (P-08-T06; DEC-22, P-08 R1, DEC-155). PROTECTED.

WorkOS holds a portal client's user record and their TOTP factor. It never sends a client an
email: its Magic Auth call emails a WorkOS-branded code and cannot be told not to, so the portal
issues its own sign-in codes (`issue_email_code`, hash only) and the firm-branded email goes out
through SES (P-08-T10 stores the challenge and sends it). No code in this module, or anywhere in
`abacus`, calls Magic Auth; a unit test scans for it.

- `WorkOsPortalIdp`: the WorkOS SDK, its blocking calls run in a thread.
- `InMemoryPortalIdp`: local runs and tests, with real RFC 6238 codes so a test can compute the
  code an authenticator app would show. F-04-T27's WorkOS fake conforms to the same port, and
  `tests/contracts/portal_idp/` runs against each.

A factor's issuer is the firm's display name, never "Accrued" (ADR-163 §7).
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import secrets
import struct
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final, Protocol
from urllib.parse import quote
from uuid import uuid4

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings

CODE_DIGITS: Final = 6
TOTP_STEP_SECONDS: Final = 30
TOTP_WINDOW: Final = 1  # one step either side, for clock drift
_SALT_BYTES: Final = 16


class PortalIdpUnavailable(Exception):
    """The provider didn't answer or isn't configured; the caller answers 503 and logs the type."""


@dataclass(frozen=True)
class TotpEnrolment:
    """What POR-01's MFA setup step shows once: the secret, as a QR code and as text, and the
    factor to keep. The secret is Restricted: never logged, never stored by the portal."""

    factor_id: str
    secret: str
    otpauth_uri: str


class PortalIdp(Protocol):
    async def upsert_user(self, email: str, *, name: str | None = None) -> str:
        """The provider's user id for this email, creating the user the first time."""
        ...

    async def enrol_totp(self, user_id: str, *, issuer: str, account: str) -> TotpEnrolment: ...

    async def challenge(self, factor_id: str) -> str:
        """A single-use challenge id for the factor."""
        ...

    async def verify(self, challenge_id: str, code: str) -> bool: ...

    async def remove_factor(self, factor_id: str) -> None:
        """Gone, whether or not it existed (the MFA reset, Story 7.2)."""
        ...


# --- email sign-in codes (own OTP) -------------------------------------------------------------


@dataclass(frozen=True)
class EmailCode:
    """A sign-in code: `code` goes in the email and nowhere else; `salt` and `digest` are kept."""

    code: str
    salt: bytes
    digest: bytes


def _digest(salt: bytes, code: str) -> bytes:
    return hmac.new(salt, code.encode(), hashlib.sha256).digest()


def issue_email_code() -> EmailCode:
    code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
    salt = secrets.token_bytes(_SALT_BYTES)
    return EmailCode(code, salt, _digest(salt, code))


def email_code_matches(salt: bytes, digest: bytes, offered: str) -> bool:
    """Constant time; anything but six digits is a miss. Attempts and expiry are the caller's."""
    if len(offered) != CODE_DIGITS or not offered.isdigit():
        return False
    return hmac.compare_digest(_digest(salt, offered), digest)


# --- TOTP (RFC 6238, for the in-memory provider and tests) --------------------------------------


def totp_at(secret: str, unix_seconds: float) -> str:
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    counter = struct.pack(">Q", int(unix_seconds // TOTP_STEP_SECONDS))
    mac = hmac.new(key, counter, hashlib.sha1).digest()  # RFC 6238 default; authenticator apps
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 10**CODE_DIGITS:0{CODE_DIGITS}d}"


def check_issuer(issuer: str) -> str:
    """The firm's display name on the client's authenticator: never the product's (ADR-163 §7)."""
    if not issuer.strip() or "accrued" in issuer.casefold():
        raise ValueError("a factor's issuer is the firm's display name")
    return issuer.strip()


def _otpauth(secret: str, issuer: str, account: str) -> str:
    label = quote(f"{issuer}:{account}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}"


@dataclass
class InMemoryPortalIdp:
    """Users, factors and challenges in this process. `now` is injectable for tests."""

    now: float | None = None
    users: dict[str, str] = field(default_factory=dict[str, str])  # email -> user id
    factors: dict[str, str] = field(default_factory=dict[str, str])  # factor id -> secret
    challenges: dict[str, str] = field(default_factory=dict[str, str])  # challenge -> factor
    unavailable: bool = False

    def _check(self) -> None:
        if self.unavailable:
            raise PortalIdpUnavailable

    def _clock(self) -> float:
        return system_now().timestamp() if self.now is None else self.now

    async def upsert_user(self, email: str, *, name: str | None = None) -> str:
        self._check()
        return self.users.setdefault(email.strip().lower(), f"user_{uuid4().hex}")

    async def enrol_totp(self, user_id: str, *, issuer: str, account: str) -> TotpEnrolment:
        self._check()
        issuer = check_issuer(issuer)
        if user_id not in self.users.values():
            raise PortalIdpUnavailable
        secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
        factor = f"auth_factor_{uuid4().hex}"
        self.factors[factor] = secret
        return TotpEnrolment(factor, secret, _otpauth(secret, issuer, account))

    async def challenge(self, factor_id: str) -> str:
        self._check()
        if factor_id not in self.factors:
            raise PortalIdpUnavailable
        challenge = f"auth_challenge_{uuid4().hex}"
        self.challenges[challenge] = factor_id
        return challenge

    async def verify(self, challenge_id: str, code: str) -> bool:
        self._check()
        factor = self.challenges.pop(challenge_id, None)  # single use, right or wrong
        if factor is None or factor not in self.factors:
            return False
        at = self._clock()
        return any(
            hmac.compare_digest(totp_at(self.factors[factor], at + d * TOTP_STEP_SECONDS), code)
            for d in range(-TOTP_WINDOW, TOTP_WINDOW + 1)
        )

    async def remove_factor(self, factor_id: str) -> None:
        self._check()
        self.factors.pop(factor_id, None)


class WorkOsPortalIdp:
    """WorkOS User Management and MFA. Errors from the SDK become `PortalIdpUnavailable`; their
    messages are never logged (they can carry the email)."""

    def __init__(self, *, api_key: str | None = None, client_id: str | None = None) -> None:
        """From settings; the contract tests pass staging credentials directly."""
        from workos import WorkOSClient

        s = settings()
        key = api_key or (s.workos_api_key.get_secret_value() if s.workos_api_key else None)
        client = client_id or s.workos_client_id
        if not key or not client:
            raise PortalIdpUnavailable("not_configured")
        self._client = WorkOSClient(api_key=key, client_id=client)

    async def _run[**P, T](self, call: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return await asyncio.to_thread(call, *args, **kwargs)
        except Exception as exc:  # the SDK's errors and transport failures alike
            raise PortalIdpUnavailable(type(exc).__name__) from None

    async def upsert_user(self, email: str, *, name: str | None = None) -> str:
        um = self._client.user_management
        address = email.strip().lower()
        page = await self._run(um.list_users, email=address, limit=1)
        found = list(getattr(page, "data", []) or [])
        if found:
            return str(found[0].id)
        created = await self._run(um.create_user, email=address, name=name, email_verified=True)
        return str(created.id)

    async def enrol_totp(self, user_id: str, *, issuer: str, account: str) -> TotpEnrolment:
        enrolled = await self._run(
            self._client.mfa.enroll_factor,
            type="totp",
            totp_issuer=check_issuer(issuer),
            totp_user=account,
            user_id=user_id,
        )
        if enrolled.totp is None:
            raise PortalIdpUnavailable("no_totp")
        return TotpEnrolment(enrolled.id, enrolled.totp.secret, enrolled.totp.uri)

    async def challenge(self, factor_id: str) -> str:
        made = await self._run(self._client.mfa.challenge_factor, factor_id)
        return made.id

    async def verify(self, challenge_id: str, code: str) -> bool:
        answer = await self._run(self._client.mfa.verify_challenge, challenge_id, code=code)
        return answer.valid

    async def remove_factor(self, factor_id: str) -> None:
        try:
            await self._run(self._client.mfa.delete_factor, factor_id)
        except PortalIdpUnavailable as exc:
            if str(exc) != "NotFoundError":
                raise


_idp: PortalIdp | None = None


def configure_portal_idp(idp: PortalIdp | None) -> None:
    """Local runs and tests only: another provider (None goes back to the environment's)."""
    if settings().environment not in ("local", "test"):
        raise RuntimeError("configure_portal_idp is for local runs and tests only")
    global _idp
    _idp = idp


def portal_idp() -> PortalIdp:
    global _idp
    if _idp is None:
        _idp = (
            InMemoryPortalIdp()
            if settings().environment in ("local", "test")
            else WorkOsPortalIdp()
        )
    return _idp

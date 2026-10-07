"""Bearer-token verification (ADR-020, ADR-029). PROTECTED. TASK-007 design §1.

The identity provider proves who someone is, nothing more. A verified token yields an issuer, a
subject and how recently (and how strongly) they authenticated. Never roles, never a tenant: access
comes from our database on every request. This is the only file that reads token claims (AUTH-001).

`JwtVerifier` checks an RS256 signature against the provider's public JWKS and requires `iss`,
`aud`, `exp`, `iat` and `sub`. The local fake provider (`abacus_tools.fakes.identity`) and WorkOS
issue the same kind of token, so changing providers is configuration, not code.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Protocol, cast

import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from abacus.kernel.config import settings

ALGORITHMS = ("RS256",)
LEEWAY_SECONDS = 30
MAX_TOKEN_BYTES = 8192  # far above any real access token; refuses oversized input before parsing
MAX_LIFETIME_SECONDS = 3600  # access tokens are short-lived; a long-lived one is refused
MIN_RSA_BITS = 2048
_REQUIRED_CLAIMS = ("iss", "aud", "exp", "iat", "sub")


class InvalidToken(Exception):
    """The bearer token is missing, malformed, expired, or not signed by the trusted provider."""


@dataclass(frozen=True)
class VerifiedIdentity:
    issuer: str
    subject: str
    # When the user last authenticated with multi-factor, per the provider; None if not MFA.
    mfa_at: datetime | None


class TokenVerifier(Protocol):
    def verify(self, token: str) -> VerifiedIdentity: ...


class JwtVerifier:
    def __init__(self, *, issuer: str, audience: str, jwks: str) -> None:
        self._issuer = issuer
        self._audience = audience
        document = cast(dict[str, object], json.loads(jwks))
        listed = document.get("keys")
        if not isinstance(listed, list):
            raise ValueError("JWKS must be an object with a 'keys' list")
        # An empty key set is valid and verifies nothing (fail closed). A key that can't be used
        # (unsupported type or algorithm, weak, malformed) is skipped, never fatal.
        self._keys: dict[str, jwt.PyJWK] = {}
        for entry in cast(list[object], listed):
            key = _parse_key(entry)
            if key is not None and key.key_id and _acceptable_key(key):
                self._keys[key.key_id] = key

    @property
    def key_count(self) -> int:
        return len(self._keys)

    def verify(self, token: str) -> VerifiedIdentity:
        if not token or len(token.encode()) > MAX_TOKEN_BYTES:
            raise InvalidToken("token missing or too large")
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            key = self._keys.get(kid) if isinstance(kid, str) else None
            if key is None or header.get("alg") not in ALGORITHMS:
                raise InvalidToken("token not signed by a trusted key")
            claims = cast(
                dict[str, object],
                jwt.decode(
                    token,
                    key=key.key,
                    algorithms=list(ALGORITHMS),
                    audience=self._audience,
                    issuer=self._issuer,
                    leeway=LEEWAY_SECONDS,
                    options={"require": list(_REQUIRED_CLAIMS)},
                ),
            )
        except jwt.PyJWTError as exc:
            raise InvalidToken(type(exc).__name__) from None
        issued, expires = claims["iat"], claims["exp"]
        if (
            not isinstance(issued, int | float)
            or not isinstance(expires, int | float)
            or expires - issued > MAX_LIFETIME_SECONDS
        ):
            raise InvalidToken("token lifetime too long")
        subject = claims["sub"]
        if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
            raise InvalidToken("subject must be a non-empty string")
        return VerifiedIdentity(self._issuer, subject, _mfa_at(claims))


def _parse_key(entry: object) -> jwt.PyJWK | None:
    if not isinstance(entry, dict):
        return None
    try:
        return jwt.PyJWK(cast(dict[str, object], entry))
    except (jwt.PyJWTError, NotImplementedError, ValueError, TypeError):
        return None


def _acceptable_key(key: jwt.PyJWK) -> bool:
    """RSA signing keys of at least 2048 bits, declared for RS256 if they declare anything."""
    if key.key_type != "RSA" or key.algorithm_name not in ALGORITHMS:
        return False
    public = key.key
    return isinstance(public, RSAPublicKey) and public.key_size >= MIN_RSA_BITS


def _mfa_at(claims: dict[str, object]) -> datetime | None:
    """`auth_time` counts as an MFA time only if `amr` says MFA was used (OpenID Connect Core),
    and only if it is not in the future: a future time would keep "recent MFA" true forever."""
    amr = claims.get("amr")
    auth_time = claims.get("auth_time")
    if not isinstance(amr, list) or "mfa" not in cast(list[object], amr):
        return None
    if isinstance(auth_time, bool) or not isinstance(auth_time, int):
        return None
    if not 0 < auth_time <= time.time() + LEEWAY_SECONDS:
        return None
    return datetime.fromtimestamp(auth_time, UTC)


_verifier: TokenVerifier | None = None


def configure_verifier(verifier: TokenVerifier) -> None:
    """Replace the verifier built from settings: local runs and tests only (the fake provider)."""
    if settings().environment not in ("local", "test"):
        raise RuntimeError("configure_verifier is for local runs and tests only")
    global _verifier
    _verifier = verifier


@lru_cache(maxsize=1)
def _from_settings() -> TokenVerifier:
    s = settings()
    if s.identity_issuer is None or s.identity_audience is None or s.identity_jwks is None:
        # Settings validation makes this unreachable outside local and test.
        raise RuntimeError("identity provider is not configured")
    verifier = JwtVerifier(
        issuer=s.identity_issuer, audience=s.identity_audience, jwks=s.identity_jwks
    )
    if verifier.key_count == 0 and s.environment not in ("local", "test"):
        # Every token would be refused with a silent 401: fail at startup instead.
        raise RuntimeError("identity_jwks has no usable RS256 key of at least 2048 bits")
    return verifier


def reset_verifier() -> None:
    """Back to the verifier built from settings (test teardown; settings changes)."""
    global _verifier
    _verifier = None
    _from_settings.cache_clear()


def token_verifier() -> TokenVerifier:
    return _verifier if _verifier is not None else _from_settings()


# --- Staff tokens (SPEC-012 Q4): a separate issuer; never accepted as a firm user's token ------

_staff_verifier: TokenVerifier | None = None


def configure_staff_verifier(verifier: TokenVerifier | None) -> None:
    """Local runs and tests only: the fake staff issuer (None resets to settings)."""
    if settings().environment not in ("local", "test"):
        raise RuntimeError("configure_staff_verifier is for local runs and tests only")
    global _staff_verifier
    _staff_verifier = verifier


def staff_verifier() -> TokenVerifier:
    """Raises `InvalidToken` when no staff issuer is configured: break-glass is then closed."""
    if _staff_verifier is not None:
        return _staff_verifier
    s = settings()
    if s.staff_issuer is None or s.staff_audience is None or s.staff_jwks is None:
        raise InvalidToken("no staff issuer configured")
    if s.staff_issuer == s.identity_issuer:
        raise InvalidToken("the staff issuer must differ from the firm issuer")
    return JwtVerifier(issuer=s.staff_issuer, audience=s.staff_audience, jwks=s.staff_jwks)

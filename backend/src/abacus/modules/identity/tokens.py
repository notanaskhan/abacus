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
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Protocol, cast

import jwt

from abacus.kernel.config import settings

ALGORITHMS = ("RS256",)
LEEWAY_SECONDS = 30
MAX_TOKEN_BYTES = 8192  # far above any real access token; refuses oversized input before parsing
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
        # An empty key set is valid and verifies nothing (fail closed).
        keys = jwt.PyJWKSet.from_dict(document).keys if listed else []
        self._keys: dict[str, jwt.PyJWK] = {
            key.key_id: key for key in keys if key.key_id and key.key_type == "RSA"
        }

    def verify(self, token: str) -> VerifiedIdentity:
        if not token or len(token) > MAX_TOKEN_BYTES:
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
        subject = claims["sub"]
        if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
            raise InvalidToken("subject must be a non-empty string")
        return VerifiedIdentity(self._issuer, subject, _mfa_at(claims))


def _mfa_at(claims: dict[str, object]) -> datetime | None:
    """`auth_time` counts as an MFA time only if `amr` says MFA was used (OpenID Connect Core)."""
    amr = claims.get("amr")
    auth_time = claims.get("auth_time")
    if not isinstance(amr, list) or "mfa" not in cast(list[object], amr):
        return None
    if isinstance(auth_time, bool) or not isinstance(auth_time, int):
        return None
    return datetime.fromtimestamp(auth_time, UTC)


_verifier: TokenVerifier | None = None


def configure_verifier(verifier: TokenVerifier) -> None:
    """Replace the verifier built from settings (tests and local runs with the fake provider)."""
    global _verifier
    _verifier = verifier


@lru_cache(maxsize=1)
def _from_settings() -> TokenVerifier:
    s = settings()
    if s.identity_issuer is None or s.identity_audience is None or s.identity_jwks is None:
        # Settings validation makes this unreachable outside local and test.
        raise RuntimeError("identity provider is not configured")
    return JwtVerifier(
        issuer=s.identity_issuer, audience=s.identity_audience, jwks=s.identity_jwks
    )


def token_verifier() -> TokenVerifier:
    return _verifier if _verifier is not None else _from_settings()

"""A fake OpenID Connect provider for tests and local runs (TASK-007 design §1).

It makes an RSA key pair per instance, publishes the public JWKS and mints RS256 access tokens
shaped like the real provider's. Product code only ever sees the public JWKS, through
`JwtVerifier`, the same verifier WorkOS tokens will go through. The private key never leaves this
process.

    idp = FakeIdentityProvider()
    configure_verifier(idp.verifier())
    token = idp.token("user-123", mfa=True)
"""

from __future__ import annotations

import json
import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from abacus.modules.identity.api import JwtVerifier

ISSUER = "https://identity.abacus.local"
AUDIENCE = "abacus-api"


class FakeIdentityProvider:
    def __init__(
        self,
        *,
        issuer: str = ISSUER,
        audience: str = AUDIENCE,
        kid: str = "fake-1",
        key: rsa.RSAPrivateKey | None = None,
    ) -> None:
        """`key`: a fixed key (the local sign-in server keeps one across restarts)."""
        self.issuer = issuer
        self.audience = audience
        self.kid = kid
        self._key = key or rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def jwks(self) -> str:
        public = RSAAlgorithm.to_jwk(self._key.public_key(), as_dict=True)
        return json.dumps({"keys": [{**public, "kid": self.kid, "alg": "RS256", "use": "sig"}]})

    def verifier(self) -> JwtVerifier:
        return JwtVerifier(issuer=self.issuer, audience=self.audience, jwks=self.jwks())

    def token(
        self,
        subject: str,
        *,
        mfa: bool = False,
        auth_time: int | None = None,
        expires_in: int = 300,
        **claims: object,
    ) -> str:
        """An access token for `subject`; `claims` override or add claims (tests of bad tokens)."""
        now = int(time.time())
        payload: dict[str, object] = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": subject,
            "iat": now,
            "exp": now + expires_in,
        }
        if mfa:
            payload["amr"] = ["pwd", "mfa"]
            payload["auth_time"] = now if auth_time is None else auth_time
        payload.update(claims)
        return jwt.encode(payload, self._key, algorithm="RS256", headers={"kid": self.kid})

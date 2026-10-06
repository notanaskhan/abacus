"""AC-1, AC-20: bearer-token verification (TASK-007 contract, "Tokens").

Bad tokens that the fake provider cannot mint are signed here with `cryptography` and stdlib
(base64, json, hmac), because AUTH-001 bans importing `jwt` in tests.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import fields
from datetime import UTC, datetime
from typing import cast

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.modules.identity.api import (
    InvalidToken,
    JwtVerifier,
    VerifiedIdentity,
    configure_verifier,
    reset_verifier,
    token_verifier,
)
from abacus_tools.fakes.identity import AUDIENCE, ISSUER, FakeIdentityProvider


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64_int(value: int) -> str:
    return _b64(value.to_bytes((value.bit_length() + 7) // 8, "big"))


def _compact(header: Mapping[str, object], payload: dict[str, object]) -> str:
    return _b64(json.dumps(header).encode()) + "." + _b64(json.dumps(payload).encode())


class Signer:
    """An RSA key that signs arbitrary headers and payloads, to build tokens the fake won't."""

    def __init__(
        self, kid: str = "hand-1", *, bits: int = 2048, alg: str | None = "RS256"
    ) -> None:
        self.kid = kid
        self.alg = alg
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=bits)

    def jwk(self) -> dict[str, str]:
        numbers = self._key.public_key().public_numbers()
        key = {
            "kty": "RSA",
            "kid": self.kid,
            "use": "sig",
            "n": _b64_int(numbers.n),
            "e": _b64_int(numbers.e),
        }
        if self.alg is not None:
            key["alg"] = self.alg
        return key

    def jwks(self) -> str:
        return json.dumps({"keys": [self.jwk()]})

    def sign(
        self,
        payload: dict[str, object],
        *,
        header: dict[str, object] | None = None,
        digest: hashes.HashAlgorithm | None = None,
    ) -> str:
        head = header if header is not None else {"alg": "RS256", "typ": "JWT", "kid": self.kid}
        signing_input = _compact(head, payload)
        signature = self._key.sign(
            signing_input.encode(), padding.PKCS1v15(), digest or hashes.SHA256()
        )
        return signing_input + "." + _b64(signature)

    def verifier(self) -> JwtVerifier:
        return JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=self.jwks())


def _claims(**overrides: object) -> dict[str, object]:
    now = int(time.time())
    claims: dict[str, object] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "user-1",
        "iat": now,
        "exp": now + 300,
    }
    claims.update(overrides)
    return claims


def _without(name: str) -> dict[str, object]:
    claims = _claims()
    del claims[name]
    return claims


@pytest.fixture(autouse=True)
def _reset_verifier_and_settings() -> Iterator[None]:
    yield
    settings.cache_clear()
    reset_verifier()


@pytest.fixture(scope="module")
def idp() -> FakeIdentityProvider:
    return FakeIdentityProvider()


@pytest.fixture(scope="module")
def verifier(idp: FakeIdentityProvider) -> JwtVerifier:
    return idp.verifier()


@pytest.fixture(scope="module")
def signer() -> Signer:
    return Signer()


def _rejects(verifier: JwtVerifier, token: str) -> None:
    with pytest.raises(InvalidToken):
        verifier.verify(token)


# --- valid tokens ------------------------------------------------------------------------------


def test_ac1_valid_token_yields_issuer_subject_and_no_mfa(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    identity = verifier.verify(idp.token("user-1"))
    assert identity == VerifiedIdentity(issuer=ISSUER, subject="user-1", mfa_at=None)


def test_ac1_fake_provider_defaults_match_the_module_constants(idp: FakeIdentityProvider) -> None:
    assert (idp.issuer, idp.audience) == (ISSUER, AUDIENCE)
    assert ISSUER == "https://identity.abacus.local"
    assert AUDIENCE == "abacus-api"


def test_ac1_jwks_is_a_json_document_with_public_keys_only(idp: FakeIdentityProvider) -> None:
    document = json.loads(idp.jwks())
    [key] = document["keys"]
    assert key["kid"] == "fake-1"
    assert key["kty"] == "RSA"
    assert not {"d", "p", "q", "dp", "dq", "qi"} & set(key)


def test_ac1_verifier_built_from_a_custom_provider_accepts_its_tokens() -> None:
    other = FakeIdentityProvider(issuer="https://idp.example.test", audience="other", kid="k-9")
    identity = other.verifier().verify(other.token("abc"))
    assert identity.issuer == "https://idp.example.test"
    assert identity.subject == "abc"


def test_ac1_subject_of_exactly_255_characters_is_valid(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    subject = "s" * 255
    assert verifier.verify(idp.token(subject)).subject == subject


def test_ac1_subject_of_one_character_is_valid(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    assert verifier.verify(idp.token("x")).subject == "x"


def test_ac1_hand_signed_rs256_token_with_a_known_kid_is_valid(signer: Signer) -> None:
    identity = signer.verifier().verify(signer.sign(_claims()))
    assert identity == VerifiedIdentity(issuer=ISSUER, subject="user-1", mfa_at=None)


def test_ac1_verifier_trusts_any_key_in_a_multi_key_jwks(idp: FakeIdentityProvider) -> None:
    second = FakeIdentityProvider(kid="fake-2")
    merged = json.dumps(
        {"keys": [*json.loads(idp.jwks())["keys"], *json.loads(second.jwks())["keys"]]}
    )
    verifier = JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=merged)
    assert verifier.verify(idp.token("a")).subject == "a"
    assert verifier.verify(second.token("b")).subject == "b"


# --- leeway ------------------------------------------------------------------------------------


def test_ac1_token_expired_within_the_30_second_leeway_is_valid(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    assert verifier.verify(idp.token("user-1", expires_in=-10)).subject == "user-1"


def test_ac1_token_issued_in_the_future_within_leeway_is_valid(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    token = idp.token("user-1", iat=int(time.time()) + 10)
    assert verifier.verify(token).subject == "user-1"


def test_ac1_token_not_yet_valid_within_leeway_is_valid(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    token = idp.token("user-1", nbf=int(time.time()) + 10)
    assert verifier.verify(token).subject == "user-1"


# --- mfa_at ------------------------------------------------------------------------------------


def test_ac1_mfa_token_yields_auth_time_as_utc_mfa_at(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    auth_time = int(time.time()) - 120
    identity = verifier.verify(idp.token("user-1", mfa=True, auth_time=auth_time))
    assert identity.mfa_at == datetime.fromtimestamp(auth_time, UTC)
    assert identity.mfa_at is not None
    assert identity.mfa_at.utcoffset() is not None
    assert identity.mfa_at.utcoffset() == datetime.now(UTC).utcoffset()


def test_ac1_mfa_token_without_explicit_auth_time_uses_a_recent_time(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    identity = verifier.verify(idp.token("user-1", mfa=True))
    assert identity.mfa_at is not None
    assert abs((datetime.now(UTC) - identity.mfa_at).total_seconds()) < 60


def test_ac1_auth_time_without_mfa_in_amr_is_not_an_mfa_time(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    token = idp.token("user-1", amr=["pwd"], auth_time=int(time.time()))
    assert verifier.verify(token).mfa_at is None


def test_ac1_auth_time_with_no_amr_is_not_an_mfa_time(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    token = idp.token("user-1", auth_time=int(time.time()))
    assert verifier.verify(token).mfa_at is None


def test_ac1_non_mfa_token_has_no_mfa_at(idp: FakeIdentityProvider, verifier: JwtVerifier) -> None:
    assert verifier.verify(idp.token("user-1", mfa=False)).mfa_at is None


# --- roles never come from the token (ADR-029) -------------------------------------------------


MINT_WITH_ROLES: list[Callable[[FakeIdentityProvider], str]] = [
    lambda idp: idp.token("user-1", role="firm_admin"),
    lambda idp: idp.token("user-1", roles=["firm_admin", "engagement_partner"]),
    lambda idp: idp.token("user-1", org_role="firm_admin"),
    lambda idp: idp.token("user-1", role="firm_admin", roles=["manager"], org_role="firm_admin"),
]


@pytest.mark.parametrize("mint", MINT_WITH_ROLES, ids=["role", "roles", "org_role", "all"])
def test_ac1_role_like_claims_are_ignored(
    idp: FakeIdentityProvider, verifier: JwtVerifier, mint: Callable[[FakeIdentityProvider], str]
) -> None:
    assert verifier.verify(mint(idp)) == verifier.verify(idp.token("user-1"))


def test_ac1_verified_identity_carries_only_issuer_subject_and_mfa_at() -> None:
    assert {f.name for f in fields(VerifiedIdentity)} == {"issuer", "subject", "mfa_at"}


# --- invalid tokens ----------------------------------------------------------------------------


def test_ac1_token_signed_by_another_key_with_the_same_kid_is_rejected(
    verifier: JwtVerifier,
) -> None:
    impostor = FakeIdentityProvider()  # same default kid, different key
    _rejects(verifier, impostor.token("user-1"))


def test_ac1_token_with_an_unknown_kid_is_rejected(verifier: JwtVerifier) -> None:
    _rejects(verifier, FakeIdentityProvider(kid="unknown").token("user-1"))


def test_ac1_token_without_a_kid_is_rejected_even_when_signed_by_the_trusted_key(
    signer: Signer,
) -> None:
    token = signer.sign(_claims(), header={"alg": "RS256", "typ": "JWT"})
    _rejects(signer.verifier(), token)


def test_ac1_token_with_an_empty_kid_is_rejected(signer: Signer) -> None:
    token = signer.sign(_claims(), header={"alg": "RS256", "typ": "JWT", "kid": ""})
    _rejects(signer.verifier(), token)


def test_ac1_alg_none_token_is_rejected(verifier: JwtVerifier) -> None:
    unsigned = _compact({"alg": "none", "typ": "JWT", "kid": "fake-1"}, _claims()) + "."
    _rejects(verifier, unsigned)


def test_ac1_alg_none_token_without_a_trailing_dot_is_rejected(verifier: JwtVerifier) -> None:
    _rejects(verifier, _compact({"alg": "none", "typ": "JWT", "kid": "fake-1"}, _claims()))


@pytest.mark.parametrize("secret", [b"secret", b"x" * 64])
def test_ac1_hs256_token_is_rejected(
    idp: FakeIdentityProvider, verifier: JwtVerifier, secret: bytes
) -> None:
    signing_input = _compact({"alg": "HS256", "typ": "JWT", "kid": "fake-1"}, _claims())
    mac = hmac.new(secret, signing_input.encode(), hashlib.sha256).digest()
    _rejects(verifier, signing_input + "." + _b64(mac))


def test_ac1_hs256_token_keyed_with_the_public_jwks_is_rejected(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    signing_input = _compact({"alg": "HS256", "typ": "JWT", "kid": "fake-1"}, _claims())
    mac = hmac.new(idp.jwks().encode(), signing_input.encode(), hashlib.sha256).digest()
    _rejects(verifier, signing_input + "." + _b64(mac))


def test_ac1_rs384_token_is_rejected_because_only_rs256_is_allowed(signer: Signer) -> None:
    token = signer.sign(
        _claims(),
        header={"alg": "RS384", "typ": "JWT", "kid": signer.kid},
        digest=hashes.SHA384(),
    )
    _rejects(signer.verifier(), token)


def test_ac1_expired_token_is_rejected(idp: FakeIdentityProvider, verifier: JwtVerifier) -> None:
    _rejects(verifier, idp.token("user-1", expires_in=-120))


def test_ac1_token_issued_in_the_future_beyond_leeway_is_rejected(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    _rejects(verifier, idp.token("user-1", iat=int(time.time()) + 120))


def test_ac1_token_not_yet_valid_beyond_leeway_is_rejected(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    _rejects(verifier, idp.token("user-1", nbf=int(time.time()) + 120))


def test_ac1_wrong_issuer_is_rejected(idp: FakeIdentityProvider, verifier: JwtVerifier) -> None:
    _rejects(verifier, idp.token("user-1", iss="https://evil.example.test"))


def test_ac1_wrong_audience_is_rejected(idp: FakeIdentityProvider, verifier: JwtVerifier) -> None:
    _rejects(verifier, idp.token("user-1", aud="someone-else"))


@pytest.mark.parametrize("missing", ["iss", "aud", "exp", "iat", "sub"])
def test_ac1_token_missing_a_required_claim_is_rejected(signer: Signer, missing: str) -> None:
    _rejects(signer.verifier(), signer.sign(_without(missing)))


@pytest.mark.parametrize("subject", ["", "s" * 256, "s" * 1000])
def test_ac1_empty_or_overlong_subject_is_rejected(
    idp: FakeIdentityProvider, verifier: JwtVerifier, subject: str
) -> None:
    _rejects(verifier, idp.token(subject))


@pytest.mark.parametrize("subject", [123, None, ["a"], {"id": "a"}])
def test_ac1_non_string_subject_is_rejected(signer: Signer, subject: object) -> None:
    _rejects(signer.verifier(), signer.sign(_claims(sub=subject)))


def test_ac1_token_over_8192_bytes_is_rejected(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    token = idp.token("user-1", padding="p" * 9000)
    assert len(token.encode()) > 8192
    _rejects(verifier, token)


def test_ac1_the_same_token_under_8192_bytes_is_valid(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    token = idp.token("user-1", padding="p" * 100)
    assert len(token.encode()) < 8192
    assert verifier.verify(token).subject == "user-1"


@pytest.mark.parametrize(
    "garbage",
    ["", " ", "garbage", "a.b", "a.b.c", "...", "eyJ.eyJ.sig", "Bearer abc", "\x00", "é.é.é"],
)
def test_ac1_garbage_is_rejected(verifier: JwtVerifier, garbage: str) -> None:
    _rejects(verifier, garbage)


def test_ac1_tampered_payload_is_rejected(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    header, _payload, signature = idp.token("user-1").split(".")
    forged = _b64(json.dumps(_claims(sub="someone-else")).encode())
    _rejects(verifier, f"{header}.{forged}.{signature}")


def test_ac1_truncated_signature_is_rejected(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    _rejects(verifier, idp.token("user-1")[:-8])


@pytest.mark.parametrize("jwks", ['{"keys": []}', '{"keys":[]}', '{ "keys" : [ ] }'])
def test_ac1_empty_jwks_verifies_nothing(idp: FakeIdentityProvider, jwks: str) -> None:
    verifier = JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=jwks)
    _rejects(verifier, idp.token("user-1"))


def test_ac1_empty_jwks_rejects_even_a_hand_signed_token(signer: Signer) -> None:
    verifier = JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks='{"keys": []}')
    _rejects(verifier, signer.sign(_claims()))


def test_ac1_verifier_for_another_issuer_rejects_this_providers_tokens(
    idp: FakeIdentityProvider,
) -> None:
    verifier = JwtVerifier(issuer="https://other.example.test", audience=AUDIENCE, jwks=idp.jwks())
    _rejects(verifier, idp.token("user-1"))


def test_ac1_verifier_for_another_audience_rejects_this_providers_tokens(
    idp: FakeIdentityProvider,
) -> None:
    verifier = JwtVerifier(issuer=ISSUER, audience="other", jwks=idp.jwks())
    _rejects(verifier, idp.token("user-1"))


def test_ac1_invalid_token_is_an_exception_type_callers_can_catch() -> None:
    assert issubclass(InvalidToken, Exception)


# --- contract revision 1 ------------------------------------------------------------------------


def test_ac1_token_lifetime_of_exactly_3600_seconds_is_valid(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    now = int(time.time())
    token = idp.token("user-1", iat=now, exp=now + 3600)
    assert verifier.verify(token).subject == "user-1"


@pytest.mark.parametrize("lifetime", [3601, 7200, 86400 * 365])
def test_ac1_token_lifetime_over_3600_seconds_is_rejected(
    idp: FakeIdentityProvider, verifier: JwtVerifier, lifetime: int
) -> None:
    now = int(time.time())
    _rejects(verifier, idp.token("user-1", iat=now, exp=now + lifetime))


def test_ac1_token_size_is_counted_in_bytes_not_characters(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    token = idp.token("user-1") + "\u00e9" * 4100  # under 8192 characters, over 8192 bytes
    assert len(token) < 8192
    assert len(token.encode()) > 8192
    _rejects(verifier, token)


def test_ac1_a_1024_bit_rsa_key_is_ignored_so_its_tokens_fail() -> None:
    weak = Signer(bits=1024)
    _rejects(weak.verifier(), weak.sign(_claims()))


def test_ac1_a_2048_bit_rsa_key_is_accepted(signer: Signer) -> None:
    assert signer.verifier().verify(signer.sign(_claims())).subject == "user-1"


def test_ac1_a_jwk_without_alg_is_accepted() -> None:
    plain = Signer(alg=None)
    assert plain.verifier().verify(plain.sign(_claims())).subject == "user-1"


@pytest.mark.parametrize("alg", ["RS384", "RS512", "HS256", "PS256", "none"])
def test_ac1_a_jwk_declaring_another_alg_is_ignored_so_its_tokens_fail(alg: str) -> None:
    other = Signer(alg=alg)
    _rejects(other.verifier(), other.sign(_claims()))


def test_ac1_a_non_rsa_key_in_the_jwks_is_ignored_and_the_rsa_key_still_works(
    signer: Signer,
) -> None:
    point = ec.generate_private_key(ec.SECP256R1()).public_key().public_numbers()
    ec_key = {
        "kty": "EC",
        "kid": "ec-1",
        "crv": "P-256",
        "x": _b64_int(point.x),
        "y": _b64_int(point.y),
    }
    jwks = json.dumps({"keys": [ec_key, signer.jwk()]})
    verifier = JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=jwks)
    assert verifier.verify(signer.sign(_claims())).subject == "user-1"
    ec_header = {"alg": "ES256", "typ": "JWT", "kid": "ec-1"}
    _rejects(verifier, _compact(ec_header, _claims()) + "." + _b64(b"x" * 64))


def test_ac1_auth_time_slightly_in_the_future_within_leeway_still_counts(
    idp: FakeIdentityProvider, verifier: JwtVerifier
) -> None:
    identity = verifier.verify(idp.token("user-1", mfa=True, auth_time=int(time.time()) + 10))
    assert identity.mfa_at is not None


@pytest.mark.parametrize("offset", [120, 3600, 10**6])
def test_ac1_auth_time_in_the_future_beyond_leeway_is_not_mfa(
    idp: FakeIdentityProvider, verifier: JwtVerifier, offset: int
) -> None:
    identity = verifier.verify(idp.token("user-1", mfa=True, auth_time=int(time.time()) + offset))
    assert identity.mfa_at is None


@pytest.mark.parametrize("auth_time", [0, -1, -(10**6), 10**20, 10**30])
def test_ac1_auth_time_that_is_not_positive_or_overflows_is_not_mfa(
    idp: FakeIdentityProvider, verifier: JwtVerifier, auth_time: int
) -> None:
    identity = verifier.verify(idp.token("user-1", mfa=True, auth_time=auth_time))
    assert identity.mfa_at is None
    assert identity.subject == "user-1"


def _explicit_environment(mp: pytest.MonkeyPatch, environment: str) -> None:
    mp.setenv("ABACUS_ENVIRONMENT", environment)
    values = {
        "DATABASE_URL": "postgresql+asyncpg://app@db.example.test:5432/abacus",
        "MIGRATIONS_DATABASE_URL": "postgresql+asyncpg://owner@db.example.test:5432/abacus",
        "RELAY_DATABASE_URL": "postgresql+asyncpg://relay@db.example.test:5432/abacus",
        "IDENTITY_DATABASE_URL": "postgresql+asyncpg://identity@db.example.test:5432/abacus",
        "IDENTITY_ISSUER": ISSUER,
        "IDENTITY_AUDIENCE": AUDIENCE,
        "IDENTITY_JWKS": '{"keys": []}',
        "S3_ENDPOINT_URL": "https://s3.example.test",
        "S3_ACCESS_KEY": "a",
        "S3_SECRET_KEY": "b",
        "TEMPORAL_TARGET": "temporal.example.test:7233",
        "TEMPORAL_PAYLOAD_KEY": "test-payload-key-Zq8Xv2Lm9Wd4Rt7Bn3Hs",
        "TEMPORAL_TLS": "true",
        "TEMPORAL_API_KEY": "test-temporal-api-key",
        "EVIDENCE_BUCKET": "test-evidence-bucket",
    }
    for name, value in values.items():
        mp.setenv(f"ABACUS_{name}", value)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac20_configure_verifier_is_refused_outside_local_and_test(
    idp: FakeIdentityProvider, environment: str
) -> None:
    settings.cache_clear()
    try:
        with pytest.MonkeyPatch.context() as mp:
            _explicit_environment(mp, environment)
            settings.cache_clear()
            with pytest.raises(RuntimeError):
                configure_verifier(idp.verifier())
    finally:
        settings.cache_clear()


@pytest.mark.parametrize("environment", ["local", "test"])
def test_ac20_configure_verifier_is_allowed_in_local_and_test(
    idp: FakeIdentityProvider, environment: str
) -> None:
    settings.cache_clear()
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("ABACUS_ENVIRONMENT", environment)
            settings.cache_clear()
            configure_verifier(idp.verifier())
    finally:
        settings.cache_clear()


def test_ac1_key_count_is_the_number_of_usable_keys(
    idp: FakeIdentityProvider, signer: Signer
) -> None:
    assert idp.verifier().key_count == 1
    assert JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks='{"keys": []}').key_count == 0
    weak = Signer(bits=1024)
    assert weak.verifier().key_count == 0
    merged = json.dumps({"keys": [*json.loads(idp.jwks())["keys"], signer.jwk(), weak.jwk()]})
    assert JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=merged).key_count == 2


def _staging(mp: pytest.MonkeyPatch, jwks: str, environment: str = "staging") -> None:
    _explicit_environment(mp, environment)
    mp.setenv("ABACUS_IDENTITY_JWKS", jwks)
    settings.cache_clear()
    reset_verifier()


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize("jwks", ['{"keys": []}', "weak"])
def test_ac20_non_local_environment_with_no_usable_key_fails_at_startup(
    environment: str, jwks: str
) -> None:
    document = json.dumps({"keys": [Signer(bits=1024).jwk()]}) if jwks == "weak" else jwks
    with pytest.MonkeyPatch.context() as mp:
        _staging(mp, document, environment)
        with pytest.raises(RuntimeError):
            token_verifier()
        reset_verifier()
        with pytest.raises(RuntimeError):
            create_app()


def test_ac20_non_local_environment_with_a_usable_key_starts_and_verifies(
    idp: FakeIdentityProvider,
) -> None:
    with pytest.MonkeyPatch.context() as mp:
        _staging(mp, idp.jwks())
        create_app()
        assert token_verifier().verify(idp.token("user-1")).subject == "user-1"


@pytest.mark.parametrize("environment", ["local", "test"])
def test_ac20_local_and_test_environments_start_with_the_empty_default_and_verify_nothing(
    idp: FakeIdentityProvider, environment: str
) -> None:
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ABACUS_ENVIRONMENT", environment)
        settings.cache_clear()
        reset_verifier()
        create_app()
        _rejects(cast(JwtVerifier, token_verifier()), idp.token("user-1"))


def test_ac20_reset_verifier_drops_the_configured_override(idp: FakeIdentityProvider) -> None:
    configure_verifier(idp.verifier())
    assert token_verifier().verify(idp.token("user-1")).subject == "user-1"
    reset_verifier()
    _rejects(cast(JwtVerifier, token_verifier()), idp.token("user-1"))  # default: empty JWKS

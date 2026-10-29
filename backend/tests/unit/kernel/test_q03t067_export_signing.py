"""Q-03-T067: export signing (G-02-T17; G-02 §4.5, AC-13), from the module's contract.

- KMS signs the SHA-256 digest (`MessageType=DIGEST`, `ECDSA_SHA_256`) and the export records the
  key KMS says signed it (`KeyId`), resolved beforehand from the alias (`DescribeKey`'s ARN).
- Every KMS error, and an answer missing what it must carry, fails closed (`SigningUnavailable`);
  nothing is signed with anything else instead.
- No signer configured fails closed; the local signer exists only in local and test.
- A signature verifies as `openssl dgst -sha256 -verify` would: over SHA-256 of the message.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast

import pytest
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from abacus.kernel.crypto import signing

MASTER = b"example-local-master-key-public-not-secret"
ALIAS = "alias/abacus-audit-export-signing"
ARN = "arn:aws:kms:us-east-2:111122223333:key/0000aaaa-1111-2222-3333-444455556666"


class FakeKms:
    def __init__(self, *, describe: object = None, sign: object = None) -> None:
        self.describe = describe
        self.sign_answer = sign
        self.calls: list[tuple[str, dict[str, object]]] = []

    def describe_key(self, **kwargs: object) -> object:
        self.calls.append(("describe_key", kwargs))
        if isinstance(self.describe, Exception):
            raise self.describe
        return self.describe

    def sign(self, **kwargs: object) -> object:
        self.calls.append(("sign", kwargs))
        if isinstance(self.sign_answer, Exception):
            raise self.sign_answer
        return self.sign_answer


def _denied(operation: str) -> ClientError:
    return ClientError({"Error": {"Code": "AccessDeniedException"}}, operation)


def _kms(fake: FakeKms) -> signing.KmsExportSigner:
    return signing.KmsExportSigner(cast(Any, fake), ALIAS)


@pytest.fixture(autouse=True)
def fresh() -> Iterator[None]:
    signing.configure_export_signer(None)
    yield
    signing.configure_export_signer(None)


async def test_kms_resolves_the_alias_to_the_keys_arn() -> None:
    fake = FakeKms(describe={"KeyMetadata": {"Arn": ARN}})
    signer = _kms(fake)
    assert signer.key_ref == ALIAS
    assert await signer.resolve_key_id() == ARN
    assert fake.calls == [("describe_key", {"KeyId": ALIAS})]


@pytest.mark.parametrize("answer", [{}, {"KeyMetadata": {}}, {"KeyMetadata": {"Arn": ""}}])
async def test_kms_describe_without_an_arn_fails_closed(answer: object) -> None:
    with pytest.raises(signing.SigningUnavailable):
        await _kms(FakeKms(describe=answer)).resolve_key_id()


async def test_kms_describe_error_fails_closed() -> None:
    with pytest.raises(signing.SigningUnavailable):
        await _kms(FakeKms(describe=_denied("DescribeKey"))).resolve_key_id()


async def test_kms_signs_the_digest_and_names_the_key_that_signed() -> None:
    digest = hashlib.sha256(b"manifest").digest()
    fake = FakeKms(sign={"Signature": b"\x30\x06der", "KeyId": ARN})
    signed = await _kms(fake).sign_digest(digest)
    assert signed == signing.SignedDigest(b"\x30\x06der", ARN)
    assert fake.calls == [
        (
            "sign",
            {
                "KeyId": ALIAS,
                "Message": digest,
                "MessageType": "DIGEST",
                "SigningAlgorithm": "ECDSA_SHA_256",
            },
        )
    ]


@pytest.mark.parametrize(
    "answer", [{}, {"Signature": b"sig"}, {"KeyId": ARN}, {"Signature": b"", "KeyId": ARN}]
)
async def test_kms_answer_missing_the_signature_or_key_fails_closed(answer: object) -> None:
    with pytest.raises(signing.SigningUnavailable):
        await _kms(FakeKms(sign=answer)).sign_digest(b"\x00" * 32)


async def test_kms_sign_error_fails_closed() -> None:
    with pytest.raises(signing.SigningUnavailable):
        await _kms(FakeKms(sign=_denied("Sign"))).sign_digest(b"\x00" * 32)


def _settings(monkeypatch: pytest.MonkeyPatch, *, alias: str | None, environment: str) -> None:
    monkeypatch.setattr(
        signing,
        "settings",
        lambda: SimpleNamespace(
            audit_export_signing_key_alias=alias,
            kms_region="us-east-2",
            environment=environment,
            local_master_key=SimpleNamespace(get_secret_value=lambda: MASTER.decode()),
        ),
    )
    signing.configure_export_signer(None)  # clears the signer built from the old settings


def test_no_signer_configured_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch, alias=None, environment="production")
    assert signing.signing_configured() is False
    with pytest.raises(signing.SigningUnavailable):
        signing.export_signer()


def test_a_configured_signer_wins_over_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch, alias=None, environment="production")
    chosen = _kms(FakeKms())
    signing.configure_export_signer(chosen)
    assert signing.signing_configured() is True
    assert signing.export_signer() is chosen


def test_settings_with_an_alias_build_the_kms_signer(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeKms()

    def client(region: str) -> FakeKms:
        assert region == "us-east-2"
        return fake

    monkeypatch.setattr(signing, "kms_client", client)
    _settings(monkeypatch, alias=ALIAS, environment="production")
    built = signing.export_signer()
    assert isinstance(built, signing.KmsExportSigner)
    assert built.key_ref == ALIAS


def test_production_without_an_alias_has_no_signer(monkeypatch: pytest.MonkeyPatch) -> None:
    _settings(monkeypatch, alias=None, environment="production")
    assert signing.signing_configured() is False


def test_the_local_signer_is_refused_outside_local_and_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(signing, "settings", lambda: SimpleNamespace(environment="staging"))
    with pytest.raises(RuntimeError):
        signing.LocalExportSigner(MASTER)


async def test_a_local_signature_verifies_like_openssl_and_only_over_its_message() -> None:
    signer = signing.LocalExportSigner(MASTER)
    assert signer.key_ref.startswith("local:")
    assert await signer.resolve_key_id() == signer.key_ref
    message = b'{"rows": 3}'
    signed = await signer.sign_digest(hashlib.sha256(message).digest())
    pem = signer.public_key_pem()
    assert signing.verify_signature(pem, message, signed.signature) is True
    assert signing.verify_signature(pem, message + b" ", signed.signature) is False


def test_a_non_ec_public_key_never_verifies() -> None:
    rsa_pem = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    assert signing.verify_signature(rsa_pem, b"m", b"sig") is False

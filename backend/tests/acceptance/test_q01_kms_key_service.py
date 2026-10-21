"""Q-01-T12 / SPEC-050 AC-13 and AC-20: the KMS key service (P1), written from the spec text.

Sources: SPEC-050 AC-13; `docs/plan/epics/Q-01.md` F3 "KMS (P1)"; ADR-035 (per-tenant keys),
ADR-104 (envelope encryption), ADR-142 (US regions). Public names and signatures only are taken
from the code: `KmsKeyService(client, *, alias_prefix, platform_key)`, the `KeyService` methods,
`seal` and `open_sealed`, `DecryptionError`. No call leaves the process: KMS is a
`botocore.stub.Stubber` or an in-memory stand-in that binds a ciphertext to its encryption
context, as the real service does.
"""

from __future__ import annotations

import inspect
import uuid
from typing import TYPE_CHECKING

import pytest
from botocore.stub import Stubber

from abacus.kernel.crypto import (
    DecryptionError,
    KmsKeyService,
    LocalKeyService,
    configure_key_service,
    key_service,
    open_sealed,
    seal,
)

from .support import (
    FAKE_ACCOUNT,
    FAKE_REGION,
    PLATFORM_ALIAS,
    TENANT_ALIAS_PREFIX,
    FakeKms,
    afails,
    as_kms,
    fails,
    kms_client,
    use_environment,
    use_staging,
)

if TYPE_CHECKING:
    from types_boto3_kms import KMSClient

TENANT_A = uuid.UUID("0a0a0a0a-0a0a-4a0a-8a0a-0a0a0a0a0a0a")
TENANT_B = uuid.UUID("0b0b0b0b-0b0b-4b0b-8b0b-0b0b0b0b0b0b")
FINGERPRINT = "a" * 64
OTHER_FINGERPRINT = "b" * 64
PLAINTEXT = b"confidential working paper: trial balance for the fake client"
DATA_KEY = bytes(range(32))
KEY_ARN = f"arn:aws:kms:{FAKE_REGION}:{FAKE_ACCOUNT}:key/00000000-0000-4000-8000-000000000000"


def kms_service(client: KMSClient) -> KmsKeyService:
    return KmsKeyService(
        client,
        alias_prefix=TENANT_ALIAS_PREFIX,
        platform_key=PLATFORM_ALIAS,
    )


def context(tenant: uuid.UUID) -> dict[str, str]:
    """The encryption context AC-13 fixes."""
    return {"abacus:tenant": str(tenant), "abacus:purpose": "dek"}


@pytest.fixture
def fake() -> FakeKms:
    return FakeKms()


@pytest.fixture
def service(fake: FakeKms) -> KmsKeyService:
    return kms_service(as_kms(fake))


# --- key_id -------------------------------------------------------------------------------------


def test_ac13_key_id_is_the_deterministic_tenant_alias(service: KmsKeyService) -> None:
    assert service.key_id(TENANT_A) == f"alias/abacus/tenant/{TENANT_A}"
    assert service.key_id(TENANT_A) == service.key_id(TENANT_A)
    assert service.key_id(TENANT_A) != service.key_id(TENANT_B)


def test_ac13_key_id_is_synchronous_and_makes_no_kms_call(
    service: KmsKeyService, fake: FakeKms
) -> None:
    assert not inspect.iscoroutinefunction(service.key_id)
    result = service.key_id(TENANT_A)
    assert isinstance(result, str)
    assert fake.calls == []


# --- wrap and unwrap ----------------------------------------------------------------------------


async def test_ac13_wrap_calls_kms_encrypt_on_the_data_key_with_the_tenant_context() -> None:
    client = kms_client()
    stub = Stubber(client)
    stub.add_response(
        "encrypt",
        {"CiphertextBlob": b"c" * 180, "KeyId": KEY_ARN},
        expected_params={
            "KeyId": f"alias/abacus/tenant/{TENANT_A}",
            "Plaintext": DATA_KEY,
            "EncryptionContext": context(TENANT_A),
        },
    )
    with stub:
        wrapped = await kms_service(client).wrap(TENANT_A, DATA_KEY)
    stub.assert_no_pending_responses()
    assert isinstance(wrapped, bytes)
    assert DATA_KEY not in wrapped


async def test_ac13_unwrap_presents_the_same_tenant_context_to_kms(
    service: KmsKeyService, fake: FakeKms
) -> None:
    wrapped = await service.wrap(TENANT_A, DATA_KEY)
    assert await service.unwrap(TENANT_A, service.key_id(TENANT_A), wrapped) == DATA_KEY
    (decrypt,) = fake.calls_to("decrypt")
    assert decrypt["EncryptionContext"] == context(TENANT_A)


async def test_ac13_wrap_and_unwrap_round_trip(service: KmsKeyService) -> None:
    for tenant in (TENANT_A, TENANT_B):
        wrapped = await service.wrap(tenant, DATA_KEY)
        assert await service.unwrap(tenant, service.key_id(tenant), wrapped) == DATA_KEY


async def test_ac13_another_tenants_context_is_refused_with_decryption_error(
    service: KmsKeyService, fake: FakeKms
) -> None:
    wrapped = await service.wrap(TENANT_A, DATA_KEY)
    # B asks, naming A's key: KMS sees B's context on A's ciphertext and refuses.
    with pytest.raises(DecryptionError):
        await service.unwrap(TENANT_B, service.key_id(TENANT_A), wrapped)
    # B asks, naming its own key: still refused.
    with pytest.raises(DecryptionError):
        await service.unwrap(TENANT_B, service.key_id(TENANT_B), wrapped)
    assert all(call["EncryptionContext"] == context(TENANT_B) for call in fake.calls_to("decrypt"))


async def test_ac13_a_kms_refusal_is_a_decryption_error() -> None:
    client = kms_client()
    stub = Stubber(client)
    stub.add_client_error("decrypt", service_error_code="InvalidCiphertextException")
    with stub, pytest.raises(DecryptionError):
        await kms_service(client).unwrap(TENANT_A, f"alias/abacus/tenant/{TENANT_A}", b"w" * 180)


# --- seal and open_sealed through KMS -----------------------------------------------------------


async def test_ac13_seal_sends_only_a_data_key_to_kms_never_the_plaintext(
    service: KmsKeyService, fake: FakeKms
) -> None:
    configure_key_service(service)
    sealed = await seal(TENANT_A, PLAINTEXT, FINGERPRINT)
    await seal(TENANT_A, PLAINTEXT, FINGERPRINT)
    first, second = fake.calls_to("encrypt")
    for call in (first, second):
        assert call["EncryptionContext"] == context(TENANT_A)
        assert len(call["Plaintext"]) == 32  # a 256-bit data key
        assert PLAINTEXT not in bytes(call["Plaintext"])
    assert first["Plaintext"] != second["Plaintext"]  # one data key per object
    assert PLAINTEXT not in sealed


async def test_ac13_sealed_objects_round_trip_through_kms(service: KmsKeyService) -> None:
    configure_key_service(service)
    sealed = await seal(TENANT_A, PLAINTEXT, FINGERPRINT)
    assert await open_sealed(TENANT_A, sealed, FINGERPRINT) == PLAINTEXT


async def test_ac13_another_tenant_cannot_open_a_sealed_object(service: KmsKeyService) -> None:
    configure_key_service(service)
    sealed = await seal(TENANT_A, PLAINTEXT, FINGERPRINT)
    with pytest.raises(DecryptionError):
        await open_sealed(TENANT_B, sealed, FINGERPRINT)


async def test_ac13_the_aad_check_stays_another_fingerprint_is_refused(
    service: KmsKeyService,
) -> None:
    """KMS would hand the data key back; the envelope's own AAD (tenant, fingerprint, key ID)
    still refuses the object."""
    configure_key_service(service)
    sealed = await seal(TENANT_A, PLAINTEXT, FINGERPRINT)
    with pytest.raises(DecryptionError):
        await open_sealed(TENANT_A, sealed, OTHER_FINGERPRINT)


# --- any KMS error fails closed -----------------------------------------------------------------

KMS_ERRORS = [
    "AccessDeniedException",
    "DisabledException",
    "KeyUnavailableException",
    "KMSInternalException",
    "KMSInvalidStateException",
    "NotFoundException",
    "ThrottlingException",
]


@pytest.mark.parametrize("code", KMS_ERRORS)
async def test_ac13_a_kms_error_fails_sealing(code: str) -> None:
    client = kms_client()
    stub = Stubber(client)
    stub.add_client_error("encrypt", service_error_code=code)
    configure_key_service(kms_service(client))
    with stub:
        await afails(lambda: seal(TENANT_A, PLAINTEXT, FINGERPRINT))
    stub.assert_no_pending_responses()


@pytest.mark.parametrize("code", KMS_ERRORS)
async def test_ac13_a_kms_error_fails_opening(code: str, fake: FakeKms) -> None:
    configure_key_service(kms_service(as_kms(fake)))
    sealed = await seal(TENANT_A, PLAINTEXT, FINGERPRINT)

    client = kms_client()
    stub = Stubber(client)
    stub.add_client_error("decrypt", service_error_code=code)
    configure_key_service(kms_service(client))
    with stub:
        error = await afails(lambda: open_sealed(TENANT_A, sealed, FINGERPRINT))
    stub.assert_no_pending_responses()
    assert PLAINTEXT not in str(error).encode()


async def test_ac13_there_is_no_fallback_to_the_local_key_service(fake: FakeKms) -> None:
    fake.fail["encrypt"] = "KMSInternalException"
    configured = kms_service(as_kms(fake))
    configure_key_service(configured)
    await afails(lambda: seal(TENANT_A, PLAINTEXT, FINGERPRINT))
    assert key_service() is configured
    assert not isinstance(key_service(), LocalKeyService)
    # One try, then it fails: nothing retries into another path.
    assert len(fake.calls_to("encrypt")) >= 1
    assert fake.calls_to("decrypt") == []


async def test_ac13_a_kms_outage_while_opening_does_not_fall_back_either(fake: FakeKms) -> None:
    configure_key_service(kms_service(as_kms(fake)))
    sealed = await seal(TENANT_A, PLAINTEXT, FINGERPRINT)
    fake.fail["decrypt"] = "ThrottlingException"
    await afails(lambda: open_sealed(TENANT_A, sealed, FINGERPRINT))
    fake.fail.clear()
    assert (
        await open_sealed(TENANT_A, sealed, FINGERPRINT) == PLAINTEXT
    )  # the outage was transient


# --- selection and the local service ------------------------------------------------------------


@pytest.mark.parametrize("name", ["staging", "production"])
def test_ac13_aws_environments_use_kms_not_the_local_service(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    use_staging(monkeypatch, ABACUS_ENVIRONMENT=name)
    chosen = key_service()
    assert isinstance(chosen, KmsKeyService)
    assert not isinstance(chosen, LocalKeyService)
    assert chosen.key_id(TENANT_A) == f"alias/abacus/tenant/{TENANT_A}"


@pytest.mark.parametrize("name", ["staging", "production"])
def test_ac13_local_key_service_still_refuses_outside_local_and_test(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    use_staging(monkeypatch, ABACUS_ENVIRONMENT=name)
    fails(lambda: LocalKeyService(b"m" * 32))


@pytest.mark.parametrize("name", ["staging", "production"])
def test_ac13_aws_environments_do_not_start_without_kms_settings(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    use_staging(monkeypatch, without=("ABACUS_KMS_PLATFORM_KEY_ALIAS",), ABACUS_ENVIRONMENT=name)
    fails(key_service)


@pytest.mark.parametrize("endpoint", ["https://s3.example.test", "http://10.0.0.5:7070"])
def test_ac13_the_local_service_needs_a_loopback_s3_endpoint(
    monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    use_environment(
        monkeypatch, {"ABACUS_ENVIRONMENT": "local", "ABACUS_S3_ENDPOINT_URL": endpoint}
    )
    fails(key_service)


@pytest.mark.parametrize("endpoint", ["http://127.0.0.1:7070", "http://localhost:7070"])
def test_ac13_the_local_service_is_the_default_locally_on_a_loopback_endpoint(
    monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    use_environment(
        monkeypatch, {"ABACUS_ENVIRONMENT": "test", "ABACUS_S3_ENDPOINT_URL": endpoint}
    )
    assert isinstance(key_service(), LocalKeyService)


# --- the platform key (readiness: "the platform KMS key usable") --------------------------------


async def test_ac24_the_platform_key_probe_passes_when_kms_answers(
    service: KmsKeyService, fake: FakeKms
) -> None:
    await service.check_platform_key()
    assert fake.calls_to("encrypt")
    assert all(call["KeyId"] == PLATFORM_ALIAS for call in fake.calls_to("encrypt"))


async def test_ac24_the_platform_key_probe_fails_when_kms_errors(fake: FakeKms) -> None:
    fake.fail["encrypt"] = "AccessDeniedException"
    await afails(kms_service(as_kms(fake)).check_platform_key)

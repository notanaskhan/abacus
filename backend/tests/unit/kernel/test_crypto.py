"""AC-13 / AC-20: envelope encryption under per-tenant keys (TASK-009 interface contract,
"Crypto"; ADR-035, ADR-104). Expectations come from the contract, not the implementation."""

from __future__ import annotations

import os
import struct
import uuid
from collections.abc import Iterator

import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import (
    DecryptionError,
    KeyService,
    LocalKeyService,
    configure_key_service,
    key_service,
    open_sealed,
    reset_key_service,
    seal,
)

MASTER = b"unit-test-master-key-0123456789abcdef"
FINGERPRINT = "a" * 64
OTHER_FINGERPRINT = "b" * 64
PLAINTEXT = b"confidential trial balance: 1,234.56"
CONNECTIONS = {
    "ABACUS_DATABASE_URL": "postgresql+asyncpg://app@db.example.test:5432/abacus",
    "ABACUS_MIGRATIONS_DATABASE_URL": "postgresql+asyncpg://owner@db.example.test:5432/abacus",
    "ABACUS_RELAY_DATABASE_URL": "postgresql+asyncpg://relay@db.example.test:5432/abacus",
    "ABACUS_IDENTITY_DATABASE_URL": "postgresql+asyncpg://identity@db.example.test:5432/abacus",
    "ABACUS_IDENTITY_ISSUER": "https://idp.example.test",
    "ABACUS_IDENTITY_AUDIENCE": "abacus-api",
    "ABACUS_IDENTITY_JWKS": '{"keys": []}',
    "ABACUS_S3_ENDPOINT_URL": "https://s3.example.test",
    "ABACUS_S3_ACCESS_KEY": "access",
    "ABACUS_S3_SECRET_KEY": "secret",
    "ABACUS_EVIDENCE_BUCKET": "evidence-bucket",
    "ABACUS_TEMPORAL_TARGET": "temporal.example.test:7233",
}


@pytest.fixture
def local_service() -> Iterator[LocalKeyService]:
    """A configured override, removed again in teardown."""
    reset_key_service()
    service = LocalKeyService(MASTER)
    configure_key_service(service)
    yield service
    reset_key_service()


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    for key in list(os.environ):
        if key.startswith("ABACUS_"):
            monkeypatch.delenv(key)
    settings.cache_clear()
    reset_key_service()
    yield monkeypatch
    monkeypatch.undo()
    settings.cache_clear()
    reset_key_service()


class Spy:
    """A key service that delegates to the local one and counts `unwrap` calls."""

    def __init__(self, prefix: str = "local") -> None:
        self._inner = LocalKeyService(MASTER)
        self._prefix = prefix
        self.unwraps = 0

    def key_id(self, tenant_id: uuid.UUID) -> str:
        return f"{self._prefix}:{tenant_id}"

    async def wrap(self, tenant_id: uuid.UUID, data_key: bytes) -> bytes:
        return await self._inner.wrap(tenant_id, data_key)

    async def unwrap(self, tenant_id: uuid.UUID, key_id: str, wrapped: bytes) -> bytes:
        self.unwraps += 1
        return await self._inner.unwrap(tenant_id, self._inner.key_id(tenant_id), wrapped)


def _staging(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    for key, value in CONNECTIONS.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("ABACUS_ENVIRONMENT", name)
    settings.cache_clear()


# --- seal / open_sealed ----------------------------------------------------------------------


async def test_ac13_sealed_bytes_begin_with_the_magic_and_hide_the_plaintext(
    local_service: LocalKeyService,
) -> None:
    sealed = await seal(uuid.uuid4(), PLAINTEXT, FINGERPRINT)
    assert sealed.startswith(b"ABE1")
    assert PLAINTEXT not in sealed
    assert b"confidential" not in sealed


async def test_ac13_open_sealed_returns_the_plaintext(local_service: LocalKeyService) -> None:
    tenant = uuid.uuid4()
    sealed = await seal(tenant, PLAINTEXT, FINGERPRINT)
    assert await open_sealed(tenant, sealed, FINGERPRINT) == PLAINTEXT


async def test_ac13_empty_plaintext_round_trips(local_service: LocalKeyService) -> None:
    tenant = uuid.uuid4()
    sealed = await seal(tenant, b"", FINGERPRINT)
    assert await open_sealed(tenant, sealed, FINGERPRINT) == b""


async def test_ac13_two_seals_of_the_same_input_differ(local_service: LocalKeyService) -> None:
    tenant = uuid.uuid4()
    first = await seal(tenant, PLAINTEXT, FINGERPRINT)
    second = await seal(tenant, PLAINTEXT, FINGERPRINT)
    assert first != second
    assert await open_sealed(tenant, first, FINGERPRINT) == PLAINTEXT
    assert await open_sealed(tenant, second, FINGERPRINT) == PLAINTEXT


async def test_ac13_another_tenant_cannot_open_the_object(local_service: LocalKeyService) -> None:
    sealed = await seal(uuid.uuid4(), PLAINTEXT, FINGERPRINT)
    with pytest.raises(DecryptionError):
        await open_sealed(uuid.uuid4(), sealed, FINGERPRINT)


async def test_ac13_another_fingerprint_cannot_open_the_object(
    local_service: LocalKeyService,
) -> None:
    tenant = uuid.uuid4()
    sealed = await seal(tenant, PLAINTEXT, FINGERPRINT)
    with pytest.raises(DecryptionError):
        await open_sealed(tenant, sealed, OTHER_FINGERPRINT)


async def test_ac13_every_flipped_byte_is_refused(local_service: LocalKeyService) -> None:
    tenant = uuid.uuid4()
    sealed = await seal(tenant, PLAINTEXT, FINGERPRINT)
    for position in range(len(sealed)):
        tampered = bytearray(sealed)
        tampered[position] ^= 0x01
        with pytest.raises(DecryptionError):
            await open_sealed(tenant, bytes(tampered), FINGERPRINT)


async def test_ac13_every_truncation_is_refused(local_service: LocalKeyService) -> None:
    tenant = uuid.uuid4()
    sealed = await seal(tenant, PLAINTEXT, FINGERPRINT)
    for length in range(len(sealed)):
        with pytest.raises(DecryptionError):
            await open_sealed(tenant, sealed[:length], FINGERPRINT)


async def test_ac13_a_wrong_magic_number_is_refused(local_service: LocalKeyService) -> None:
    tenant = uuid.uuid4()
    sealed = await seal(tenant, PLAINTEXT, FINGERPRINT)
    with pytest.raises(DecryptionError):
        await open_sealed(tenant, b"ABE2" + sealed[4:], FINGERPRINT)
    with pytest.raises(DecryptionError):
        await open_sealed(tenant, PLAINTEXT, FINGERPRINT)


async def test_ac13_a_key_id_longer_than_4096_is_refused(local_service: LocalKeyService) -> None:
    tenant = uuid.uuid4()
    sealed = await seal(tenant, PLAINTEXT, FINGERPRINT)
    key_len = struct.unpack_from(">H", sealed, 4)[0]
    rest = sealed[6 + key_len :]
    oversized = b"ABE1" + struct.pack(">H", 4097) + b"k" * 4097 + rest
    with pytest.raises(DecryptionError):
        await open_sealed(tenant, oversized, FINGERPRINT)


async def test_ac13_a_wrapped_key_longer_than_4096_is_refused(
    local_service: LocalKeyService,
) -> None:
    tenant = uuid.uuid4()
    sealed = await seal(tenant, PLAINTEXT, FINGERPRINT)
    key_len = struct.unpack_from(">H", sealed, 4)[0]
    key_part = sealed[: 6 + key_len]
    wrapped_len = struct.unpack_from(">H", sealed, 6 + key_len)[0]
    rest = sealed[6 + key_len + 2 + wrapped_len :]
    oversized = key_part + struct.pack(">H", 4097) + b"w" * 4097 + rest
    with pytest.raises(DecryptionError):
        await open_sealed(tenant, oversized, FINGERPRINT)


async def test_ac13_an_object_sealed_under_another_master_key_is_refused(
    local_service: LocalKeyService,
) -> None:
    tenant = uuid.uuid4()
    sealed = await seal(tenant, PLAINTEXT, FINGERPRINT)
    configure_key_service(LocalKeyService(b"a-different-master-key-0123456789ab"))
    with pytest.raises(DecryptionError):
        await open_sealed(tenant, sealed, FINGERPRINT)


# --- LocalKeyService -------------------------------------------------------------------------


def test_ac13_local_key_id_names_the_tenant() -> None:
    tenant = uuid.uuid4()
    assert LocalKeyService(MASTER).key_id(tenant) == f"local:{tenant}"


def test_ac13_a_master_key_under_32_bytes_is_refused() -> None:
    with pytest.raises(ValueError):
        LocalKeyService(b"x" * 31)
    LocalKeyService(b"x" * 32)


@pytest.mark.parametrize("name", ["staging", "production"])
def test_ac13_local_key_service_is_refused_outside_local_and_test(
    environment: pytest.MonkeyPatch, name: str
) -> None:
    _staging(environment, name)
    with pytest.raises(RuntimeError):
        LocalKeyService(MASTER)


@pytest.mark.parametrize("name", ["local", "test"])
def test_ac13_local_key_service_is_allowed_in_local_and_test(
    environment: pytest.MonkeyPatch, name: str
) -> None:
    environment.setenv("ABACUS_ENVIRONMENT", name)
    settings.cache_clear()
    LocalKeyService(MASTER)


async def test_ac13_wrap_and_unwrap_round_trip_and_wrapping_is_randomised() -> None:
    service = LocalKeyService(MASTER)
    tenant = uuid.uuid4()
    key = os.urandom(32)
    first = await service.wrap(tenant, key)
    second = await service.wrap(tenant, key)
    assert key not in first
    assert first != second
    assert await service.unwrap(tenant, service.key_id(tenant), first) == key


async def test_ac13_unwrap_with_another_tenants_key_id_is_refused() -> None:
    service = LocalKeyService(MASTER)
    owner, other = uuid.uuid4(), uuid.uuid4()
    wrapped = await service.wrap(owner, os.urandom(32))
    with pytest.raises(DecryptionError):
        await service.unwrap(other, service.key_id(owner), wrapped)
    with pytest.raises(DecryptionError):
        await service.unwrap(owner, service.key_id(other), wrapped)


async def test_ac13_unwrap_of_a_key_wrapped_for_another_tenant_is_refused() -> None:
    service = LocalKeyService(MASTER)
    owner, other = uuid.uuid4(), uuid.uuid4()
    wrapped = await service.wrap(owner, os.urandom(32))
    with pytest.raises(DecryptionError):
        await service.unwrap(other, service.key_id(other), wrapped)


# --- the default key service -----------------------------------------------------------------


@pytest.mark.parametrize("name", ["local", "test"])
def test_ac13_default_key_service_is_local_in_local_and_test(
    environment: pytest.MonkeyPatch, name: str
) -> None:
    environment.setenv("ABACUS_ENVIRONMENT", name)
    settings.cache_clear()
    service: KeyService = key_service()
    assert isinstance(service, LocalKeyService)


@pytest.mark.parametrize("name", ["staging", "production"])
def test_ac13_default_key_service_refuses_to_start_in_aws_environments(
    environment: pytest.MonkeyPatch, name: str
) -> None:
    _staging(environment, name)
    with pytest.raises(RuntimeError):
        key_service()


def test_ac13_a_configured_override_is_used(local_service: LocalKeyService) -> None:
    assert key_service() is local_service


@pytest.mark.parametrize("endpoint", ["https://s3.example.test", "http://10.0.0.5:7070"])
def test_ac13_default_key_service_refuses_a_non_loopback_endpoint_even_locally(
    environment: pytest.MonkeyPatch, endpoint: str
) -> None:
    environment.setenv("ABACUS_ENVIRONMENT", "local")
    environment.setenv("ABACUS_S3_ENDPOINT_URL", endpoint)
    settings.cache_clear()
    with pytest.raises(RuntimeError):
        key_service()


@pytest.mark.parametrize(
    "endpoint", ["http://127.0.0.1:7070", "http://localhost:7070", "http://[::1]:7070"]
)
def test_ac13_default_key_service_accepts_loopback_endpoints(
    environment: pytest.MonkeyPatch, endpoint: str
) -> None:
    environment.setenv("ABACUS_ENVIRONMENT", "test")
    environment.setenv("ABACUS_S3_ENDPOINT_URL", endpoint)
    settings.cache_clear()
    assert isinstance(key_service(), LocalKeyService)


def test_ac13_reset_key_service_removes_the_override(
    environment: pytest.MonkeyPatch,
) -> None:
    environment.setenv("ABACUS_ENVIRONMENT", "local")
    settings.cache_clear()
    override = LocalKeyService(b"override-master-key-0123456789abcdef")
    configure_key_service(override)
    assert key_service() is override
    reset_key_service()
    assert key_service() is not override
    assert isinstance(key_service(), LocalKeyService)


# --- revision 1: key id, wrapped-key length, no raw errors -------------------------------------


async def test_ac13_an_envelope_naming_another_key_id_is_refused_without_unwrapping() -> None:
    tenant = uuid.uuid4()
    reset_key_service()
    configure_key_service(Spy(prefix="rogue"))
    try:
        sealed = await seal(tenant, PLAINTEXT, FINGERPRINT)
        spy = Spy(prefix="local")
        configure_key_service(spy)
        with pytest.raises(DecryptionError):
            await open_sealed(tenant, sealed, FINGERPRINT)
        assert spy.unwraps == 0
    finally:
        reset_key_service()


async def test_ac13_a_matching_key_id_does_unwrap() -> None:
    tenant = uuid.uuid4()
    spy = Spy()
    reset_key_service()
    configure_key_service(spy)
    try:
        sealed = await seal(tenant, PLAINTEXT, FINGERPRINT)
        assert await open_sealed(tenant, sealed, FINGERPRINT) == PLAINTEXT
        assert spy.unwraps == 1
    finally:
        reset_key_service()


async def test_ac13_a_wrapped_key_shorter_than_44_bytes_is_refused(
    local_service: LocalKeyService,
) -> None:
    tenant = uuid.uuid4()
    sealed = await seal(tenant, PLAINTEXT, FINGERPRINT)
    key_len = struct.unpack_from(">H", sealed, 4)[0]
    key_part = sealed[: 6 + key_len]
    for length in (0, 1, 12, 43):
        short = key_part + struct.pack(">H", length) + b"w" * length + os.urandom(12 + 32)
        with pytest.raises(DecryptionError):
            await open_sealed(tenant, short, FINGERPRINT)


async def test_ac13_arbitrary_bytes_only_ever_raise_decryption_error(
    local_service: LocalKeyService,
) -> None:
    tenant = uuid.uuid4()
    sealed = await seal(tenant, PLAINTEXT, FINGERPRINT)
    key_len = struct.unpack_from(">H", sealed, 4)[0]
    header = sealed[: 6 + key_len]
    for size in range(0, 200, 3):
        for blob in (
            b"ABE1" + os.urandom(size),
            header + os.urandom(size),
            header + struct.pack(">H", 44) + os.urandom(size),
        ):
            with pytest.raises(DecryptionError):
                await open_sealed(tenant, blob, FINGERPRINT)

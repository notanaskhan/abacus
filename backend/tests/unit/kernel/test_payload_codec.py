"""AC-20: the Temporal payload codec (a keyring), its settings and the Temporal client helpers
(TASK-010b interface contract and revision 1, "Encryption"). Expectations are the contract's."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from temporalio.api.common.v1 import Payload
from temporalio.client import Client
from temporalio.converter import DataConverter, DefaultFailureConverterWithEncodedAttributes

from abacus.kernel.config import Settings, settings
from abacus.kernel.crypto.payload_codec import (
    ENCODING,
    PayloadDecryptionError,
    PayloadEncryptionCodec,
)
from abacus.kernel.temporal import (
    SEALING_ID,
    configure_temporal_client,
    data_converter,
    payload_codec,
    temporal_client,
)

SECRET = b"test-payload-secret-0123456789abcdef-xyz"
OTHER_SECRET = b"test-other-secret-0123456789abcdefghij"
REAL_KEY = "test-payload-key-Zq8Xv2Lm9Wd4Rt7Bn3Hs"
PLAINTEXT = b'{"tenant_id": "test-distinctive-plaintext-4417"}'


def _payload(data: bytes = PLAINTEXT) -> Payload:
    return Payload(metadata={"encoding": b"json/plain"}, data=data)


def _codec(secret: bytes = SECRET, key_id: str = "platform-v1") -> PayloadEncryptionCodec:
    return PayloadEncryptionCodec({key_id: secret}, current=key_id)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    for key in list(os.environ):
        if key.startswith("ABACUS_"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    settings.cache_clear()
    configure_temporal_client(None)
    yield
    configure_temporal_client(None)
    settings.cache_clear()


def _explicit_env(
    monkeypatch: pytest.MonkeyPatch, environment: str, *, key: bool = True, tls: bool = True
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    values = {
        "database_url": "postgresql+asyncpg://app@db.example.test:5432/abacus",
        "migrations_database_url": "postgresql+asyncpg://owner@db.example.test:5432/abacus",
        "relay_database_url": "postgresql+asyncpg://relay@db.example.test:5432/abacus",
        "identity_database_url": "postgresql+asyncpg://identity@db.example.test:5432/abacus",
        "identity_issuer": "https://idp.example.test",
        "identity_audience": "abacus-api",
        "identity_jwks": '{"keys": []}',
        "temporal_target": "temporal.example.test:7233",
        "evidence_bucket": "test-evidence-bucket",
    }
    if key:
        values["temporal_payload_key"] = REAL_KEY
    if tls:
        values["temporal_tls"] = "true"
        values["temporal_api_key"] = "test-temporal-api-key"
    for name in Settings.model_fields:
        if name.startswith("s3_"):
            values[name] = "https://s3.example.test"
    for name, value in values.items():
        monkeypatch.setenv(f"ABACUS_{name.upper()}", value)


# --- construction --------------------------------------------------------------------------------


def test_ac20_the_encoding_constant_is_the_contract_value() -> None:
    assert ENCODING == b"binary/abacus-encrypted"


@pytest.mark.parametrize("length", [0, 1, 16, 31])
def test_ac20_a_short_secret_is_a_value_error(length: int) -> None:
    with pytest.raises(ValueError):
        PayloadEncryptionCodec({"platform-v1": b"k" * length}, current="platform-v1")


def test_ac20_a_short_secret_anywhere_in_the_keyring_is_a_value_error() -> None:
    with pytest.raises(ValueError):
        PayloadEncryptionCodec({"test-a": SECRET, "test-b": b"short"}, current="test-a")


def test_ac20_a_32_byte_secret_is_accepted() -> None:
    PayloadEncryptionCodec({"platform-v1": b"k" * 32}, current="platform-v1")


def test_ac20_a_current_key_outside_the_keyring_is_a_value_error() -> None:
    with pytest.raises(ValueError):
        PayloadEncryptionCodec({"test-a": SECRET}, current="test-b")


def test_ac20_an_empty_keyring_is_a_value_error() -> None:
    with pytest.raises(ValueError):
        PayloadEncryptionCodec({}, current="platform-v1")


# --- encode and decode ---------------------------------------------------------------------------


async def test_ac20_encode_gives_one_encrypted_payload_per_input() -> None:
    codec = _codec(key_id="test-key-7")
    sealed = await codec.encode([_payload(b"one"), _payload(b"two"), _payload(PLAINTEXT)])
    assert len(sealed) == 3
    for payload in sealed:
        assert payload.metadata["encoding"] == b"binary/abacus-encrypted"
        assert payload.metadata["encryption-key-id"] == b"test-key-7"


async def test_ac20_encode_of_nothing_is_nothing() -> None:
    assert list(await _codec().encode([])) == []


async def test_ac20_encoded_data_does_not_contain_the_plaintext() -> None:
    [sealed] = await _codec().encode([_payload()])
    assert PLAINTEXT not in sealed.data
    assert b"test-distinctive-plaintext-4417" not in sealed.SerializeToString()


async def test_ac20_encoded_data_differs_on_every_call() -> None:
    codec = _codec()
    assert (await codec.encode([_payload()]))[0].data != (await codec.encode([_payload()]))[0].data


async def test_ac20_decode_of_encode_is_the_original() -> None:
    codec = _codec()
    inputs = [_payload(b"one"), _payload(PLAINTEXT), _payload(b"")]
    assert list(await codec.decode(await codec.encode(inputs))) == inputs


async def test_ac20_a_second_codec_with_the_same_secret_and_key_id_decodes() -> None:
    sealed = await _codec().encode([_payload()])
    assert list(await _codec().decode(sealed)) == [_payload()]


async def test_ac20_a_keyring_encodes_with_the_current_key_and_decodes_any_known_key() -> None:
    old = _codec(SECRET, "test-old")
    ring = PayloadEncryptionCodec(
        {"test-old": SECRET, "test-new": OTHER_SECRET}, current="test-new"
    )
    sealed_old = await old.encode([_payload()])
    [sealed_new] = await ring.encode([_payload()])
    assert sealed_new.metadata["encryption-key-id"] == b"test-new"
    assert list(await ring.decode(sealed_old)) == [_payload()]
    assert list(await ring.decode([sealed_new])) == [_payload()]
    with pytest.raises(PayloadDecryptionError):
        await old.decode([sealed_new])  # the old codec doesn't hold the new key


# --- decode refusals -----------------------------------------------------------------------------


async def test_ac20_decode_refuses_plain_json_instead_of_passing_it_through() -> None:
    plain = Payload(metadata={"encoding": b"json/plain"}, data=b'{"a": 1}')
    with pytest.raises(PayloadDecryptionError):
        await _codec().decode([plain])


async def test_ac20_decode_refuses_a_payload_with_no_metadata() -> None:
    with pytest.raises(PayloadDecryptionError):
        await _codec().decode([Payload(data=b"x" * 64)])


async def test_ac20_decode_refuses_an_unknown_key_id() -> None:
    sealed = await _codec(key_id="test-key-a").encode([_payload()])
    with pytest.raises(PayloadDecryptionError):
        await _codec(key_id="test-key-b").decode(sealed)


async def test_ac20_decode_refuses_a_relabelled_key_id() -> None:
    codec = PayloadEncryptionCodec(
        {"test-key-a": SECRET, "test-key-b": SECRET}, current="test-key-a"
    )
    [sealed] = await codec.encode([_payload()])
    sealed.metadata["encryption-key-id"] = b"test-key-b"
    with pytest.raises(PayloadDecryptionError):
        await codec.decode([sealed])


async def test_ac20_decode_refuses_an_unknown_encoding_even_with_a_known_key_id() -> None:
    [sealed] = await _codec().encode([_payload()])
    sealed.metadata["encoding"] = b"binary/plain"
    with pytest.raises(PayloadDecryptionError):
        await _codec().decode([sealed])


@pytest.mark.parametrize("position", [0, 5, 12, -1])
async def test_ac20_decode_refuses_flipped_bytes(position: int) -> None:
    codec = _codec()
    [sealed] = await codec.encode([_payload()])
    data = bytearray(sealed.data)
    data[position] ^= 0x01
    sealed.data = bytes(data)
    with pytest.raises(PayloadDecryptionError):
        await codec.decode([sealed])


async def test_ac20_decode_refuses_truncated_data() -> None:
    codec = _codec()
    [sealed] = await codec.encode([_payload()])
    sealed.data = sealed.data[:8]
    with pytest.raises(PayloadDecryptionError):
        await codec.decode([sealed])


async def test_ac20_decode_refuses_a_codec_with_another_secret() -> None:
    sealed = await _codec(SECRET).encode([_payload()])
    with pytest.raises(PayloadDecryptionError):
        await _codec(OTHER_SECRET).decode(sealed)


async def test_ac20_one_bad_payload_in_a_batch_fails_the_batch() -> None:
    codec = _codec()
    sealed = [*await codec.encode([_payload()]), _payload()]
    with pytest.raises(PayloadDecryptionError):
        await codec.decode(sealed)


# --- settings ------------------------------------------------------------------------------------


@pytest.mark.parametrize("environment", ["local", "test"])
def test_ac20_local_and_test_have_a_default_payload_key(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    key = Settings().temporal_payload_key
    assert key is not None
    assert len(key.get_secret_value()) >= 32


def test_ac20_the_payload_key_is_not_echoed_by_repr() -> None:
    value = Settings()
    assert value.temporal_payload_key is not None
    assert value.temporal_payload_key.get_secret_value() not in repr(value)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac20_the_payload_key_is_required_outside_local_and_test(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _explicit_env(monkeypatch, environment, key=False)
    with pytest.raises(ValueError):
        Settings()


@pytest.mark.parametrize("environment", ["local", "test", "staging", "production"])
@pytest.mark.parametrize("weak", ["test-short", "a" * 40, "ab" * 20])
def test_ac20_a_short_or_unvaried_payload_key_is_a_validation_error_in_any_environment(
    monkeypatch: pytest.MonkeyPatch, environment: str, weak: str
) -> None:
    if environment in ("staging", "production"):
        _explicit_env(monkeypatch, environment)
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    monkeypatch.setenv("ABACUS_TEMPORAL_PAYLOAD_KEY", weak)
    with pytest.raises(ValueError):
        Settings()


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac20_an_example_payload_key_outside_local_and_test_is_a_validation_error(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _explicit_env(monkeypatch, environment)
    monkeypatch.setenv("ABACUS_TEMPORAL_PAYLOAD_KEY", "example-Zq8Xv2Lm9Wd4Rt7Bn3Hs-Kp5Yc")
    with pytest.raises(ValueError):
        Settings()


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac20_the_payload_key_error_does_not_echo_the_key(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _explicit_env(monkeypatch, environment)
    key = "example-test-distinctive-key-material-9921"
    monkeypatch.setenv("ABACUS_TEMPORAL_PAYLOAD_KEY", key)
    with pytest.raises(ValueError) as raised:
        Settings()
    assert key not in str(raised.value)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac20_a_real_payload_key_with_tls_and_an_api_key_loads(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _explicit_env(monkeypatch, environment)
    loaded = Settings()
    assert loaded.temporal_payload_key is not None
    assert loaded.temporal_payload_key.get_secret_value() == REAL_KEY
    assert loaded.temporal_tls is True
    assert loaded.temporal_api_key is not None


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac20_temporal_needs_tls_and_an_api_key_outside_local_and_test(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    _explicit_env(monkeypatch, environment, tls=False)
    with pytest.raises(ValueError):
        Settings()
    monkeypatch.setenv("ABACUS_TEMPORAL_TLS", "true")
    with pytest.raises(ValueError):  # TLS alone is not enough
        Settings()
    monkeypatch.delenv("ABACUS_TEMPORAL_TLS")
    monkeypatch.setenv("ABACUS_TEMPORAL_API_KEY", "test-temporal-api-key")
    with pytest.raises(ValueError):  # nor an API key alone
        Settings()


@pytest.mark.parametrize("environment", ["local", "test"])
def test_ac20_local_and_test_need_neither_tls_nor_an_api_key(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    assert Settings().temporal_api_key is None


@pytest.mark.parametrize("environment", ["local", "test"])
def test_ac20_an_example_payload_key_is_allowed_in_local_and_test(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    monkeypatch.setenv("ABACUS_TEMPORAL_PAYLOAD_KEY", "example-Zq8Xv2Lm9Wd4Rt7Bn3Hs-Kp5Yc")
    assert Settings().temporal_payload_key is not None


def test_ac20_temporal_namespace_and_task_queue_defaults() -> None:
    value = Settings()
    assert value.temporal_namespace == "default"
    assert value.temporal_task_queue == "abacus"


def test_ac20_temporal_namespace_and_task_queue_come_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ABACUS_TEMPORAL_NAMESPACE", "test-namespace")
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", "test-queue")
    value = Settings()
    assert (value.temporal_namespace, value.temporal_task_queue) == (
        "test-namespace",
        "test-queue",
    )


# --- the kernel Temporal helpers -----------------------------------------------------------------


def test_ac20_the_sealing_id_is_platform_v1() -> None:
    assert SEALING_ID == "platform-v1"


async def test_ac20_payload_codec_is_built_from_the_settings_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ABACUS_TEMPORAL_PAYLOAD_KEY", REAL_KEY)
    settings.cache_clear()
    codec = payload_codec()
    assert isinstance(codec, PayloadEncryptionCodec)
    assert codec.key_id == SEALING_ID
    [sealed] = await codec.encode([_payload()])
    assert sealed.metadata["encryption-key-id"] == SEALING_ID.encode()
    assert list(await _codec(REAL_KEY.encode()).decode([sealed])) == [_payload()]


def test_ac20_data_converter_carries_the_codec_and_the_encoded_failure_converter() -> None:
    converter = data_converter()
    assert isinstance(converter, DataConverter)
    assert isinstance(converter.payload_codec, PayloadEncryptionCodec)
    assert converter.failure_converter_class is DefaultFailureConverterWithEncodedAttributes


async def test_ac20_data_converter_encrypts_and_decrypts_values() -> None:
    converter = data_converter()
    value = {"run_id": str(uuid.uuid4())}
    sealed = await converter.encode([value])
    assert all(p.metadata["encoding"] == ENCODING for p in sealed)
    assert await converter.decode(sealed, [dict]) == [value]


class _Stub:
    """Stands in for a connected client; only identity matters."""


async def test_ac20_configure_temporal_client_overrides_and_none_resets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _Stub()
    configure_temporal_client(cast(Client, stub))
    assert await temporal_client() is stub
    configure_temporal_client(None)
    seen: dict[str, object] = {}

    async def connect(target: str, **kwargs: object) -> object:
        seen["target"] = target
        seen.update(kwargs)
        return stub

    monkeypatch.setattr(Client, "connect", connect)
    assert await temporal_client() is stub
    assert seen["target"] == "127.0.0.1:7233"
    assert seen["namespace"] == "default"
    converter = seen["data_converter"]
    assert isinstance(converter, DataConverter)
    assert isinstance(converter.payload_codec, PayloadEncryptionCodec)

"""Envelope encryption under per-tenant keys (ADR-035, ADR-104). PROTECTED. TASK-009 design §2.

    sealed = await seal(tenant_id, plaintext, fingerprint)
    plaintext = await open_sealed(tenant_id, sealed, fingerprint)

Every object gets a fresh 256-bit data key and AES-256-GCM. The data key is wrapped by the
tenant's key through the configured `KeyService`. The tenant ID and the content fingerprint are
bound as associated data: an object can't be opened as another tenant's, or as other content. The
only package that imports `cryptography` (CRYPTO-001).

Envelope format v1 (all lengths big-endian):
    b"ABE1" | key_id_len:u16 | key_id | wrapped_len:u16 | wrapped | nonce(12) | ciphertext+tag
"""

from __future__ import annotations

import asyncio
import os
import struct
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from urllib.parse import urlsplit
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from abacus.kernel.config import LOCAL_STACK, settings
from abacus.kernel.errors import ServiceUnavailable
from abacus.kernel.logging import get_logger
from abacus.kernel.storage import AwsError, error_code, kms_client

if TYPE_CHECKING:
    from types_boto3_kms import KMSClient

_log = get_logger(__name__)

MAGIC = b"ABE1"
_NONCE = 12
_TAG = 16
_MAX_HEADER_FIELD = 4096
_MIN_WRAPPED = _NONCE + 16 + _TAG  # no key service wraps a 256-bit key into less


class DecryptionError(Exception):
    """The object can't be opened: tampered, wrong tenant, wrong fingerprint or unknown key."""


class KeyService(Protocol):
    """Wraps data keys under a tenant's key. AWS: KMS, one key per firm (TASK-014).

    Implementations must bind the tenant into the wrap (local: AAD; KMS: EncryptionContext) and
    must only unwrap with a key ID that belongs to the tenant; `open_sealed` also checks the
    envelope's key ID against `key_id(tenant)` before calling `unwrap`."""

    def key_id(self, tenant_id: UUID) -> str: ...

    async def wrap(self, tenant_id: UUID, data_key: bytes) -> bytes: ...

    async def unwrap(self, tenant_id: UUID, key_id: str, wrapped: bytes) -> bytes: ...


class LocalKeyService:
    """Local and test only: tenant key = HKDF-SHA256(local master key, info = tenant ID)."""

    def __init__(self, master_key: bytes) -> None:
        if settings().environment not in ("local", "test"):
            raise RuntimeError("LocalKeyService is for local runs and tests only (ADR-104)")
        if len(master_key) < 32:
            raise ValueError("local master key must be at least 32 bytes")
        self._master = master_key

    def key_id(self, tenant_id: UUID) -> str:
        return f"local:{tenant_id}"

    def _tenant_key(self, tenant_id: UUID) -> AESGCM:
        derived = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"abacus-tenant-key-v1",
            info=tenant_id.bytes,
        ).derive(self._master)
        return AESGCM(derived)

    async def wrap(self, tenant_id: UUID, data_key: bytes) -> bytes:
        nonce = os.urandom(_NONCE)
        return nonce + self._tenant_key(tenant_id).encrypt(nonce, data_key, tenant_id.bytes)

    async def unwrap(self, tenant_id: UUID, key_id: str, wrapped: bytes) -> bytes:
        if key_id != self.key_id(tenant_id):
            raise DecryptionError("key does not belong to this tenant")
        try:
            return self._tenant_key(tenant_id).decrypt(
                wrapped[:_NONCE], wrapped[_NONCE:], tenant_id.bytes
            )
        except (InvalidTag, ValueError):
            raise DecryptionError("data key can't be unwrapped") from None


class KeyServiceUnavailable(ServiceUnavailable):
    """The key service can't be reached or failed: sealing and opening fail closed (503). Not a
    `DecryptionError`: callers treat that as "this object does not open" and move on, which an
    outage must never look like."""


# KMS answers that mean this ciphertext can't be opened with this key and context, now: wrong
# encryption context (another tenant), wrong or disabled key, a key scheduled for deletion or gone
# (a crypto-shredded tenant), or a policy refusing the caller. Every other error is an outage.
_KMS_REFUSALS = frozenset(
    {"InvalidCiphertextException", "IncorrectKeyException", "InvalidKeyUsageException"}
    | {"AccessDeniedException", "DisabledException", "KMSInvalidStateException"}
    | {"NotFoundException"}
)
_DEK_PURPOSE = "dek"
_PROBE_PURPOSE = "readyz"


class KmsKeyService:
    """AWS KMS, one key per tenant (ADR-035, ADR-104; SPEC-050 AC-13). Each per-object data key is
    wrapped by KMS `Encrypt` under the tenant's key with the encryption context
    `{"abacus:tenant": <tenant id>, "abacus:purpose": "dek"}`, so KMS itself refuses an unwrap
    under another tenant's context (and `Decrypt` names the key, so it refuses another key too).
    `key_id` is the tenant's deterministic alias, `<alias_prefix><tenant id>`; the key behind the
    alias is made by the tenant key workflow, not here. Any error fails closed: there is no
    fallback to `LocalKeyService`, and a refusal is a `DecryptionError` where an outage is a
    `KeyServiceUnavailable`.

    `client` is a boto3 KMS client; its calls are blocking, so they run in a thread."""

    def __init__(self, client: KMSClient, *, alias_prefix: str, platform_key: str | None) -> None:
        self._client = client
        self._prefix = alias_prefix
        self._platform_key = platform_key

    def key_id(self, tenant_id: UUID) -> str:
        return f"{self._prefix}{tenant_id}"

    @staticmethod
    def _context(tenant_id: UUID) -> dict[str, str]:
        return {"abacus:tenant": str(tenant_id), "abacus:purpose": _DEK_PURPOSE}

    async def wrap(self, tenant_id: UUID, data_key: bytes) -> bytes:
        try:
            response = await asyncio.to_thread(
                self._client.encrypt,
                KeyId=self.key_id(tenant_id),
                Plaintext=data_key,
                EncryptionContext=self._context(tenant_id),
            )
        except AwsError as exc:
            code = error_code(exc)
            _log.warning("kms.wrap_failed", kms_error=code, error_type=type(exc).__name__)
            raise KeyServiceUnavailable("the data key can't be wrapped") from None
        wrapped = response.get("CiphertextBlob")
        if not wrapped:
            raise KeyServiceUnavailable("the data key can't be wrapped")
        return wrapped

    async def unwrap(self, tenant_id: UUID, key_id: str, wrapped: bytes) -> bytes:
        if key_id != self.key_id(tenant_id):
            raise DecryptionError("key does not belong to this tenant")
        try:
            response = await asyncio.to_thread(
                self._client.decrypt,
                CiphertextBlob=wrapped,
                KeyId=key_id,
                EncryptionContext=self._context(tenant_id),
            )
        except AwsError as exc:
            code = error_code(exc)
            _log.warning("kms.unwrap_failed", kms_error=code, error_type=type(exc).__name__)
            if code in _KMS_REFUSALS:
                raise DecryptionError("data key can't be unwrapped") from None
            raise KeyServiceUnavailable("the data key can't be unwrapped") from None
        data_key = response.get("Plaintext")
        if not data_key:
            raise KeyServiceUnavailable("the data key can't be unwrapped")
        return data_key

    async def check_platform_key(self) -> None:
        """Readiness (`/readyz`): the platform key is usable (an `Encrypt` of a probe value)."""
        if not self._platform_key:
            raise KeyServiceUnavailable("no platform key is configured")
        try:
            await asyncio.to_thread(
                self._client.encrypt,
                KeyId=self._platform_key,
                Plaintext=b"readyz",
                EncryptionContext={"abacus:purpose": _PROBE_PURPOSE},
            )
        except AwsError as exc:
            code = error_code(exc)
            _log.warning("kms.probe_failed", kms_error=code, error_type=type(exc).__name__)
            raise KeyServiceUnavailable("the platform key is not usable") from None


_service: KeyService | None = None


def configure_key_service(service: KeyService) -> None:
    global _service
    _service = service


def _is_loopback(endpoint: str | None) -> bool:
    host = urlsplit(endpoint).hostname if endpoint else None
    return host in ("127.0.0.1", "localhost", "::1")


@lru_cache(maxsize=1)
def _from_settings() -> KeyService:
    s = settings()
    # The local master key is public (it's in the repository). Even in "local" (the default
    # environment), it may only protect objects stored on this machine: a deployment that forgot
    # ABACUS_ENVIRONMENT and points at real storage fails here instead of "encrypting" with it.
    if (
        s.environment in ("local", "test")
        and s.local_master_key is not None
        and _is_loopback(s.s3_endpoint_url)
    ):
        return LocalKeyService(s.local_master_key.get_secret_value().encode())
    # Staging and production use KMS (SPEC-050 AC-13), which settings validation guarantees is
    # configured there. Anywhere else, refuse rather than fall back to a key service that is
    # not meant for the data (the local one is for loopback storage only).
    if s.environment not in LOCAL_STACK:
        return KmsKeyService(
            kms_client(region=s.kms_region),
            alias_prefix=s.kms_alias_prefix,
            platform_key=s.kms_platform_key_alias,
        )
    raise RuntimeError("no key service configured for this environment (ADR-104)")


def reset_key_service() -> None:
    """Back to the key service built from settings (test teardown; settings changes)."""
    global _service
    _service = None
    _from_settings.cache_clear()


def key_service() -> KeyService:
    return _service if _service is not None else _from_settings()


@runtime_checkable
class PlatformKeyProbe(Protocol):
    """A key service that can say whether the platform key is usable (AWS: KMS Encrypt)."""

    async def check_platform_key(self) -> None: ...


async def check_platform_key() -> None:
    """Readiness (`/readyz`): the configured key service works. Raises if it doesn't. A service
    with its own probe is asked; any other wraps and unwraps a throwaway key for a probe tenant."""
    service = key_service()
    if isinstance(service, PlatformKeyProbe):
        await service.check_platform_key()
        return
    probe_tenant = UUID(int=0)
    data_key = os.urandom(32)
    wrapped = await service.wrap(probe_tenant, data_key)
    if await service.unwrap(probe_tenant, service.key_id(probe_tenant), wrapped) != data_key:
        raise DecryptionError("key service round trip failed")


def _aad(tenant_id: UUID, fingerprint: str, key_id: str) -> bytes:
    return b"|".join(
        [b"abacus-evidence-v1", tenant_id.bytes, fingerprint.encode(), key_id.encode()]
    )


@dataclass(frozen=True)
class _Envelope:
    key_id: str
    wrapped: bytes
    nonce: bytes
    ciphertext: bytes


def _pack(envelope: _Envelope) -> bytes:
    key_id = envelope.key_id.encode()
    return b"".join(
        [
            MAGIC,
            struct.pack(">H", len(key_id)),
            key_id,
            struct.pack(">H", len(envelope.wrapped)),
            envelope.wrapped,
            envelope.nonce,
            envelope.ciphertext,
        ]
    )


def _unpack(sealed: bytes) -> _Envelope:
    try:
        if sealed[:4] != MAGIC:
            raise DecryptionError("not an envelope")
        offset = 4
        (key_len,) = struct.unpack_from(">H", sealed, offset)
        offset += 2
        if key_len > _MAX_HEADER_FIELD:
            raise DecryptionError("malformed envelope")
        key_id = sealed[offset : offset + key_len].decode()
        offset += key_len
        (wrapped_len,) = struct.unpack_from(">H", sealed, offset)
        offset += 2
        if wrapped_len > _MAX_HEADER_FIELD:
            raise DecryptionError("malformed envelope")
        wrapped = sealed[offset : offset + wrapped_len]
        offset += wrapped_len
        nonce = sealed[offset : offset + _NONCE]
        offset += _NONCE
        ciphertext = sealed[offset:]
    except (struct.error, UnicodeDecodeError):
        raise DecryptionError("malformed envelope") from None
    if (
        len(wrapped) != wrapped_len
        or wrapped_len < _MIN_WRAPPED
        or len(nonce) != _NONCE
        or len(ciphertext) < _TAG
    ):
        raise DecryptionError("malformed envelope")
    return _Envelope(key_id, wrapped, nonce, ciphertext)


async def seal(tenant_id: UUID, plaintext: bytes, fingerprint: str) -> bytes:
    service = key_service()
    key_id = service.key_id(tenant_id)
    data_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(_NONCE)
    ciphertext = AESGCM(data_key).encrypt(nonce, plaintext, _aad(tenant_id, fingerprint, key_id))
    wrapped = await service.wrap(tenant_id, data_key)
    return _pack(_Envelope(key_id, wrapped, nonce, ciphertext))


async def open_sealed(tenant_id: UUID, sealed: bytes, fingerprint: str) -> bytes:
    envelope = _unpack(sealed)
    service = key_service()
    # The header is untrusted: only this tenant's key may be asked to unwrap (ADR-104).
    if envelope.key_id != service.key_id(tenant_id):
        raise DecryptionError("key does not belong to this tenant")
    try:
        data_key = await service.unwrap(tenant_id, envelope.key_id, envelope.wrapped)
        return AESGCM(data_key).decrypt(
            envelope.nonce, envelope.ciphertext, _aad(tenant_id, fingerprint, envelope.key_id)
        )
    except (InvalidTag, ValueError):
        raise DecryptionError("object can't be opened") from None


__all__ = [
    "DecryptionError",
    "KeyService",
    "KeyServiceUnavailable",
    "KmsKeyService",
    "LocalKeyService",
    "PlatformKeyProbe",
    "check_platform_key",
    "configure_key_service",
    "key_service",
    "open_sealed",
    "reset_key_service",
    "seal",
]

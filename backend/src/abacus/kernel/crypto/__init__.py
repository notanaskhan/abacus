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

import os
import struct
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from abacus.kernel.config import settings

MAGIC = b"ABE1"
_NONCE = 12
_MAX_HEADER_FIELD = 4096


class DecryptionError(Exception):
    """The object can't be opened: tampered, wrong tenant, wrong fingerprint or unknown key."""


class KeyService(Protocol):
    """Wraps data keys under a tenant's key. AWS: KMS, one key per firm (TASK-014)."""

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
        except InvalidTag:
            raise DecryptionError("data key can't be unwrapped") from None


_service: KeyService | None = None


def configure_key_service(service: KeyService) -> None:
    global _service
    _service = service


@lru_cache(maxsize=1)
def _from_settings() -> KeyService:
    s = settings()
    if s.environment in ("local", "test") and s.local_master_key is not None:
        return LocalKeyService(s.local_master_key.get_secret_value().encode())
    # AWS environments need the KMS key service (TASK-014): refuse rather than fall back.
    raise RuntimeError("no key service configured for this environment (ADR-104)")


def key_service() -> KeyService:
    return _service if _service is not None else _from_settings()


def _aad(tenant_id: UUID, fingerprint: str) -> bytes:
    return b"abacus-evidence-v1|" + tenant_id.bytes + b"|" + fingerprint.encode()


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
    if len(wrapped) != wrapped_len or len(nonce) != _NONCE or len(ciphertext) < 16:
        raise DecryptionError("malformed envelope")
    return _Envelope(key_id, wrapped, nonce, ciphertext)


async def seal(tenant_id: UUID, plaintext: bytes, fingerprint: str) -> bytes:
    service = key_service()
    data_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(_NONCE)
    ciphertext = AESGCM(data_key).encrypt(nonce, plaintext, _aad(tenant_id, fingerprint))
    wrapped = await service.wrap(tenant_id, data_key)
    return _pack(_Envelope(service.key_id(tenant_id), wrapped, nonce, ciphertext))


async def open_sealed(tenant_id: UUID, sealed: bytes, fingerprint: str) -> bytes:
    envelope = _unpack(sealed)
    data_key = await key_service().unwrap(tenant_id, envelope.key_id, envelope.wrapped)
    try:
        return AESGCM(data_key).decrypt(
            envelope.nonce, envelope.ciphertext, _aad(tenant_id, fingerprint)
        )
    except (InvalidTag, ValueError):
        raise DecryptionError("object can't be opened") from None


__all__ = [
    "DecryptionError",
    "KeyService",
    "LocalKeyService",
    "configure_key_service",
    "key_service",
    "open_sealed",
    "seal",
]

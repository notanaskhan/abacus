"""Temporal payload encryption (ADR-017). PROTECTED. TASK-010 design §6.

Every payload a workflow or activity sends to Temporal is sealed here first: AES-256-GCM under a
platform key derived from `temporal_payload_key`, with the key ID bound as associated data.
Payloads carry identifiers only (TASK-010 design §6), so a platform key, not a per-firm one, is
enough (Q5). A payload that isn't ours, or doesn't open, is refused, never passed through.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from temporalio.api.common.v1 import Payload
from temporalio.converter import PayloadCodec

ENCODING = b"binary/abacus-encrypted"
_NONCE = 12


class PayloadDecryptionError(Exception):
    """A payload that isn't sealed by this platform key, or has been altered."""


class PayloadEncryptionCodec(PayloadCodec):
    def __init__(self, secret: bytes, key_id: str = "platform-v1") -> None:
        if len(secret) < 32:
            raise ValueError("temporal payload key must be at least 32 bytes")
        self.key_id = key_id
        derived = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"abacus-temporal-payloads-v1",
            info=key_id.encode(),
        ).derive(secret)
        self._aead = AESGCM(derived)

    async def encode(self, payloads: Sequence[Payload]) -> list[Payload]:
        sealed: list[Payload] = []
        for payload in payloads:
            nonce = os.urandom(_NONCE)
            ciphertext = self._aead.encrypt(
                nonce, payload.SerializeToString(), self.key_id.encode()
            )
            sealed.append(
                Payload(
                    metadata={"encoding": ENCODING, "encryption-key-id": self.key_id.encode()},
                    data=nonce + ciphertext,
                )
            )
        return sealed

    async def decode(self, payloads: Sequence[Payload]) -> list[Payload]:
        opened: list[Payload] = []
        for payload in payloads:
            if (
                payload.metadata.get("encoding") != ENCODING
                or payload.metadata.get("encryption-key-id") != self.key_id.encode()
            ):
                raise PayloadDecryptionError("payload not sealed by this platform key")
            data = payload.data
            try:
                plain = self._aead.decrypt(data[:_NONCE], data[_NONCE:], self.key_id.encode())
            except (InvalidTag, ValueError):
                raise PayloadDecryptionError("payload can't be opened") from None
            original = Payload()
            original.ParseFromString(plain)
            opened.append(original)
        return opened

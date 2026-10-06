"""Temporal payload encryption (ADR-017). PROTECTED. TASK-010 design §6, revision 1.

Every payload a workflow or activity sends to Temporal is sealed here first: AES-256-GCM under a
platform key, with the key ID bound as associated data. Payloads carry identifiers only (design
§6), so a platform key, not a per-firm one, is enough (Q5). Failure messages and stack traces are
encoded too, through `kernel.temporal`'s failure converter.

Keyring: payloads are sealed with the current key and opened with whichever known key sealed
them, so a key can be rotated without stranding running workflows or recorded histories
(TASK-014 adds the KMS-held keys). A payload that isn't ours, or doesn't open, is refused.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from temporalio.api.common.v1 import Payload
from temporalio.converter import PayloadCodec

ENCODING = b"binary/abacus-encrypted"
_NONCE = 12


class PayloadDecryptionError(Exception):
    """A payload that isn't sealed by a known platform key, or has been altered."""


def _aead(secret: bytes, key_id: str) -> AESGCM:
    if len(secret) < 32:
        raise ValueError("temporal payload key must be at least 32 bytes")
    return AESGCM(
        HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"abacus-temporal-payloads-v1",
            info=key_id.encode(),
        ).derive(secret)
    )


class PayloadEncryptionCodec(PayloadCodec):
    def __init__(self, keys: Mapping[str, bytes], current: str) -> None:
        if current not in keys:
            raise ValueError("the current key must be in the keyring")
        self.key_id = current
        self._keys = {key_id: _aead(secret, key_id) for key_id, secret in keys.items()}

    async def encode(self, payloads: Sequence[Payload]) -> list[Payload]:
        aead = self._keys[self.key_id]
        sealed: list[Payload] = []
        for payload in payloads:
            nonce = os.urandom(_NONCE)
            ciphertext = aead.encrypt(nonce, payload.SerializeToString(), self.key_id.encode())
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
            key_id = payload.metadata.get("encryption-key-id", b"").decode(errors="replace")
            aead = self._keys.get(key_id)
            if payload.metadata.get("encoding") != ENCODING or aead is None:
                raise PayloadDecryptionError("payload not sealed by a known platform key")
            data = payload.data
            try:
                plain = aead.decrypt(data[:_NONCE], data[_NONCE:], key_id.encode())
            except (InvalidTag, ValueError):
                raise PayloadDecryptionError("payload can't be opened") from None
            original = Payload()
            original.ParseFromString(plain)
            opened.append(original)
        return opened

"""Sealed list cursors (ADR-139, P-36; F-03-T29): AES-GCM under a key derived (HKDF) from the
payload keyring the deployment holds, so a cursor names its key id and survives a key being added.
Local runs and tests without a keyring seal with a key made for the process. The associated data
binds a cursor to what it was issued for (`kernel.listing` passes tenant, resource and query)."""

from __future__ import annotations

import base64
import os
from functools import lru_cache
from typing import Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from abacus.kernel.config import LOCAL_STACK, settings
from abacus.kernel.errors import ServiceUnavailable

_VERSION: Final = 1
_NONCE: Final = 12
_INFO: Final = b"abacus.listing.cursor.v1"
_LOCAL_KID: Final = "local"


class CursorUnreadable(ValueError):
    """Not a cursor this deployment sealed for this associated data."""


def _derive(secret: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_INFO).derive(secret)


@lru_cache(maxsize=1)
def _process_key() -> bytes:
    return os.urandom(32)


def _keys() -> tuple[str, dict[str, bytes]]:
    """The current key id and every key a cursor may have been sealed with."""
    s = settings()
    ring = s.temporal_payload_keys
    if ring and s.temporal_payload_current in ring:
        keys = {kid: _derive(secret.get_secret_value().encode()) for kid, secret in ring.items()}
        return s.temporal_payload_current, keys
    if s.environment in LOCAL_STACK:
        return _LOCAL_KID, {_LOCAL_KID: _process_key()}
    raise ServiceUnavailable("no key to seal list cursors with")


def seal_cursor(body: bytes, aad: bytes) -> str:
    kid, keys = _keys()
    nonce = os.urandom(_NONCE)
    sealed = AESGCM(keys[kid]).encrypt(nonce, body, aad)
    kid_bytes = kid.encode()
    token = bytes([_VERSION, len(kid_bytes)]) + kid_bytes + nonce + sealed
    return base64.urlsafe_b64encode(token).rstrip(b"=").decode()


def open_cursor(token: str, aad: bytes) -> bytes:
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except ValueError as exc:
        raise CursorUnreadable from exc
    if len(raw) < 2 or raw[0] != _VERSION:
        raise CursorUnreadable
    kid_end = 2 + raw[1]
    try:
        kid = raw[2:kid_end].decode()
    except UnicodeDecodeError as exc:
        raise CursorUnreadable from exc
    nonce, sealed = raw[kid_end : kid_end + _NONCE], raw[kid_end + _NONCE :]
    key = _keys()[1].get(kid)
    if key is None or len(nonce) != _NONCE:
        raise CursorUnreadable
    try:
        return AESGCM(key).decrypt(nonce, sealed, aad)
    except InvalidTag as exc:
        raise CursorUnreadable from exc

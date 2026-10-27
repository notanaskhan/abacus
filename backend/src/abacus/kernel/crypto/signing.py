"""Detached export signatures (G-02-T17; G-02 §4.5, AC-13). PROTECTED.

An audit-log export's `manifest.json` is signed with the environment's asymmetric export-signing
key so that anyone holding the published public key (`docs/operations/export-signing-keys.md`)
can check that the manifest, and through its SHA-256 the CSV, came from this environment:

    openssl dgst -sha256 -verify export-signing.pem -signature manifest.sig manifest.json

The signature is ECDSA P-256 over SHA-256, DER-encoded (what KMS `Sign` returns and what
`openssl dgst -verify` reads). In AWS the key is KMS (`ECC_NIST_P256`, `SIGN_VERIFY`), named by
`audit_export_signing_key_alias`; the private key never leaves KMS. Locally and in tests a key
derived from the public local master key stands in, and only there: it signs nothing anyone
should trust. No signer configured fails closed (`SigningUnavailable`).
"""

from __future__ import annotations

import asyncio
import hashlib
from functools import lru_cache
from typing import TYPE_CHECKING, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from abacus.kernel.config import settings
from abacus.kernel.errors import ServiceUnavailable
from abacus.kernel.logging import get_logger
from abacus.kernel.storage import AwsError, error_code, kms_client

if TYPE_CHECKING:
    from types_boto3_kms import KMSClient

_log = get_logger(__name__)
# The P-256 group order: a derived scalar is reduced into [1, n - 1].
_P256_ORDER = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551


class SigningUnavailable(ServiceUnavailable):
    """No export-signing key is configured, or KMS refused or failed the signature: nothing is
    signed with anything else instead (503)."""


class ExportSigner(Protocol):
    """Signs a SHA-256 digest; `key_ref` names the key (the KMS alias, or `local:<fingerprint>`)
    and is recorded on the export."""

    @property
    def key_ref(self) -> str: ...

    async def sign_digest(self, digest: bytes) -> bytes: ...


class LocalExportSigner:
    """Local and test only: a P-256 key derived from the (public) local master key."""

    def __init__(self, master_key: bytes) -> None:
        if settings().environment not in ("local", "test"):
            raise RuntimeError("LocalExportSigner is for local runs and tests only")
        material = HKDF(
            algorithm=hashes.SHA256(),
            length=48,
            salt=b"abacus-export-signing-v1",
            info=b"audit-log-export",
        ).derive(master_key)
        scalar = int.from_bytes(material, "big") % (_P256_ORDER - 1) + 1
        self._key = ec.derive_private_key(scalar, ec.SECP256R1())
        der = self._key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self._ref = f"local:{hashlib.sha256(der).hexdigest()[:16]}"

    @property
    def key_ref(self) -> str:
        return self._ref

    def public_key_pem(self) -> bytes:
        return self._key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )

    async def sign_digest(self, digest: bytes) -> bytes:
        return self._key.sign(digest, ec.ECDSA(Prehashed(hashes.SHA256())))


class KmsExportSigner:
    """AWS KMS `Sign` with `ECDSA_SHA_256` over the digest (`MessageType=DIGEST`). Every error
    fails closed as `SigningUnavailable`; the error code is logged, never the digest."""

    def __init__(self, client: KMSClient, alias: str) -> None:
        self._client = client
        self._alias = alias

    @property
    def key_ref(self) -> str:
        return self._alias

    async def sign_digest(self, digest: bytes) -> bytes:
        try:
            response = await asyncio.to_thread(
                self._client.sign,
                KeyId=self._alias,
                Message=digest,
                MessageType="DIGEST",
                SigningAlgorithm="ECDSA_SHA_256",
            )
        except AwsError as exc:
            code = error_code(exc)
            _log.warning("kms.sign_failed", kms_error=code, error_type=type(exc).__name__)
            raise SigningUnavailable("the export can't be signed") from None
        signature = response.get("Signature")
        if not signature:
            raise SigningUnavailable("the export can't be signed")
        return signature


_signer: list[ExportSigner | None] = [None]


def configure_export_signer(signer: ExportSigner | None) -> None:
    """Tests and local runs: use `signer` (None goes back to the one built from settings)."""
    _signer[0] = signer
    _from_settings.cache_clear()


@lru_cache(maxsize=1)
def _from_settings() -> ExportSigner | None:
    s = settings()
    if s.audit_export_signing_key_alias is not None:
        return KmsExportSigner(kms_client(region=s.kms_region), s.audit_export_signing_key_alias)
    if s.environment in ("local", "test") and s.local_master_key is not None:
        return LocalExportSigner(s.local_master_key.get_secret_value().encode())
    return None


def export_signer() -> ExportSigner:
    """The configured signer; `SigningUnavailable` when there is none."""
    found = _signer[0] if _signer[0] is not None else _from_settings()
    if found is None:
        raise SigningUnavailable("no export-signing key is configured")
    return found


def signing_configured() -> bool:
    return (_signer[0] if _signer[0] is not None else _from_settings()) is not None


def verify_signature(public_key_pem: bytes, message: bytes, signature: bytes) -> bool:
    """What `openssl dgst -sha256 -verify` does: the DER ECDSA signature over SHA-256(message)."""
    key = serialization.load_pem_public_key(public_key_pem)
    if not isinstance(key, ec.EllipticCurvePublicKey):
        return False
    try:
        key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        return False
    return True


__all__ = [
    "ExportSigner",
    "KmsExportSigner",
    "LocalExportSigner",
    "SigningUnavailable",
    "configure_export_signer",
    "export_signer",
    "signing_configured",
    "verify_signature",
]

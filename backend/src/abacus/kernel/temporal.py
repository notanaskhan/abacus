"""The Temporal client (ADR-017). TASK-010 design §6.

Every client, in the API and in the worker, encrypts payloads with the platform codec. Tests may
substitute a connected client with `configure_temporal_client`.
"""

from __future__ import annotations

import dataclasses

from temporalio.client import Client
from temporalio.converter import DataConverter

from abacus.kernel.config import settings
from abacus.kernel.crypto.payload_codec import PayloadEncryptionCodec

_client: Client | None = None


def payload_codec() -> PayloadEncryptionCodec:
    key = settings().temporal_payload_key
    if key is None:  # settings validation makes this unreachable outside local and test
        raise RuntimeError("temporal_payload_key is not configured")
    return PayloadEncryptionCodec(key.get_secret_value().encode())


def data_converter() -> DataConverter:
    return dataclasses.replace(DataConverter.default, payload_codec=payload_codec())


def configure_temporal_client(client: Client | None) -> None:
    """Tests: use this client (None: connect from settings on next use)."""
    global _client
    _client = client


async def temporal_client() -> Client:
    global _client
    if _client is None:
        s = settings()
        if s.temporal_target is None:  # unreachable outside local and test
            raise RuntimeError("temporal_target is not configured")
        _client = await Client.connect(
            s.temporal_target, namespace=s.temporal_namespace, data_converter=data_converter()
        )
    return _client

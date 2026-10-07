"""The Temporal client (ADR-017). TASK-010 design §6, revision 1.

Every client, in the API and in the worker, encrypts payloads with the platform codec and encodes
failure messages and stack traces too (`DefaultFailureConverterWithEncodedAttributes`): an
exception's text, which can carry ledger values or identifiers, never reaches Temporal in
plaintext. Outside local and test the connection uses TLS and an API key (settings enforce it).
Tests may substitute a connected client with `configure_temporal_client`.
"""

from __future__ import annotations

import dataclasses

from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor
from temporalio.converter import DataConverter, DefaultFailureConverterWithEncodedAttributes

from abacus.kernel.config import settings
from abacus.kernel.crypto.payload_codec import PayloadEncryptionCodec

# Which platform key seals new payloads (the keyring opens older ones too).
SEALING_ID = "platform-v1"
_client: Client | None = None


def payload_codec() -> PayloadEncryptionCodec:
    key = settings().temporal_payload_key
    if key is None:  # settings validation makes this unreachable outside local and test
        raise RuntimeError("temporal_payload_key is not configured")
    return PayloadEncryptionCodec(
        {SEALING_ID: key.get_secret_value().encode()}, current=SEALING_ID
    )


def data_converter() -> DataConverter:
    return dataclasses.replace(
        DataConverter.default,
        payload_codec=payload_codec(),
        failure_converter_class=DefaultFailureConverterWithEncodedAttributes,
    )


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
            s.temporal_target,
            namespace=s.temporal_namespace,
            data_converter=data_converter(),
            # One trace across processes (TASK-013): the client puts the caller's trace in the
            # workflow's headers; workers using this client continue it in workflows and
            # activities. Headers carry the traceparent only (the codec encrypts payloads).
            interceptors=[TracingInterceptor()],
            tls=s.temporal_tls,
            api_key=s.temporal_api_key.get_secret_value() if s.temporal_api_key else None,
        )
    return _client

"""N-02-T18: the DocuSign adapter against a recorded transport (no network).

A two-signer envelope is created exactly once under a retried send (the second call reads the
first back by its idempotency field), recipients are captive and routed, KBA is asked for the
e-file family, SMS never appears, and a host outside DocuSign's is refused before any request.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from abacus.modules.signatures.docusign import (
    IDEMPOTENCY_FIELD,
    DocuSignAccount,
    DocuSignProvider,
    HostNotAllowed,
    PlacedField,
    SourceFile,
)
from abacus.modules.signatures.provider import EnvelopeSpec, SignerSpec

pytestmark = pytest.mark.asyncio
PDF = b"%PDF-1.7\n% Form 8879-PE\n%%EOF\n"
SHA = hashlib.sha256(PDF).hexdigest()


def _account(base: str = "https://demo.docusign.net") -> DocuSignAccount:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return DocuSignAccount("ik-1", "user-1", "acct-1", base, "account-d.docusign.com", pem)


class _DocuSign:
    """A recorded DocuSign: envelopes by idempotency field, recipients by client user id."""

    def __init__(self) -> None:
        self.creates: list[Any] = []  # request bodies as DocuSign received them
        self.by_key: dict[str, str] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer t"
        if request.method == "GET" and path.endswith("/envelopes"):
            field = request.url.params["custom_field"].split("=", 1)[1]
            found = self.by_key.get(field)
            return httpx.Response(
                200, json={"envelopes": [{"envelopeId": found}] if found else []}
            )
        if request.method == "POST" and path.endswith("/envelopes"):
            body = json.loads(request.content)
            self.creates.append(body)
            key = body["customFields"]["textCustomFields"][0]["value"]
            self.by_key[key] = "env-1"
            return httpx.Response(201, json={"envelopeId": "env-1"})
        if path.endswith("/envelopes/env-1/recipients"):
            signers = [
                {"clientUserId": s["clientUserId"], "recipientId": s["recipientId"]}
                for s in self.creates[0]["recipients"]["signers"]
            ]
            return httpx.Response(200, json={"signers": signers})
        if path.endswith("/envelopes/env-1"):
            return httpx.Response(200, json={"envelopeId": "env-1", "status": "sent"})
        return httpx.Response(404)


def _adapter(fake: _DocuSign) -> DocuSignProvider:
    async def documents(_envelope: str) -> Sequence[SourceFile]:
        return [SourceFile("Document 1", PDF, SHA)]

    async def fields(_envelope: str) -> Sequence[PlacedField]:
        return [PlacedField("s-1", 1, "signature", 2, 300.0, 640.0, None)]

    async def order(_envelope: str) -> str:
        return "parallel"

    return DocuSignProvider(
        _account(),
        httpx.AsyncClient(transport=httpx.MockTransport(fake)),
        documents=documents,
        fields=fields,
        signer_order=order,
    )


SPEC = EnvelopeSpec(
    envelope_id="e-1",
    idempotency_key="envelope:e-1",
    document_sha256s=(SHA,),
    signers=(SignerSpec("s-1", 1, 1, "kba"), SignerSpec("s-2", 2, 1, "kba")),
)


async def test_ac_two_signer_envelope_is_created_once_under_a_retried_send() -> None:
    fake = _DocuSign()
    adapter = _adapter(fake)
    first = await adapter.create_and_send(SPEC)
    retried = await adapter.create_and_send(SPEC)
    assert len(fake.creates) == 1
    assert first.provider_envelope_id == retried.provider_envelope_id == "env-1"
    assert first.recipients == retried.recipients == {"s-1": "1", "s-2": "2"}
    created = fake.creates[0]
    fields = created["customFields"]["textCustomFields"]
    assert fields[0] == {"name": IDEMPOTENCY_FIELD, "value": "envelope:e-1", "show": "false"}
    signers = created["recipients"]["signers"]
    assert [s["routingOrder"] for s in signers] == ["1", "1"]  # parallel: one routing group
    assert all(
        s["authenticationMethod"] == "KBA" and s["requireIdLookup"] == "true" for s in signers
    )
    assert signers[0]["tabs"]["signHereTabs"] == [
        {"documentId": "1", "pageNumber": "2", "xPosition": "300", "yPosition": "640"}
    ]
    assert "sms" not in json.dumps(created).lower()


async def test_a_document_whose_bytes_changed_is_never_sent() -> None:
    fake = _DocuSign()
    adapter = _adapter(fake)
    changed = EnvelopeSpec("e-2", "envelope:e-2", ("0" * 64,), SPEC.signers)
    with pytest.raises(Exception, match="documents"):
        await adapter.create_and_send(changed)
    assert fake.creates == []


async def test_a_host_outside_docusign_is_refused_before_any_request() -> None:
    def never(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request may leave")

    async def documents(_envelope: str) -> Sequence[SourceFile]:
        return []

    async def fields(_envelope: str) -> Sequence[PlacedField]:
        return []

    async def order(_envelope: str) -> str:
        return "sequential"

    with pytest.raises(HostNotAllowed):
        DocuSignProvider(
            _account("https://docusign.example.com"),
            httpx.AsyncClient(transport=httpx.MockTransport(never)),
            documents=documents,
            fields=fields,
            signer_order=order,
        )

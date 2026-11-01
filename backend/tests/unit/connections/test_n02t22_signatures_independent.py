# ac-test-author: ayushkbhatia
"""N-02-T22 (TASK-2232; ADR-078; DEC-1284): independent AC tests for N-02-T18 to T20, the parts
that need no database, beside the W7 interception harness it uses. Written from the backlog rows
and ADR-342, not from the builders' tests.

- **Retries re-read before re-writing:** a create whose answer was lost is found by its
  idempotency key on the retry; DocuSeal receives one create.
- **Egress allowlist:** an API host other than DocuSeal's (the EU host included, until ADR-342's
  data-location question is answered) is refused before any request; a file link off DocuSeal's
  file hosts is never fetched.
- **Kill switch:** with `signatures.esign_provider` off, or no install source registered, the
  firm's adapter is never built and the install's secret is never read.
- **Interception harness (W7):** every request the adapter makes over a whole envelope, through
  httpx's real transports, is HTTPS to a declared DocuSeal host; writes go to the API host only
  and the key never leaves it.
- **Forged and replayed provider calls** (DocuSeal's webhooks; the plan's "Connect"): a wrong key,
  a moved timestamp, an edited body and a stale delivery are refused.
- **Validation by code (INV-1):** the builder's checks import no model, gateway or agent.
- **No SMS for the e-file family:** no contract shape, adapter or DocuSeal field offers it.
- **Send and Undo are human-only:** an agent, the platform and support are refused before
  anything is read, and the matrix denies the agent and the system.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, get_args
from uuid import uuid4

import httpx
import pytest

from abacus.kernel.db import ActorKind, TenantContext
from abacus.kernel.flags import Flag
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.signatures import builder, contract, docuseal, docuseal_firm
from abacus.modules.signatures.docuseal import (
    ALLOWED_HOSTS,
    DOCUMENT_HOSTS,
    DocuSealAccount,
    DocuSealError,
    DocuSealProvider,
    HostNotAllowed,
    PlacedField,
    SourceFile,
)
from abacus.modules.signatures.provider import EnvelopeSpec, ProviderUnavailable, SignerSpec
from abacus.modules.signatures.status_poll import verify_webhook

from .write_interception import intercept

Json = dict[str, Any]  # Any: DocuSeal-shaped JSON, built key by key
PDF = b"%PDF-1.7\n% independent 8879\n%%EOF\n"
SHA = hashlib.sha256(PDF).hexdigest()
KEY = "independent-test-key"
SPEC = EnvelopeSpec(
    envelope_id="env-22",
    idempotency_key="envelope:env-22",
    document_sha256s=(SHA,),
    signers=(SignerSpec("sig-a", 1, 1, "kba"), SignerSpec("sig-b", 2, 1, "email_code")),
)


class _Server:
    """DocuSeal as the adapter sees it: one submission, created at most once per key."""

    def __init__(self, *, lose_first_answer: bool = False) -> None:
        self.lose_first_answer = lose_first_answer
        self.creates = 0
        self.requests: list[httpx.Request] = []
        self.body: Json | None = None

    def _submission(self) -> Json:
        assert self.body is not None
        return {
            "id": 7,
            "audit_log_url": "https://docuseal.com/file/audit.pdf",
            "submitters": [
                {
                    "id": 70 + n,
                    "uuid": f"u-{n}",
                    "external_id": s["external_id"],
                    "metadata": s["metadata"],
                    "status": "completed",
                    "completed_at": "2027-01-04T15:00:00Z",
                    "values": [{"field": "signature 1.1", "value": "https://docuseal.com/file/i"}],
                }
                for n, s in enumerate(self.body["submitters"])
            ],
            "submission_events": [],
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host, path, method = request.url.host, request.url.path, request.method
        if host != "api.docuseal.com":
            return httpx.Response(200, content=b"file")
        if method == "GET" and path == "/submitters":
            if self.body is None:
                return httpx.Response(200, json={"data": []})
            wanted = request.url.params["external_id"]
            rows = [
                {"submission_id": 7, **s}
                for s in self._submission()["submitters"]
                if s["external_id"] == wanted
            ]
            return httpx.Response(200, json={"data": rows})
        if method == "POST" and path == "/submissions/pdf":
            self.creates += 1
            self.body = json.loads(request.content)
            if self.lose_first_answer and self.creates == 1:
                raise httpx.ReadTimeout("the answer was lost", request=request)
            return httpx.Response(200, json=self._submission())
        if method == "GET" and path == "/submissions/7":
            return httpx.Response(200, json=self._submission())
        if method == "GET" and path == "/submissions/7/documents":
            return httpx.Response(
                200, json={"documents": [{"url": "https://docuseal.com/file/m"}]}
            )
        if method == "DELETE" and path == "/submissions/7":
            return httpx.Response(200, json={"id": 7})
        return httpx.Response(404)


def _provider(client: httpx.AsyncClient, host: str = "api.docuseal.com") -> DocuSealProvider:
    async def documents(_envelope: str) -> list[SourceFile]:
        return [SourceFile("Document 1", PDF, SHA, ((612.0, 792.0),))]

    async def fields(_envelope: str) -> list[PlacedField]:
        return [
            PlacedField("sig-a", 1, "signature", 1, 300.0, 600.0, 150.0, 40.0, None),
            PlacedField("sig-b", 1, "signature", 1, 300.0, 700.0, 150.0, 40.0, None),
        ]

    async def order(_envelope: str) -> str:
        return "sequential"

    async def audit_text(_content: bytes) -> str:
        return "sig-a@signers.invalid\nIP: 192.0.2.10\nsig-b@signers.invalid\nIP: 192.0.2.11\n"

    return DocuSealProvider(
        DocuSealAccount(KEY, host),
        client,
        documents=documents,
        fields=fields,
        signer_order=order,
        audit_text=audit_text,
    )


# --- Retries re-read before re-writing ---------------------------------------------------------


async def test_a_retry_after_a_lost_answer_finds_the_first_create_and_never_writes_twice() -> None:
    server = _Server(lose_first_answer=True)
    adapter = _provider(httpx.AsyncClient(transport=httpx.MockTransport(server)))
    with pytest.raises(httpx.ReadTimeout):
        await adapter.create_and_send(SPEC)
    made = await adapter.create_and_send(SPEC)  # the activity's retry
    assert made.provider_envelope_id == "7"
    assert server.creates == 1
    lookups = [r for r in server.requests if r.url.path == "/submitters"]
    assert len(lookups) == 2  # each attempt reads before it writes


# --- Egress allowlist and the kill switch --------------------------------------------------------


@pytest.mark.parametrize("host", ["api.docuseal.eu", "docuseal.com", "api.docuseal.com.evil.test"])
async def test_an_api_host_outside_the_allowlist_is_refused_before_any_request(host: str) -> None:
    server = _Server()
    with pytest.raises(HostNotAllowed):
        _provider(httpx.AsyncClient(transport=httpx.MockTransport(server)), host)
    assert server.requests == []


async def test_a_file_link_off_docuseals_file_hosts_is_never_fetched() -> None:
    server = _Server()
    adapter = _provider(httpx.AsyncClient(transport=httpx.MockTransport(server)))
    with pytest.raises(HostNotAllowed):
        await adapter._file("https://files.elsewhere.test/m.pdf", "documents")  # pyright: ignore[reportPrivateUsage] -- the adapter's internals under test
    with pytest.raises(DocuSealError):
        await adapter._file("http://docuseal.com/file/m.pdf", "documents")  # pyright: ignore[reportPrivateUsage] -- the adapter's internals under test
    assert server.requests == []


async def test_the_kill_switch_off_builds_no_adapter_and_reads_no_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read: list[TenantContext] = []

    async def secret(tenant: TenantContext) -> bytes | None:
        read.append(tenant)
        return json.dumps({"api_key": KEY, "api_host": "api.docuseal.com"}).encode()

    async def off(_tenant: object, _flag: Flag) -> bool:
        return False

    monkeypatch.setattr(docuseal_firm, "flag_enabled", off)
    docuseal_firm.register_esign_install(secret)
    try:
        with pytest.raises(ProviderUnavailable):
            await docuseal_firm.firm_provider(uuid4())
        assert read == []
        docuseal_firm.register_esign_install(None)

        async def on(_tenant: object, _flag: Flag) -> bool:
            return True

        monkeypatch.setattr(docuseal_firm, "flag_enabled", on)
        with pytest.raises(ProviderUnavailable):  # no install source: nothing is sent
            await docuseal_firm.firm_provider(uuid4())
    finally:
        docuseal_firm.register_esign_install(None)


# --- Interception harness (W7) -------------------------------------------------------------------


async def test_w7_every_request_of_a_whole_envelope_is_https_to_a_declared_docuseal_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _Server()
    declared = ALLOWED_HOSTS | DOCUMENT_HOSTS
    with intercept(monkeypatch, declared, responder=server) as harness:
        adapter = _provider(httpx.AsyncClient())  # httpx's real transport, caught by the harness
        await adapter.create_and_send(SPEC)
        await adapter.status("7")
        await adapter.completed("7")
        await adapter.void("7", "replaced")
    assert harness.calls
    assert all(c.scheme == "https" and c.host in declared for c in harness.calls)
    writes = [c for c in harness.calls if c.method not in ("GET", "HEAD")]
    assert {c.host for c in writes} == {"api.docuseal.com"}
    assert {(c.method, c.path) for c in writes} == {
        ("POST", "/submissions/pdf"),
        ("DELETE", "/submissions/7"),
    }
    for request in server.requests:
        on_api = request.url.host == "api.docuseal.com"
        assert ("X-Auth-Token" in request.headers) is on_api  # the key stays on the API host
    created = server.body
    assert created is not None
    assert created["send_email"] is False and created["send_sms"] is False
    assert all(s["send_sms"] is False for s in created["submitters"])


# --- Forged and replayed provider calls ----------------------------------------------------------


def test_forged_moved_edited_and_stale_webhook_deliveries_are_refused() -> None:
    key, body, now = b"whsec_independent", b'{"event_type":"form.completed"}', 1_800_000_000
    signed = hmac.new(key, f"{now}.".encode() + body, hashlib.sha256).hexdigest()
    assert verify_webhook(body, f"{now}.{signed}", [key], now)
    assert not verify_webhook(body, f"{now}.{signed}", [b"whsec_other"], now)  # forged
    assert not verify_webhook(body, f"{now + 1}.{signed}", [key], now)  # moved timestamp
    assert not verify_webhook(body + b" ", f"{now}.{signed}", [key], now)  # edited body
    assert not verify_webhook(body, f"{now}.{signed}", [key], now + 301)  # replayed late
    assert not verify_webhook(body, None, [key], now)


# --- Validation by code, no SMS, human-only verbs ------------------------------------------------


def test_the_builders_checks_import_no_model_gateway_or_agent() -> None:
    tree = ast.parse(Path(builder.__file__).read_text(encoding="utf-8"))
    modules = [
        (node.module or "") if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    ]
    assert not [m for m in modules if "ai_gateway" in m or ".agents" in m or "anthropic" in m]


async def test_sms_is_offered_nowhere_for_the_efile_family() -> None:
    assert "sms_code" not in get_args(contract.IdentityMethod)
    assert not [m for m in docuseal._IDENTITY if "sms" in m]  # pyright: ignore[reportPrivateUsage] -- the adapter's internals under test
    server = _Server()
    adapter = _provider(httpx.AsyncClient(transport=httpx.MockTransport(server)))
    sms = EnvelopeSpec(
        envelope_id="env-sms",
        idempotency_key="envelope:env-sms",
        document_sha256s=(SHA,),
        signers=(SignerSpec("sig-a", 1, 1, "sms_code"),),
    )
    with pytest.raises(DocuSealError):
        await adapter.create_and_send(sms)
    assert server.creates == 0


@pytest.mark.parametrize("kind", ["agent", "system", "support"])
async def test_send_and_undo_refuse_anyone_but_a_person_before_reading_anything(
    kind: ActorKind,
) -> None:
    user = uuid4()
    ctx = AuthContext(TenantContext(uuid4(), kind, str(user)), user, uuid4(), None, None)
    for verb in (builder.send, builder.undo_send, builder.check_send):
        with pytest.raises(Forbidden):
            await verb(ctx, uuid4())
    rule = RULES["envelope.send"]
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system") == "deny"

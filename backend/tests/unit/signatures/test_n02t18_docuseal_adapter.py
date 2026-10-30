"""N-02-T18 (ADR-342): the DocuSeal adapter against a recorded transport (no network).

A two-signer envelope is created exactly once under a retried send (the second call finds the
first by its submitters' external id and idempotency key), DocuSeal sends no email or SMS,
KBA is asked once per e-file signer before the signature, fields go as page fractions, anchors
and hosts outside DocuSeal's are refused before any request, the API key never reaches a file
host, and void is an archive. Shapes follow the sandbox run of 2026-10-30 (TASK-2151): events
carry no data, so each signer's IP and device come from the audit log's text.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from typing import Any

import httpx
import pytest

from abacus.modules.signatures.docuseal import (
    IDEMPOTENCY_KEY,
    DocuSealAccount,
    DocuSealProvider,
    HostNotAllowed,
    PlacedField,
    SourceFile,
    audit_entries,
)
from abacus.modules.signatures.provider import EnvelopeSpec, SignerSpec

pytestmark = pytest.mark.asyncio
PDF = b"%PDF-1.7\n% Form 8879-PE\n%%EOF\n"
SHA = hashlib.sha256(PDF).hexdigest()
LETTER = (612.0, 792.0)
Json = dict[str, Any]  # Any: DocuSeal-shaped JSON, built and read key by key
KEY = "test-key-not-a-secret"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)\n"
    "Chrome/130.0.0.0 Safari/537.36"
)
# DocuSeal's audit log text as pdfium reads it (sandbox layout; synthetic values).
AUDIT = f"""DocuSeal Audit Log
Envelope ID: 41
Document 1 Original SHA256:
Signer 1
s-1@signers.invalid
IP: 203.0.113.9
Session ID: 94005e505ec359c4
User agent: {UA}
Time zone: America/Chicago
SIGNATURE
s-2@signers.invalid
Event Log
October 30, 2026 at 5:51 PM Submission completed by s-1@signers.invalid
"""


def _account(host: str = "api.docuseal.com") -> DocuSealAccount:
    return DocuSealAccount(KEY, host)


class _DocuSeal:
    """A recorded DocuSeal: submitters by external id, one submission, files on its hosts."""

    def __init__(self) -> None:
        self.creates: list[Json] = []  # request bodies as DocuSeal received them
        self.audit_log_url = "https://docuseal.com/file/audit.pdf"
        self.deleted: list[str] = []
        self.files: list[httpx.Request] = []

    def submission(self) -> Json:
        made = self.creates[0]
        return {
            "id": 41,
            "audit_log_url": self.audit_log_url,
            "submitters": [
                {
                    "id": 100 + n,
                    "uuid": f"uuid-{n}",
                    "external_id": s["external_id"],
                    "metadata": s["metadata"],
                    "status": "completed" if n == 0 else "opened",
                    "opened_at": "2027-06-01T15:00:00Z",
                    "completed_at": "2027-06-01T15:05:00Z" if n == 0 else None,
                    "values": [
                        {"field": "signature 1.1", "value": "https://docuseal.com/file/s.png"}
                    ],
                }
                for n, s in enumerate(made["submitters"])
            ],
            "submission_events": [
                {"submitter_id": 100, "event_type": "complete_verification", "data": {}},
                {"submitter_id": 100, "event_type": "complete_form", "data": {}},
            ],
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != "api.docuseal.com" or request.url.path.startswith("/file/"):
            assert "X-Auth-Token" not in request.headers  # the key never leaves the API host
            self.files.append(request)
            return httpx.Response(200, content=b"bytes:" + request.url.path.encode())
        assert request.headers["X-Auth-Token"] == KEY
        path, method = request.url.path, request.method
        if method == "GET" and path == "/submitters":
            wanted = request.url.params["external_id"]
            listed: list[Json] = self.submission()["submitters"] if self.creates else []
            rows = [{"submission_id": 41, **s} for s in listed if s["external_id"] == wanted]
            return httpx.Response(200, json={"data": rows})
        if method == "POST" and path == "/submissions/pdf":
            self.creates.append(json.loads(request.content))
            return httpx.Response(200, json=self.submission())
        if method == "GET" and path == "/submissions/41":
            return httpx.Response(200, json=self.submission())
        if method == "GET" and path == "/submissions/41/documents":
            assert request.url.params["merge"] == "true"
            return httpx.Response(
                200,
                json={
                    "id": 41,
                    "documents": [{"name": "m", "url": "https://docuseal.com/file/m.pdf"}],
                },
            )
        if method == "DELETE" and path == "/submissions/41":
            self.deleted.append(path)
            return httpx.Response(200, json={"id": 41, "archived_at": "2027-06-02T00:00:00Z"})
        return httpx.Response(404)


def _adapter(
    fake: Callable[[httpx.Request], httpx.Response],
    placed: Sequence[PlacedField] | None = None,
    mode: str = "parallel",
    audit: str = AUDIT,
) -> DocuSealProvider:
    async def documents(_envelope: str) -> Sequence[SourceFile]:
        return [SourceFile("Document 1", PDF, SHA, (LETTER, LETTER))]

    async def fields(_envelope: str) -> Sequence[PlacedField]:
        if placed is not None:
            return placed
        return [
            PlacedField("s-1", 1, "signature", 2, 306.0, 396.0, 153.0, 39.6, None),
            PlacedField("s-1", 1, "date", 2, 306.0, 440.0, 61.2, 19.8, None),
            PlacedField("s-2", 1, "signature", 2, 306.0, 600.0, 153.0, 39.6, None),
        ]

    async def order(_envelope: str) -> str:
        return mode

    async def audit_text(content: bytes) -> str:
        assert content == b"bytes:/file/audit.pdf"  # the certificate, read as stored
        return audit

    return DocuSealProvider(
        _account(),
        httpx.AsyncClient(transport=httpx.MockTransport(fake)),
        documents=documents,
        fields=fields,
        signer_order=order,
        audit_text=audit_text,
    )


SPEC = EnvelopeSpec(
    envelope_id="e-1",
    idempotency_key="envelope:e-1",
    document_sha256s=(SHA,),
    signers=(SignerSpec("s-1", 1, 1, "kba"), SignerSpec("s-2", 2, 1, "email_code")),
)


async def test_ac_two_signer_envelope_is_created_once_under_a_retried_send() -> None:
    fake = _DocuSeal()
    adapter = _adapter(fake)
    first = await adapter.create_and_send(SPEC)
    retried = await adapter.create_and_send(SPEC)
    assert len(fake.creates) == 1
    assert first.provider_envelope_id == retried.provider_envelope_id == "41"
    assert first.recipients == retried.recipients == {"s-1": "100", "s-2": "101"}
    created = fake.creates[0]
    assert created["send_email"] is False and created["send_sms"] is False
    submitters = created["submitters"]
    assert [s["external_id"] for s in submitters] == ["s-1", "s-2"]
    assert all(s["metadata"] == {IDEMPOTENCY_KEY: "envelope:e-1"} for s in submitters)
    assert all(s["send_email"] is False and s["send_sms"] is False for s in submitters)
    assert [s["order"] for s in submitters] == [0, 0]  # parallel: one routing group
    assert "phone" not in json.dumps(created) and "2fa" not in json.dumps(created)
    assert all("name" not in s for s in submitters)  # nothing pre-filled into a signature
    assert [s["email"] for s in submitters] == ["s-1@signers.invalid", "s-2@signers.invalid"]


async def test_signers_see_titles_and_the_date_is_the_read_only_signing_date() -> None:
    fake = _DocuSeal()
    await _adapter(fake, mode="sequential").create_and_send(SPEC)
    created = fake.creates[0]
    fields = created["documents"][0]["fields"]
    assert [f["title"] for f in fields] == [
        "Identity check",
        "Signature",
        "Date signed",
        "Signature",
    ]
    assert all(f["name"] != f["title"] for f in fields)  # our names stay internal
    first, second = created["submitters"]
    assert first["fields"] == [{"name": "date 1.2", "readonly": True, "default_value": "{{date}}"}]
    assert second["fields"] == []


async def test_sequential_signers_are_ordered_and_fields_are_page_fractions() -> None:
    fake = _DocuSeal()
    await _adapter(fake, mode="sequential").create_and_send(SPEC)
    created = fake.creates[0]
    assert [s["order"] for s in created["submitters"]] == [0, 1]
    fields = created["documents"][0]["fields"]
    assert [(f["type"], f["role"]) for f in fields] == [
        ("kba", "Signer 1"),  # once, before the e-file signer's first signature
        ("signature", "Signer 1"),
        ("date", "Signer 1"),
        ("signature", "Signer 2"),  # email_code: proved in the portal, nothing at DocuSeal
    ]
    assert fields[1]["areas"] == [{"x": 0.5, "y": 0.5, "w": 0.25, "h": 0.05, "page": 2}]


async def test_a_document_whose_bytes_changed_is_never_sent() -> None:
    fake = _DocuSeal()
    changed = EnvelopeSpec("e-2", "envelope:e-2", ("0" * 64,), SPEC.signers)
    with pytest.raises(Exception, match="documents"):
        await _adapter(fake).create_and_send(changed)
    assert fake.creates == []


async def test_an_anchored_field_is_refused_before_sending() -> None:
    fake = _DocuSeal()
    anchored = [PlacedField("s-1", 1, "signature", None, None, None, None, None, "/sig1/")]
    with pytest.raises(Exception, match="placement"):
        await _adapter(fake, anchored).create_and_send(SPEC)
    assert fake.creates == []


async def test_an_identity_method_docuseal_cannot_honour_is_refused() -> None:
    fake = _DocuSeal()
    odd = EnvelopeSpec("e-3", "envelope:e-3", (SHA,), (SignerSpec("s-1", 1, 1, "sms_code"),))
    with pytest.raises(Exception, match="identity"):
        await _adapter(fake).create_and_send(odd)
    assert fake.creates == []


async def test_status_completion_and_void() -> None:
    fake = _DocuSeal()
    adapter = _adapter(fake)
    await adapter.create_and_send(SPEC)
    states = {s.signer_id: s.status for s in await adapter.status("41")}
    assert states == {"s-1": "signed", "s-2": "viewed"}
    done = await adapter.completed("41")
    assert done.combined_document == b"bytes:/file/m.pdf"
    assert done.certificate == b"bytes:/file/audit.pdf"
    (signer,) = done.signers  # only the completed submitter
    assert signer.signer_id == "s-1" and signer.signed_image == b"bytes:/file/s.png"
    assert signer.ip == "203.0.113.9" and signer.identity_result == "kba_verified"
    assert signer.user_agent_family == "Chrome" and signer.device_label == "Chrome · macOS"
    assert len(fake.files) == 3
    await adapter.void("41", "expired")
    assert fake.deleted == ["/submissions/41"]


async def test_a_completed_signer_with_no_ip_in_the_audit_log_is_never_recorded() -> None:
    fake = _DocuSeal()
    await _adapter(fake).create_and_send(SPEC)
    no_ip = AUDIT.replace("IP: 203.0.113.9\n", "")
    with pytest.raises(Exception, match="audit_log"):
        await _adapter(fake, audit=no_ip).completed("41")


async def test_audit_entries_read_each_signer_block_and_a_wrapped_user_agent() -> None:
    entries = audit_entries(AUDIT)
    assert entries["s-1@signers.invalid"].ip == "203.0.113.9"
    assert entries["s-1@signers.invalid"].user_agent == UA.replace("\n", " ")
    assert entries["s-2@signers.invalid"].ip is None  # not signed yet: no IP line
    spoofed = audit_entries(AUDIT.replace("203.0.113.9", "not-an-ip"))
    assert spoofed["s-1@signers.invalid"].ip is None


async def test_a_file_url_off_docuseal_hosts_is_refused() -> None:
    fake = _DocuSeal()
    adapter = _adapter(fake)
    await adapter.create_and_send(SPEC)
    fake.audit_log_url = "https://files.example.com/audit.pdf"
    with pytest.raises(HostNotAllowed):
        await adapter.completed("41")
    assert all(r.url.host != "files.example.com" for r in fake.files)


async def test_a_host_outside_docuseal_is_refused_before_any_request() -> None:
    def never(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request may leave")

    async def documents(_envelope: str) -> Sequence[SourceFile]:
        return []

    async def fields(_envelope: str) -> Sequence[PlacedField]:
        return []

    async def order(_envelope: str) -> str:
        return "sequential"

    async def audit_text(_content: bytes) -> str:
        return ""

    for host in ("api.docuseal.eu", "docuseal.example.com"):
        with pytest.raises(HostNotAllowed):
            DocuSealProvider(
                _account(host),
                httpx.AsyncClient(transport=httpx.MockTransport(never)),
                documents=documents,
                fields=fields,
                signer_order=order,
                audit_text=audit_text,
            )


async def test_a_redirected_file_is_never_stored() -> None:
    fake = _DocuSeal()
    adapter = _adapter(fake)
    await adapter.create_and_send(SPEC)
    fake.audit_log_url = "https://docuseal.com/file/moved.pdf"
    original = fake.__call__

    def moved(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/file/moved.pdf":
            return httpx.Response(302, headers={"Location": "https://files.example.com/a.pdf"})
        return original(request)

    redirected = _adapter(moved)
    with pytest.raises(Exception, match="audit_log"):
        await redirected.completed("41")

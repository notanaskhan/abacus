"""The DocuSign adapter behind the `EsignProvider` port (N-02-T18; N-02 §3.5; ADR-149; W7;
DF-11, DF-12; DEC-1179). PROTECTED.

One instance per firm and call, built by `firm_provider` only when every switch is on: the
firm's `signatures.docusign` flag (the kill switch), the W7 capability `esignature_envelope_send`
enabled in `write-capabilities.yaml` (v1: declared, never enabled, so this adapter is
unreachable until a person opens W7), and a connected DocuSign install whose sealed secret holds
the account. Otherwise `ProviderUnavailable`: nothing leaves.

- **Auth.** OAuth JWT grant (RS256, `signature impersonation`), the private key from the sealed
  install secret; the token is held in memory for the call only.
- **Create, exactly once.** The envelope carries a text custom field `accrued_idempotency` with the
  send's key. A create first lists envelopes by that field and, if one exists, reads it back
  instead of creating a second (a retried send after a timeout). Recipients are captive
  (`clientUserId` = our signer id, signing inside POR-06's embedded view, DF-12) in routing order
  (sequential: each signer's order; parallel: its routing group); identity per DF-11 (KBA for the
  e-file family, email for letters, the firm's sign-in for members; SMS is never sent). Tabs come
  from placed fields in PDF points, or anchors on rendered letters.
- **Read.** Status from the recipients (the truth; a Connect call is only a hint, N-02-T19), the
  combined document, the certificate and each signer's evidence from the audit events.
- **Hosts.** Only DocuSign's OAuth and REST hosts (`ALLOWED_HOSTS`); a base URI elsewhere is
  refused before any request. Q-01's egress firewall lists them when W7 opens.

Document bytes are read from our stores at create and sent once; nothing from a client's documents
is logged. The request and response hashes are recorded write-once by the caller
(`envelope_provider_calls`).
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, cast
from urllib.parse import urlsplit

import httpx
import jwt

from abacus.kernel.errors import ServiceUnavailable
from abacus.modules.signatures.provider import (
    Completed,
    Created,
    EnvelopeSpec,
    SignerEvidence,
    SignerState,
)

Json = dict[str, Any]  # Any: DocuSign's JSON, read key by key and never trusted for state
IDEMPOTENCY_FIELD: Final = "accrued_idempotency"
# DocuSign's demo and production OAuth and REST hosts [verify against the account's base URI].
ALLOWED_HOSTS: Final = frozenset(
    {
        "account-d.docusign.com",
        "demo.docusign.net",
        "account.docusign.com",
        "www.docusign.net",
        "na2.docusign.net",
        "na3.docusign.net",
        "na4.docusign.net",
        "eu.docusign.net",
    }
)
_SCOPE: Final = "signature impersonation"
_AUTH_HEADER: Final = "Authorization"  # our outbound call to DocuSign, never an inbound request
_JWT_GRANT: Final = "urn:ietf:params:oauth:grant-type:jwt-bearer"
_TOKEN_SECONDS: Final = 3600
_KBA_CONFIG: Final = "ID Check $"
# DF-11 to DocuSign's captive-recipient authentication (in-person ID is the handwritten path and
# never reaches DocuSign).
_AUTH_METHOD: Final[dict[str, str]] = {
    "kba": "KBA",
    "email_code": "Email",
    "firm_sso": "SingleSignOn_Other",
}
_STATUS: Final[dict[str, str]] = {
    "created": "pending",
    "sent": "pending",
    "delivered": "viewed",
    "signed": "signed",
    "completed": "signed",
    "declined": "declined",
    "authfailed": "verification_failed",
}
_TAB: Final[dict[str, str]] = {
    "signature": "signHereTabs",
    "date": "dateSignedTabs",
    "initial": "initialHereTabs",
    "pin": "textTabs",
    "title_prefill": "textTabs",
}


class DocuSignError(ServiceUnavailable):
    """DocuSign refused or failed: the activity retries; nothing is half-recorded. Carries the
    step and the HTTP status only, never a response body."""

    code = "provider_unavailable"

    def __init__(self, step: str, status: int | None = None) -> None:
        super().__init__(step)
        self.step = step
        self.status = status


class HostNotAllowed(ValueError):
    """An account or OAuth host outside DocuSign's: refused before any request."""


@dataclass(frozen=True)
class DocuSignAccount:
    """The sealed install secret, opened for one call (Restricted; never logged)."""

    integration_key: str
    user_id: str
    account_id: str
    base_uri: str  # e.g. https://demo.docusign.net
    oauth_host: str  # e.g. account-d.docusign.com
    private_key_pem: str

    @classmethod
    def from_secret(cls, raw: bytes) -> DocuSignAccount:
        body = cast(dict[str, str], json.loads(raw))
        return cls(
            integration_key=body["integration_key"],
            user_id=body["user_id"],
            account_id=body["account_id"],
            base_uri=body["base_uri"].rstrip("/"),
            oauth_host=body["oauth_host"],
            private_key_pem=body["private_key_pem"],
        )


@dataclass(frozen=True)
class SourceFile:
    """One document's bytes, in envelope order, and the hash the envelope recorded."""

    name: str
    content: bytes
    sha256: str


@dataclass(frozen=True)
class PlacedField:
    """One placed field for a signer: a document (1-based), a kind and a place."""

    signer_id: str
    document: int
    kind: str
    page: int | None
    x: float | None
    y: float | None
    anchor: str | None


DocumentLoader = Callable[[str], Awaitable[Sequence[SourceFile]]]
FieldLoader = Callable[[str], Awaitable[Sequence[PlacedField]]]


def _host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _identity_result(recipient: Json) -> str:
    """The identity check's outcome as DocuSign recorded it (KBA's lookup status), else the
    authentication method used."""
    status = cast(Json, recipient.get("recipientAuthenticationStatus") or {})
    lookup = cast(Json, status.get("idLookupResult") or {})
    return str(lookup.get("status") or recipient.get("authenticationMethod") or "")


def _when(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


class DocuSignProvider:
    """One firm's DocuSign account, for one activity call."""

    name = "docusign"

    def __init__(
        self,
        account: DocuSignAccount,
        http: httpx.AsyncClient,
        *,
        documents: DocumentLoader,
        fields: FieldLoader,
        signer_order: Callable[[str], Awaitable[str]],
        clock: Callable[[], float] = time.time,
    ) -> None:
        for host in (_host_of(account.base_uri), account.oauth_host.lower()):
            if host not in ALLOWED_HOSTS:
                raise HostNotAllowed(host)
        self._account = account
        self._http = http
        self._documents = documents
        self._fields = fields
        self._signer_order = signer_order
        self._clock = clock
        self._token: tuple[str, float] | None = None

    # --- transport ---------------------------------------------------------------------------

    async def _bearer(self) -> str:
        now = self._clock()
        if self._token is not None and self._token[1] - 60 > now:
            return self._token[0]
        a = self._account
        assertion = jwt.encode(
            {
                "iss": a.integration_key,
                "sub": a.user_id,
                "aud": a.oauth_host,
                "iat": int(now),
                "exp": int(now) + _TOKEN_SECONDS,
                "scope": _SCOPE,
            },
            a.private_key_pem,
            algorithm="RS256",
        )
        got = await self._http.post(
            f"https://{a.oauth_host}/oauth/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
        if got.status_code != 200:
            raise DocuSignError("token", got.status_code)
        body = cast(Json, got.json())
        token = str(body["access_token"])
        self._token = (token, now + float(body.get("expires_in", _TOKEN_SECONDS)))
        return token

    async def _call(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        url = f"{self._account.base_uri}/restapi/v2.1/accounts/{self._account.account_id}{path}"
        got = await self._http.request(
            method,
            url,
            json=body,
            params=params,
            headers={_AUTH_HEADER: f"Bearer {await self._bearer()}"},
        )
        if got.status_code >= 400:
            raise DocuSignError(method.lower(), got.status_code)
        return got

    # --- create ------------------------------------------------------------------------------

    async def _existing(self, key: str) -> str | None:
        found = await self._call(
            "GET",
            "/envelopes",
            params={"from_date": "2020-01-01", "custom_field": f"{IDEMPOTENCY_FIELD}={key}"},
        )
        envelopes = cast(list[Json], found.json().get("envelopes") or [])
        return str(envelopes[0]["envelopeId"]) if envelopes else None

    async def _recipient_ids(self, provider_envelope_id: str) -> dict[str, str]:
        got = await self._call("GET", f"/envelopes/{provider_envelope_id}/recipients")
        signers = cast(list[Json], got.json().get("signers") or [])
        return {str(s["clientUserId"]): str(s["recipientId"]) for s in signers}

    def _signer(
        self, spec: EnvelopeSpec, index: int, order_mode: str, placed: Sequence[PlacedField]
    ) -> Json:
        s = spec.signers[index]
        method = _AUTH_METHOD.get(s.identity_method)
        if method is None:
            raise DocuSignError("identity")
        tabs: dict[str, list[Json]] = {}
        for f in placed:
            if f.signer_id != s.signer_id:
                continue
            tab: Json = {"documentId": str(f.document)}
            if f.anchor is not None:
                tab |= {"anchorString": f.anchor, "anchorUnits": "pixels"}
            else:
                tab |= {
                    "pageNumber": str(f.page or 1),
                    "xPosition": str(round(f.x or 0)),
                    "yPosition": str(round(f.y or 0)),
                }
            tabs.setdefault(_TAB[f.kind], []).append(tab)
        recipient: Json = {
            "recipientId": str(index + 1),
            "clientUserId": s.signer_id,
            "routingOrder": str(s.routing_group if order_mode == "parallel" else s.order),
            "name": f"Signer {s.order}",  # the person's name is DocuSign's from the session
            "email": f"{s.signer_id}@signers.invalid",  # captive: DocuSign never emails them
            "authenticationMethod": method,
            "tabs": tabs,
        }
        if s.identity_method == "kba":
            recipient |= {"requireIdLookup": "true", "idCheckConfigurationName": _KBA_CONFIG}
        return recipient

    async def create_and_send(self, spec: EnvelopeSpec) -> Created:
        """Create and send once per idempotency key; a retry reads the first one back."""
        known = await self._existing(spec.idempotency_key)
        if known is not None:
            listed = await self._call("GET", f"/envelopes/{known}")
            return Created(known, await self._recipient_ids(known), _sha(listed.content))
        files = await self._documents(spec.envelope_id)
        if tuple(f.sha256 for f in files) != spec.document_sha256s:
            raise DocuSignError("documents")
        placed = await self._fields(spec.envelope_id)
        order_mode = await self._signer_order(spec.envelope_id)
        body = {
            "status": "sent",
            "emailSubject": "Documents to sign",
            "documents": [
                {
                    "documentId": str(n),
                    "name": f.name,
                    "fileExtension": "pdf",
                    "documentBase64": base64.b64encode(f.content).decode(),
                }
                for n, f in enumerate(files, start=1)
            ],
            "recipients": {
                "signers": [
                    self._signer(spec, i, order_mode, placed) for i in range(len(spec.signers))
                ]
            },
            "customFields": {
                "textCustomFields": [
                    {"name": IDEMPOTENCY_FIELD, "value": spec.idempotency_key, "show": "false"}
                ]
            },
        }
        made = await self._call("POST", "/envelopes", body=body)
        provider_id = str(made.json()["envelopeId"])
        return Created(provider_id, await self._recipient_ids(provider_id), _sha(made.content))

    # --- read --------------------------------------------------------------------------------

    async def status(self, provider_envelope_id: str) -> tuple[SignerState, ...]:
        got = await self._call("GET", f"/envelopes/{provider_envelope_id}/recipients")
        out: list[SignerState] = []
        for s in cast(list[Json], got.json().get("signers") or []):
            status = _STATUS.get(str(s.get("status", "")).lower(), "pending")
            out.append(
                SignerState(
                    signer_id=str(s["clientUserId"]),
                    status=status,
                    viewed_at=_when(s.get("deliveredDateTime")),
                    signed_at=_when(s.get("signedDateTime")),
                    kba_failures=3 if status == "verification_failed" else 0,
                    decline_reason="other" if status == "declined" else None,
                )
            )
        return tuple(out)

    async def completed(self, provider_envelope_id: str) -> Completed:
        base = f"/envelopes/{provider_envelope_id}"
        combined = (await self._call("GET", f"{base}/documents/combined")).content
        certificate = (await self._call("GET", f"{base}/documents/certificate")).content
        recipients = cast(
            list[Json],
            (await self._call("GET", f"{base}/recipients")).json().get("signers") or [],
        )
        events = cast(
            list[Json],
            (await self._call("GET", f"{base}/audit_events")).json().get("auditEvents") or [],
        )
        signed_from: dict[str, str] = {}
        for event in events:
            fields = {
                str(f.get("name")): str(f.get("value", ""))
                for f in cast(list[Json], event.get("eventFields") or [])
            }
            if fields.get("Action") == "Signed" and fields.get("UserName"):
                signed_from[fields["UserName"]] = fields.get("ClientIPAddress", "")
        evidence: list[SignerEvidence] = []
        for r in recipients:
            if str(r.get("status", "")).lower() not in ("signed", "completed"):
                continue
            recipient = str(r["recipientId"])
            image = (
                await self._call("GET", f"{base}/recipients/{recipient}/signature_image")
            ).content
            evidence.append(
                SignerEvidence(
                    signer_id=str(r["clientUserId"]),
                    signed_image=image,
                    signed_at=_when(r.get("signedDateTime")) or datetime.fromtimestamp(0),
                    ip=signed_from.get(str(r.get("name", "")), ""),
                    login_ref=str(r.get("userId") or recipient),
                    identity_result=_identity_result(r),
                    signature_method="provider_adopted",
                    user_agent_family=None,
                    device_label=None,
                )
            )
        return Completed(combined, certificate, tuple(evidence))

    # --- writes after create -----------------------------------------------------------------

    async def remind(self, provider_envelope_id: str, signer_id: str) -> None:
        recipient = (await self._recipient_ids(provider_envelope_id)).get(signer_id)
        if recipient is None:
            raise DocuSignError("remind")
        await self._call(
            "PUT",
            f"/envelopes/{provider_envelope_id}/recipients",
            params={"resend_envelope": "true"},
            body={"signers": [{"recipientId": recipient}]},
        )

    async def void(self, provider_envelope_id: str, reason: str) -> None:
        await self._call(
            "PUT",
            f"/envelopes/{provider_envelope_id}",
            body={"status": "voided", "voidedReason": reason},
        )

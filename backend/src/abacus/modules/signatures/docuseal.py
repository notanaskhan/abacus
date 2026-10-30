"""The DocuSeal adapter behind the `EsignProvider` port (N-02-T18; N-02 §3.5; ADR-342; W7;
DF-11, DF-12; DEC-1276). PROTECTED.

One instance per firm and call, built by `firm_provider` only when every switch is on: the
firm's `signatures.esign_provider` flag (the kill switch), the W7 capability
`esignature_envelope_send` enabled in `write-capabilities.yaml` (opened by registry version 2,
ADR-150 accepted 2026-10-30, DEC-1280), and a connected DocuSeal install whose
sealed secret holds the API key. Otherwise `ProviderUnavailable`: nothing leaves.

- **Auth.** DocuSeal's API key in `X-Auth-Token`, sent only to the API host; file downloads
  carry no key.
- **Create, exactly once.** Each submitter carries `external_id` = our signer id and
  `metadata.accrued_idempotency` = the send's key. A create first lists submitters by the first
  signer's id and, if one carries the key, reads that submission back instead of creating a
  second (a retried send after a timeout). DocuSeal sends nothing itself (`send_email` and
  `send_sms` off): every client message is Accrued's (DEC-59). Signers are ordered (sequential:
  each signer's order; parallel: its routing group); identity per DF-11 and ADR-342 (a `kba`
  field before the signature for the e-file family; letters rely on portal MFA and ERSD consent;
  SMS is never used). Fields are placed fields in PDF points, sent as page fractions from the
  page's top-left corner; anchors are refused (DocuSeal has no anchor search). Signers see field
  titles, never our field names; a date field is the signing date, filled by DocuSeal and read
  only; the signer's name is not sent, so DocuSeal pre-fills nothing into a typed signature.
  DocuSeal asks its KBA step last, after the signature and before the form completes: a signer
  who fails it never completes (N-02-T06, 2026-10-30).
- **Read.** Status from the submission's submitters (the truth; a webhook is only a hint,
  N-02-T19), the merged signed document, the audit log (the certificate) and each signer's
  signature image. The API's events carry no IP or user agent (their `data` is empty on the
  sandbox), so each signer's IP and device come from the audit log DocuSeal generated, read in
  an isolated child (`audit_text`); a completed signer with no IP there is refused, never
  recorded without one.
- **Void** is archive (DocuSeal has no void); the envelope's own state records the void.
- **Hosts.** Only DocuSeal's API host (`ALLOWED_HOSTS`) and its file hosts (`DOCUMENT_HOSTS`); a
  host elsewhere is refused before any request. Q-01's egress firewall lists both when W7 opens.

Document bytes are read from our stores at create and sent once; nothing from a client's documents
is logged. The request and response hashes are recorded write-once by the caller
(`envelope_provider_calls`).
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, cast
from urllib.parse import urlsplit

import httpx

from abacus.kernel.errors import ServiceUnavailable
from abacus.kernel.request_context import client_ip, device_of
from abacus.modules.signatures.provider import (
    Completed,
    Created,
    EnvelopeSpec,
    SignerEvidence,
    SignerState,
)

Json = dict[str, Any]  # Any: DocuSeal's JSON, read key by key and never trusted for state
IDEMPOTENCY_KEY: Final = "accrued_idempotency"
# DocuSeal's global API host. The EU host (api.docuseal.eu) stays refused until the data-location
# question in ADR-342 is answered.
ALLOWED_HOSTS: Final = frozenset({"api.docuseal.com"})
# Where DocuSeal serves signed documents, audit logs and signature images: all three from
# docuseal.com/file/…, 200 with no redirect and no key (sandbox, 2026-10-30).
DOCUMENT_HOSTS: Final = frozenset({"docuseal.com"})
_KEY_HEADER: Final = "X-Auth-Token"  # our outbound call to DocuSeal, never an inbound request
_STATUS: Final[dict[str, str]] = {
    "awaiting": "pending",
    "sent": "pending",
    "opened": "viewed",
    "completed": "signed",
    "declined": "declined",
}
_FIELD: Final[dict[str, str]] = {
    "signature": "signature",
    "date": "date",
    "initial": "initials",
    "pin": "text",
    "title_prefill": "text",
}
# What the signer reads on DocuSeal's form; our field names stay internal.
_TITLE: Final[dict[str, str]] = {
    "signature": "Signature",
    "date": "Date signed",
    "initial": "Initials",
    "pin": "PIN",
    "title_prefill": "Title",
}
_SIGNING_DATE: Final = "{{date}}"  # DocuSeal fills the day the signer completes
# DF-11 at DocuSeal: KBA for the e-file family; email codes and the firm's sign-in are proved in
# our portal (MFA and ERSD consent) before the signing URL is fetched, so DocuSeal adds nothing.
# In-person ID is the handwritten path and never reaches DocuSeal; SMS is never sent.
_IDENTITY: Final = frozenset({"kba", "email_code", "firm_sso"})


class DocuSealError(ServiceUnavailable):
    """DocuSeal refused or failed: the activity retries; nothing is half-recorded. Carries the
    step and the HTTP status only, never a response body."""

    code = "provider_unavailable"

    def __init__(self, step: str, status: int | None = None) -> None:
        super().__init__(step)
        self.step = step
        self.status = status


class HostNotAllowed(ValueError):
    """An API or file host outside DocuSeal's: refused before any request."""


@dataclass(frozen=True)
class DocuSealAccount:
    """The sealed install secret, opened for one call (Restricted; never logged). The webhook
    keys (DocuSeal's `whsec_…` per webhook, used whole as the HMAC key) verify deliveries to the
    install's receiver (ADR-152, DEC-1281); more than one while a key rotates."""

    api_key: str
    api_host: str  # e.g. api.docuseal.com
    webhook_keys: tuple[str, ...] = ()

    @classmethod
    def from_secret(cls, raw: bytes) -> DocuSealAccount:
        body = cast(dict[str, object], json.loads(raw))
        keys = body.get("webhook_keys")
        return cls(
            api_key=str(body["api_key"]),
            api_host=str(body["api_host"]).lower(),
            webhook_keys=tuple(str(k) for k in cast(list[object], keys))
            if isinstance(keys, list)
            else (),
        )


@dataclass(frozen=True)
class SourceFile:
    """One document's bytes, in envelope order, the hash the envelope recorded and each page's
    size in PDF points (width, height)."""

    name: str
    content: bytes
    sha256: str
    page_sizes: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class PlacedField:
    """One placed field for a signer: a document (1-based), a kind and a box in PDF points from
    the page's top-left corner, or an anchor."""

    signer_id: str
    document: int
    kind: str
    page: int | None
    x: float | None
    y: float | None
    w: float | None
    h: float | None
    anchor: str | None


DocumentLoader = Callable[[str], Awaitable[Sequence[SourceFile]]]
FieldLoader = Callable[[str], Awaitable[Sequence[PlacedField]]]
AuditText = Callable[[bytes], Awaitable[str]]  # the audit log PDF's text, read in isolation


def _host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _when(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _fraction(value: float, whole: float) -> float:
    return min(max(value / whole, 0.0), 1.0) if whole > 0 else 0.0


def _role(index: int) -> str:
    return f"Signer {index + 1}"


def _email(signer_id: str) -> str:
    """The submitter's address at DocuSeal: never mailed, and the key to its audit log block."""
    return f"{signer_id}@signers.invalid"


@dataclass(frozen=True)
class AuditEntry:
    ip: str | None
    user_agent: str | None


_AUDIT_KEY: Final = re.compile(r"^(IP|Session ID|User agent|Time zone): ?(.*)$")


def audit_entries(text: str) -> dict[str, AuditEntry]:
    """Each signer's IP and user agent from DocuSeal's audit log text, by their address there.
    A signer's block starts at their address; a wrapped user agent runs on until the next key,
    address, field label (upper case) or the event log."""
    found: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    key: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.endswith("@signers.invalid") and " " not in line:
            current = found.setdefault(line.lower(), {})
            key = None
            continue
        if current is None:
            continue
        if line == "Event Log":
            break
        matched = _AUDIT_KEY.match(line)
        if matched is not None:
            key = str(matched.group(1))
            current[key] = matched.group(2)
        elif key == "User agent" and line and not line.isupper():
            current[key] = f"{current[key]} {line}"
        else:
            key = None
    return {
        address: AuditEntry(client_ip(body.get("IP")), body.get("User agent") or None)
        for address, body in found.items()
    }


class DocuSealProvider:
    """One firm's DocuSeal account, for one activity call."""

    name = "docuseal"

    def __init__(
        self,
        account: DocuSealAccount,
        http: httpx.AsyncClient,
        *,
        documents: DocumentLoader,
        fields: FieldLoader,
        signer_order: Callable[[str], Awaitable[str]],
        audit_text: AuditText,
    ) -> None:
        if account.api_host not in ALLOWED_HOSTS:
            raise HostNotAllowed(account.api_host)
        self._account = account
        self._http = http
        self._documents = documents
        self._fields = fields
        self._signer_order = signer_order
        self._audit_text = audit_text

    # --- transport ---------------------------------------------------------------------------

    async def _call(
        self,
        method: str,
        path: str,
        *,
        body: object | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        got = await self._http.request(
            method,
            f"https://{self._account.api_host}{path}",
            json=body,
            params=params,
            headers={_KEY_HEADER: self._account.api_key},
        )
        if not 200 <= got.status_code < 300:  # redirects are not followed, so a 3xx fails too
            raise DocuSealError(method.lower(), got.status_code)
        return got

    async def _file(self, url: object, step: str) -> bytes:
        """A signed file DocuSeal links to, from its file hosts only and without the key."""
        if not isinstance(url, str) or urlsplit(url).scheme != "https":
            raise DocuSealError(step)
        if _host_of(url) not in DOCUMENT_HOSTS:
            raise HostNotAllowed(_host_of(url))
        got = await self._http.get(url)
        if got.status_code != 200:  # a redirect's body is never stored as a signed file
            raise DocuSealError(step, got.status_code)
        return got.content

    async def _submission(self, provider_envelope_id: str) -> Json:
        return cast(Json, (await self._call("GET", f"/submissions/{provider_envelope_id}")).json())

    # --- create ------------------------------------------------------------------------------

    async def _existing(self, spec: EnvelopeSpec) -> str | None:
        found = await self._call(
            "GET",
            "/submitters",
            params={"external_id": spec.signers[0].signer_id, "limit": "100"},
        )
        for row in cast(list[Json], found.json().get("data") or []):
            meta = cast(Json, row.get("metadata") or {})
            if meta.get(IDEMPOTENCY_KEY) == spec.idempotency_key:
                return str(row["submission_id"])
        return None

    @staticmethod
    def _recipients(submission: Json) -> dict[str, str]:
        return {
            str(s["external_id"]): str(s["id"])
            for s in cast(list[Json], submission.get("submitters") or [])
            if s.get("external_id")
        }

    def _orders(self, spec: EnvelopeSpec, order_mode: str) -> dict[str, int]:
        """DocuSeal's 0-based order: sequential signers by their order, parallel by routing
        group; signers sharing a number sign in parallel."""
        keys = {
            s.signer_id: (s.routing_group if order_mode == "parallel" else s.order)
            for s in spec.signers
        }
        ranks = {value: rank for rank, value in enumerate(sorted(set(keys.values())))}
        return {signer: ranks[value] for signer, value in keys.items()}

    def _document(
        self,
        number: int,
        file: SourceFile,
        roles: dict[str, str],
        kba: frozenset[str],
        placed: Sequence[PlacedField],
        verified: set[str],
        dates: dict[str, list[str]],
    ) -> Json:
        fields: list[Json] = []
        for n, f in enumerate((p for p in placed if p.document == number), start=1):
            if f.anchor is not None or None in (f.page, f.x, f.y, f.w, f.h):
                raise DocuSealError("placement")
            page = cast(int, f.page)
            if page > len(file.page_sizes):
                raise DocuSealError("placement")
            width, height = file.page_sizes[page - 1]
            area: Json = {
                "x": _fraction(cast(float, f.x), width),
                "y": _fraction(cast(float, f.y), height),
                "w": _fraction(cast(float, f.w), width),
                "h": _fraction(cast(float, f.h), height),
                "page": page,
            }
            role = roles[f.signer_id]
            if f.kind == "signature" and f.signer_id in kba and f.signer_id not in verified:
                # Once per signer, on their first signature; DocuSeal asks it as the form's last
                # step, so the form cannot complete without it.
                fields.append(
                    {
                        "name": f"kba {role}",
                        "title": "Identity check",
                        "type": "kba",
                        "role": role,
                        "areas": [area],
                    }
                )
                verified.add(f.signer_id)
            name = f"{f.kind} {number}.{n}"
            if f.kind == "date":
                dates.setdefault(f.signer_id, []).append(name)
            fields.append(
                {
                    "name": name,
                    "title": _TITLE[f.kind],
                    "type": _FIELD[f.kind],
                    "role": role,
                    "required": True,
                    "areas": [area],
                }
            )
        return {
            "name": file.name,
            "file": base64.b64encode(file.content).decode(),
            "fields": fields,
            "position": number - 1,
        }

    async def create_and_send(self, spec: EnvelopeSpec) -> Created:
        """Create once per idempotency key; a retry reads the first one back."""
        if not spec.signers:
            raise DocuSealError("signers")
        known = await self._existing(spec)
        if known is not None:
            got = await self._call("GET", f"/submissions/{known}")
            return Created(known, self._recipients(cast(Json, got.json())), _sha(got.content))
        files = await self._documents(spec.envelope_id)
        if tuple(f.sha256 for f in files) != spec.document_sha256s:
            raise DocuSealError("documents")
        for s in spec.signers:
            if s.identity_method not in _IDENTITY:
                raise DocuSealError("identity")
        placed = await self._fields(spec.envelope_id)
        orders = self._orders(spec, await self._signer_order(spec.envelope_id))
        roles = {s.signer_id: _role(i) for i, s in enumerate(spec.signers)}
        kba = frozenset(s.signer_id for s in spec.signers if s.identity_method == "kba")
        verified: set[str] = set()
        dates: dict[str, list[str]] = {}
        documents = [
            self._document(n, f, roles, kba, placed, verified, dates)
            for n, f in enumerate(files, start=1)
        ]
        body = {
            "name": "Documents to sign",
            "send_email": False,
            "send_sms": False,
            "order": "preserved",
            "documents": documents,
            "submitters": [
                {
                    "role": roles[s.signer_id],
                    # No name: DocuSeal would pre-fill it into a typed signature.
                    "email": _email(s.signer_id),  # DocuSeal never emails them
                    "external_id": s.signer_id,
                    "metadata": {IDEMPOTENCY_KEY: spec.idempotency_key},
                    "order": orders[s.signer_id],
                    "send_email": False,
                    "send_sms": False,
                    "fields": [
                        {"name": d, "readonly": True, "default_value": _SIGNING_DATE}
                        for d in dates.get(s.signer_id, [])
                    ],
                }
                for s in spec.signers
            ],
        }
        made = await self._call("POST", "/submissions/pdf", body=body)
        created = cast(Json, made.json())
        return Created(str(created["id"]), self._recipients(created), _sha(made.content))

    # --- read --------------------------------------------------------------------------------

    async def status(self, provider_envelope_id: str) -> tuple[SignerState, ...]:
        submission = await self._submission(provider_envelope_id)
        out: list[SignerState] = []
        for s in cast(list[Json], submission.get("submitters") or []):
            if not s.get("external_id"):
                continue
            status = _STATUS.get(str(s.get("status", "")).lower(), "pending")
            out.append(
                SignerState(
                    signer_id=str(s["external_id"]),
                    status=status,
                    viewed_at=_when(s.get("opened_at")),
                    signed_at=_when(s.get("completed_at")),
                    # A failed KBA keeps the form open; its report waits on F-09-T63 [verify].
                    kba_failures=0,
                    decline_reason="other" if status == "declined" else None,
                )
            )
        return tuple(out)

    async def completed(self, provider_envelope_id: str) -> Completed:
        submission = await self._submission(provider_envelope_id)
        merged = await self._call(
            "GET", f"/submissions/{provider_envelope_id}/documents", params={"merge": "true"}
        )
        documents = cast(list[Json], merged.json().get("documents") or [])
        if not documents:
            raise DocuSealError("documents")
        combined = await self._file(documents[0].get("url"), "documents")
        certificate = await self._file(submission.get("audit_log_url"), "audit_log")
        audit = audit_entries(await self._audit_text(certificate))
        events = cast(list[Json], submission.get("submission_events") or [])
        evidence: list[SignerEvidence] = []
        for s in cast(list[Json], submission.get("submitters") or []):
            if str(s.get("status", "")).lower() != "completed" or not s.get("external_id"):
                continue
            mine = [e for e in events if e.get("submitter_id") == s.get("id")]
            seen = audit.get(_email(str(s["external_id"])).lower())
            if seen is None or seen.ip is None:
                raise DocuSealError("audit_log")  # never a signature record without its IP
            family, device = device_of(seen.user_agent)
            verified = any(e.get("event_type") == "complete_verification" for e in mine)
            image_url = next(
                (
                    v.get("value")
                    for v in cast(list[Json], s.get("values") or [])
                    if str(v.get("field", "")).startswith("signature ")
                ),
                None,
            )
            evidence.append(
                SignerEvidence(
                    signer_id=str(s["external_id"]),
                    signed_image=await self._file(image_url, "signature_image"),
                    signed_at=_when(s.get("completed_at")) or datetime.fromtimestamp(0),
                    ip=seen.ip,
                    login_ref=str(s.get("uuid") or s["id"]),
                    identity_result="kba_verified" if verified else "portal_verified",
                    signature_method="provider_adopted",
                    user_agent_family=family,
                    device_label=device,
                )
            )
        return Completed(combined, certificate, tuple(evidence))

    # --- writes after create -----------------------------------------------------------------

    async def remind(self, provider_envelope_id: str, signer_id: str) -> None:
        """Reminders are Accrued's mail (`reminder_sender`, ADR-342): DocuSeal sends nothing.
        This only confirms the signer is part of the submission."""
        if signer_id not in self._recipients(await self._submission(provider_envelope_id)):
            raise DocuSealError("remind")

    async def void(self, provider_envelope_id: str, reason: str) -> None:
        """DocuSeal has no void: the submission is archived (its form closes) and the envelope's
        own state carries the void and its reason."""
        del reason  # recorded on our side, never sent to the provider
        await self._call("DELETE", f"/submissions/{provider_envelope_id}")

"""A fake e-signature provider for synthetic environments (N-02-T14; N-02 §3.5; ADR-101).

`install_fake_esign()` configures it as `signatures`' provider; refused outside local, test and
evaluation (`SYNTHETIC_ENVIRONMENTS`), so no fake ever serves a real firm. Product code never
imports this. Tests and the local stack drive its signers (`view`, `sign`, `decline`,
`fail_identity`) and then signal the envelope's workflow, which polls this for the truth.

It behaves like the real provider where it matters: a create with a known idempotency key
answers the envelope it already made; routing groups sign in order; three failed identity
checks lock a signer (`verification_failed`); a voided envelope refuses further signing; the
completed package carries a combined document, a certificate and, per signer, the five IRS
items. Everything it returns is synthetic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final

from abacus.kernel.clock import system_now
from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings
from abacus.modules.signatures.api import (
    Completed,
    Created,
    EnvelopeSpec,
    SignerEvidence,
    SignerState,
    configure_provider,
)

KBA_LIMIT: Final = 3


class FakeEsignRefused(RuntimeError):
    """The fake provider is for synthetic environments only."""


class FakeEsignError(RuntimeError):
    """The fake refused a signer action the real provider would refuse too."""


@dataclass
class _Signer:
    spec_order: int
    routing_group: int
    identity_method: str
    status: str = "pending"
    viewed_at: datetime | None = None
    signed_at: datetime | None = None
    kba_failures: int = 0
    decline_reason: str | None = None
    ip: str = "198.51.100.7"  # TEST-NET-2: never a real client's address
    login_ref: str = ""


@dataclass
class _Envelope:
    envelope_id: str
    provider_envelope_id: str
    signers: dict[str, _Signer]
    voided: bool = False
    reminders: list[str] = field(default_factory=list[str])


def _one_page_pdf(label: str) -> bytes:
    """A blank one-page PDF that names itself in a comment: real enough for a reader (POR-06's
    signed copy merges the document and its certificate, N-02-T23)."""
    return (
        "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
        f"% {label}\ntrailer<</Root 1 0 R>>\n%%EOF\n"
    ).encode()


class FakeEsign:
    name = "fake"

    def __init__(self) -> None:
        self._by_key: dict[str, str] = {}
        self._envelopes: dict[str, _Envelope] = {}
        self.calls: list[str] = []

    # --- EsignProvider --------------------------------------------------------------------------

    async def create_and_send(self, spec: EnvelopeSpec) -> Created:
        self.calls.append("create_and_send")
        known = self._by_key.get(spec.idempotency_key)
        if known is None:
            known = f"fake-{hashlib.sha256(spec.idempotency_key.encode()).hexdigest()[:16]}"
            self._by_key[spec.idempotency_key] = known
            self._envelopes[known] = _Envelope(
                spec.envelope_id,
                known,
                {
                    s.signer_id: _Signer(
                        s.order, s.routing_group, s.identity_method, login_ref=f"user-{s.order}"
                    )
                    for s in spec.signers
                },
            )
        found = self._envelopes[known]
        recipients = {signer: f"{known}-r{s.spec_order}" for signer, s in found.signers.items()}
        body = json.dumps({"envelopeId": known, "recipients": recipients}, sort_keys=True)
        return Created(known, recipients, hashlib.sha256(body.encode()).hexdigest())

    async def status(self, provider_envelope_id: str) -> tuple[SignerState, ...]:
        self.calls.append("status")
        found = self._envelopes[provider_envelope_id]
        return tuple(
            SignerState(
                signer_id=signer,
                status=s.status,
                viewed_at=s.viewed_at,
                signed_at=s.signed_at,
                kba_failures=s.kba_failures,
                decline_reason=s.decline_reason,
            )
            for signer, s in found.signers.items()
        )

    async def completed(self, provider_envelope_id: str) -> Completed:
        self.calls.append("completed")
        found = self._envelopes[provider_envelope_id]
        if any(s.status != "signed" for s in found.signers.values()):
            raise FakeEsignError("not every signer has signed")
        document = _one_page_pdf(f"fake combined document {found.envelope_id}")
        certificate = _one_page_pdf(f"fake certificate {provider_envelope_id}")
        return Completed(
            document,
            certificate,
            tuple(
                SignerEvidence(
                    signer_id=signer,
                    signed_image=f"fake signature image {signer}".encode(),
                    signed_at=s.signed_at or system_now(),
                    ip=s.ip,
                    login_ref=s.login_ref,
                    identity_result=(
                        "KBA passed · 4 of 4 questions"
                        if s.identity_method == "kba"
                        else "Email code verified"
                    ),
                    signature_method="typed",
                    user_agent_family="Safari",
                    device_label="iPhone",
                )
                for signer, s in sorted(found.signers.items(), key=lambda kv: kv[1].spec_order)
            ),
        )

    async def remind(self, provider_envelope_id: str, signer_id: str) -> None:
        self._envelopes[provider_envelope_id].reminders.append(signer_id)

    async def void(self, provider_envelope_id: str, reason: str) -> None:
        self.calls.append(f"void:{reason}")
        self._envelopes[provider_envelope_id].voided = True

    async def signing_url(self, provider_envelope_id: str, signer_id: str) -> str:
        self.calls.append("signing_url")
        found = self._envelopes[provider_envelope_id]
        if found.voided or signer_id not in found.signers:
            raise FakeEsignError("no such signer")
        order = found.signers[signer_id].spec_order
        return f"https://fake-esign.invalid/s/{provider_envelope_id}/{order}"

    # --- Driving signers (tests and the local stack) --------------------------------------------

    def _signer(self, provider_envelope_id: str, signer_id: str) -> _Signer:
        found = self._envelopes[provider_envelope_id]
        if found.voided:
            raise FakeEsignError("the envelope is voided")
        signer = found.signers[signer_id]
        earlier = [
            s
            for s in found.signers.values()
            if s.routing_group < signer.routing_group and s.status != "signed"
        ]
        if earlier:
            raise FakeEsignError("not this signer's turn")
        return signer

    def view(self, provider_envelope_id: str, signer_id: str) -> None:
        signer = self._signer(provider_envelope_id, signer_id)
        signer.viewed_at = signer.viewed_at or system_now()
        if signer.status == "pending":
            signer.status = "viewed"

    def sign(self, provider_envelope_id: str, signer_id: str, *, ip: str | None = None) -> None:
        signer = self._signer(provider_envelope_id, signer_id)
        if signer.status == "verification_failed":
            raise FakeEsignError("identity check locked")
        self.view(provider_envelope_id, signer_id)
        signer.status = "signed"
        signer.signed_at = system_now()
        if ip is not None:
            signer.ip = ip

    def decline(self, provider_envelope_id: str, signer_id: str, reason: str) -> None:
        signer = self._signer(provider_envelope_id, signer_id)
        signer.status = "declined"
        signer.decline_reason = reason

    def fail_identity(self, provider_envelope_id: str, signer_id: str) -> None:
        signer = self._signer(provider_envelope_id, signer_id)
        signer.kba_failures = min(KBA_LIMIT, signer.kba_failures + 1)
        if signer.kba_failures == KBA_LIMIT:
            signer.status = "verification_failed"


def install_fake_esign() -> FakeEsign:
    """Configure the fake as the provider; refused outside synthetic environments."""
    if settings().environment not in SYNTHETIC_ENVIRONMENTS:
        raise FakeEsignRefused(settings().environment)
    fake = FakeEsign()
    configure_provider(fake)
    return fake

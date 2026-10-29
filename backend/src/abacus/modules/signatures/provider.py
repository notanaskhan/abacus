"""The e-signature provider an envelope is sent through (N-02-T14; N-02 §3.5; ADR-149).

EnvelopeWorkflow's activities talk to one `EsignProvider`, configured at startup: the fake
(`abacus_tools.fakes.esign`, synthetic environments only) until the DocuSign adapter lands
through W7 (N-02-T18). With none configured, a send is refused (`provider_unavailable`) and
nothing leaves. The webhook is a hint and the poll is the truth (ADR-041's pattern): state comes
only from `status`, never from a signal's payload. The provider sees identifiers, routing,
identity methods and document hashes; document bytes stay in our stores.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from abacus.kernel.errors import ServiceUnavailable


class ProviderUnavailable(ServiceUnavailable):
    """No e-signature provider is configured here: nothing is sent."""

    code = "provider_unavailable"


@dataclass(frozen=True)
class SignerSpec:
    signer_id: str  # our `envelope_signers.id`, the provider's client user id
    order: int
    routing_group: int
    identity_method: str


@dataclass(frozen=True)
class EnvelopeSpec:
    envelope_id: str
    idempotency_key: str  # a retried create reads back by this, never creates twice
    document_sha256s: tuple[str, ...]
    signers: tuple[SignerSpec, ...]


@dataclass(frozen=True)
class Created:
    provider_envelope_id: str
    recipients: dict[str, str]  # our signer id -> the provider's recipient id
    response_sha256: str


@dataclass(frozen=True)
class SignerState:
    signer_id: str
    status: str  # pending | viewed | signed | declined | verification_failed
    viewed_at: datetime | None
    signed_at: datetime | None
    kba_failures: int
    decline_reason: str | None


@dataclass(frozen=True)
class SignerEvidence:
    """The five IRS items for a remote signature (R-05; chapter 06 §6.3), as the provider
    recorded them: the signed image, the date and time, the IP address and login ID, the
    identity-verification result and the signature method; plus the device."""

    signer_id: str
    signed_image: bytes
    signed_at: datetime
    ip: str
    login_ref: str
    identity_result: str
    signature_method: str
    user_agent_family: str | None
    device_label: str | None


@dataclass(frozen=True)
class Completed:
    combined_document: bytes
    certificate: bytes
    signers: tuple[SignerEvidence, ...]


class EsignProvider(Protocol):
    name: str

    async def create_and_send(self, spec: EnvelopeSpec) -> Created: ...

    async def status(self, provider_envelope_id: str) -> tuple[SignerState, ...]: ...

    async def completed(self, provider_envelope_id: str) -> Completed: ...

    async def remind(self, provider_envelope_id: str, signer_id: str) -> None: ...

    async def void(self, provider_envelope_id: str, reason: str) -> None: ...


_provider: EsignProvider | None = None


def configure_provider(provider: EsignProvider | None) -> None:
    """Startup and tests: the provider every envelope uses; None removes it."""
    global _provider
    _provider = provider


def provider() -> EsignProvider:
    if _provider is None:
        raise ProviderUnavailable
    return _provider
